import json
import os
import socket
import time
from datetime import datetime, timezone
from decimal import Decimal
from typing import Dict, Any, List

import boto3
from botocore.exceptions import ClientError

from src.config import (
    AWS_REGION,
    S3_BUCKET,
    SQS_QUEUE_URL,
    DYNAMODB_GLOSSARY_TABLE,
    DYNAMODB_CHUNKS_TABLE,
    CLOUDWATCH_NAMESPACE,
    SOURCE_LANG,
    TARGET_LANG,
    PROMPT_PATH,
    SCHEMA_PATH,
)
from src.aws.structured_log import log_event
from src.worker.model_clients import call_model_with_retry


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def require_settings() -> None:
    missing = []
    if not S3_BUCKET:
        missing.append("S3_BUCKET")
    if not SQS_QUEUE_URL:
        missing.append("SQS_QUEUE_URL")
    if missing:
        raise RuntimeError(f"Variáveis obrigatórias ausentes: {', '.join(missing)}")


def load_text_file(path) -> str:
    with path.open("r", encoding="utf-8") as f:
        return f.read()


def load_json_file(path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def load_glossary(glossary_table) -> Dict[str, str]:
    """Carrega o glossário do DynamoDB. Para o trabalho acadêmico, o glossário tende a ser pequeno."""
    glossary: Dict[str, str] = {}
    kwargs = {"ProjectionExpression": "source_term, target_term"}
    while True:
        response = glossary_table.scan(**kwargs)
        for item in response.get("Items", []):
            source = item.get("source_term")
            target = item.get("target_term")
            if source and target:
                glossary[source] = target
        last_key = response.get("LastEvaluatedKey")
        if not last_key:
            break
        kwargs["ExclusiveStartKey"] = last_key
    return glossary


def put_glossary_terms(glossary_table, terms: List[Dict[str, str]], worker_id: str) -> None:
    for term in terms:
        source = (term.get("source") or "").strip()
        target = (term.get("target") or "").strip()
        if not source or not target:
            continue
        try:
            glossary_table.put_item(
                Item={
                    "source_term": source,
                    "target_term": target,
                    "created_at": utc_now(),
                    "created_by": worker_id,
                },
                ConditionExpression="attribute_not_exists(source_term)",
            )
            log_event("INFO", "glossary_term_created", source_term=source, target_term=target, worker_id=worker_id)
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException":
                log_event("INFO", "glossary_term_already_exists", source_term=source, worker_id=worker_id)
            else:
                raise


def get_s3_json(s3, bucket: str, key: str) -> Dict[str, Any]:
    obj = s3.get_object(Bucket=bucket, Key=key)
    return json.loads(obj["Body"].read().decode("utf-8"))


def put_s3_json(s3, key: str, payload: Any) -> None:
    s3.put_object(
        Bucket=S3_BUCKET,
        Key=key,
        Body=json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8"),
        ContentType="application/json; charset=utf-8",
    )


def update_chunk_status(chunks_table, document_id: str, chunk_id: int, status: str, **extra: Any) -> None:
    item = {
        "document_id": document_id,
        "chunk_id": int(chunk_id),
        "status": status,
        "updated_at": utc_now(),
        **extra,
    }
    chunks_table.put_item(Item=item)


def put_metrics(cloudwatch, document_id: str, worker_id: str, metrics: Dict[str, Any], error: bool = False) -> None:
    metric_data = [
        {"MetricName": "ChunksError" if error else "ChunksProcessed", "Value": 1.0, "Unit": "Count"},
    ]
    if not error:
        metric_data.extend([
            {"MetricName": "LatencyMs", "Value": float(metrics.get("total_latency_ms", 0)), "Unit": "Milliseconds"},
            {"MetricName": "LLMLatencyMs", "Value": float(metrics.get("llm_latency_ms", 0)), "Unit": "Milliseconds"},
            {"MetricName": "InputTokens", "Value": float(metrics.get("input_tokens", 0)), "Unit": "Count"},
            {"MetricName": "OutputTokens", "Value": float(metrics.get("output_tokens", 0)), "Unit": "Count"},
        ])

    for metric in metric_data:
        metric["Dimensions"] = [
            {"Name": "DocumentId", "Value": document_id},
            {"Name": "WorkerId", "Value": worker_id},
        ]

    cloudwatch.put_metric_data(Namespace=CLOUDWATCH_NAMESPACE, MetricData=metric_data)


def process_message(message: Dict[str, Any], clients: Dict[str, Any], worker_id: str) -> None:
    s3 = clients["s3"]
    sqs = clients["sqs"]
    cloudwatch = clients["cloudwatch"]
    glossary_table = clients["glossary_table"]
    chunks_table = clients["chunks_table"]

    body = json.loads(message["Body"])
    document_id = body["document_id"]
    chunk_id = int(body["chunk_id"])
    s3_bucket = body.get("s3_bucket", S3_BUCKET)
    s3_key = body["s3_key"]
    receipt_handle = message["ReceiptHandle"]
    receive_count = message.get("Attributes", {}).get("ApproximateReceiveCount", "1")

    log_event("INFO", "chunk_received", document_id=document_id, chunk_id=chunk_id, worker_id=worker_id, receive_count=receive_count)

    inicio = time.time()
    update_chunk_status(
        chunks_table,
        document_id,
        chunk_id,
        "PROCESSING",
        worker_id=worker_id,
        s3_chunk_key=s3_key,
        receive_count=int(receive_count),
    )

    chunk = get_s3_json(s3, s3_bucket, s3_key)
    glossary = load_glossary(glossary_table)
    prompt = load_text_file(PROMPT_PATH)
    schema = load_json_file(SCHEMA_PATH)

    contexto = {
        "system_prompt": prompt,
        "document_id": document_id,
        "chunk_id": chunk_id,
        "source_language": SOURCE_LANG,
        "target_language": TARGET_LANG,
        "glossary": glossary,
        "input_text": chunk["text"],
        "expected_output_schema": schema,
    }

    resultado_llm = call_model_with_retry(contexto)
    total_latency_ms = int((time.time() - inicio) * 1000)
    put_glossary_terms(glossary_table, resultado_llm.get("new_terms", []), worker_id)

    output = {
        "document_id": document_id,
        "chunk_id": chunk_id,
        "total_chunks": chunk.get("total_chunks"),
        "translated_text": resultado_llm["translated_text"],
        "new_terms": resultado_llm.get("new_terms", []),
        "metrics": {
            "llm_latency_ms": int(resultado_llm["metrics"].get("llm_latency_ms", 0)),
            "total_latency_ms": total_latency_ms,
            "input_tokens": int(resultado_llm["metrics"].get("input_tokens", 0)),
            "output_tokens": int(resultado_llm["metrics"].get("output_tokens", 0)),
            "worker_id": worker_id,
        },
        "status": "OK",
        "created_at": utc_now(),
    }

    output_key = f"outputs/{document_id}/chunks/chunk_{chunk_id:05d}.json"
    put_s3_json(s3, output_key, output)

    update_chunk_status(
        chunks_table,
        document_id,
        chunk_id,
        "DONE",
        worker_id=worker_id,
        s3_chunk_key=s3_key,
        s3_output_key=output_key,
        total_chunks=int(chunk.get("total_chunks", 0)),
        total_latency_ms=total_latency_ms,
        input_tokens=int(output["metrics"]["input_tokens"]),
        output_tokens=int(output["metrics"]["output_tokens"]),
    )

    put_metrics(cloudwatch, document_id, worker_id, output["metrics"], error=False)
    sqs.delete_message(QueueUrl=SQS_QUEUE_URL, ReceiptHandle=receipt_handle)

    log_event("INFO", "chunk_done", document_id=document_id, chunk_id=chunk_id, worker_id=worker_id, output_key=output_key, latency_ms=total_latency_ms)


def main():
    require_settings()

    worker_id = os.getenv("WORKER_ID") or f"{socket.gethostname()}-{os.getpid()}"
    max_messages = int(os.getenv("MAX_MESSAGES", "0"))

    session = boto3.Session(region_name=AWS_REGION)
    clients = {
        "s3": session.client("s3"),
        "sqs": session.client("sqs"),
        "cloudwatch": session.client("cloudwatch"),
    }
    dynamodb = session.resource("dynamodb")
    clients["glossary_table"] = dynamodb.Table(DYNAMODB_GLOSSARY_TABLE)
    clients["chunks_table"] = dynamodb.Table(DYNAMODB_CHUNKS_TABLE)
    clients["sqs"] = session.client("sqs")

    log_event("INFO", "worker_started", worker_id=worker_id, queue_url=SQS_QUEUE_URL, bucket=S3_BUCKET)

    processed = 0
    while True:
        response = clients["sqs"].receive_message(
            QueueUrl=SQS_QUEUE_URL,
            MaxNumberOfMessages=1,
            WaitTimeSeconds=10,
            VisibilityTimeout=180,
            AttributeNames=["ApproximateReceiveCount"],
        )
        messages = response.get("Messages", [])
        if not messages:
            log_event("INFO", "no_messages", worker_id=worker_id)
            if max_messages > 0 and processed >= max_messages:
                break
            continue

        for message in messages:
            try:
                process_message(message, clients, worker_id)
                processed += 1
            except Exception as exc:
                # Não apagar a mensagem da fila. Assim, o SQS tentará novamente e,
                # depois do limite configurado, enviará para a DLQ.
                try:
                    body = json.loads(message.get("Body", "{}"))
                    document_id = body.get("document_id", "unknown")
                    chunk_id = int(body.get("chunk_id", -1))
                    update_chunk_status(
                        clients["chunks_table"],
                        document_id,
                        chunk_id,
                        "ERROR",
                        worker_id=worker_id,
                        last_error=str(exc),
                    )
                    put_metrics(clients["cloudwatch"], document_id, worker_id, {}, error=True)
                except Exception:
                    pass
                log_event("ERROR", "chunk_failed", worker_id=worker_id, error_message=str(exc))

        if max_messages > 0 and processed >= max_messages:
            log_event("INFO", "worker_finished_by_limit", worker_id=worker_id, processed=processed)
            break


if __name__ == "__main__":
    main()
