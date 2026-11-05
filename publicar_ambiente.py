"""
Bloco 1 — Publicador de Vídeos Ambiente
Lê abas ES_AMBIENTE e PT_AMBIENTE na planilha central.
Para vídeos com status='unlisted' e publish_at <= agora,
muda privacyStatus para 'public' via YouTube API.
"""

import os, json, time, datetime
from zoneinfo import ZoneInfo

from google.oauth2.service_account import Credentials
from google.oauth2.credentials import Credentials as YTCredentials
from google.auth.transport.requests import Request
import gspread
from googleapiclient.discovery import build

# ==============================================================================
# 1. AUTH
# ==============================================================================
GOOGLE_JSON       = os.environ.get("GOOGLE_CREDENTIALS")
YT_TOKEN_ES_JSON  = os.environ.get("YOUTUBE_TOKEN_ES_JSON")
YT_TOKEN_PT_JSON  = os.environ.get("YOUTUBE_TOKEN_PT_JSON")
SHEET_ID          = "1KgIjWrLUVlllhlZB1R9fkHGxxZlLsax1aOVGZrYwgnU"

creds_sheets = Credentials.from_service_account_info(
    json.loads(GOOGLE_JSON),
    scopes=['https://www.googleapis.com/auth/spreadsheets']
)
gc = gspread.authorize(creds_sheets)

def build_youtube(token_json_str):
    creds = YTCredentials.from_authorized_user_info(json.loads(token_json_str.lstrip('﻿')))
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
    return build('youtube', 'v3', credentials=creds)

# ==============================================================================
# 2. PUBLICAR VÍDEOS DE UMA ABA
# ==============================================================================
def publicar_aba(aba_nome, youtube):
    agora = datetime.datetime.now(ZoneInfo("America/Sao_Paulo"))
    print(f"\n📋 Verificando aba: {aba_nome} — {agora.strftime('%Y-%m-%d %H:%M BRT')}")

    try:
        sheet = gc.open_by_key(SHEET_ID)
        ws = sheet.worksheet(aba_nome)
    except gspread.WorksheetNotFound:
        print(f"  ⚠️  Aba {aba_nome} não encontrada — pulando.")
        return

    registros = ws.get_all_records()
    if not registros:
        print("  → Nenhum registro ainda.")
        return

    publicados = 0
    for i, row in enumerate(registros, start=2):  # linha 1 = cabeçalho
        status = str(row.get('status', '')).strip()
        publish_at_str = str(row.get('publish_at', '')).strip()
        video_id = str(row.get('video_id', '')).strip()

        if status != 'unlisted' or not video_id or not publish_at_str:
            continue

        try:
            publish_at = datetime.datetime.strptime(
                publish_at_str, '%Y-%m-%d %H:%M'
            ).replace(tzinfo=ZoneInfo("America/Sao_Paulo"))
        except ValueError:
            print(f"  ⚠️  Linha {i}: data inválida '{publish_at_str}' — pulando.")
            continue

        if agora < publish_at:
            restante = publish_at - agora
            h = int(restante.total_seconds() // 3600)
            print(f"  ⏳ {video_id} — publica em {h}h (às {publish_at.strftime('%d/%m %H:%M')})")
            continue

        # Publicar
        titulo = str(row.get('titulo', video_id))
        print(f"  🌐 Publicando: {titulo[:60]}… ({video_id})")
        for tentativa in range(3):
            try:
                youtube.videos().update(
                    part="status",
                    body={
                        "id": video_id,
                        "status": {"privacyStatus": "public"}
                    }
                ).execute()
                # Atualizar planilha
                col_status = list(registros[0].keys()).index('status') + 1
                ws.update_cell(i, col_status, 'public')
                publicados += 1
                print(f"    ✅ Publicado — planilha atualizada.")
                break
            except Exception as e:
                print(f"    ⚠️  Tentativa {tentativa+1}: {e}")
                if tentativa < 2:
                    time.sleep(10)

    print(f"  → Total publicados: {publicados}")

# ==============================================================================
# 3. MAIN
# ==============================================================================
def main():
    print("🌙 Publicador de Vídeos Ambiente\n")

    if YT_TOKEN_ES_JSON:
        yt_es = build_youtube(YT_TOKEN_ES_JSON)
        publicar_aba('ES_AMBIENTE', yt_es)
    else:
        print("⚠️  YOUTUBE_TOKEN_ES_JSON não definido — ES pulado.")

    if YT_TOKEN_PT_JSON:
        yt_pt = build_youtube(YT_TOKEN_PT_JSON)
        publicar_aba('PT_AMBIENTE', yt_pt)
    else:
        print("⚠️  YOUTUBE_TOKEN_PT_JSON não definido — PT pulado.")

    print("\n✅ Publicador concluído.")

if __name__ == "__main__":
    main()
