# 🎓 Datathon - Machine Learning Engineering

API de previsão de defasagem escolar com deploy automatizado e monitoramento em tempo real.

**🚀 Deploy:** [https://datathon-machine-learning-engineering-1.onrender.com](https://datathon-machine-learning-engineering-1.onrender.com)  
**📊 Painel de Monitoramento:** [https://datathon-machine-learning-engineering-1.onrender.com/monitor/dashboard](https://datathon-machine-learning-engineering-1.onrender.com/monitor/dashboard)  
**📖 Documentação Interativa:** [https://datathon-machine-learning-engineering-1.onrender.com/docs](https://datathon-machine-learning-engineering-1.onrender.com/docs)

---

## 🎯 Visão Geral do Projeto

### Problema de Negócio

O **risco de defasagem escolar** é um dos principais desafios da educação pública brasileira. Alunos em defasagem idade-série apresentam maior risco de evasão e baixo desempenho. Este projeto desenvolve um modelo preditivo para identificar, com antecedência, alunos em risco de defasagem no próximo ano letivo.

### Solução Proposta

Pipeline completa de Machine Learning, desde a coleta e pré-processamento de dados até o deploy em produção:

1. **Análise Exploratória e Feature Engineering** - Criação de features preditivas a partir de dados do PEDE 2022
2. **Treinamento e Validação** - Modelo supervisionado com validação cruzada
3. **API REST** - Endpoint para inferência em lote via upload de CSV
4. **Deploy Automatizado** - Containerização Docker e deploy no Render.com
5. **Monitoramento** - Logging no S3 e dashboard web para acompanhamento

### Stack Tecnológica

- **Linguagem:** Python 3.11+
- **Frameworks de ML:** scikit-learn, pandas, numpy
- **API:** FastAPI 0.116+
- **Serialização:** joblib
- **Testes:** pytest
- **Empacotamento:** Docker + docker-compose
- **Deploy:** Render.com (cloud PaaS)
- **Monitoramento:** AWS S3 (logs) + Streamlit (dashboard web)
- **CI/CD:** Blueprint YAML (render.yaml)

---

## 🔄 Pipeline de Machine Learning

### 1. Pré-processamento de Dados

- **Normalização de colunas:** Conversão de nomes de colunas para formato padronizado
- **Mapeamento de aliases:** Aceita variações de nomes (`serie`, `fase`, `fase_adj`)
- **Conversão de tipos:** Limpeza e conversão de valores numéricos (remoção de `%`, `,` → `.`)
- **Mapeamento de fases:** Conversão de série numérica para `FASE X` padronizada

### 2. Engenharia de Features

- **`gap_idade`:** Defasagem entre idade real e idade ideal para a fase
- **`media_notas`:** Média aritmética de português, inglês e matemática
- **`z_notas_fase`:** Z-score das notas normalizado por fase (identifica alunos acima/abaixo da média da turma)
- **`z_ieg_fase`:** Z-score do IEG normalizado por fase (engajamento relativo)
- **`feat_IPV`:** Índice de Ponto de Virada

### 3. Treinamento e Validação

- **Algoritmo:** Modelo de regressão supervisionado (scikit-learn)
- **Validação:** Validação cruzada (cross-validation)
- **Métrica:** MAE, RMSE para avaliar erro de predição
- **Target:** Score de defasagem previsto para o próximo ano (escala 0-10)

### 4. Seleção de Modelo

- Pipeline completo salvo com `joblib` incluindo pré-processamento e modelo
- Schema JSON com features obrigatórias para validação em produção

### 5. Pós-processamento

- Cálculo do `score_de_defasagem_atual` baseado em:
  - Gap de idas de Chamadas à API

#### Exemplo 1: cURL (linha de comando)

```bash
curl -X POST "https://datathon-machine-learning-engineering-1.onrender.com/predict-csv" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@alunos.csv" \
  -o resultado.csv
```

#### Exemplo 2: Python (requests)

```python
import requests

url = "https://datathon-machine-learning-engineering-1.onrender.com/predict-csv"
files = {"file": open("alunos.csv", "rb")}
response = requests.post(url, files=files)

if response.ok:
    with open("resultado.csv", "wb") as f:
        f.write(response.content)
    print("Predições salvas em resultado.csv")
else:
    print(f"Erro: {response.status_code} - {response.text}")
```

#### Exemplo 3: Healthcheck

```bash
curl https://datathon-machine-learning-engineering-1AWS S3** e disponibiliza dados via endpoints JSON e painel web.

### Painel Web de Monitoramento

Acesse o dashboard visual em:
```
https://datathon-machine-learning-engineering-1.onrender.com/monitor/dashboard
```

**Recursos do painel:**
- Status de saúde da API (`/health`)
- KPIs: total de requisições, linhas processadas, médias previstas
- Tabelas de médias globais por fase
- Histórico de requisições com timestamps

### API de Monitoramento (JSON)

```bash
curl https://datathon-machine-learning-engineering-1.onrender.com/monitor/summary-s3?limit=10
```

**Informações retornadas:**
- Total de requisições gravadas no S3
- Histórico de uploads (filename, timestamp, linhas processadas)
- Médias por fase: score previsto, gap de idade, notas brutas e IEG
- Estatísticas agregadas por fasereinado com validação cruzada e salvo em:
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
Datathon-Machine-Learning-Engineering/
├── api/                         # Código da API
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py              # FastAPI application (endpoints)
│   │   ├── model_runtime.py     # Carregamento do modelo serializado
│   │   ├── preprocessing.py     # Feature engineering e validação
│   │   ├── s3_logger.py         # Upload de logs para AWS S3
│   │   └── config.py            # Configurações (env vars)
│   ├── artifacts/
│   │   ├── modelo_defasagem_pipeline.joblib  # Pipeline treinado
│   │   ├── modelo_defasagem_schema.json      # Schema de validação
│   │   └── modelo_defasagem_impacto.csv      # Importância de features
│   ├── test_inputs/
│   │   └── pede2022_api_input.csv            # CSV de exemplo
│   ├── tests/
│   │   ├── test_api_predict_csv.py           # Testes unitários
│   │   └── test_request_simple.py            # Teste de integração
│   ├── Dockerfile               # Container da API FastAPI
│   ├── Dockerfile.monitor       # Container do Streamlit (opcional)
│   ├── streamlit_app.py         # Dashboard de monitoramento
│   ├── requirements.txt         # Dependências Python
│   └── README.md                # Documentação da API
├── data/
│   ├── modelo_previsao_defasagem.ipynb       # Notebook de treinamento
│   ├── inferencia_modelo_final_defasagem.ipynb  # Notebook de inferência
│   └── data_modeling.ipynb                   # Análise exploratória
├── docker-compose.yml           # Orquestração local (API + Monitor)
├── render.yaml                  # Blueprint para deploy no Render.com
└── README.md                    # Este arquivo
```

---

## 🚀 Instruções de Deploy

### Pré-requisitos

- **Python:** 3.11 ou superior
- **Docker:** 20.10+ (opcional, para deploy local)
- **AWS S3:** Bucket configurado para logs (opcional, para monitoramento)
- **Render.com:** Conta gratuita (para deploy em cloud)

### Deploy Local (Docker)

#### 1. Clone o repositório

```bash
git clone https://github.com/udanielsantin/Datathon-Machine-Learning-Engineering.git
cd Datathon-Machine-Learning-Engineering
```

#### 2. Configure variáveis de ambiente

```bash
cd api
cp .env.example .env
# Edite api/.env com suas credenciais AWS (opcional para S3)
```

#### 3. Suba a aplicação com Docker Compose

```bash
cd ..
docker compose up --build
```

A API estará disponível em: `http://localhost:8000`  
O painel de monitoramento em: `http://localhost:8501`

### Deploy Local (Python Virtual Environment)

#### 1. Instale as dependências

```bash
cd api
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

#### 2. Inicie o servidor

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### Deploy em Produção (Render.com)

#### Método 1: Blueprint YAML (automático)

1. Faça fork/clone deste repositório
2. Acesse [Render Dashboard](https://dashboard.render.com/)
3. **New +** → **Blueprint**
4. Conecte este repositório
5. Configure variáveis de ambiente (AWS credentials)
6. Render vai criar automaticamente os serviços definidos em `render.yaml`

#### Método 2: Manual

1. Acesse [Render Dashboard](https://dashboard.render.com/)
2. **New +** → **Web Service**
3. Conecte o repositório GitHub
4. Configure:
   - **Name:** datathon-api
   - **Runtime:** Docker
   - **Dockerfile Path:** `api/Dockerfile`
   - **Docker Context:** `api`
5. Adicione variáveis de ambiente:
   ```
   AWS_REGION=us-east-1
   S3_BUCKET=seu-bucket-s3
   S3_PREFIX=datathon/logs
   AWS_ACCESS_KEY_ID=sua-key
   AWS_SECRET_ACCESS_KEY=sua-secret
   ```
6. **Create Web Service**
7. Aguarde ~5-10 minutos até status `Live`

---

## 🧪 Testes

### Testes Unitários

```bash
cd api
source .venv/bin/activate  # ou docker exec -it datathon-api bash
pytest tests/test_api_predict_csv.py -v
```

### Teste de Integração

```bash
# API local deve estar rodando em http://localhost:8000
cd api
python tests/test_request_simple.py
```

### Teste com CSV de exemplo

```bash
curl -X POST "http://localhost:8000/predict-csv" \
  -F "file=@api/test_inputs/pede2022_api_input.csv" \
  -o resultado.cstAPI application
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
- **Monitoramento:** Streamlit dashboard com status da API, alertas e tendencias


