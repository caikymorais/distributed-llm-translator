import json
import time
from pathlib import Path
from typing import Dict, List
from multiprocessing import Process, Queue, current_process

from src.config import N_WORKERS
from src.worker.worker_local import carregar_chunks, processar_chunk


BASE_DIR = Path(__file__).resolve().parents[2]
PARALLEL_RESULTS_PATH = BASE_DIR / "data" / "output" / "translated_parallel_local.json"
PARALLEL_GLOSSARIO_PATH = BASE_DIR / "data" / "output" / "glossario_parallel_local.json"
PARALLEL_METRICS_PATH = BASE_DIR / "data" / "output" / "metrics_parallel_local.json"


def worker_process(jobs: Queue, results: Queue):
    worker_id = current_process().name
    glossario_local: Dict[str, str] = {}

    while True:
        item = jobs.get()
        if item is None:
            break

        chunk = item
        try:
            saida, glossario_local = processar_chunk(chunk, glossario_local, worker_id)
            results.put({
                "type": "success",
                "saida": saida,
                "glossario_local": glossario_local
            })
        except Exception as e:
            results.put({
                "type": "error",
                "chunk_id": chunk["chunk_id"],
                "worker_id": worker_id,
                "error_message": str(e)
            })


def main():
    inicio_total = time.time()

    chunks = carregar_chunks()
    print(f"Total de chunks: {len(chunks)}")
    print(f"Iniciando {N_WORKERS} workers em paralelo...")

    jobs: Queue = Queue()
    results: Queue = Queue()

    for chunk in chunks:
        jobs.put(chunk)

    for _ in range(N_WORKERS):
        jobs.put(None)

    processos: List[Process] = []
    for i in range(N_WORKERS):
        p = Process(
            target=worker_process,
            args=(jobs, results),
            name=f"worker-local-{i+1}"
        )
        p.start()
        processos.append(p)

    resultados: List[Dict] = []
    glossario_global: Dict[str, str] = {}
    erros: List[Dict] = []

    recebidos = 0
    esperados = len(chunks)

    while recebidos < esperados:
        result = results.get()

        if result["type"] == "success":
            resultados.append(result["saida"])
            for k, v in result["glossario_local"].items():
                if k not in glossario_global:
                    glossario_global[k] = v
        else:
            erros.append(result)

        recebidos += 1

    for p in processos:
        p.join()

    fim_total = time.time()
    total_ms = int((fim_total - inicio_total) * 1000)

    resultados.sort(key=lambda x: x["chunk_id"])

    total_input_tokens = sum(r["metrics"].get("input_tokens", 0) for r in resultados)
    total_output_tokens = sum(r["metrics"].get("output_tokens", 0) for r in resultados)
    total_chunks_ok = len(resultados)
    total_chunks_error = len(erros)

    throughput_chunks_per_sec = round(total_chunks_ok / max((total_ms / 1000), 0.001), 2)

    metricas = {
        "n_workers": N_WORKERS,
        "total_chunks": len(chunks),
        "chunks_ok": total_chunks_ok,
        "chunks_error": total_chunks_error,
        "total_time_ms": total_ms,
        "throughput_chunks_per_sec": throughput_chunks_per_sec,
        "total_input_tokens": total_input_tokens,
        "total_output_tokens": total_output_tokens,
        "error_rate": round(total_chunks_error / len(chunks), 4) if chunks else 0
    }

    PARALLEL_RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)

    with PARALLEL_RESULTS_PATH.open("w", encoding="utf-8") as f:
        json.dump(resultados, f, ensure_ascii=False, indent=2)

    with PARALLEL_GLOSSARIO_PATH.open("w", encoding="utf-8") as f:
        json.dump(glossario_global, f, ensure_ascii=False, indent=2)

    with PARALLEL_METRICS_PATH.open("w", encoding="utf-8") as f:
        json.dump({
            "summary": metricas,
            "errors": erros
        }, f, ensure_ascii=False, indent=2)

    print(f"Resultados paralelos salvos em: {PARALLEL_RESULTS_PATH}")
    print(f"Glossário paralelo salvo em: {PARALLEL_GLOSSARIO_PATH}")
    print(f"Métricas paralelas salvas em: {PARALLEL_METRICS_PATH}")
    print(f"Resumo: {metricas}")


if __name__ == "__main__":
    main()