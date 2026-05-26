"""Configurações centrais da versão AWS-only.

Esta versão foi preparada para apresentação no AWS Academy.
Não há execução local, Bedrock, Ollama ou API externa. O modelo é simulado
com MODEL_MODE=fake para validar a arquitetura distribuída com AWS.
"""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    return int(value)


def _env_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    return float(value)


MODEL_MODE = "fake"
SOURCE_LANG = os.getenv("SOURCE_LANG", "en")
TARGET_LANG = os.getenv("TARGET_LANG", "pt-BR")
MAX_CHARS_PER_CHUNK = _env_int("MAX_CHARS_PER_CHUNK", 400)
MAX_RETRIES = _env_int("MAX_RETRIES", 3)
BACKOFF_BASE_SECONDS = _env_float("BACKOFF_BASE_SECONDS", 1.0)
DOCUMENT_ID = os.getenv("DOCUMENT_ID", "doc_001")
FAKE_FAILURE_RATE = _env_float("FAKE_FAILURE_RATE", 0.0)

# AWS Academy / EC2
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
S3_BUCKET = os.getenv("S3_BUCKET", "tradutor-distribuido-atv-2026")
SQS_QUEUE_URL = os.getenv("SQS_QUEUE_URL", "")
SQS_DLQ_URL = os.getenv("SQS_DLQ_URL", "")
DYNAMODB_GLOSSARY_TABLE = os.getenv("DYNAMODB_GLOSSARY_TABLE", "TranslationGlossary")
DYNAMODB_CHUNKS_TABLE = os.getenv("DYNAMODB_CHUNKS_TABLE", "TranslationChunks")
CLOUDWATCH_NAMESPACE = os.getenv("CLOUDWATCH_NAMESPACE", "TradutorDistribuido")

PROMPT_PATH = BASE_DIR / "prompts" / "system" / "translator_v2.txt"
SCHEMA_PATH = BASE_DIR / "prompts" / "tools" / "translation_output_schema.json"
