import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List

import boto3
from boto3.dynamodb.types import TypeSerializer

from src.config import (
    AWS_REGION,
    S3_BUCKET,
    SQS_QUEUE_URL,
    DYNAMODB_CHUNKS_TABLE,
    MAX_CHARS_PER_CHUNK,
    DOCUMENT_ID,
)
from src.orchestrator.chunker import carregar_texto, dividir_em_paragrafos, agrupar_em_chunks


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def require_settings() -> None:
    if not S3_BUCKET:
        raise RuntimeError("S3_BUCKET não configurado")
    if not SQS_QUEUE_URL:
        raise RuntimeError("SQS_QUEUE_URL não configurado")


def put_dynamodb_item(table, item: Dict[str, Any]) -> None:
    table.put_item(Item=item)


def upload_json(s3, key: str, payload: Any) -> None:
    s3.put_object(
        Bucket=S3_BUCKET,
        Key=key,
        Body=json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8"),
        ContentType="application/json; charset=utf-8",
    )


def submit_job(input_file: Path, document_id: str, max_chars: int) -> List[Dict[str, Any]]:
    require_settings()

    session = boto3.Session(region_name=AWS_REGION)
    s3 = session.client("s3")
    sqs = session.client("sqs")
    dynamodb = session.resource("dynamodb")
    chunks_table = dynamodb.Table(DYNAMODB_CHUNKS_TABLE)

    texto = carregar_texto(input_file)
    paragrafos = dividir_em_paragrafos(texto)
    chunks = agrupar_em_chunks(paragrafos, max_chars=max_chars, document_id=document_id)

    input_key = f"input/{document_id}/corpus.txt"
    s3.put_object(
        Bucket=S3_BUCKET,
        Key=input_key,
        Body=texto.encode("utf-8"),
        ContentType="text/plain; charset=utf-8",
    )

    manifest = {
        "document_id": document_id,
        "input_key": input_key,
        "total_chunks": len(chunks),
        "max_chars_per_chunk": max_chars,
        "created_at": utc_now(),
    }
    upload_json(s3, f"chunks/{document_id}/manifest.json", manifest)

    for chunk in chunks:
        chunk_id = int(chunk["chunk_id"])
        chunk_key = f"chunks/{document_id}/chunk_{chunk_id:05d}.json"
        upload_json(s3, chunk_key, chunk)

        put_dynamodb_item(chunks_table, {
            "document_id": document_id,
            "chunk_id": chunk_id,
            "status": "PENDING",
            "s3_chunk_key": chunk_key,
            "total_chunks": len(chunks),
            "created_at": utc_now(),
            "updated_at": utc_now(),
        })

        message_body = {
            "document_id": document_id,
            "chunk_id": chunk_id,
            "s3_bucket": S3_BUCKET,
            "s3_key": chunk_key,
            "created_at": utc_now(),
        }
        sqs.send_message(QueueUrl=SQS_QUEUE_URL, MessageBody=json.dumps(message_body, ensure_ascii=False))

    print(json.dumps({
        "status": "SUBMITTED",
        "document_id": document_id,
        "total_chunks": len(chunks),
        "bucket": S3_BUCKET,
        "queue_url": SQS_QUEUE_URL,
    }, ensure_ascii=False, indent=2))
    return chunks


def main():
    parser = argparse.ArgumentParser(description="Envia um corpus para processamento distribuído na AWS")
    parser.add_argument("--input", default="data/input/corpus_en.txt", help="Arquivo de entrada local")
    parser.add_argument("--document-id", default=DOCUMENT_ID, help="Identificador do documento")
    parser.add_argument("--max-chars", type=int, default=MAX_CHARS_PER_CHUNK, help="Tamanho máximo do chunk")
    args = parser.parse_args()

    input_file = Path(args.input).resolve()
    submit_job(input_file=input_file, document_id=args.document_id, max_chars=args.max_chars)


if __name__ == "__main__":
    main()
