# Tradutor distribuído de grandes volumes de texto (Tema 4)

## Objetivo
Construir um sistema que recebe um corpus de texto em inglês e produz a tradução para português em paralelo, mantendo consistência terminológica por meio de um glossário distribuído.

## Estrutura de pastas
- `src/orchestrator/chunker.py`: lê o corpus e divide em chunks com limite de caracteres.
- `src/worker/worker_local.py`: processa chunks sequencialmente, simulando chamadas ao modelo de linguagem.
- `src/worker/parallel_workers_local.py`: processa chunks em paralelo com múltiplos workers locais.
- `prompts/system/translator_v1.txt`: system prompt versionado do tradutor.
- `data/input/corpus_en.txt`: corpus de entrada.
- `data/output/*.json`: chunks, traduções e glossários gerados.

## Execução local
1. Gerar chunks:
   ```bash
   python src/orchestrator/chunker.py
   ```
2. Processar sequencialmente (1 worker):
   ```bash
   python src/worker/worker_local.py
   ```
3. Processar em paralelo (3 workers):
   ```bash
   python src/worker/parallel_workers_local.py
   ```