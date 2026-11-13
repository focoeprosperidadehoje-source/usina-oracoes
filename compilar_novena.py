"""
Bloco 2 — Compilador de Novenas
Detecta séries de novena completas (9 dias públicos) no canal ES,
baixa os vídeos com yt-dlp, concatena sem re-encode e faz upload
como unlisted. Publicação via publicar_ambiente.py (cron 23:20 BRT).
"""

import os, sys, json, re, time, datetime, subprocess
from collections import defaultdict
from zoneinfo import ZoneInfo

from google.oauth2.service_account import Credentials
from google.oauth2.credentials import Credentials as YTCredentials
from google.auth.transport.requests import Request
import gspread
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# ==============================================================================
# 1. CONFIG
# ==============================================================================
GOOGLE_JSON    = os.environ.get("GOOGLE_CREDENTIALS")
YT_TOKEN_JSON  = os.environ.get("YOUTUBE_TOKEN_JSON")
CANAL          = os.environ.get("CANAL", "ES")
SHEET_ID       = "1KgIjWrLUVlllhlZB1R9fkHGxxZlLsax1aOVGZrYwgnU"
PASTA_TEMP     = "/tmp/novena_comp"
PUBLISH_DELAY_BASE_H = 48  # primeira compilação: now+48h; demais: +24h cada

CONFIGS = {
    "ES": {
        "channel_id": "UCyPGsztvMnUhDeoI_6H4bsA",
        "aba_sheet": "ES_NOVENAS_COMPILADAS",
        "playlist_nome": "Novenas Completas — La Morenita",
        "idioma": "es-419",
        "descricao_tpl": (
            "🙏 {serie} — Novena Completa de 9 Días\n\n"
            "Reúne los 9 días completos para que puedas rezar sin interrupciones.\n\n"
            "▶ Oración 24H en Vivo → https://youtube.com/channel/UCyPGsztvMnUhDeoI_6H4bsA/live\n\n"
            "#Novena #NuestraSeñora #OraciónCatólica #Guadalupe #Fe #Milagros"
        ),
        "titulo_tpl": "Novena Completa de 9 Días — {serie} 🙏",
        "tags": ["novena completa", "9 días", "nuestra señora", "oración", "guadalupe",
                 "fe", "milagros", "rosario", "católico"],
    },
    "PT": {
        "channel_id": "UClATmmCFTo_UDHgfXPjwyqw",
        "aba_sheet": "PT_NOVENAS_COMPILADAS",
        "playlist_nome": "Novenas Completas — Nossa Senhora",
        "idioma": "pt-BR",
        "descricao_tpl": (
            "🙏 {serie} — Novena Completa de 9 Dias\n\n"
            "Reúne os 9 dias completos para você rezar sem interrupções.\n\n"
            "▶ Oração 24H ao Vivo → https://youtube.com/channel/UClATmmCFTo_UDHgfXPjwyqw/live\n\n"
            "#Novena #NossaSenhora #OraçãoCatólica #Aparecida #Fé #Milagres"
        ),
        "titulo_tpl": "Novena Completa de 9 Dias — {serie} 🙏",
        "tags": ["novena completa", "9 dias", "nossa senhora", "oração", "aparecida",
                 "fé", "milagres", "rosário", "católico"],
    },
}

os.makedirs(PASTA_TEMP, exist_ok=True)
cfg = CONFIGS.get(CANAL)
if not cfg:
    print(f"❌ Canal desconhecido: {CANAL}"); sys.exit(1)

# ==============================================================================
# 2. AUTH
# ==============================================================================
creds_sheets = Credentials.from_service_account_info(
    json.loads(GOOGLE_JSON),
    scopes=['https://www.googleapis.com/auth/spreadsheets']
)
gc = gspread.authorize(creds_sheets)

creds_yt = YTCredentials.from_authorized_user_info(json.loads(YT_TOKEN_JSON.lstrip('﻿')))
if creds_yt.expired and creds_yt.refresh_token:
    creds_yt.refresh(Request())
youtube = build('youtube', 'v3', credentials=creds_yt)

# ==============================================================================
# 3. SHEET HELPER
# ==============================================================================
HEADERS_COMP = ['canal', 'video_id', 'serie', 'titulo', 'dias',
                 'data_geracao', 'publish_at', 'status']

def obter_aba_compiladas():
    sheet = gc.open_by_key(SHEET_ID)
    try:
        return sheet.worksheet(cfg['aba_sheet'])
    except gspread.WorksheetNotFound:
        ws = sheet.add_worksheet(title=cfg['aba_sheet'], rows=500, cols=10)
        ws.append_row(HEADERS_COMP)
        time.sleep(2)
        return ws

def series_ja_compiladas(ws):
    registros = ws.get_all_records()
    return {str(r.get('serie', '')).strip() for r in registros if r.get('serie')}

# ==============================================================================
# 4. DESCOBRIR VÍDEOS DE NOVENA NO CANAL
# ==============================================================================
# ES: "Día N" / "Dia N"  |  PT: "Nº Dia" / "N° Dia"
PADRAO_DIA_ES = re.compile(r'\bD[ií]a\s+(\d{1,2})\b', re.IGNORECASE)
PADRAO_DIA_PT = re.compile(r'\b(\d{1,2})[°º]\s*[Dd]ia\b', re.IGNORECASE)

def extrair_dia(titulo):
    m = PADRAO_DIA_ES.search(titulo)
    if m:
        return int(m.group(1)), 'es'
    m = PADRAO_DIA_PT.search(titulo)
    if m:
        return int(m.group(1)), 'pt'
    return None, None

def calcular_serie(titulo, fmt):
    if fmt == 'es':
        s = PADRAO_DIA_ES.sub('', titulo)
    else:
        s = PADRAO_DIA_PT.sub('', titulo)
    s = re.sub(r'\s*🙏.*', '', s)
    s = re.sub(r'\s*[-—–|]+\s*$', '', s).strip()
    return re.sub(r'\s{2,}', ' ', s)

def listar_videos_canal():
    """Retorna lista de {video_id, titulo, published_at} para todos os vídeos públicos."""
    from googleapiclient.errors import HttpError
    uploads_id = "UU" + cfg['channel_id'][2:]  # UC... → UU...
    videos = []
    page_token = None
    print("  📺 Buscando vídeos do canal (uploads playlist)...")
    while True:
        try:
            resp = youtube.playlistItems().list(
                part="snippet",
                playlistId=uploads_id,
                maxResults=50,
                pageToken=page_token
            ).execute()
        except HttpError as e:
            if e.resp.status == 403 and "quotaExceeded" in str(e):
                print(f"[WARN] quotaExceeded ao listar videos — cota esgotada. Nada compilado.")
                return []
            raise
        for item in resp.get("items", []):
            sn = item["snippet"]
            vid = sn["resourceId"]["videoId"]
            videos.append({
                "video_id": vid,
                "titulo": sn.get("title", ""),
                "published_at": sn.get("publishedAt", ""),
            })
        page_token = resp.get("nextPageToken")
        if not page_token:
            break
        time.sleep(0.5)
    print(f"  → {len(videos)} vídeos encontrados")
    return videos

def agrupar_novenas(videos):
    """Agrupa vídeos de novena por série, retornando grupos completos (9 dias)."""
    grupos = defaultdict(dict)
    for v in videos:
        dia, fmt = extrair_dia(v['titulo'])
        if dia is None or dia < 1 or dia > 9:
            continue
        serie = calcular_serie(v['titulo'], fmt)
        if not serie:
            continue
        # Em caso de duplicata (re-gravação), fica com o mais recente
        if dia not in grupos[serie] or v['published_at'] > grupos[serie][dia]['published_at']:
            grupos[serie][dia] = v

    completas = []
    for serie, dias in grupos.items():
        if all(d in dias for d in range(1, 10)):
            completas.append({
                'serie': serie,
                'videos': [dias[d] for d in range(1, 10)],
            })
    return completas

# ==============================================================================
# 5. GARANTIR PLAYLIST DE COMPILAÇÕES
# ==============================================================================
def obter_ou_criar_playlist():
    nome = cfg['playlist_nome']
    page_token = None
    while True:
        resp = youtube.playlists().list(
            part="snippet", mine=True, maxResults=50, pageToken=page_token
        ).execute()
        for p in resp.get("items", []):
            if p["snippet"]["title"] == nome:
                pid = p["id"]
                print(f"  📂 Playlist encontrada: {nome} → {pid}")
                return pid
        page_token = resp.get("nextPageToken")
        if not page_token:
            break

    # Criar
    r = youtube.playlists().insert(
        part="snippet,status",
        body={
            "snippet": {"title": nome, "defaultLanguage": cfg['idioma']},
            "status": {"privacyStatus": "public"},
        }
    ).execute()
    pid = r["id"]
    print(f"  📂 Playlist CRIADA: {nome} → {pid}")
    return pid

# ==============================================================================
# 6. BAIXAR + COMPILAR
# ==============================================================================
def baixar_video(video_id, destino_dir):
    url = f"https://www.youtube.com/watch?v={video_id}"
    saida = os.path.join(destino_dir, f"{video_id}.mp4")
    if os.path.exists(saida):
        return saida
    cmd = [
        "yt-dlp",
        "-f", "bestvideo[ext=mp4][height<=720]+bestaudio[ext=m4a]/best[ext=mp4][height<=720]/best[ext=mp4]",
        "--merge-output-format", "mp4",
        "--sleep-interval", "3",
        "--max-sleep-interval", "7",
        "-o", saida,
        url,
    ]
    for tentativa in range(3):
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode == 0 and os.path.exists(saida):
            mb = os.path.getsize(saida) / (1024 * 1024)
            print(f"    ✅ {video_id} baixado ({mb:.0f} MB)")
            return saida
        print(f"    ⚠️  Tentativa {tentativa+1}: {r.stderr[-200:]}")
        time.sleep(10)
    return None

def compilar_videos(video_paths, saida):
    concat_txt = os.path.join(PASTA_TEMP, "concat_novena.txt")
    with open(concat_txt, "w") as f:
        for p in video_paths:
            f.write(f"file '{p}'\n")
    r = subprocess.run([
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0", "-i", concat_txt,
        "-c", "copy", saida
    ], capture_output=True, text=True)
    if r.returncode != 0:
        print(f"  ❌ Concat erro: {r.stderr[-500:]}")
        return None
    mb = os.path.getsize(saida) / (1024 * 1024)
    print(f"  ✅ Compilação: {mb:.0f} MB")
    return saida

# ==============================================================================
# 7. UPLOAD
# ==============================================================================
def upload_compilacao(video_path, titulo, descricao, tags, idioma):
    body = {
        "snippet": {
            "title": titulo[:100],
            "description": descricao,
            "tags": tags[:15],
            "categoryId": "22",
            "defaultLanguage": idioma,
            "defaultAudioLanguage": idioma,
        },
        "status": {
            "privacyStatus": "unlisted",
            "selfDeclaredMadeForKids": False,
            "selfDeclaredMadeWithAlteredContent": True,
        }
    }
    for tentativa in range(3):
        try:
            resp = youtube.videos().insert(
                part="snippet,status",
                body=body,
                media_body=MediaFileUpload(video_path, chunksize=-1, resumable=True, mimetype="video/mp4")
            ).execute()
            vid = resp.get("id")
            print(f"  ✅ Upload OK! ID: {vid}")
            return vid
        except Exception as e:
            print(f"  ❌ Tentativa {tentativa+1}: {e}")
            time.sleep(15)
    return None

def adicionar_a_playlist(video_id, playlist_id):
    try:
        youtube.playlistItems().insert(
            part="snippet",
            body={"snippet": {
                "playlistId": playlist_id,
                "resourceId": {"kind": "youtube#video", "videoId": video_id}
            }}
        ).execute()
        print(f"  📂 Adicionado à playlist.")
    except Exception as e:
        print(f"  ⚠️  Playlist insert: {e}")

# ==============================================================================
# 8. MAIN
# ==============================================================================
def main():
    print(f"\n📿 Bloco 2 — Compilador de Novenas — Canal {CANAL}\n")

    aba = obter_aba_compiladas()
    ja_compiladas = series_ja_compiladas(aba)
    print(f"Séries já compiladas: {len(ja_compiladas)}")

    todos_videos = listar_videos_canal()
    grupos_completos = agrupar_novenas(todos_videos)
    print(f"Séries com 9 dias completos encontradas: {len(grupos_completos)}")

    pendentes = [g for g in grupos_completos if g['serie'] not in ja_compiladas]
    print(f"Séries pendentes de compilação: {len(pendentes)}")

    if not pendentes:
        print("✅ Nada a compilar.")
        return

    # Ordenar por data do Día 1 (mais antigas primeiro)
    pendentes.sort(key=lambda g: g['videos'][0]['published_at'])

    playlist_id = obter_ou_criar_playlist()
    agora = datetime.datetime.now(ZoneInfo("America/Sao_Paulo"))

    for i, grupo in enumerate(pendentes):
        serie = grupo['serie']
        print(f"\n{'='*60}")
        print(f"📿 Série {i+1}/{len(pendentes)}: {serie}")

        # Escalonamento: 48h, 72h, 96h... entre compilações
        publish_at = agora + datetime.timedelta(hours=PUBLISH_DELAY_BASE_H + i * 24)

        # Baixar os 9 vídeos
        pasta_serie = os.path.join(PASTA_TEMP, f"serie_{i}")
        os.makedirs(pasta_serie, exist_ok=True)
        paths = []
        falhou = False
        for v in grupo['videos']:
            p = baixar_video(v['video_id'], pasta_serie)
            if not p:
                print(f"  ❌ Falha ao baixar {v['video_id']} — série pulada.")
                falhou = True
                break
            paths.append(p)

        if falhou:
            continue

        # Compilar
        saida = os.path.join(PASTA_TEMP, f"novena_compilada_{i}.mp4")
        if os.path.exists(saida):
            os.remove(saida)
        video_comp = compilar_videos(paths, saida)
        if not video_comp:
            continue

        # Upload
        titulo = cfg['titulo_tpl'].format(serie=serie)
        descricao = cfg['descricao_tpl'].format(serie=serie)
        video_id = upload_compilacao(video_comp, titulo, descricao, cfg['tags'], cfg['idioma'])
        if not video_id:
            continue

        # Adicionar à playlist
        adicionar_a_playlist(video_id, playlist_id)

        # Registrar na planilha
        try:
            dias_str = ",".join(v['video_id'] for v in grupo['videos'])
            aba.append_row([
                CANAL, video_id, serie, titulo, dias_str,
                agora.strftime('%Y-%m-%d %H:%M'),
                publish_at.strftime('%Y-%m-%d %H:%M'),
                'unlisted'
            ])
            print(f"  📋 Registrado em {cfg['aba_sheet']} → publica {publish_at.strftime('%d/%m %H:%M')} BRT")
        except Exception as e:
            print(f"  ⚠️  Planilha: {e}")

        # Limpar arquivos locais
        for p in paths:
            try: os.remove(p)
            except: pass
        try: os.remove(video_comp)
        except: pass

    print(f"\n📿 Compilador concluído — {len(pendentes)} séries processadas.")

if __name__ == "__main__":
    main()
