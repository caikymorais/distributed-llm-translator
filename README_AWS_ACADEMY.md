# Execução AWS-only no AWS Academy

Esta versão do projeto foi preparada para ser validada somente na AWS Academy.

## Recursos usados

| Serviço | Uso |
|---|---|
| S3 | Armazena corpus, chunks, traduções parciais e tradução final |
| SQS | Distribui os chunks entre os workers |
| SQS DLQ | Guarda mensagens com falha após várias tentativas |
| DynamoDB | Mantém glossário compartilhado e status dos chunks |
| EC2 | Executa os workers distribuídos |
| CloudWatch | Guarda logs e métricas |

## Variáveis no `.env`

```bash
AWS_REGION=us-east-1
S3_BUCKET=tradutor-distribuido-atv-2026
SQS_QUEUE_URL=https://sqs.us-east-1.amazonaws.com/SEU_ACCOUNT_ID/translation-jobs-queue
SQS_DLQ_URL=https://sqs.us-east-1.amazonaws.com/SEU_ACCOUNT_ID/translation-jobs-dlq
DYNAMODB_GLOSSARY_TABLE=TranslationGlossary
DYNAMODB_CHUNKS_TABLE=TranslationChunks
CLOUDWATCH_NAMESPACE=TradutorDistribuido
MODEL_MODE=fake
SOURCE_LANG=en
TARGET_LANG=pt-BR
MAX_CHARS_PER_CHUNK=400
MAX_RETRIES=3
BACKOFF_BASE_SECONDS=1
FAKE_FAILURE_RATE=0.0
DOCUMENT_ID=doc_001
```

## Instalação em cada EC2

```bash
sudo dnf update -y
sudo dnf install python3 python3-pip git -y

git clone URL_DO_SEU_REPOSITORIO
cd NOME_DO_REPOSITORIO

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Crie o arquivo `.env`:

```bash
cp .env.example .env
nano .env
```

Carregue as variáveis:

```bash
set -a
source .env
set +a
```

## Teste de acesso à AWS

```bash
aws sts get-caller-identity
aws s3 ls s3://tradutor-distribuido-atv-2026
```

## Enviar job para processamento

Execute uma vez, em uma das EC2:

```bash
python3 -m src.orchestrator.aws_submit_job \
  --input data/input/corpus_en.txt \
  --document-id doc_001 \
  --max-chars 400
```

Esse comando:

1. lê o corpus;
2. divide em chunks;
3. salva corpus e chunks no S3;
4. registra os chunks no DynamoDB com status `PENDING`;
5. envia uma mensagem por chunk para o SQS.

## Rodar workers distribuídos

Na EC2 1:

```bash
set -a
source .env
set +a
export WORKER_ID=worker-1
python3 -m src.worker.worker_aws
```

Na EC2 2:

```bash
set -a
source .env
set +a
export WORKER_ID=worker-2
python3 -m src.worker.worker_aws
```

## Coletar resultado final

Depois que os chunks forem processados:

```bash
python3 -m src.orchestrator.aws_collect_results \
  --document-id doc_001 \
  --output data/output/final_translation.txt
```

O resultado também será salvo no S3 em:

```text
outputs/doc_001/final_translation.txt
outputs/doc_001/results_merged.json
```

## Verificar DLQ

```bash
python3 -m src.aws.check_dlq
```

O esperado em uma execução correta é:

```json
{
  "messages_available": "0",
  "messages_in_flight": "0"
}
```

## Demonstração para apresentação

Mostre:

1. bucket S3 com `input/`, `chunks/` e `outputs/`;
2. fila SQS recebendo mensagens;
3. duas EC2 rodando `worker_aws.py` ao mesmo tempo;
4. tabela `TranslationChunks` com status `DONE`;
5. tabela `TranslationGlossary` com termos técnicos;
6. métricas no CloudWatch;
7. arquivo final em `outputs/doc_001/final_translation.txt`.

## Observação sobre o modelo

A solução usa `MODEL_MODE=fake` para simular a chamada a um modelo de linguagem. Essa decisão elimina dependência de Bedrock, GPU, Ollama ou qualquer API externa. O objetivo da validação é demonstrar a arquitetura distribuída com SQS, EC2, DynamoDB, S3 e CloudWatch.
