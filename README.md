# Tradutor Distribuído AWS-only com Glossário Compartilhado

Projeto acadêmico do **Tema 4 — Tradutor e localizador distribuído de grandes volumes de texto**.

A solução recebe um corpus textual em inglês, divide o conteúdo em chunks e processa esses chunks em paralelo por meio de workers executando em instâncias EC2 diferentes. Para manter consistência terminológica entre partes diferentes do mesmo documento, os workers compartilham um glossário técnico em DynamoDB.

> Esta versão foi preparada para validação no ambiente **AWS Academy Learner Lab** e utiliza `MODEL_MODE=fake`, simulando a chamada ao modelo de linguagem para concentrar a avaliação nos conceitos de sistemas distribuídos, paralelismo, troca de mensagens, memória compartilhada distribuída, observabilidade e tolerância a falhas.

---

## 1. Objetivo

Implementar um pipeline distribuído de tradução técnica capaz de:

- particionar um texto grande em chunks;
- distribuir os chunks em uma fila SQS;
- processar chunks em paralelo por dois ou mais workers EC2;
- manter um glossário técnico compartilhado em DynamoDB;
- armazenar entradas e saídas em S3;
- registrar métricas e logs estruturados;
- tratar falhas com retry, backoff e Dead Letter Queue.

---

## 2. Arquitetura Geral

```text
Corpus em inglês na EC2
        ↓
Orquestrador AWS
src.orchestrator.aws_submit_job
        ↓
S3: armazena corpus e chunks
DynamoDB: registra chunks como PENDING
SQS: recebe uma mensagem por chunk
        ↓
EC2 Worker 1        EC2 Worker 2
src.worker.worker_aws
        ↓
DynamoDB: glossário compartilhado + status dos chunks
CloudWatch: métricas e logs
S3: resultados traduzidos
        ↓
Coletor final
src.orchestrator.aws_collect_results
        ↓
Tradução final consolidada
```

---

## 3. Serviços AWS Utilizados

| Serviço | Uso no projeto |
|---|---|
| Amazon EC2 | Execução dos workers distribuídos |
| Amazon S3 | Armazenamento do corpus, chunks e resultados finais |
| Amazon SQS | Fila de mensagens para distribuir chunks entre workers |
| SQS Dead Letter Queue | Tratamento de mensagens que falham repetidamente |
| Amazon DynamoDB | Glossário compartilhado e controle do status dos chunks |
| Amazon CloudWatch | Métricas de latência, tokens, erros e chunks processados |

---

## 4. Estrutura de Diretórios

```text
.
├── data/
│   └── input/
│       └── corpus_en.txt
├── docs/
├── infra/
├── prompts/
│   ├── system/
│   │   ├── translator_v1.txt
│   │   └── translator_v2.txt
│   └── tools/
│       └── translation_output_schema.json
├── src/
│   ├── aws/
│   │   ├── check_dlq.py
│   │   └── structured_log.py
│   ├── orchestrator/
│   │   ├── aws_collect_results.py
│   │   ├── aws_submit_job.py
│   │   └── chunker.py
│   ├── worker/
│   │   ├── model_clients.py
│   │   └── worker_aws.py
│   └── config.py
├── .env.example
├── requirements.txt
└── README.md
```

---

## 5. Componentes do Código

### 5.1 `src/config.py`

Centraliza as configurações do projeto, lendo variáveis de ambiente como região AWS, bucket S3, URLs das filas SQS, nomes das tabelas DynamoDB, tamanho dos chunks e parâmetros de retry.

O modo de modelo está fixado como:

```python
MODEL_MODE = "fake"
```

### 5.2 `src/orchestrator/chunker.py`

Responsável por:

- ler o texto de entrada;
- dividir o corpus em parágrafos;
- agrupar parágrafos em chunks respeitando o limite de caracteres;
- adicionar metadados como `document_id`, `chunk_id` e `total_chunks`.

### 5.3 `src/orchestrator/aws_submit_job.py`

É o orquestrador inicial da execução.

Responsabilidades:

1. ler o corpus de entrada;
2. gerar os chunks;
3. salvar o corpus original no S3;
4. salvar cada chunk no S3;
5. registrar cada chunk no DynamoDB com status `PENDING`;
6. publicar uma mensagem na fila SQS para cada chunk.

### 5.4 `src/worker/worker_aws.py`

É o principal componente distribuído do sistema.

Cada worker:

1. consome uma mensagem da fila SQS;
2. carrega o chunk correspondente no S3;
3. consulta o glossário no DynamoDB;
4. monta o contexto com prompt, schema, glossário e texto do chunk;
5. chama o modelo fake com retry e backoff;
6. grava novos termos técnicos no glossário compartilhado;
7. salva o resultado traduzido no S3;
8. atualiza o status do chunk para `DONE` no DynamoDB;
9. publica métricas no CloudWatch;
10. remove a mensagem da fila SQS somente após sucesso.

### 5.5 `src/worker/model_clients.py`

Simula a chamada a um modelo de linguagem.

A simulação:

- adiciona latência artificial;
- identifica termos técnicos relevantes;
- calcula estimativa de tokens de entrada e saída;
- permite simular falhas por meio da variável `FAKE_FAILURE_RATE`;
- implementa retry com backoff exponencial.

### 5.6 `src/orchestrator/aws_collect_results.py`

Consolida a tradução final.

Responsabilidades:

- listar os resultados parciais salvos no S3;
- ordenar os chunks por `chunk_id`;
- juntar os textos traduzidos;
- salvar a tradução final localmente;
- salvar `final_translation.txt` e `results_merged.json` no S3;
- consultar o DynamoDB para resumir o status dos chunks.

### 5.7 `src/aws/check_dlq.py`

Consulta a Dead Letter Queue e mostra quantas mensagens estão disponíveis ou em processamento.

---

## 6. Engenharia de Contexto Aplicada

A engenharia de contexto foi implementada por meio de:

- prompts versionados no diretório `prompts/system/`;
- schema JSON de resposta em `prompts/tools/translation_output_schema.json`;
- glossário técnico compartilhado em DynamoDB;
- inclusão do `document_id`, `chunk_id`, idioma de origem, idioma de destino e glossário no contexto enviado ao modelo;
- separação entre código de aplicação e arquivos de prompt.

O prompt `translator_v2.txt` orienta o tradutor a preservar a terminologia, usar obrigatoriamente o glossário compartilhado e retornar apenas JSON válido.

---

## 7. Pré-requisitos

Na EC2:

```bash
sudo dnf update -y
sudo dnf install python3 python3-pip git -y
```

Dependências Python:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

O arquivo `requirements.txt` utiliza:

```text
boto3
python-dotenv
```

---

## 8. Configuração do Ambiente

Crie um arquivo `.env` a partir do modelo:

```bash
cp .env.example .env
nano .env
```

Exemplo de configuração:

```bash
AWS_REGION=us-east-1
S3_BUCKET=SEU_BUCKET_S3
SQS_QUEUE_URL=SUA_URL_DA_FILA_PRINCIPAL
SQS_DLQ_URL=SUA_URL_DA_DLQ
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

Carregue as variáveis:

```bash
set -a
source .env
set +a
```

Teste:

```bash
echo $S3_BUCKET
echo $MODEL_MODE
```

---

## 9. Recursos AWS Necessários

### 9.1 S3

Bucket sugerido:

```text
tradutor-distribuido-atv-2026
```

Pastas esperadas:

```text
input/
chunks/
outputs/
metrics/
```

### 9.2 SQS

Fila principal:

```text
translation-jobs-queue
```

DLQ:

```text
translation-jobs-dlq
```

Configuração sugerida:

```text
maxReceiveCount = 3
```

### 9.3 DynamoDB

Tabela do glossário:

```text
TranslationGlossary
Partition key: source_term String
```

Tabela de controle dos chunks:

```text
TranslationChunks
Partition key: document_id String
Sort key: chunk_id Number
```

### 9.4 EC2

Usar pelo menos duas instâncias EC2:

```text
worker-1
worker-2
```

As duas devem estar na mesma região dos demais recursos AWS.

---

## 10. Execução do Experimento

### 10.1 Enviar o corpus para processamento

Execute em uma das EC2:

```bash
source .venv/bin/activate
set -a
source .env
set +a

python3 -m src.orchestrator.aws_submit_job \
  --input data/input/corpus_en.txt \
  --document-id doc_001 \
  --max-chars 400
```

Saída esperada:

```json
{
  "status": "SUBMITTED",
  "document_id": "doc_001",
  "total_chunks": 3,
  "bucket": "tradutor-distribuido-atv-2026",
  "queue_url": "..."
}
```

### 10.2 Rodar o worker 1

Na EC2 `worker-1`:

```bash
source .venv/bin/activate
set -a
source .env
set +a

export WORKER_ID=worker-1
python3 -m src.worker.worker_aws
```

### 10.3 Rodar o worker 2

Na EC2 `worker-2`:

```bash
source .venv/bin/activate
set -a
source .env
set +a

export WORKER_ID=worker-2
python3 -m src.worker.worker_aws
```

### 10.4 Coletar a tradução final

Após o processamento dos chunks:

```bash
python3 -m src.orchestrator.aws_collect_results \
  --document-id doc_001 \
  --output data/output/final_translation.txt
```

### 10.5 Verificar a DLQ

```bash
python3 -m src.aws.check_dlq
```

Resultado esperado em execução sem falhas:

```json
{
  "messages_available": "0",
  "messages_in_flight": "0"
}
```

---

## 11. Teste de Falha

Para demonstrar tolerância a falhas, altere temporariamente no `.env`:

```bash
FAKE_FAILURE_RATE=1.0
```

Carregue novamente:

```bash
set -a
source .env
set +a
```

Execute o worker. A chamada fake irá falhar, o worker não apagará a mensagem da fila, e após o limite configurado no SQS a mensagem poderá ser enviada à DLQ.

Depois do teste, retorne para:

```bash
FAKE_FAILURE_RATE=0.0
```

---

## 12. Métricas Coletadas

O sistema publica no CloudWatch:

| Métrica | Descrição |
|---|---|
| `ChunksProcessed` | Quantidade de chunks processados com sucesso |
| `ChunksError` | Quantidade de chunks com erro |
| `LatencyMs` | Latência total do processamento do chunk |
| `LLMLatencyMs` | Latência simulada da chamada ao modelo |
| `InputTokens` | Estimativa de tokens de entrada |
| `OutputTokens` | Estimativa de tokens de saída |

Dimensões usadas:

```text
DocumentId
WorkerId
```

---

## 13. Demonstração Recomendada

1. Mostrar o bucket S3 com as pastas e arquivos.
2. Executar o orquestrador e mostrar mensagens no SQS.
3. Rodar `worker-1` e `worker-2` em EC2 diferentes.
4. Mostrar a tabela `TranslationChunks` com status `DONE`.
5. Mostrar a tabela `TranslationGlossary` preenchida.
6. Mostrar os resultados em `outputs/doc_001/chunks/` no S3.
7. Executar o coletor final.
8. Mostrar `final_translation.txt` no S3.
9. Mostrar as métricas no CloudWatch.
10. Mostrar a DLQ vazia ou executar um teste controlado de falha.

---

## 14. Limitações

- A tradução é simulada com `MODEL_MODE=fake`.
- O sistema não avalia qualidade linguística real.
- O glossário é simples, usando chave `source_term`.
- A coleta de métricas é suficiente para análise acadêmica, mas poderia ser ampliada com dashboards automatizados.
- A infraestrutura foi pensada para AWS Academy, com foco em simplicidade e reprodutibilidade.

---

## 15. Melhorias Futuras

- Substituir o modelo fake por Amazon Bedrock ou SLM auto-hospedado.
- Criar dashboard CloudWatch automatizado.
- Adicionar CloudFormation/Terraform completo.
- Implementar lock mais sofisticado para aprovação humana de termos conflitantes.
- Adicionar testes automatizados.
- Comparar execução com 1, 2 e 3 workers.
- Gerar gráficos automaticamente a partir dos resultados salvos.
