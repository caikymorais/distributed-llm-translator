# Tradutor distribuído AWS-only

Projeto do Tema 4: tradutor/localizador distribuído de grandes volumes de texto com consistência terminológica.

Esta versão foi limpa para a apresentação no **AWS Academy** e usa somente:

- Amazon S3;
- Amazon SQS;
- SQS DLQ;
- Amazon DynamoDB;
- Amazon EC2 Workers;
- Amazon CloudWatch;
- `MODEL_MODE=fake`.

Não há execução local, Bedrock, Ollama ou API externa. A tradução é simulada para validar a arquitetura distribuída.

## Fluxo

```text
Corpus na EC2
 ↓
src.orchestrator.aws_submit_job
 ↓
S3 + SQS + DynamoDB
 ↓
EC2 worker-1 e EC2 worker-2
 ↓
outputs no S3 + glossário no DynamoDB + métricas no CloudWatch
 ↓
src.orchestrator.aws_collect_results
```

## Comandos principais

### 1. Instalar dependências

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Carregar variáveis

```bash
set -a
source .env
set +a
```

### 3. Enviar o corpus para SQS/S3/DynamoDB

```bash
python3 -m src.orchestrator.aws_submit_job \
  --input data/input/corpus_en.txt \
  --document-id doc_001 \
  --max-chars 400
```

### 4. Rodar worker na EC2 1

```bash
export WORKER_ID=worker-1
python3 -m src.worker.worker_aws
```

### 5. Rodar worker na EC2 2

```bash
export WORKER_ID=worker-2
python3 -m src.worker.worker_aws
```

### 6. Coletar resultado final

```bash
python3 -m src.orchestrator.aws_collect_results \
  --document-id doc_001 \
  --output data/output/final_translation.txt
```

### 7. Conferir DLQ

```bash
python3 -m src.aws.check_dlq
```

Veja também `README_AWS_ACADEMY.md`.
