#!/usr/bin/env python3
"""
gerar_token_pt.py — Gera youtube_token.json para o Canal PT.

Execute no VPS via VNC/terminal:
    pip3 install google-auth-oauthlib
    python3 /root/gerar_token_pt.py

O script mostra uma URL. Abra no navegador, autorize com a conta
do Canal PT (canalinteligenciadivina@gmail.com), copie o código
e cole aqui. O token será salvo em /root/ao_vivo_pt/youtube_token.json
"""

import json
from pathlib import Path

TOKEN_ES   = Path("/root/ao_vivo_es/youtube_token.json")
TOKEN_PT   = Path("/root/ao_vivo_pt/youtube_token.json")
TOKEN_PT.parent.mkdir(parents=True, exist_ok=True)

# Lê client_id e client_secret do token ES existente (mesma conta Google)
with open(TOKEN_ES) as f:
    es = json.load(f)

client_config = {
    "installed": {
        "client_id":     es["client_id"],
        "client_secret": es["client_secret"],
        "auth_uri":      "https://accounts.google.com/o/oauth2/auth",
        "token_uri":     "https://oauth2.googleapis.com/token",
        "redirect_uris": ["urn:ietf:wg:oauth:2.0:oob", "http://localhost"],
    }
}

SCOPES = [
    "https://www.googleapis.com/auth/youtube",
    "https://www.googleapis.com/auth/youtube.force-ssl",
    "https://www.googleapis.com/auth/youtube.upload",
]

from google_auth_oauthlib.flow import InstalledAppFlow

flow = InstalledAppFlow.from_client_config(client_config, SCOPES)

print("\n" + "="*60)
print("GERAÇÃO DO TOKEN PT — Canal Nossa Senhora Aparecida")
print("="*60)
print("\n1. Copie a URL abaixo e abra no navegador")
print("2. Faça login com canalinteligenciadivina@gmail.com")
print("   ** Escolha o Canal PT (Português) quando aparecer **")
print("3. Autorize o acesso e copie o código mostrado")
print("4. Cole o código aqui e pressione Enter\n")

creds = flow.run_console()

token_data = {
    "token":         creds.token,
    "refresh_token": creds.refresh_token,
    "token_uri":     creds.token_uri,
    "client_id":     creds.client_id,
    "client_secret": creds.client_secret,
    "scopes":        list(creds.scopes),
}

with open(TOKEN_PT, "w") as f:
    json.dump(token_data, f, indent=2)

print(f"\n✅  Token PT salvo em: {TOKEN_PT}")
print("\nPróximo passo: adicionar como secret YOUTUBE_TOKEN_PT no GitHub.")
print("Execute: cat /root/ao_vivo_pt/youtube_token.json | base64 -w0")
print("Cole o resultado como secret YOUTUBE_TOKEN_PT no repo usina-oracoes.")
