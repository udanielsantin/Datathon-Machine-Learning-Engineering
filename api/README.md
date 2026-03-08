# API de previsao de defasagem

Esta API recebe um CSV com dados do aluno, calcula as features esperadas pelo modelo final e devolve um CSV com `score_de_defasagem_atual` e `score_previsto_proximo_ano`.

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

No EC2, o recomendado e usar IAM Role na instancia com permissao de `s3:PutObject`, `s3:GetObject` e `s3:ListBucket` no bucket/prefixo.

## Rodar API (FastAPI)

```bash
cd /workspaces/Datathon-Machine-Learning-Engineering/api
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

## Endpoint principal

`POST /predict-csv`
- multipart/form-data com campo `file`
- resposta: `text/csv` com colunas originais + colunas calculadas + `score_de_defasagem_atual` + `score_previsto_proximo_ano`

Exemplo com curl:

```bash
curl -X POST "http://localhost:8000/predict-csv" \
  -H "accept: text/csv" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@/caminho/entrada.csv" \
  -o saida_predita.csv
```

## Schema da entrada

`GET /schema` retorna:
- colunas obrigatorias no formato esperado pelo CSV (`serie,idade,ipv,portugues,ingles,matematica,ieg`)
- aliases aceitos para cada coluna
- schema interno do modelo (features de inferencia)

## Logs

Logs sao enviados para **S3**: um JSON por requisicao em `s3://$S3_BUCKET/$S3_PREFIX/<request_id>.json`

Cada log contem:
- metadados da requisicao
- media de retorno da API
- medias por fase (`media_prevista`, `media_gap_idade`, `media_z_notas`, `media_z_ieg`)

Leitura de historico:
- **S3** (objetos `.json`): `GET /monitor/summary-s3`

## Monitoramento com Streamlit

```bash
cd /workspaces/Datathon-Machine-Learning-Engineering/api
streamlit run streamlit_app.py --server.port 8501
```

O painel consulta `GET /monitor/summary-s3` e mostra:
- historico de retornos da API
- medias globais por fase
- detalhe de fases por requisicao recente

Paginas de monitoramento:
- API monitor via S3 (JSON): `http://<host>:8000/monitor/summary-s3`
- Dashboard Streamlit: `http://<host>:8501`

## Docker (API + Monitor)

Arquivos criados:
- `api/Dockerfile` (FastAPI)
- `api/Dockerfile.monitor` (Streamlit)
- `docker-compose.yml` (subir os 2 servicos)

Subir local/EC2:

```bash
cd /workspaces/Datathon-Machine-Learning-Engineering
cp api/.env.example api/.env
# edite api/.env com AWS_REGION, S3_BUCKET, S3_PREFIX
docker compose up -d --build
```

Ver status:

```bash
docker compose ps
docker compose logs -f api
docker compose logs -f monitor
```

## Deploy no EC2 (resumo)

1. Instale Docker e Docker Compose no EC2.
2. Suba o codigo para a instancia.
3. Configure `api/.env`.
4. Garanta IAM Role com acesso ao S3.
5. Abra Security Group nas portas:
  - `8000` (API/docs)
  - `8501` (dashboard)
6. Rode `docker compose up -d --build`.

Rotas uteis apos deploy:
- `http://<EC2_PUBLIC_IP>:8000/docs`
- `http://<EC2_PUBLIC_IP>:8000/health`
- `http://<EC2_PUBLIC_IP>:8000/monitor/summary-s3`
- `http://<EC2_PUBLIC_IP>:8501`
