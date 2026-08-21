#!/usr/bin/env python3
"""
gerar_token_pt.py — Gera youtube_token.json para o Canal PT (live stream).
Executar uma única vez no VPS após o setup inicial.

Uso:
  cd /root/ao_vivo_pt
  python3 gerar_token_pt.py

O script mostra uma URL — abra no browser, autorize com
canalinteligenciadivina@gmail.com escolhendo o Canal PT,
cole o código de volta aqui. O token é salvo automaticamente.
"""

import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv("/root/ao_vivo_pt/.env")

CLIENT_ID     = os.environ.get("YT_CLIENT_ID", "")
CLIENT_SECRET = os.environ.get("YT_CLIENT_SECRET", "")
SAVE_PATH     = Path("/root/ao_vivo_pt/youtube_token.json")
SCOPES        = ["https://www.googleapis.com/auth/youtube"]

if not CLIENT_ID or not CLIENT_SECRET:
    print("ERRO: YT_CLIENT_ID ou YT_CLIENT_SECRET ausentes no .env")
    print("O setup_vps_pt_inicial.yml deve ter preenchido estas variáveis.")
    sys.exit(1)

try:
    from google_auth_oauthlib.flow import InstalledAppFlow
except ImportError:
    print("Instalando google-auth-oauthlib...")
    import subprocess
    subprocess.run([sys.executable, "-m", "pip", "install", "-q", "google-auth-oauthlib"], check=True)
    from google_auth_oauthlib.flow import InstalledAppFlow

client_config = {
    "installed": {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "redirect_uris": ["urn:ietf:wg:oauth:2.0:oob", "http://localhost"],
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
    }
}

print("=" * 60)
print("Gerador de Token YouTube — Canal PT")
print("=" * 60)
print()
print("1. Copie a URL abaixo e abra no seu navegador")
print("2. Faça login com canalinteligenciadivina@gmail.com")
print("3. Escolha o Canal PT quando perguntado")
print("4. Autorize e copie o código exibido")
print("5. Cole o código aqui e pressione Enter")
print()

flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
creds = flow.run_console()

SAVE_PATH.write_text(creds.to_json())
print()
print(f"✅ Token salvo em {SAVE_PATH}")
print()
print("Próximo passo — iniciar a live PT:")
print("  systemctl start ao_vivo_pt")
print("  systemctl status ao_vivo_pt")
