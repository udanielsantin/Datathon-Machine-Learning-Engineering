# 🎓 Datathon - Machine Learning Engineering

API de previsão de defasagem escolar com deploy automatizado e monitoramento em tempo real.

**🚀 Deploy:** [https://datathon-machine-learning-engineering-1.onrender.com](https://datathon-machine-learning-engineering-1.onrender.com)

---

## 📊 Como funciona

### 1. Modelo de Machine Learning

O modelo foi desenvolvido no notebook [`data/modelo_previsao_defasagem.ipynb`](data/modelo_previsao_defasagem.ipynb) usando:

- **Dataset:** PEDE 2022 (dados de alunos da rede pública)
- **Features principais:**
  - `Fase_adj`: Fase/série do aluno
  - `gap_idade`: Defasagem idade-série
  - `feat_IPV`: Índice de Pobreza e Vulnerabilidade
  - `z_notas_fase`: Z-score das notas normalizadas por fase
  - `z_ieg_fase`: Z-score do IEG (engajamento) por fase
  
- **Target:** Score de defasagem previsto para o próximo ano (0-10)
  
- **Pipeline:** Modelo treinado com validação cruzada e salvo em:
  - `api/artifacts/modelo_defasagem_pipeline.joblib`
  - `api/artifacts/modelo_defasagem_schema.json`

### 2. API FastAPI

A API (`api/app/main.py`) recebe um CSV com dados dos alunos, calcula as features necessárias e retorna predições.

**Endpoints principais:**

| Endpoint | Método | Descrição |
|----------|--------|-----------|
| `/health` | GET | Healthcheck da API |
| `/schema` | GET | Formato esperado do CSV e features |
| `/predict-csv` | POST | Upload CSV e recebe predições |
| `/monitor/summary-s3` | GET | Monitoramento e histórico (S3) |

---

## 🔌 Como usar a API

### 📥 Enviar CSV para predição

**Endpoint:** `POST /predict-csv`

**CSV de entrada** (colunas obrigatórias):
```csv
serie,idade,ipv,portugues,ingles,matematica,ieg
3,10,0.45,7.5,6.8,7.2,8.1
4,12,0.62,6.3,5.9,6.1,7.4
```

**Aliases aceitos:**
- `serie` = `fase` = `fase_adj`
- `ipv` = `feat_ipv`

**CSV de retorno** (colunas originais + novas):
```csv
serie,idade,ipv,portugues,ingles,matematica,ieg,Fase_adj,gap_idade,z_notas_fase,z_ieg_fase,score_de_defasagem_atual,score_previsto_proximo_ano
3,10,0.45,7.5,6.8,7.2,8.1,FASE 3,1.0,-0.34,0.52,1.53,1.82
4,12,0.62,6.3,5.9,6.1,7.4,FASE 4,3.0,0.21,-0.18,3.47,3.65
```

**Novas colunas:**
- `score_de_defasagem_atual`: Score calculado da defasagem atual
- `score_previsto_proximo_ano`: Predição do modelo para próximo ano
- Features calculadas: `Fase_adj`, `gap_idade`, `z_notas_fase`, `z_ieg_fase`

### 📝 Exemplo de uso

**Via cURL:**
```bash
curl -X POST "https://datathon-machine-learning-engineering-1.onrender.com/predict-csv" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@alunos.csv" \
  -o resultado.csv
```

**Via Python:**
```python
import requests

url = "https://datathon-machine-learning-engineering-1.onrender.com/predict-csv"
files = {"file": open("alunos.csv", "rb")}
response = requests.post(url, files=files)

with open("resultado.csv", "wb") as f:
    f.write(response.content)
```

**Via Interface Web (Swagger):**
```
https://datathon-machine-learning-engineering-1.onrender.com/docs
```

---

## 📈 Monitoramento

A API registra cada requisição automaticamente no **S3**.

### Ver histórico de requisições

**Monitor S3:**
```bash
curl https://datathon-machine-learning-engineering-1.onrender.com/monitor/summary-s3?limit=10
```

**Informações retornadas:**
- Total de requisições
- Histórico de uploads (filename, timestamp, linhas processadas)
- Médias de predição por fase
- Estatísticas agregadas

### Dashboard Streamlit (opcional)

Se deployado, acesse:
```
https://datathon-monitor.onrender.com
```

Visualize:
- Gráficos de histórico de predições
- Médias por fase
- Timeline de requisições

---

## 🚀 Deploy no Render

### Deploy rápido (3 minutos)

1. **Fork/Clone** este repositório
2. Acesse [Render Dashboard](https://dashboard.render.com/)
3. **New +** → **Web Service**
4. Conecte este repositório
5. Configure:
   ```
   Name: datathon-api
   Runtime: Docker
   Dockerfile Path: api/Dockerfile
   Docker Context: api
   Health Check Path: /health
   ```
6. **Adicione variáveis de ambiente (obrigatório):**
   ```
   AWS_REGION=us-east-1
   S3_BUCKET=seu-bucket-s3
   S3_PREFIX=datathon/logs
   AWS_ACCESS_KEY_ID=sua-access-key
   AWS_SECRET_ACCESS_KEY=sua-secret-key
   ```
7. **Create Web Service**
8. Aguarde ~5-10 minutos até status `Live`

### Testar após deploy

```bash
# Health check
curl https://SEU-APP.onrender.com/health

# Upload CSV de teste
curl -X POST "https://SEU-APP.onrender.com/predict-csv" \
  -F "file=@api/test_inputs/pede2022_api_input.csv" \
  -o teste_resultado.csv

# Ver monitoramento
curl https://SEU-APP.onrender.com/monitor/summary-s3
```

**Documentação completa:** [`DEPLOY_RENDER.md`](DEPLOY_RENDER.md)

---

## 🛠️ Desenvolvimento Local

### Requisitos
- Python 3.11+
- Docker (opcional)

### Setup sem Docker

```bash
cd api
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Configurar .env
cp .env.example .env
# Edite api/.env com suas credenciais AWS

# Carregar variáveis e iniciar
set -a && source .env && set +a
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Acesse: http://localhost:8000/docs

### Setup com Docker

```bash
# API
docker build -f api/Dockerfile -t datathon-api ./api
docker run -p 8000:8000 --env-file api/.env datathon-api

# Ou use docker-compose (API + Monitor)
docker compose up --build
```

---

## 📁 Estrutura do Projeto

```
.
├── api/
│   ├── app/
│   │   ├── main.py              # FastAPI application
│   │   ├── model_runtime.py     # Carregamento do modelo
│   │   ├── preprocessing.py     # Feature engineering
│   │   ├── s3_logger.py         # Upload logs para S3
│   │   └── config.py            # Configurações
│   ├── artifacts/
│   │   ├── modelo_defasagem_pipeline.joblib  # Modelo treinado
│   │   └── modelo_defasagem_schema.json      # Schema das features
│   ├── tests/
│   │   └── test_api_predict_csv.py
│   ├── Dockerfile               # Container da API
│   ├── Dockerfile.monitor       # Container do Streamlit
│   ├── streamlit_app.py         # Dashboard de monitoramento
│   └── requirements.txt
├── data/
│   ├── modelo_previsao_defasagem.ipynb   # Notebook de treinamento
│   └── inferencia_modelo_final_defasagem.ipynb
├── docker-compose.yml
├── render.yaml                  # Blueprint do Render
└── README.md
```

---

## 🧪 Testes

```bash
cd api

# Teste via HTTP request (API deve estar rodando)
python test_request_simple.py

# Teste via pytest
pytest tests/test_api_predict_csv.py -v
```

---

## 📝 Notas Técnicas

- **Framework:** FastAPI 0.116+
- **ML Pipeline:** scikit-learn (salvo via joblib)
- **Storage:** Logs locais (JSONL) + AWS S3
- **Containerização:** Docker multi-stage
- **Deploy:** Render.com (Blueprint YAML)
- **Monitoramento:** Streamlit dashboard

---

## 🔒 Segurança

- ✅ `.env` files adicionados ao `.gitignore`
- ✅ Credenciais AWS via variáveis de ambiente
- ⚠️ **Rotacione credenciais AWS** expostas em desenvolvimento antes de produção
- ✅ Health checks configurados
- ✅ Validação de input com Pydantic

---

## 📄 Licença

MIT License - veja [LICENSE](LICENSE) para detalhes.

---

## 👤 Autor

**Daniel Santin**  
GitHub: [@udanielsantin](https://github.com/udanielsantin)

---

**💡 Dúvidas?** Abra uma [issue](https://github.com/udanielsantin/Datathon-Machine-Learning-Engineering/issues) ou veja a [documentação completa de deploy](DEPLOY_RENDER.md).
