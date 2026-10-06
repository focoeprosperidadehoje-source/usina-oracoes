"""
Gera o OAuth token para o comunidade.py do canal ES.
Use quando o GCP project separado para comunidade ES estiver criado.

Como usar:
  1. Baixe o client_secret JSON do GCP Console (ver instruções abaixo)
  2. Salve como 'client_secret_comunidade_es.json' na mesma pasta deste script
  3. python gerar_token_comunidade_es.py
  4. Copie o conteúdo de 'token_comunidade_es.json' para o secret YOUTUBE_TOKEN_ES_COMUNIDADE no GitHub

Instruções para criar o OAuth client no GCP (5 min):
  https://console.cloud.google.com/apis/credentials
  → Create Credentials → OAuth client ID → Desktop app → nome "comunidade-es"
  → Download JSON → salvar como client_secret_comunidade_es.json
"""
import json, os
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    "https://www.googleapis.com/auth/youtube",
    "https://www.googleapis.com/auth/youtube.force-ssl",
]

CLIENT_SECRET_FILE = os.path.join(os.path.dirname(__file__), "client_secret_comunidade_es.json")
OUTPUT_FILE = os.path.join(os.path.dirname(__file__), "token_comunidade_es.json")

if not os.path.exists(CLIENT_SECRET_FILE):
    print(f"❌ Arquivo não encontrado: {CLIENT_SECRET_FILE}")
    print("   Baixe o client_secret JSON no GCP Console e salve com esse nome.")
    exit(1)

print("Abrindo navegador para autorização...")
flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRET_FILE, scopes=SCOPES)
creds = flow.run_local_server(port=0)

token_data = {
    "token":         creds.token,
    "refresh_token": creds.refresh_token,
    "token_uri":     creds.token_uri,
    "client_id":     creds.client_id,
    "client_secret": creds.client_secret,
    "scopes":        list(creds.scopes),
}

with open(OUTPUT_FILE, "w") as f:
    json.dump(token_data, f, indent=2)

print(f"\n✅ Token salvo em: {OUTPUT_FILE}")
print("\nPróximos passos:")
print("  1. Abra o arquivo acima e copie TODO o conteúdo (Ctrl+A, Ctrl+C)")
print("  2. GitHub → usina-oracoes → Settings → Secrets → Actions")
print("  3. New secret: nome = YOUTUBE_TOKEN_ES_COMUNIDADE, valor = conteúdo copiado")
print("  4. Avise o Claude Code para atualizar comunidade.py a usar o novo secret")
