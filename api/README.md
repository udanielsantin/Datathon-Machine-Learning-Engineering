# API de previsao de defasagem

Esta API recebe um CSV com dados do aluno, calcula as features esperadas pelo modelo final e devolve um CSV com `score_previsto_proximo_ano`.

## Entrada esperada no CSV

Colunas obrigatorias (aceita aliases simples):
- `serie` (ou `fase`, `fase_adj`) -> vira `Fase_adj`
- `idade` -> usada no `gap_idade`
- `ipv` (ou `feat_ipv`) -> vira `feat_IPV`
- `portugues`
- `ingles`
- `matematica`
- `ieg`

Features calculadas pela API:
- `Fase_adj`
- `gap_idade`
- `z_notas_fase`
- `z_ieg_fase`

## Setup

```bash
cd /workspaces/Datathon-Machine-Learning-Engineering/api
pip install -r requirements.txt
cp .env.example .env
```

Se quiser log no S3, configure credenciais AWS no ambiente e preencha:
- `S3_BUCKET`
- `S3_PREFIX`
- `AWS_REGION`

## Rodar API (FastAPI)

```bash
cd /workspaces/Datathon-Machine-Learning-Engineering/api
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

## Endpoint principal

`POST /predict-csv`
- multipart/form-data com campo `file`
- resposta: `text/csv` com colunas originais + colunas calculadas + `score_previsto_proximo_ano`

Exemplo com curl:

```bash
curl -X POST "http://localhost:8000/predict-csv" \
  -H "accept: text/csv" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@/caminho/entrada.csv" \
  -o saida_predita.csv
```

## Logs

- Local: `api/logs/inference_history.jsonl`
- S3: um JSON por requisicao em `s3://$S3_BUCKET/$S3_PREFIX/<request_id>.json`

Cada log contem:
- metadados da requisicao
- media de retorno da API
- medias por fase (`media_prevista`, `media_gap_idade`, `media_z_notas`, `media_z_ieg`)

## Monitoramento com Streamlit

```bash
cd /workspaces/Datathon-Machine-Learning-Engineering/api
streamlit run streamlit_app.py --server.port 8501
```

O painel consulta `GET /monitor/summary` e mostra:
- historico de retornos da API
- medias globais por fase
- detalhe de fases por requisicao recente
