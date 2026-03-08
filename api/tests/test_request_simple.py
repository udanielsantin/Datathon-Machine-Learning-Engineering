#!/usr/bin/env python3
"""Teste simples fazendo requisição real na API rodando em localhost:8000"""
import requests
import time
from pathlib import Path

API_URL = "http://localhost:8000"
CSV_PATH = Path(__file__).parent / "test_inputs" / "pede2022_api_input.csv"

print("="*60)
print("TESTE DE REQUISIÇÃO NA API")
print("="*60)

# 1. Health check
print("\n1️⃣  Testando /health...")
try:
    response = requests.get(f"{API_URL}/health", timeout=5)
    if response.status_code == 200:
        print(f"   ✅ API está rodando: {response.json()}")
    else:
        print(f"   ❌ Health check falhou: {response.status_code}")
        exit(1)
except requests.exceptions.ConnectionError:
    print(f"   ❌ API não está rodando em {API_URL}")
    print("   Execute primeiro: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload")
    exit(1)

# 2. Verifica se CSV existe
print(f"\n2️⃣  Verificando CSV de teste...")
if not CSV_PATH.exists():
    print(f"   ❌ CSV não encontrado: {CSV_PATH}")
    exit(1)
print(f"   ✅ CSV encontrado: {CSV_PATH.name}")
print(f"   📊 Tamanho: {CSV_PATH.stat().st_size} bytes")

# 3. Faz upload do CSV
print(f"\n3️⃣  Enviando CSV para /predict-csv...")
with CSV_PATH.open("rb") as f:
    files = {"file": (CSV_PATH.name, f, "text/csv")}
    response = requests.post(f"{API_URL}/predict-csv", files=files, timeout=30)

if response.status_code != 200:
    print(f"   ❌ Erro no upload: {response.status_code}")
    print(f"   Resposta: {response.text[:500]}")
    exit(1)

print(f"   ✅ Upload concluído com sucesso!")

# Headers da resposta
request_id = response.headers.get("X-Request-Id")
s3_status = response.headers.get("X-S3-Status")

print(f"   📋 Request ID: {request_id}")
print(f"   📋 S3 Status: {s3_status}")

# Conta linhas retornadas
linhas_csv = response.text.count('\n')
print(f"   📊 Linhas no CSV retornado: {linhas_csv}")

# 4. Valida conteúdo do CSV
print(f"\n4️⃣  Validando colunas retornadas...")
primeira_linha = response.text.split('\n')[0]
colunas = primeira_linha.split(',')

colunas_esperadas = [
    "score_de_defasagem_atual",
    "score_previsto_proximo_ano",
    "Fase_adj",
    "gap_idade",
    "z_notas_fase",
    "z_ieg_fase"
]

encontradas = []
for col in colunas_esperadas:
    if col in primeira_linha:
        print(f"   ✅ {col}")
        encontradas.append(col)
    else:
        print(f"   ❌ {col} - FALTANDO")

# 5. Testa monitor S3
print(f"\n5️⃣  Testando /monitor/summary-s3...")
time.sleep(2)  # Aguarda propagação

response_s3 = requests.get(f"{API_URL}/monitor/summary-s3?limit=10", timeout=10)

if response_s3.status_code == 200:
    data = response_s3.json()
    print(f"   ✅ Monitor S3 funcionando!")
    print(f"   📊 Bucket: {data.get('s3_bucket')}")
    print(f"   📊 Prefix: {data.get('s3_prefix')}")
    print(f"   📊 Total requests no S3: {data.get('total_requests', 0)}")
    
    # Procura o request_id
    history = data.get("history", [])
    request_ids = [entry.get("request_id") for entry in history]
    
    if request_id in request_ids:
        print(f"   ✅ Log encontrado no S3! Request ID: {request_id}")
        
        # Busca detalhes
        log_entry = next((e for e in history if e.get("request_id") == request_id), None)
        if log_entry:
            print(f"\n   📊 DETALHES DO LOG:")
            print(f"      Arquivo: {log_entry.get('input_filename')}")
            print(f"      Linhas processadas: {log_entry.get('rows_scored')}")
            print(f"      Média prevista: {log_entry.get('api_return_mean', 0):.4f}")
            print(f"      Score atual: {log_entry.get('api_current_score_mean', 0):.4f}")
            
            phase_summary = log_entry.get("phase_summary", [])
            if phase_summary:
                print(f"\n   📊 RESUMO POR FASE:")
                for phase in phase_summary[:3]:  # Mostra só 3 primeiras
                    print(f"      Fase {phase.get('Fase_adj')}: {phase.get('total_alunos')} alunos")
    else:
        print(f"   ⚠️  Request {request_id} não apareceu no S3 ainda")
        print(f"   📋 Últimos IDs: {request_ids[:3]}")
        
elif response_s3.status_code == 400:
    print(f"   ⚠️  S3 não configurado ou erro de acesso")
    print(f"   Resposta: {response_s3.text[:300]}")
else:
    print(f"   ❌ Erro: {response_s3.status_code}")
    print(f"   Resposta: {response_s3.text[:300]}")

# 6. Testa monitor local (jsonl)
print(f"\n6️⃣  Testando /monitor/summary (local)...")
response_local = requests.get(f"{API_URL}/monitor/summary?limit=5", timeout=5)

if response_local.status_code == 200:
    data_local = response_local.json()
    print(f"   ✅ Monitor local funcionando!")
    print(f"   📊 Total requests: {data_local.get('total_requests', 0)}")
    
    history_local = data_local.get("history", [])
    if history_local:
        last = history_local[-1]
        print(f"   📋 Último request: {last.get('request_id')}")
        print(f"   📋 Arquivo: {last.get('input_filename')}")
else:
    print(f"   ❌ Erro: {response_local.status_code}")

# Resumo final
print(f"\n{'='*60}")
if s3_status == "ok" and len(encontradas) == len(colunas_esperadas):
    print("✅ TESTE PASSOU! Tudo funcionando corretamente")
    print(f"   - API respondendo")
    print(f"   - CSV processado ({linhas_csv} linhas)")
    print(f"   - Todas colunas presentes")
    print(f"   - S3 upload: {s3_status}")
elif s3_status == "not_uploaded":
    print("⚠️  TESTE PARCIAL: API OK mas S3 não configurado")
    print(f"   Configure AWS_REGION, S3_BUCKET, S3_PREFIX no .env")
else:
    print("⚠️  TESTE COM PROBLEMAS")
    if len(encontradas) < len(colunas_esperadas):
        print(f"   - Colunas faltando no retorno")
    if s3_status != "ok":
        print(f"   - S3 status: {s3_status}")
print("="*60)
