import json
import time
from pathlib import Path
from typing import Dict, List, Tuple

from src.config import (
    BASE_DIR,
    SOURCE_LANG,
    TARGET_LANG,
    DOCUMENT_ID,
    PROMPT_PATH,
    SCHEMA_PATH,
)
from src.worker.model_clients import call_model_with_retry

CHUNKS_PATH = BASE_DIR / "data" / "output" / "chunks_local.json"
TRANSLATED_PATH = BASE_DIR / "data" / "output" / "translated_local.json"
GLOSSARIO_PATH = BASE_DIR / "data" / "output" / "glossario_local.json"


def carregar_chunks() -> List[Dict]:
    if not CHUNKS_PATH.exists():
        raise FileNotFoundError(f"Arquivo de chunks não encontrado: {CHUNKS_PATH}")
    with CHUNKS_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def carregar_glossario() -> Dict[str, str]:
    if not GLOSSARIO_PATH.exists():
        return {}
    with GLOSSARIO_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def salvar_glossario(glossario: Dict[str, str]) -> None:
    GLOSSARIO_PATH.parent.mkdir(parents=True, exist_ok=True)
    with GLOSSARIO_PATH.open("w", encoding="utf-8") as f:
        json.dump(glossario, f, ensure_ascii=False, indent=2)


def carregar_prompt() -> str:
    with PROMPT_PATH.open("r", encoding="utf-8") as f:
        return f.read()


def carregar_schema() -> Dict:
    with SCHEMA_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def montar_contexto(chunk: Dict, glossario: Dict[str, str], prompt: str, schema: Dict) -> Dict:
    return {
        "system_prompt": prompt,
        "document_id": chunk["document_id"],
        "chunk_id": chunk["chunk_id"],
        "source_language": SOURCE_LANG,
        "target_language": TARGET_LANG,
        "glossary": glossario,
        "input_text": chunk["text"],
        "expected_output_schema": schema,
    }


def processar_chunk(chunk: Dict, glossario: Dict[str, str], worker_id: str) -> Tuple[Dict, Dict[str, str]]:
    inicio = time.time()
    prompt = carregar_prompt()
    schema = carregar_schema()
    contexto = montar_contexto(chunk, glossario, prompt, schema)

    resultado_llm = call_model_with_retry(contexto)

    total_ms = int((time.time() - inicio) * 1000)
    for termo in resultado_llm["new_terms"]:
        src = termo["source"]
        tgt = termo["target"]
        if src not in glossario:
            glossario[src] = tgt

    saida = {
        "document_id": chunk.get("document_id", DOCUMENT_ID),
        "chunk_id": chunk["chunk_id"],
        "total_chunks": chunk["total_chunks"],
        "translated_text": resultado_llm["translated_text"],
        "new_terms": resultado_llm["new_terms"],
        "metrics": {
            "llm_latency_ms": resultado_llm["metrics"]["llm_latency_ms"],
            "total_latency_ms": total_ms,
            "input_tokens": resultado_llm["metrics"]["input_tokens"],
            "output_tokens": resultado_llm["metrics"]["output_tokens"],
            "worker_id": worker_id,
        },
        "status": "OK",
    }
    return saida, glossario


def main():
    chunks = carregar_chunks()
    glossario = carregar_glossario()
    resultados: List[Dict] = []
    worker_id = "worker-local-1"

    for chunk in chunks:
        print(f"Processando chunk {chunk['chunk_id']}...")
        try:
            saida, glossario = processar_chunk(chunk, glossario, worker_id)
            resultados.append(saida)
        except Exception as e:
            resultados.append({
                "document_id": chunk.get("document_id", DOCUMENT_ID),
                "chunk_id": chunk["chunk_id"],
                "total_chunks": chunk["total_chunks"],
                "translated_text": "",
                "new_terms": [],
                "metrics": {"worker_id": worker_id},
                "status": "ERROR",
                "error_message": str(e),
            })

    TRANSLATED_PATH.parent.mkdir(parents=True, exist_ok=True)
    with TRANSLATED_PATH.open("w", encoding="utf-8") as f:
        json.dump(resultados, f, ensure_ascii=False, indent=2)

    salvar_glossario(glossario)
    print(f"Resultados salvos em: {TRANSLATED_PATH}")
    print(f"Glossário atualizado salvo em: {GLOSSARIO_PATH}")


if __name__ == "__main__":
    main()
