import argparse
import json
from pathlib import Path
from typing import List, Dict, Any

import boto3
from boto3.dynamodb.conditions import Key

from src.config import AWS_REGION, S3_BUCKET, DYNAMODB_CHUNKS_TABLE, DOCUMENT_ID, BASE_DIR


def list_output_keys(s3, document_id: str) -> List[str]:
    prefix = f"outputs/{document_id}/chunks/"
    keys: List[str] = []
    continuation_token = None
    while True:
        kwargs = {"Bucket": S3_BUCKET, "Prefix": prefix}
        if continuation_token:
            kwargs["ContinuationToken"] = continuation_token
        response = s3.list_objects_v2(**kwargs)
        for obj in response.get("Contents", []):
            key = obj["Key"]
            if key.endswith(".json"):
                keys.append(key)
        if not response.get("IsTruncated"):
            break
        continuation_token = response.get("NextContinuationToken")
    return sorted(keys)


def get_json(s3, key: str) -> Dict[str, Any]:
    obj = s3.get_object(Bucket=S3_BUCKET, Key=key)
    return json.loads(obj["Body"].read().decode("utf-8"))


def query_chunk_status(document_id: str) -> List[Dict[str, Any]]:
    dynamodb = boto3.resource("dynamodb", region_name=AWS_REGION)
    table = dynamodb.Table(DYNAMODB_CHUNKS_TABLE)
    items: List[Dict[str, Any]] = []
    kwargs = {"KeyConditionExpression": Key("document_id").eq(document_id)}
    while True:
        response = table.query(**kwargs)
        items.extend(response.get("Items", []))
        if "LastEvaluatedKey" not in response:
            break
        kwargs["ExclusiveStartKey"] = response["LastEvaluatedKey"]
    return items


def collect_results(document_id: str, output_path: Path) -> None:
    s3 = boto3.client("s3", region_name=AWS_REGION)
    keys = list_output_keys(s3, document_id)
    results = [get_json(s3, key) for key in keys]
    results.sort(key=lambda x: int(x["chunk_id"]))

    final_text = "\n\n".join(r.get("translated_text", "") for r in results)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(final_text, encoding="utf-8")

    merged = {
        "document_id": document_id,
        "total_outputs_found": len(results),
        "results": results,
    }
    merged_key = f"outputs/{document_id}/results_merged.json"
    final_key = f"outputs/{document_id}/final_translation.txt"
    s3.put_object(
        Bucket=S3_BUCKET,
        Key=merged_key,
        Body=json.dumps(merged, ensure_ascii=False, indent=2).encode("utf-8"),
        ContentType="application/json; charset=utf-8",
    )
    s3.put_object(
        Bucket=S3_BUCKET,
        Key=final_key,
        Body=final_text.encode("utf-8"),
        ContentType="text/plain; charset=utf-8",
    )

    statuses = query_chunk_status(document_id)
    status_count: Dict[str, int] = {}
    for item in statuses:
        status = item.get("status", "UNKNOWN")
        status_count[status] = status_count.get(status, 0) + 1

    print(json.dumps({
        "document_id": document_id,
        "local_output": str(output_path),
        "s3_final_key": final_key,
        "s3_merged_key": merged_key,
        "outputs_found": len(results),
        "chunk_status_count": status_count,
    }, ensure_ascii=False, indent=2))


def main():
    parser = argparse.ArgumentParser(description="Coleta resultados traduzidos do S3")
    parser.add_argument("--document-id", default=DOCUMENT_ID)
    parser.add_argument("--output", default=str(BASE_DIR / "data" / "output" / "final_translation.txt"))
    args = parser.parse_args()
    collect_results(args.document_id, Path(args.output))


if __name__ == "__main__":
    main()
