import random
import time
from typing import Dict, Any, List

from src.config import (
    TARGET_LANG,
    MAX_RETRIES,
    BACKOFF_BASE_SECONDS,
    FAKE_FAILURE_RATE,
)


TECHNICAL_TERMS = {
    "distributed systems": "sistemas distribuídos",
    "parallel workers": "workers paralelos",
    "throughput": "vazão",
    "synchronization": "sincronização",
    "consistency": "consistência",
    "translation pipeline": "pipeline de tradução",
    "shared glossary": "glossário compartilhado",
    "retries": "retentativas",
    "backoff": "backoff",
    "message queues": "filas de mensagens",
    "orchestrator": "orquestrador",
    "structured logs": "logs estruturados",
    "latency": "latência",
    "token usage": "consumo de tokens",
    "error rate": "taxa de erro",
}


def _estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def _terms_found(text: str) -> List[Dict[str, str]]:
    lower_text = text.lower()
    found = []
    for source, target in TECHNICAL_TERMS.items():
        if source in lower_text:
            found.append({"source": source, "target": target})
    return found


def translate(contexto: Dict[str, Any]) -> Dict[str, Any]:

    inicio = time.time()
    texto = contexto["input_text"]

    if FAKE_FAILURE_RATE > 0 and random.random() < FAKE_FAILURE_RATE:
        raise RuntimeError("Falha simulada na chamada ao modelo")

    time.sleep(random.uniform(0.15, 0.45))

    translated_text = texto
    replacements = {
        "Distributed systems": "Sistemas distribuídos",
        "distributed systems": "sistemas distribuídos",
        "Parallel workers": "Workers paralelos",
        "parallel workers": "workers paralelos",
        "throughput": "vazão",
        "synchronization": "sincronização",
        "consistency": "consistência",
        "translation pipeline": "pipeline de tradução",
        "shared glossary": "glossário compartilhado",
        "Retries": "Retentativas",
        "retries": "retentativas",
        "backoff": "backoff",
        "Message queues": "Filas de mensagens",
        "message queues": "filas de mensagens",
        "orchestrator": "orquestrador",
        "Structured logs": "Logs estruturados",
        "latency": "latência",
        "token usage": "consumo de tokens",
        "error rate": "taxa de erro",
    }
    for source, target in replacements.items():
        translated_text = translated_text.replace(source, target)

    translated_text = f"[TRADUÇÃO SIMULADA {TARGET_LANG}] {translated_text}"

    latency_ms = int((time.time() - inicio) * 1000)
    return {
        "translated_text": translated_text,
        "new_terms": _terms_found(texto),
        "metrics": {
            "llm_latency_ms": latency_ms,
            "input_tokens": _estimate_tokens(texto),
            "output_tokens": _estimate_tokens(translated_text),
        },
    }


def call_model_once(contexto: Dict[str, Any]) -> Dict[str, Any]:
    return translate(contexto)


def call_model_with_retry(contexto: Dict[str, Any]) -> Dict[str, Any]:
    tentativa = 0
    ultimo_erro = None

    while tentativa < MAX_RETRIES:
        try:
            return call_model_once(contexto)
        except Exception as exc:
            ultimo_erro = exc
            tentativa += 1
            if tentativa < MAX_RETRIES:
                espera = BACKOFF_BASE_SECONDS * (2 ** (tentativa - 1))
                time.sleep(espera)

    raise RuntimeError(f"Falha após {MAX_RETRIES} tentativas: {ultimo_erro}")
