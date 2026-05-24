import json
import time
import random
from pathlib import Path
from typing import Dict, List, Tuple

from src.config import (
    MODEL_MODE,
    SOURCE_LANG,
    TARGET_LANG,
    MAX_RETRIES,
    BACKOFF_BASE_SECONDS,
    DOCUMENT_ID,
)

BASE_DIR = Path(__file__).resolve().parents[2]

CHUNKS_PATH = BASE_DIR / "data" / "output" / "chunks_local.json"
TRANSLATED_PATH = BASE_DIR / "data" / "output" / "translated_local.json"
GLOSSARIO_PATH = BASE_DIR / "data" / "output" / "glossario_local.json"

PROMPT_PATH = BASE_DIR / "prompts" / "system" / "translator_v2.txt"
SCHEMA_PATH = BASE_DIR / "prompts" / "tools" / "translation_output_schema.json"


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
    with GLOSSARIO_PATH.open("w", encoding="utf-8") as f:
        json.dump(glossario, f, ensure_ascii=False, indent=2)


def carregar_prompt() -> str:
    with PROMPT_PATH.open("r", encoding="utf-8") as f:
        return f.read()


def carregar_schema() -> Dict:
    with SCHEMA_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def montar_contexto(chunk: Dict, glossario: Dict[str, str], prompt: str, schema: Dict) -> Dict:
    """
    Prepara o contexto que seria enviado ao modelo.
    Mesmo em modo fake, isso mostra a engenharia de contexto explícita.
    """
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


def fake_traducao(contexto: Dict) -> Dict:
    """
    Simula a resposta de um modelo de linguagem.
    """
    texto = contexto["input_text"]

    latency_ms = random.randint(400, 1200)
    time.sleep(latency_ms / 1000.0)

    # SIMULAÇÃO DE FALHA: em ~20% das chamadas, dispara exceção
    if random.random() < 0.8:
        raise RuntimeError("Falha simulada na chamada ao modelo")

    translated_text = f"[TRADUZIDO {TARGET_LANG}] {texto[:80]}..."

    new_terms = [
        {"source": "distributed systems", "target": "sistemas distribuídos"},
        {"source": "parallel workers", "target": "workers paralelos"},
    ]

    input_tokens = max(1, len(texto) // 4)
    output_tokens = max(1, len(translated_text) // 4)

    return {
        "translated_text": translated_text,
        "new_terms": new_terms,
        "metrics": {
            "llm_latency_ms": latency_ms,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
        },
    }


def chamar_modelo_com_retry(contexto: Dict) -> Dict:
    """
    Encapsula a chamada ao modelo com retry + backoff.
    Por enquanto usa o modo fake.
    """
    tentativa = 0
    ultimo_erro = None

    while tentativa < MAX_RETRIES:
        try:
            if MODEL_MODE == "fake":
                return fake_traducao(contexto)
            else:
                raise NotImplementedError(f"MODEL_MODE '{MODEL_MODE}' ainda não implementado")
        except Exception as e:
            ultimo_erro = e
            tentativa += 1
            if tentativa < MAX_RETRIES:
                espera = BACKOFF_BASE_SECONDS * tentativa
                time.sleep(espera)

    raise RuntimeError(f"Falha após {MAX_RETRIES} tentativas: {ultimo_erro}")


def processar_chunk(chunk: Dict, glossario: Dict[str, str], worker_id: str) -> Tuple[Dict, Dict[str, str]]:
    inicio = time.time()

    prompt = carregar_prompt()
    schema = carregar_schema()
    contexto = montar_contexto(chunk, glossario, prompt, schema)

    resultado_llm = chamar_modelo_com_retry(contexto)

    fim = time.time()
    total_ms = int((fim - inicio) * 1000)

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
    print(f"Lendo chunks de: {CHUNKS_PATH}")
    chunks = carregar_chunks()

    glossario = carregar_glossario()
    print(f"Glossário inicial tem {len(glossario)} termos")

    resultados: List[Dict] = []
    worker_id = "worker-local-1"

    for chunk in chunks:
        print(f"Processando chunk {chunk['chunk_id']}...")
        try:
            saida, glossario = processar_chunk(chunk, glossario, worker_id)
            resultados.append(saida)
        except Exception as e:
            resultados.append(
                {
                    "document_id": chunk.get("document_id", DOCUMENT_ID),
                    "chunk_id": chunk["chunk_id"],
                    "total_chunks": chunk["total_chunks"],
                    "translated_text": "",
                    "new_terms": [],
                    "metrics": {
                        "worker_id": worker_id,
                    },
                    "status": "ERROR",
                    "error_message": str(e),
                }
            )

    with TRANSLATED_PATH.open("w", encoding="utf-8") as f:
        json.dump(resultados, f, ensure_ascii=False, indent=2)

    salvar_glossario(glossario)

    print(f"Resultados salvos em: {TRANSLATED_PATH}")
    print(f"Glossário atualizado salvo em: {GLOSSARIO_PATH}")
    print(f"Total de termos no glossário: {len(glossario)}")


if __name__ == "__main__":
    main()