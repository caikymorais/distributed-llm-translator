import json
import time
from pathlib import Path
from typing import Dict, List
from multiprocessing import Process, Queue, current_process

from src.config import BASE_DIR, N_WORKERS
from src.worker.worker_local import carregar_chunks, processar_chunk

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
            results.put({"type": "success", "saida": saida, "glossario_local": glossario_local})
        except Exception as e:
            results.put({
                "type": "error",
                "chunk_id": chunk["chunk_id"],
                "worker_id": worker_id,
                "error_message": str(e),
            })


def main():
    inicio_total = time.time()
    chunks = carregar_chunks()
    print(f"Total de chunks: {len(chunks)}")
    print(f"Iniciando {N_WORKERS} workers locais em paralelo...")

    jobs: Queue = Queue()
    results: Queue = Queue()

    for chunk in chunks:
        jobs.put(chunk)
    for _ in range(N_WORKERS):
        jobs.put(None)

    processos: List[Process] = []
    for i in range(N_WORKERS):
        p = Process(target=worker_process, args=(jobs, results), name=f"worker-local-{i + 1}")
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

    total_ms = int((time.time() - inicio_total) * 1000)
    resultados.sort(key=lambda x: x["chunk_id"])
    total_input_tokens = sum(r["metrics"].get("input_tokens", 0) for r in resultados)
    total_output_tokens = sum(r["metrics"].get("output_tokens", 0) for r in resultados)

    metricas = {
        "n_workers": N_WORKERS,
        "total_chunks": len(chunks),
        "chunks_ok": len(resultados),
        "chunks_error": len(erros),
        "total_time_ms": total_ms,
        "throughput_chunks_per_sec": round(len(resultados) / max((total_ms / 1000), 0.001), 2),
        "total_input_tokens": total_input_tokens,
        "total_output_tokens": total_output_tokens,
        "error_rate": round(len(erros) / len(chunks), 4) if chunks else 0,
    }

    PARALLEL_RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with PARALLEL_RESULTS_PATH.open("w", encoding="utf-8") as f:
        json.dump(resultados, f, ensure_ascii=False, indent=2)
    with PARALLEL_GLOSSARIO_PATH.open("w", encoding="utf-8") as f:
        json.dump(glossario_global, f, ensure_ascii=False, indent=2)
    with PARALLEL_METRICS_PATH.open("w", encoding="utf-8") as f:
        json.dump({"summary": metricas, "errors": erros}, f, ensure_ascii=False, indent=2)

    print(f"Resumo: {metricas}")


if __name__ == "__main__":
    main()
