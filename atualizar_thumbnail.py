"""
Bloco 3 — Thumbnail Updater
Env: GOOGLE_CREDENTIALS, YOUTUBE_TOKEN_ES_JSON (ou _PT_JSON), CANAL, VIDEO_ID (opcional)
Se VIDEO_ID não for passado, processa todos os uploads dos últimos 7 dias do canal.
"""

import os, sys, json, time, datetime, re, textwrap, random
from zoneinfo import ZoneInfo
from io import BytesIO

from google.oauth2.service_account import Credentials
from google.oauth2.credentials import Credentials as YTCredentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from PIL import Image, ImageDraw, ImageFont

# ==============================================================================
# 1. CONFIG
# ==============================================================================
GOOGLE_JSON   = os.environ.get("GOOGLE_CREDENTIALS")
CANAL         = os.environ.get("CANAL", "ES")
VIDEO_ID_UNICO = os.environ.get("VIDEO_ID", "").strip()
PASTA_TEMP    = "/tmp/thumbnail_b3"
DIAS_RETROATIVOS = 7

os.makedirs(PASTA_TEMP, exist_ok=True)

CONFIGS = {
    'ES': {
        'pasta_imagens': '1FSpmGvSZDleU4gUJePAj4t5h0ZoVSmEo',
        'token_env':     'YOUTUBE_TOKEN_ES_JSON',
        'channel_id':    'UCyPGsztvMnUhDeoI_6H4bsA',
    },
    'PT': {
        'pasta_imagens': '1FSpmGvSZDleU4gUJePAj4t5h0ZoVSmEo',
        'token_env':     'YOUTUBE_TOKEN_PT_JSON',
        'channel_id':    'UClATmmCFTo_UDHgfXPjwyqw',
    },
}

cfg = CONFIGS.get(CANAL)
if not cfg:
    print(f"❌ Canal desconhecido: {CANAL}"); sys.exit(1)

YT_TOKEN_JSON = os.environ.get(cfg['token_env'])
if not YT_TOKEN_JSON:
    print(f"❌ Token {cfg['token_env']} não encontrado."); sys.exit(1)

# ==============================================================================
# 2. AUTH
# ==============================================================================
credenciais_dict = json.loads(GOOGLE_JSON)
creds_drive = Credentials.from_service_account_info(
    credenciais_dict,
    scopes=['https://www.googleapis.com/auth/drive.readonly']
)
drive_service = build('drive', 'v3', credentials=creds_drive)

creds_yt = YTCredentials.from_authorized_user_info(json.loads(YT_TOKEN_JSON.lstrip('﻿')))
if creds_yt.expired and creds_yt.refresh_token:
    creds_yt.refresh(Request())
youtube = build('youtube', 'v3', credentials=creds_yt)

# ==============================================================================
# 3. HELPERS
# ==============================================================================
def listar_imagens_drive(folder_id):
    res, page_token = [], None
    while True:
        for _ in range(3):
            try:
                resp = drive_service.files().list(
                    q=f"'{folder_id}' in parents and trashed=false",
                    spaces='drive', fields='nextPageToken, files(id, name)',
                    pageToken=page_token
                ).execute()
                break
            except Exception as e:
                print(f"[WARN] Drive: {e}"); time.sleep(5)
        else:
            return res
        for f in resp.get('files', []):
            if f['name'].lower().endswith(('.jpg', '.jpeg', '.png')):
                res.append(f)
        page_token = resp.get('nextPageToken')
        if not page_token:
            break
    return res

def baixar_imagem(file_id, destino):
    for _ in range(3):
        try:
            req = drive_service.files().get_media(fileId=file_id)
            with open(destino, 'wb') as f:
                f.write(req.execute())
            return destino
        except Exception as e:
            print(f"[WARN] Download {file_id}: {e}"); time.sleep(5)
    return None

def criar_thumbnail(img_path, titulo, destino):
    try:
        img = Image.open(img_path).convert("RGB").resize((1280, 720), Image.LANCZOS)
        # dark overlay na metade inferior
        overlay = Image.new('RGBA', (1280, 720), (0, 0, 0, 0))
        ImageDraw.Draw(overlay).rectangle([(0, 400), (1280, 720)], fill=(0, 0, 0, 180))
        img = Image.alpha_composite(img.convert('RGBA'), overlay).convert('RGB')
        draw = ImageDraw.Draw(img)
        try:
            font_lg = ImageFont.truetype("Anton.ttf", 62)
            font_sm = ImageFont.truetype("Anton.ttf", 30)
        except:
            font_lg = font_sm = ImageFont.load_default()

        # Divide título em principal e subtítulo pelo "—"
        partes = re.split(r'\s*[—–]\s*', titulo, maxsplit=1)
        principal = partes[0].strip()
        subtitulo = partes[1].strip() if len(partes) > 1 else ''
        # Remove emojis do texto renderizado (evita problemas de codificação no Pillow)
        principal = re.sub(r'[^\x00-\x7FÀ-ÿ\w\s\.\!\?\,\:\;\-\(\)\[\]\/\\&\'\"áéíóúâêîôûãõàèìòùçñü]',
                           '', principal).strip()
        subtitulo = re.sub(r'[^\x00-\x7FÀ-ÿ\w\s\.\!\?\,\:\;\-\(\)\[\]\/\\&\'\"áéíóúâêîôûãõàèìòùçñü]',
                           '', subtitulo).strip()

        # Word-wrap (max 20 chars/linha para Anton 62px)
        linhas = textwrap.wrap(principal, width=20)[:3]

        y = 420
        for i, linha in enumerate(linhas):
            cor = (255, 220, 80) if i == 0 else (235, 235, 235)
            bb = draw.textbbox((0, 0), linha, font=font_lg)
            w = bb[2] - bb[0]; h = bb[3] - bb[1]
            x = (1280 - w) // 2
            draw.text((x + 2, y + 2), linha, font=font_lg, fill=(0, 0, 0, 160))
            draw.text((x, y), linha, font=font_lg, fill=cor)
            y += h + 6

        if subtitulo:
            sub = subtitulo[:50]
            bb2 = draw.textbbox((0, 0), sub, font=font_sm)
            x2 = (1280 - (bb2[2] - bb2[0])) // 2
            y2 = min(y + 10, 682)
            draw.text((x2, y2), sub, font=font_sm, fill=(180, 180, 180))

        img.save(destino, 'JPEG', quality=92)
        return destino
    except Exception as e:
        print(f"[WARN] Thumbnail: {e}")
        return None

def set_thumbnail(video_id, thumb_path):
    for _ in range(3):
        try:
            youtube.thumbnails().set(
                videoId=video_id,
                media_body=MediaFileUpload(thumb_path, mimetype='image/jpeg')
            ).execute()
            return True
        except Exception as e:
            print(f"  ⚠️  thumbnails.set: {e}"); time.sleep(10)
    return False

def obter_videos_recentes(channel_id, dias=7):
    uploads_pid = 'UU' + channel_id[2:]
    corte = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=dias)
    video_ids, page_token = [], None
    while True:
        resp = youtube.playlistItems().list(
            part='contentDetails', playlistId=uploads_pid,
            maxResults=50, pageToken=page_token
        ).execute()
        for item in resp.get('items', []):
            cd = item['contentDetails']
            pub = cd.get('videoPublishedAt', '')
            if pub:
                try:
                    dt = datetime.datetime.fromisoformat(pub.replace('Z', '+00:00'))
                    if dt >= corte:
                        video_ids.append(cd['videoId'])
                    else:
                        return video_ids  # lista é ordenada DESC por data
                except:
                    video_ids.append(cd['videoId'])
        page_token = resp.get('nextPageToken')
        if not page_token:
            break
    return video_ids

# ==============================================================================
# 4. MAIN
# ==============================================================================
def main():
    print(f"\n🖼️  Bloco 3 — Thumbnail Updater — Canal {CANAL}")

    # Busca imagens de Maria no Drive
    img_files = listar_imagens_drive(cfg['pasta_imagens'])
    if not img_files:
        print("❌ Sem imagens no Drive."); sys.exit(1)
    print(f"  → {len(img_files)} imagens disponíveis")

    # Baixa 5 imagens para sortear
    sample = random.sample(img_files, min(5, len(img_files)))
    imgs_locais = []
    for f in sample:
        ext = os.path.splitext(f['name'])[1].lower() or '.jpg'
        dest = os.path.join(PASTA_TEMP, f"img_{f['id']}{ext}")
        if not os.path.exists(dest):
            baixar_imagem(f['id'], dest)
        if os.path.exists(dest):
            imgs_locais.append(dest)
    if not imgs_locais:
        print("❌ Falha ao baixar imagens."); sys.exit(1)

    # Determina quais vídeos processar
    if VIDEO_ID_UNICO:
        video_ids = [VIDEO_ID_UNICO]
        print(f"  → Modo unitário: {VIDEO_ID_UNICO}")
    else:
        video_ids = obter_videos_recentes(cfg['channel_id'], dias=DIAS_RETROATIVOS)
        print(f"  → {len(video_ids)} vídeos recentes (últimos {DIAS_RETROATIVOS} dias)")

    if not video_ids:
        print("  ℹ️  Nenhum vídeo para processar."); return

    # Busca detalhes em lote
    detalhes = {}
    for i in range(0, len(video_ids), 50):
        batch = video_ids[i:i+50]
        resp = youtube.videos().list(part='snippet,status', id=','.join(batch)).execute()
        for item in resp.get('items', []):
            detalhes[item['id']] = item

    processados = 0
    for video_id in video_ids:
        item = detalhes.get(video_id)
        if not item:
            continue
        titulo = item['snippet'].get('title', '')
        status = item['status'].get('privacyStatus', '')
        print(f"\n  📹 {video_id} | {titulo[:55]} | {status}")

        img_path = random.choice(imgs_locais)
        thumb_path = os.path.join(PASTA_TEMP, f"thumb_{video_id}.jpg")
        thumb = criar_thumbnail(img_path, titulo, thumb_path)
        if not thumb:
            print("  ⚠️  Thumbnail não gerado; pulando.")
            continue

        ok = set_thumbnail(video_id, thumb_path)
        if ok:
            print(f"  ✅ Thumbnail aplicado")
            processados += 1
        try:
            os.remove(thumb_path)
        except:
            pass
        time.sleep(2)

    print(f"\n🖼️  Concluído — {processados} thumbnails aplicados.")

if __name__ == "__main__":
    main()
