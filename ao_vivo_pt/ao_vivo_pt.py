#!/usr/bin/env python3
"""
ao_vivo_pt.py — Live 24/7 Canal PT — Arquitetura Pivot
Voz: pt-BR-FranciscaNeural (Nossa Senhora Aparecida)

Threads:
  TRANSMISSOR — ciclos 12h, RTMP horizontal, rotação de blocos base
  SUPLICAS    — segmento 2-3min de intercessão personalizada a cada bloco
  MONITOR     — saúde do disco e alertas de estoque mínimo
  ASSEMBLER   — combina audio_*.mp3 (GitHub Actions) + videos_base/

Blocos base (~20min H) chegam via rsync do GitHub Actions 3×/dia.
VPS não encoda blocos longos — só transmite + gera segmentos curtos de súplicas.
"""

import os
import json
import time
import random
import logging
import threading
import subprocess
import asyncio
import re
import tempfile
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path
from io import BytesIO

import pytz
from dotenv import load_dotenv
from google import genai
from google.oauth2.service_account import Credentials as SACredentials
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials as OAuthCredentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaFileUpload
import edge_tts

load_dotenv()

try:
    from PIL import Image, ImageDraw, ImageFont
    _PIL_OK = True
except ImportError:
    _PIL_OK = False


# ═══════════════════════════════════════════════════════════════════════
# LOGGING
# ═══════════════════════════════════════════════════════════════════════

LOG_FILE = Path("/root/ao_vivo_pt/ao_vivo.log")
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(threadName)s — %(message)s",
    handlers=[
        logging.FileHandler(str(LOG_FILE)),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger("ao_vivo_pt")


# ═══════════════════════════════════════════════════════════════════════
# CONSTANTES E CONFIGURAÇÃO
# ═══════════════════════════════════════════════════════════════════════

CANAL_ID       = os.environ.get("CANAL_ID_PT", "UClATmmCFTo_UDHgfXPjwyqw")
PLAYLIST_LIVES = os.environ.get("PLAYLIST_ID_LIVES_PT", "")
FUSO           = pytz.timezone(os.environ.get("FUSO_PT", "America/Sao_Paulo"))

STREAM_KEY_H   = os.environ.get("STREAM_KEY_H_PT", "")
STREAM_KEY_V   = ""   # Live PT começa apenas horizontal
INGEST_URL     = os.environ.get("INGEST_URL", "rtmp://a.rtmp.youtube.com/live2")
BROADCAST_ID_H = os.environ.get("BROADCAST_ID_H_PT", "")
MODO_PERMANENTE = bool(STREAM_KEY_H)

BASE_DIR        = Path("/root/ao_vivo_pt")
DIR_BLOCOS      = BASE_DIR / "blocos"
DIR_SUPLICAS    = BASE_DIR / "suplicas"
DIR_INSUMOS_H   = BASE_DIR / "insumos_h"   # imagens Aparecida 16:9
DIR_INSUMOS_V   = BASE_DIR / "insumos_v"   # fallback
DIR_MUSICAS_M   = BASE_DIR / "musicas" / "manha"
DIR_MUSICAS_N   = BASE_DIR / "musicas" / "noite"
DIR_VIDEOS_BASE = BASE_DIR / "videos_base"  # slides Aparecida sem som (10min cada)

PLAYLIST_H_FILE = BASE_DIR / "playlist_h.txt"
YT_TOKEN_FILE   = BASE_DIR / "youtube_token.json"
GCP_CREDS_FILE  = BASE_DIR / "google_credentials_pt.json"

# IDs Google Drive — assets para súplicas no VPS
DRIVE_INSUMOS_H_ID = os.environ.get("DRIVE_APARECIDA_H_ID", "1I_KLQUiPQrpFGQ2EibtlqtrvHJ0DK9LC")
DRIVE_MUSICAS_M_ID = os.environ.get("DRIVE_MUSICAS_M_ID_PT", "")
DRIVE_MUSICAS_N_ID = os.environ.get("DRIVE_MUSICAS_N_ID_PT", "")

# Timing
DURACAO_BLOCO_SEG    = 20 * 60
DURACAO_SUPLICA_SEG  = 160
SUPLICA_GERAR_OFFSET = 22 * 60
ROLLING_INICIAIS     = 50
ROLLING_ANTECIPACAO  = 1500
SUPLICA_INTERVAL     = 30 * 60
SUPLICA_MAX_READY    = 8              # máx súplicas prontas (cap de CPU)
ASSEMBLER_BLOCOS_MAX = 8             # máx blocos H prontos — assembler dorme acima disso
DURACAO_CICLO_SEG    = 12 * 3600     # 12h por broadcast (2×/dia = 2 notificações + 1 slot vídeo longo)
BLOCOS_MINIMOS       = 1

# TTS e Gemini
VOZ          = "pt-BR-ThalitaMultilingualNeural"
VOZ_RATE     = "-30%"
VOZ_PITCH    = "-8Hz"
MODELOS_LIVE = ["gemini-3.5-flash-lite", "gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash"]

CHAVES_CONTEUDO = [c for c in [
    os.environ.get("GEMINI_KEY_LIVE_CONTENT_1_PT", ""),
    os.environ.get("GEMINI_KEY_LIVE_CONTENT_2_PT", ""),
] if c]

CHAVES_CHAT = [c for c in [
    os.environ.get("GEMINI_KEY_LIVE_CHAT_1_PT", ""),
    os.environ.get("GEMINI_KEY_LIVE_CHAT_2_PT", ""),
    os.environ.get("GEMINI_KEY_LIVE_CHAT_3_PT", ""),
] if c]

PILARES = {
    0: "Guerra Espiritual e Proteção Divina",
    1: "Libertação de Vícios e Ataduras",
    2: "Restauração Familiar e Matrimonial",
    3: "Providência Divina e Portas Abertas",
    4: "Misericórdia Divina e Cura Física",
    5: "O Manto Sagrado de Aparecida",
    6: "Milagres e Gratidão",
}

RTMP_BASE = "rtmp://a.rtmp.youtube.com/live2"
FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_ALT  = "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"

_THUMB_LINHAS = {
    "manha": ["FORÇA E", "RESTAURAÇÃO", "COM NOSSA SENHORA"],
    "tarde":  ["PROTEÇÃO", "DIVINA", "COM NOSSA SENHORA"],
    "noite":  ["DESCANSO", "E CURA", "COM NOSSA SENHORA"],
}

TITULOS_LIVE = {
    0: "🔴 Nossa Senhora Te Protege AGORA de Todo Ataque — Oração Poderosa AO VIVO",
    1: "🔴 Nossa Senhora Rompe HOJE Essa Atadura — Libertação Poderosa AO VIVO",
    2: "🔴 Nossa Senhora Restaura Sua Família HOJE — Milagre de Reconciliação AO VIVO",
    3: "🔴 Nossa Senhora Abre HOJE Portas Fechadas — Milagre de Providência AO VIVO",
    4: "🔴 Nossa Senhora Cura Seu Corpo AGORA — Milagre de Cura AO VIVO",
    5: "🔴 O Manto de Aparecida Te Cobre AGORA — Proteção e Milagres AO VIVO",
    6: "🔴 Nossa Senhora Tem um Milagre para Você HOJE — Receba AO VIVO",
}

DESCRICAO_LIVE = (
    "🙏 Transmissão contínua de oração com Nossa Senhora Aparecida.\n\n"
    "Deixe seu pedido nos comentários — sua Mãe do Céu está ouvindo você.\n\n"
    "💝 Apoie esta missão de oração contínua:\n"
    "👉 https://www.paypal.com/donate/?hosted_button_id=P5E5EBVM2HWGS\n\n"
    "📿 Artigos abençoados:\n"
    "• Terço de Nossa Senhora → https://amzn.to/40ewSZU\n"
    "• Bíblia Letra Gigante → https://amzn.to/4afDGLy\n\n"
    "🔔 Ative o sininho · 👍 Curta · ➡️ Visite o canal"
)

# Estado global
_estado = {
    "live_id_h": None,
    "proc_h": None,
}
_lock = threading.Lock()
_lock_suplica = threading.Lock()
_suplica_caminhos = {"h": None}

_ev_suplica_gerar = threading.Event()
_ev_suplica_pronta = threading.Event()
_ev_parar = threading.Event()

_rotation_idx = 0

MIN_BLOCO_BYTES = 10 * 1024 * 1024

_stream_id_cache = {"id": None}


# ═══════════════════════════════════════════════════════════════════════
# CALENDÁRIO LITÚRGICO
# ═══════════════════════════════════════════════════════════════════════

def _pascoa(ano: int) -> datetime:
    a = ano % 19
    b, c = divmod(ano, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    mes = (h + l - 7 * m + 114) // 31
    dia = (h + l - 7 * m + 114) % 31 + 1
    return datetime(ano, mes, dia)

def calcular_contexto_sazonal(data: datetime) -> str:
    ano = data.year
    p   = _pascoa(ano)
    fixas = {
        (1, 1):   "Ano Novo — Solenidade de Santa Maria Mãe de Deus",
        (2, 2):   "Apresentação do Senhor — Festa da Candelária",
        (3, 19):  "São José — Patrono da Família Universal",
        (5, 13):  "Nossa Senhora de Fátima",
        (6, 13):  "Santo Antônio de Lisboa — Padroeiro dos Pobres",
        (8, 15):  "Assunção de Nossa Senhora",
        (10, 12): "Nossa Senhora Aparecida — Padroeira do Brasil",
        (11, 1):  "Todos os Santos",
        (11, 2):  "Finados",
        (12, 8):  "Imaculada Conceição de Nossa Senhora",
        (12, 24): "Véspera de Natal",
        (12, 25): "Natal do Senhor",
    }
    if (data.month, data.day) in fixas:
        return fixas[(data.month, data.day)]
    diff = (data.date() - p.date()).days
    moveis = {
        -46: "Quarta-feira de Cinzas — Início da Quaresma",
        -7:  "Domingo de Ramos",
        -2:  "Sexta-feira Santa — Paixão e Morte do Senhor",
         0:  "Aleluia! Páscoa da Ressurreição!",
        49:  "Pentecostes",
        60:  "Corpus Christi",
    }
    if diff in moveis:
        return moveis[diff]
    if data.weekday() == 4:
        return "Sexta-feira — Jornada de Misericórdia e Perdão"
    return PILARES.get(data.weekday(), "Jornada de Oração e Intercessão")


# ═══════════════════════════════════════════════════════════════════════
# GEMINI
# ═══════════════════════════════════════════════════════════════════════

def rodar_gemini(prompt: str, usa_chat: bool = False) -> str:
    chaves = CHAVES_CHAT if usa_chat else CHAVES_CONTEUDO
    for modelo in MODELOS_LIVE:
        modelo_morto = False
        for chave in chaves:
            try:
                client = genai.Client(api_key=chave)
                resp = client.models.generate_content(model=modelo, contents=prompt)
                return resp.text.strip()
            except Exception as e:
                msg = str(e)
                log.warning(f"Gemini {modelo} [{chave[-6:]}]: {msg[:100]}")
                if "404" in msg or "no longer" in msg.lower() or "not found" in msg.lower():
                    log.warning(f"Modelo {modelo} descontinuado — pulando para o próximo.")
                    modelo_morto = True
                    break
                if "503" in msg or "unavailable" in msg.lower():
                    break
        if modelo_morto:
            continue
    log.error("Todos os modelos/chaves Gemini falharam.")
    return ""


# ═══════════════════════════════════════════════════════════════════════
# GOOGLE APIS
# ═══════════════════════════════════════════════════════════════════════

def _load_gcp_info() -> dict:
    if GCP_CREDS_FILE.exists():
        return json.loads(GCP_CREDS_FILE.read_text())
    return json.loads(os.environ["GOOGLE_CREDENTIALS_PT"])

def _creds_drive() -> SACredentials:
    creds = SACredentials.from_service_account_info(
        _load_gcp_info(),
        scopes=["https://www.googleapis.com/auth/drive.readonly"]
    )
    creds.refresh(Request())
    return creds

def _creds_youtube() -> OAuthCredentials:
    raw = os.environ.get("YOUTUBE_TOKEN_PT") or YT_TOKEN_FILE.read_text()
    data = json.loads(raw)
    creds = OAuthCredentials.from_authorized_user_info(
        data, scopes=["https://www.googleapis.com/auth/youtube"]
    )
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        YT_TOKEN_FILE.write_text(creds.to_json())
        log.info("YouTube token PT renovado.")
    return creds

def get_drive():
    return build("drive", "v3", credentials=_creds_drive())

def get_youtube():
    return build("youtube", "v3", credentials=_creds_youtube())


# ═══════════════════════════════════════════════════════════════════════
# DRIVE — DOWNLOAD DE ASSETS
# ═══════════════════════════════════════════════════════════════════════

def _baixar_pasta_drive(drive, folder_id: str, dest: Path, exts=(".mp3", ".jpg", ".png", ".jpeg")):
    if not folder_id:
        return
    dest.mkdir(parents=True, exist_ok=True)
    existentes = {f.name for f in dest.iterdir()}
    page_token = None
    n = 0
    while True:
        resp = drive.files().list(
            q=f"'{folder_id}' in parents and trashed=false",
            fields="nextPageToken, files(id, name)",
            pageToken=page_token,
            pageSize=100,
        ).execute()
        for arq in resp.get("files", []):
            nome = arq["name"]
            if not any(nome.lower().endswith(e) for e in exts):
                continue
            if nome in existentes:
                continue
            dest_arq = dest / nome
            for tentativa in range(4):
                try:
                    req = drive.files().get_media(fileId=arq["id"])
                    buf = BytesIO()
                    dl = MediaIoBaseDownload(buf, req, chunksize=16 * 1024 * 1024)
                    done = False
                    while not done:
                        _, done = dl.next_chunk()
                    dest_arq.write_bytes(buf.getvalue())
                    n += 1
                    break
                except Exception as e:
                    log.warning(f"  tentativa {tentativa+1}/4 para {nome}: {e}")
                    time.sleep(5 * (tentativa + 1))
        page_token = resp.get("nextPageToken")
        if not page_token:
            break
    log.info(f"Drive ↓ {n} arquivo(s) em {dest.name}")

def garantir_assets_vps():
    try:
        drive = get_drive()
        imgs_h = list(DIR_INSUMOS_H.glob("*.jpg")) + list(DIR_INSUMOS_H.glob("*.png"))
        if len(imgs_h) < 5:
            log.info("Baixando imagens Aparecida horizontal...")
            _baixar_pasta_drive(drive, DRIVE_INSUMOS_H_ID, DIR_INSUMOS_H, (".jpg", ".png", ".jpeg"))
        if DRIVE_MUSICAS_M_ID and not list(DIR_MUSICAS_M.glob("*.mp3")):
            log.info("Baixando músicas manhã PT...")
            _baixar_pasta_drive(drive, DRIVE_MUSICAS_M_ID, DIR_MUSICAS_M)
        if DRIVE_MUSICAS_N_ID and not list(DIR_MUSICAS_N.glob("*.mp3")):
            log.info("Baixando músicas noite PT...")
            _baixar_pasta_drive(drive, DRIVE_MUSICAS_N_ID, DIR_MUSICAS_N)
        log.info("Assets VPS PT: OK")
    except Exception as e:
        log.warning(f"garantir_assets_vps: {e} — continuando sem assets do Drive")


# ═══════════════════════════════════════════════════════════════════════
# BLOCOS — ROTAÇÃO E PLAYLIST
# ═══════════════════════════════════════════════════════════════════════

def listar_blocos() -> list[Path]:
    """Lista blocos H disponíveis em DIR_BLOCOS, ordenados por nome."""
    resultado = []
    for h in sorted(DIR_BLOCOS.glob("*_h.mp4")):
        try:
            if h.stat().st_size < MIN_BLOCO_BYTES:
                continue
        except OSError:
            continue
        resultado.append(h)
    return resultado

def _construir_playlist_rolling(blocos: list, rot_idx: int, n: int) -> tuple:
    playlist = BASE_DIR / "_playlist_h.txt"
    linhas = ["ffconcat version 1.0"]
    dur = 0.0
    for i in range(n):
        h = blocos[(rot_idx + i) % len(blocos)]
        try:
            rel = h.relative_to(BASE_DIR)
        except ValueError:
            rel = h
        linhas.append(f"file '{rel}'")
        dur += DURACAO_BLOCO_SEG
    playlist.write_text("\n".join(linhas))
    log.info(f"Playlist H rolling: {n} blocos, {dur/60:.0f}min buffer")
    return playlist, (rot_idx + n) % len(blocos), dur

def _resetar_playlist(path: Path, primeiro: Path):
    try:
        rel = primeiro.relative_to(path.parent)
    except ValueError:
        rel = primeiro
    path.write_text(f"ffconcat version 1.0\nfile '{rel}'\n")

def _append_playlist(path: Path, arquivo: Path):
    try:
        rel = arquivo.relative_to(path.parent)
    except ValueError:
        rel = arquivo
    with open(path, "a") as f:
        f.write(f"file '{rel}'\n")
    log.info(f"  playlist {path.name} ← {arquivo.name}")

def _limpar_suplicas_antigas(max_age_h: int = 3):
    cutoff = time.time() - max_age_h * 3600
    for f in DIR_SUPLICAS.glob("suplica_*"):
        if f.stat().st_mtime < cutoff:
            f.unlink(missing_ok=True)


# ═══════════════════════════════════════════════════════════════════════
# CHAT AO VIVO
# ═══════════════════════════════════════════════════════════════════════

def buscar_msgs_chat(yt, broadcast_id: str) -> list[dict]:
    if not broadcast_id:
        return []
    try:
        b = yt.liveBroadcasts().list(part="snippet", id=broadcast_id).execute()
        if not b.get("items"):
            return []
        chat_id = b["items"][0]["snippet"].get("liveChatId")
        if not chat_id:
            return []
        resp = yt.liveChatMessages().list(
            part="snippet,authorDetails", liveChatId=chat_id, maxResults=200
        ).execute()
        msgs = []
        for item in resp.get("items", []):
            autor = item["authorDetails"]["displayName"]
            texto = item["snippet"].get("displayMessage", "").strip()
            if texto and len(texto) > 5:
                msgs.append({"autor": autor, "texto": texto})
        return msgs
    except Exception as e:
        log.warning(f"buscar_msgs_chat ({broadcast_id}): {e}")
        return []

def extrair_suplicantes(msgs: list[dict], max_s: int = 6) -> list[dict]:
    palavras = ["ora", "reze", "orem", "preciso", "peço", "intercede",
                "doente", "emprego", "família", "casamento", "cura",
                "libertação", "milagre", "ajuda", "dor", "vício", "Nossa Senhora"]
    resultado = []
    for m in msgs:
        if any(p in m["texto"].lower() for p in palavras):
            resultado.append({"nome": m["autor"], "pedido": m["texto"][:200]})
        if len(resultado) >= max_s:
            break
    return resultado

def nomes_ficticios(n: int = 5) -> list[dict]:
    nomes = ["Maria", "João", "Ana", "Roberto", "Patrícia", "Carlos",
             "Rosa", "Fernando", "Elena", "José", "Sônia", "Carmen"]
    pedidos = [
        "a saúde de sua mãe doente",
        "emprego urgente para sua família",
        "a restauração de seu casamento",
        "libertação de uma dependência",
        "um milagre financeiro urgente",
        "proteção sobre seu lar e filhos",
    ]
    return [{"nome": random.choice(nomes), "pedido": random.choice(pedidos)} for _ in range(n)]


# ═══════════════════════════════════════════════════════════════════════
# SÚPLICAS — ROTEIRO E VÍDEO
# ═══════════════════════════════════════════════════════════════════════

def _gerar_roteiro_suplica(suplicantes: list[dict]) -> str:
    linhas = "\n".join(f"  - {s['nome']}: {s['pedido']}" for s in suplicantes)
    agora  = datetime.now(FUSO)

    prompt = (
        f"Você é Nossa Senhora Aparecida, falando em primeira pessoa, em português do Brasil.\n"
        f"Vá interceder por estas almas em 2-3 minutos.\n\n"
        f"Intenções dos fiéis:\n{linhas}\n\n"
        f"Instruções:\n"
        f"- MENCIONE cada pessoa pelo nome com sua intenção específica\n"
        f"- Tom maternal e caloroso, 380-450 palavras\n"
        f"- Inclua uma bênção breve ao final\n"
        f"- Somente texto corrido, sem markdown, sem títulos\n"
        f"- A última frase fica sintaticamente incompleta para se unir fluidamente\n"
        f"  com a próxima oração que vem na transmissão"
    )
    texto = rodar_gemini(prompt, usa_chat=True)
    texto = re.sub(r'\*+', '', texto)
    texto = re.sub(r'#{1,6}\s+', '', texto)
    texto = re.sub(r'\n{3,}', '\n\n', texto)
    return texto.strip()

async def _tts_async(texto: str, saida: Path):
    comm = edge_tts.Communicate(texto, voice=VOZ, rate=VOZ_RATE, pitch=VOZ_PITCH)
    await comm.save(str(saida))

def _musica_periodo() -> str | None:
    hora  = datetime.now(FUSO).hour
    pasta = DIR_MUSICAS_M if 5 <= hora < 18 else DIR_MUSICAS_N
    musicas = list(pasta.glob("*.mp3"))
    return str(random.choice(musicas)) if musicas else None

def _duracao_audio(audio: Path) -> int:
    try:
        r = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(audio)],
            capture_output=True, text=True
        )
        return max(60, int(float(r.stdout.strip())) + 5)
    except Exception:
        return DURACAO_SUPLICA_SEG

def _run_ffmpeg(cmd: list[str], label: str):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"FFmpeg [{label}] falhou:\n{r.stderr[-600:]}")
    log.info(f"FFmpeg [{label}] OK")

def _montar_suplica(audio: Path, saida: Path, dur: int, imgs_dir: Path):
    imgs = list(imgs_dir.glob("*.jpg")) + list(imgs_dir.glob("*.png"))
    if not imgs:
        cmd = ["ffmpeg", "-y",
               "-f", "lavfi", "-i", "color=c=0x1a0a2e:s=1280x720:r=30",
               "-i", str(audio), "-t", str(dur),
               "-c:v", "libx264", "-preset", "ultrafast", "-crf", "28",
               "-g", "60", "-keyint_min", "30",
               "-c:a", "aac", "-b:a", "128k", "-pix_fmt", "yuv420p", str(saida)]
        _run_ffmpeg(cmd, f"suplica cor {saida.name}")
        return

    random.shuffle(imgs)
    n_imgs = dur // 8 + 3
    imgs_loop = [imgs[i % len(imgs)] for i in range(n_imgs)]

    concat_file = saida.with_suffix(".concat_s.txt")
    linhas = ["ffconcat version 1.0"]
    for img in imgs_loop:
        linhas.append(f"file '{img}'")
        linhas.append("duration 8")
    linhas.append(f"file '{imgs_loop[-1]}'")
    concat_file.write_text("\n".join(linhas))

    musica = _musica_periodo()
    if musica:
        inputs  = ["-i", str(audio), "-i", musica]
        afiltro = (
            "[1:a]volume=1.0[pray];"
            f"[2:a]volume=0.12,aloop=loop=-1:size=2e+09,atrim=duration={dur}[mus];"
            "[pray][mus]amix=inputs=2:duration=first[aout]"
        )
    else:
        inputs  = ["-i", str(audio)]
        afiltro = "[1:a]volume=1.0[aout]"

    vfiltro = "[0:v]scale=1280:720:force_original_aspect_ratio=increase,crop=1280:720,setsar=1,fps=30[vout]"
    cmd = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0", "-i", str(concat_file),
        *inputs,
        "-filter_complex", f"{vfiltro};{afiltro}",
        "-map", "[vout]", "-map", "[aout]",
        "-t", str(dur),
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "26",
        "-g", "60", "-keyint_min", "30",
        "-c:a", "aac", "-b:a", "128k", "-r", "30", "-pix_fmt", "yuv420p",
        str(saida),
    ]
    _run_ffmpeg(cmd, f"suplica {saida.name}")
    concat_file.unlink(missing_ok=True)


# ═══════════════════════════════════════════════════════════════════════
# YOUTUBE — BROADCASTS
# ═══════════════════════════════════════════════════════════════════════

def _titulo_live_do_dia() -> str:
    return TITULOS_LIVE[datetime.now(FUSO).weekday()]

def _stream_id_da_chave(yt) -> str:
    if _stream_id_cache["id"]:
        return _stream_id_cache["id"]
    sid_env = os.environ.get("STREAM_ID_H_PT", "")
    if sid_env:
        _stream_id_cache["id"] = sid_env
        return sid_env
    resp  = yt.liveStreams().list(part="id,cdn", mine=True, maxResults=50).execute()
    itens = resp.get("items", [])
    for item in itens:
        nome = item.get("cdn", {}).get("ingestionInfo", {}).get("streamName", "")
        if nome == STREAM_KEY_H:
            _stream_id_cache["id"] = item["id"]
            return item["id"]
    if len(itens) == 1:
        sid = itens[0]["id"]
        log.warning(f"STREAM_KEY_H_PT não achada por nome — usando único liveStream ({sid})")
        _stream_id_cache["id"] = sid
        return sid
    raise RuntimeError(
        f"liveStream da STREAM_KEY_H_PT não encontrado ({len(itens)} streams) "
        "— defina STREAM_ID_H_PT no .env"
    )

def adotar_broadcast_ativo(yt) -> str | None:
    try:
        resp = yt.liveBroadcasts().list(
            part="id,status,contentDetails,snippet",
            broadcastStatus="active", broadcastType="all", maxResults=5,
        ).execute()
        itens = resp.get("items", [])
    except Exception as e:
        log.warning(f"adotar_broadcast_ativo: list ({e})")
        return None
    if not itens:
        return None
    sid = ""
    try:
        sid = _stream_id_da_chave(yt)
    except Exception:
        pass
    alvo = itens[0]
    for item in itens:
        if item.get("contentDetails", {}).get("boundStreamId", "") == sid:
            alvo = item
            break
    bid    = alvo["id"]
    priv   = alvo.get("status", {}).get("privacyStatus", "?")
    titulo = alvo.get("snippet", {}).get("title", "")[:60]
    log.info(f"Broadcast ATIVO adotado: {bid} ({priv}) — {titulo}")
    return bid

def _limpar_orfaos(yt, max_del: int = 15, idade_min_h: int = 3):
    try:
        resp = yt.liveBroadcasts().list(
            part="id,snippet", broadcastStatus="upcoming",
            broadcastType="all", maxResults=50,
        ).execute()
        itens = resp.get("items", [])
    except Exception as e:
        log.warning(f"limpar_orfaos: list ({e})")
        return
    agora = datetime.now(timezone.utc)
    n = 0
    for item in itens:
        if n >= max_del:
            break
        sched = item.get("snippet", {}).get("scheduledStartTime", "")
        try:
            t = datetime.strptime(sched[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)
        except Exception:
            continue
        if (agora - t).total_seconds() < idade_min_h * 3600:
            continue
        try:
            yt.liveBroadcasts().delete(id=item["id"]).execute()
            log.info(f"Órfão apagado: {item['id']}")
            n += 1
        except Exception as e:
            log.warning(f"limpar_orfaos: delete {item['id']} ({e})")

def criar_broadcast_permanente(yt) -> str:
    titulo = _titulo_live_do_dia()
    broadcast = yt.liveBroadcasts().insert(
        part="snippet,status,contentDetails",
        body={
            "snippet": {
                "title": titulo,
                "description": DESCRICAO_LIVE,
                "scheduledStartTime": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
            },
            "status": {
                "privacyStatus": "unlisted",
                "selfDeclaredMadeForKids": False,
            },
            "contentDetails": {
                "enableAutoStart": True,
                "enableAutoStop": False,
                "latencyPreference": "normal",
                "monitorStream": {"enableMonitorStream": False},
                "selfDeclaredMadeWithAlteredContent": True,
            },
        },
    ).execute()
    bid = broadcast["id"]
    yt.liveBroadcasts().bind(part="id,contentDetails", id=bid,
                             streamId=_stream_id_da_chave(yt)).execute()
    try:
        snip = yt.videos().list(part="snippet", id=bid).execute()["items"][0]["snippet"]
        snip["defaultLanguage"]      = "pt"
        snip["defaultAudioLanguage"] = "pt"
        yt.videos().update(part="snippet", body={"id": bid, "snippet": snip}).execute()
    except Exception as e:
        log.warning(f"idioma do broadcast {bid}: {e}")
    log.info(f"Broadcast PT criado (não listado, autoStart): {bid} — {titulo}")
    return bid

def _finalizar_broadcast(yt, bid: str):
    try:
        yt.liveBroadcasts().transition(broadcastStatus="complete", id=bid,
                                       part="id,status").execute()
        log.info(f"Broadcast {bid} encerrado — VOD em processamento.")
    except Exception as e:
        log.warning(f"finalizar {bid}: transition ({e})")
    if PLAYLIST_LIVES:
        for tentativa in range(1, 4):
            try:
                yt.playlistItems().insert(
                    part="snippet",
                    body={"snippet": {
                        "playlistId": PLAYLIST_LIVES,
                        "resourceId": {"kind": "youtube#video", "videoId": bid},
                    }},
                ).execute()
                log.info(f"VOD {bid} adicionado à playlist (tentativa {tentativa}).")
                break
            except Exception as e:
                if tentativa < 3:
                    time.sleep(120)
                else:
                    log.warning(f"finalizar {bid}: playlist insert falhou ({e})")

def _publicar_apos_golive(yt, bid: str, espera_seg: int = 60, timeout_seg: int = 1800):
    t0 = time.time()
    ao_vivo = False
    while time.time() - t0 < timeout_seg:
        if _ev_parar.wait(timeout=30):
            return
        try:
            itens = yt.liveBroadcasts().list(part="status", id=bid).execute().get("items", [])
            if not itens:
                return
            st = itens[0]["status"]["lifeCycleStatus"]
            if st == "live":
                ao_vivo = True
                break
            if st in ("complete", "revoked"):
                return
        except Exception as e:
            log.warning(f"publicar: poll {bid}: {e}")
    if not ao_vivo:
        return
    if _ev_parar.wait(timeout=espera_seg):
        return
    try:
        yt.liveBroadcasts().update(
            part="status",
            body={"id": bid, "status": {"privacyStatus": "public",
                                        "selfDeclaredMadeForKids": False}},
        ).execute()
        log.info(f"Broadcast {bid} agora PÚBLICO")
        _aplicar_thumbnail(yt, bid)
        _ativar_transmissao_dupla(yt, bid)
    except Exception as e:
        log.error(f"publicar: falha ao tornar {bid} público: {e}")


# ═══════════════════════════════════════════════════════════════════════
# THUMBNAIL
# ═══════════════════════════════════════════════════════════════════════

def _fonte(size: int):
    if not _PIL_OK:
        return None
    for path in (FONT_PATH, FONT_ALT):
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            continue
    return ImageFont.load_default()

def _aplicar_thumbnail(yt, bid: str):
    if not _PIL_OK:
        return
    try:
        hora = datetime.now(FUSO).hour
        if 5 <= hora < 12:
            periodo = "manha"
        elif 12 <= hora < 19:
            periodo = "tarde"
        else:
            periodo = "noite"
        linhas = _THUMB_LINHAS[periodo]

        fotos = list(DIR_INSUMOS_H.glob("*.jpg")) + list(DIR_INSUMOS_H.glob("*.jpeg"))
        if not fotos:
            return
        bg = Image.open(random.choice(fotos)).convert("RGB")
        w, h = 1280, 720

        bg_ratio = bg.width / bg.height
        tgt_ratio = w / h
        if bg_ratio > tgt_ratio:
            new_h = h
            new_w = int(bg.width * h / bg.height)
        else:
            new_w = w
            new_h = int(bg.height * w / bg.width)
        bg = bg.resize((new_w, new_h), Image.LANCZOS)
        left = (new_w - w) // 2
        top  = (new_h - h) // 2
        bg   = bg.crop((left, top, left + w, top + h))

        # Gradiente suave só na metade inferior — Aparecida visível no topo
        overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        ov_draw = ImageDraw.Draw(overlay)
        grad_start = int(h * 0.42)
        for y_line in range(grad_start, h):
            t = (y_line - grad_start) / (h - grad_start)
            alpha = int(t * 200)
            ov_draw.line([(0, y_line), (w, y_line)], fill=(0, 0, 0, alpha))
        bg = Image.alpha_composite(bg.convert("RGBA"), overlay).convert("RGB")

        draw = ImageDraw.Draw(bg, "RGBA")

        # Badge "AO VIVO" — canto superior esquerdo com fundo vermelho
        f_vivo = _fonte(26)
        badge_txt = " ● AO VIVO AGORA "
        bb = draw.textbbox((0, 0), badge_txt, font=f_vivo)
        bh_badge = bb[3] - bb[1]
        draw.rectangle([(14, 14), (14 + bb[2] + 6, 14 + bh_badge + 8)], fill=(210, 20, 20, 240))
        draw.text((18, 18), badge_txt, font=f_vivo, fill=(255, 255, 255, 255))

        # Título — na parte inferior (55% da altura para baixo)
        f_titulo = _fonte(74)
        total_h_px = sum(draw.textbbox((0, 0), l, font=f_titulo)[3] for l in linhas) + 12 * (len(linhas) - 1)
        y = int(h * 0.52)
        for linha in linhas:
            bbox = draw.textbbox((0, 0), linha, font=f_titulo)
            lw   = bbox[2] - bbox[0]
            lh   = bbox[3] - bbox[1]
            # Sombra para legibilidade
            draw.text(((w - lw) // 2 + 2, y + 2), linha, font=f_titulo, fill=(0, 0, 0, 180))
            draw.text(((w - lw) // 2, y), linha, font=f_titulo, fill=(255, 255, 255, 255))
            y += lh + 12

        # Linha dourada + brand na base
        draw.rectangle([(w // 10, h - 56), (w - w // 10, h - 53)], fill=(212, 175, 55, 230))
        brand = "Nossa Senhora Aparecida · Oração 24 Horas"
        f_brand = _fonte(34)
        bbox  = draw.textbbox((0, 0), brand, font=f_brand)
        bw    = bbox[2] - bbox[0]
        draw.text(((w - bw) // 2, h - 48), brand, font=f_brand, fill=(212, 175, 55, 255))

        buf = BytesIO()
        bg.save(buf, format="JPEG", quality=90)
        img_bytes = buf.getvalue()

        fd, tmp = tempfile.mkstemp(suffix=".jpg")
        os.close(fd)
        with open(tmp, "wb") as f:
            f.write(img_bytes)
        yt.thumbnails().set(
            videoId=bid,
            media_body=MediaFileUpload(tmp, mimetype="image/jpeg"),
        ).execute()
        log.info(f"Thumbnail PT aplicada ao broadcast {bid}")
        os.remove(tmp)
    except Exception as e:
        log.warning(f"thumbnail PT: {e}")


def _ativar_transmissao_dupla(yt, bid: str):
    """Ativa transmissão dupla (MULTI_ASPECT_MODE_CROP) via API interna do YouTube.
    O YouTube gera automaticamente a versão 9:16 a partir da horizontal."""
    try:
        items = yt.liveBroadcasts().list(part="snippet", id=bid).execute().get("items", [])
        if not items:
            log.warning(f"[DUPLA] Broadcast {bid} não encontrado")
            return
        video_id = items[0]["snippet"].get("videoId", "") or bid
        if not video_id:
            log.warning(f"[DUPLA] videoId não encontrado para broadcast {bid}")
            return
        creds = yt._http.credentials
        token = getattr(creds, "token", None)
        if not token:
            log.warning("[DUPLA] Token OAuth não disponível para transmissão dupla")
            return
        payload = json.dumps({
            "encryptedVideoId": video_id,
            "multiAspectCreatorSettings": {"mode": "MULTI_ASPECT_MODE_CROP"},
        }).encode("utf-8")
        req = urllib.request.Request(
            "https://www.youtube.com/youtubei/v1/video_manager/metadata_update",
            data=payload,
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            status = resp.status
        if status == 200:
            log.info(f"[DUPLA] Transmissão dupla ativada: broadcast {bid} → video {video_id}")
        else:
            log.warning(f"[DUPLA] Resposta inesperada {status} ao ativar transmissão dupla")
    except Exception as e:
        log.warning(f"[DUPLA] Erro ao ativar transmissão dupla: {e}")


# ═══════════════════════════════════════════════════════════════════════
# FFMPEG — STREAMING
# ═══════════════════════════════════════════════════════════════════════

def _iniciar_proc_playlist(playlist: Path, sk: str, nome: str) -> subprocess.Popen:
    try:
        rel_playlist = str(playlist.relative_to(BASE_DIR))
    except ValueError:
        rel_playlist = str(playlist)

    cmd = [
        "ffmpeg",
        "-re",
        "-fflags", "+genpts",
        "-f", "concat", "-safe", "0",
        "-i", rel_playlist,
        "-c:v", "libx264", "-preset", "ultrafast", "-threads", "2",
        "-b:v", "2000k", "-maxrate", "2500k", "-bufsize", "5000k",
        "-g", "60", "-keyint_min", "30",
        "-c:a", "copy",
        "-f", "flv", f"{INGEST_URL}/{sk}",
    ]
    log_ffmpeg = BASE_DIR / f"ffmpeg_{nome.lower()}.log"
    stderr_f   = open(log_ffmpeg, "wb", buffering=0)
    p = subprocess.Popen(cmd, cwd=str(BASE_DIR), stdout=subprocess.DEVNULL, stderr=stderr_f)
    p._stderr_f = stderr_f
    log.info(f"FFmpeg {nome} (playlist) PID {p.pid} → {log_ffmpeg.name}")
    with _lock:
        _estado[f"proc_{nome.lower()}"] = p
    return p

def _matar_proc(proc: subprocess.Popen | None, nome: str):
    if not proc or proc.poll() is not None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=12)
    except subprocess.TimeoutExpired:
        proc.kill()
    try:
        f = getattr(proc, "_stderr_f", None)
        if f: f.close()
    except Exception: pass
    log.info(f"FFmpeg {nome} encerrado.")


# ═══════════════════════════════════════════════════════════════════════
# THREAD: SÚPLICAS
# ═══════════════════════════════════════════════════════════════════════

def loop_suplicas():
    yt = get_youtube()
    DIR_SUPLICAS.mkdir(parents=True, exist_ok=True)

    while not _ev_parar.is_set():
        _ev_suplica_gerar.wait(timeout=60)
        if _ev_parar.is_set():
            break
        if not _ev_suplica_gerar.is_set():
            continue
        _ev_suplica_gerar.clear()

        log.info("Súplicas PT: iniciando geração...")
        try:
            with _lock:
                bid_h = _estado.get("live_id_h")

            msgs = buscar_msgs_chat(yt, bid_h) if bid_h else []
            suplicantes = extrair_suplicantes(msgs) or nomes_ficticios(5)

            roteiro = _gerar_roteiro_suplica(suplicantes)
            if not roteiro:
                log.warning("Súplica PT: roteiro vazio — pulando")
                _ev_suplica_pronta.set()
                continue

            ts = datetime.now(FUSO).strftime("%Y%m%d_%H%M%S")
            audio_path = DIR_SUPLICAS / f"suplica_{ts}.mp3"
            asyncio.run(_tts_async(roteiro, audio_path))

            if not audio_path.exists() or audio_path.stat().st_size < 1024:
                log.warning("Súplica PT: áudio inválido — pulando")
                _ev_suplica_pronta.set()
                continue

            dur = _duracao_audio(audio_path)
            sh  = DIR_SUPLICAS / f"suplica_{ts}_h.mp4"
            _montar_suplica(audio_path, sh, dur, DIR_INSUMOS_H)
            audio_path.unlink(missing_ok=True)

            with _lock_suplica:
                _suplica_caminhos["h"] = sh

            _ev_suplica_pronta.set()
            log.info(f"Súplica PT pronta: {sh.name} ({dur}s)")

        except Exception as e:
            log.error(f"Súplica PT: erro: {e}")
            _ev_suplica_pronta.set()


# ═══════════════════════════════════════════════════════════════════════
# THREAD: ASSEMBLER
# ═══════════════════════════════════════════════════════════════════════

def _montar_bloco_h(audio: Path) -> Path:
    ts    = audio.stem.replace("audio_", "")
    saida = DIR_BLOCOS / f"bloco_{ts}_h.mp4"
    if saida.exists():
        return saida

    videos = sorted(DIR_VIDEOS_BASE.glob("*.mp4"))
    if not videos:
        raise RuntimeError(f"Sem vídeos em {DIR_VIDEOS_BASE}")

    try:
        r = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(audio)],
            capture_output=True, text=True, timeout=15
        )
        dur = max(int(float(r.stdout.strip())), 1200)
    except Exception:
        dur = DURACAO_BLOCO_SEG

    vids_shuffled = list(videos)
    random.shuffle(vids_shuffled)
    concat_file = saida.with_suffix(".vconcat.txt")
    linhas = ["ffconcat version 1.0"]
    total  = 0
    idx    = 0
    while total < dur + 300:
        linhas.append(f"file '{vids_shuffled[idx % len(vids_shuffled)]}'")
        total += 600
        idx   += 1
    concat_file.write_text("\n".join(linhas))

    musica    = _musica_periodo()
    extra_inp = ["-i", musica] if musica else []
    if musica:
        afiltro = (
            "[1:a]volume=1.0[pray];"
            f"[2:a]volume=0.13,aloop=loop=-1:size=2e+09,atrim=duration={dur}[mus];"
            "[pray][mus]amix=inputs=2:duration=first:dropout_transition=3[aout]"
        )
    else:
        afiltro = "[1:a]volume=1.0[aout]"

    vfiltro = (
        "[0:v]scale=1280:720:force_original_aspect_ratio=increase,"
        "crop=1280:720,setsar=1,fps=30[vout]"
    )

    saida_tmp = saida.with_suffix(".tmp.mp4")
    cmd = [
        "nice", "-n", "19",
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0", "-i", str(concat_file),
        "-i", str(audio),
        *extra_inp,
        "-filter_complex", f"{vfiltro};{afiltro}",
        "-map", "[vout]", "-map", "[aout]",
        "-t", str(dur),
        "-c:v", "libx264", "-preset", "ultrafast",
        "-b:v", "2500k", "-maxrate", "2500k", "-bufsize", "5000k",
        "-g", "60", "-keyint_min", "30",
        "-c:a", "aac", "-b:a", "128k", "-ar", "44100",
        "-r", "30", "-pix_fmt", "yuv420p",
        "-threads", "1",
        str(saida_tmp),
    ]
    log.info(f"Assembler PT: montando {saida.name} ({dur//60}min)...")
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=4500)
    concat_file.unlink(missing_ok=True)
    if result.returncode != 0:
        saida_tmp.unlink(missing_ok=True)
        raise RuntimeError(f"FFmpeg assembler PT falhou: {result.stderr[-600:]}")
    saida_tmp.rename(saida)
    mb = saida.stat().st_size // (1024 * 1024)
    log.info(f"Assembler PT: {saida.name} pronto ({mb} MB)")
    return saida

def loop_assembler():
    log.info("Assembler PT iniciado — aguardando audio_*.mp3 em blocos/")
    while not _ev_parar.is_set():
        try:
            blocos_h = len(list(DIR_BLOCOS.glob("bloco_*_h.mp4")))
            if blocos_h >= ASSEMBLER_BLOCOS_MAX:
                log.info(f"Assembler PT: cap atingido ({blocos_h}/{ASSEMBLER_BLOCOS_MAX}) — aguardando slot livre")
                now = time.time()
                for audio in list(DIR_BLOCOS.glob("audio_*.mp3")):
                    ts = audio.stem.replace("audio_", "")
                    bloco_existe = (DIR_BLOCOS / f"bloco_{ts}_h.mp4").exists()
                    audio_antigo = (now - audio.stat().st_mtime) > 86400
                    if bloco_existe or audio_antigo:
                        audio.unlink(missing_ok=True)
                _ev_parar.wait(timeout=300)
                continue
            for audio in sorted(DIR_BLOCOS.glob("audio_*.mp3")):
                ts      = audio.stem.replace("audio_", "")
                bloco_h = DIR_BLOCOS / f"bloco_{ts}_h.mp4"
                if bloco_h.exists():
                    audio.unlink(missing_ok=True)
                    continue
                try:
                    _montar_bloco_h(audio)
                    log.info(f"Assembler PT: {bloco_h.name} adicionado à rotação.")
                    if bloco_h.exists():
                        audio.unlink(missing_ok=True)
                except Exception as e:
                    log.error(f"Assembler PT erro ({audio.name}): {e}")
        except Exception as e:
            log.error(f"loop_assembler PT erro: {e}")
        _ev_parar.wait(timeout=60)
    log.info("Assembler PT encerrado.")


# ═══════════════════════════════════════════════════════════════════════
# THREAD: TRANSMISSOR
# ═══════════════════════════════════════════════════════════════════════

def loop_transmissor():
    global _rotation_idx
    ciclo = 0

    if MODO_PERMANENTE:
        log.info("Modo PERMANENTE PT: usando stream key fixa (sem criar broadcasts via API)")
        log.info(f"  sk_h={STREAM_KEY_H[:8]}...")
        with _lock:
            _estado["live_id_h"] = BROADCAST_ID_H

        yt = None
        try:
            yt = get_youtube()
            log.info("YouTube API PT OK — broadcast novo a cada ciclo de 6h.")
        except Exception as e:
            log.error(f"YouTube API PT indisponível ({e}) — SEM auto-broadcast!")

        while not _ev_parar.is_set():
            ciclo += 1
            log.info(f"Transmissor PT — ciclo {ciclo} de 6h")
            proc_h = None

            blocos = listar_blocos()
            while not blocos and not _ev_parar.is_set():
                log.warning("Sem blocos PT disponíveis — aguardando 60s...")
                _ev_parar.wait(timeout=60)
                blocos = listar_blocos()
            if _ev_parar.is_set():
                break

            bid_h = None
            if yt:
                try:
                    _limpar_orfaos(yt)
                    bid_h = adotar_broadcast_ativo(yt)
                    if not bid_h:
                        bid_h = criar_broadcast_permanente(yt)
                    with _lock:
                        _estado["live_id_h"] = bid_h
                    threading.Thread(target=_publicar_apos_golive, args=(yt, bid_h),
                                     name="PublicaLivePT", daemon=True).start()
                except Exception as e:
                    log.error(f"broadcast PT do ciclo: {e}")

            rot_idx_h = _rotation_idx % len(blocos)
            playlist_h, rot_idx_h, buf_h = _construir_playlist_rolling(
                blocos, rot_idx_h, ROLLING_INICIAIS)
            proc_h = _iniciar_proc_playlist(playlist_h, STREAM_KEY_H, "H")

            ciclo_start     = time.time()
            ultimo_check_bc = time.time()
            ultimo_suplica  = ciclo_start - (SUPLICA_INTERVAL - 5 * 60)

            try:
                while not _ev_parar.is_set():
                    elapsed = time.time() - ciclo_start
                    if elapsed >= DURACAO_CICLO_SEG:
                        log.info(f"Ciclo {ciclo}: 6h completas — encerrando FFmpeg.")
                        break

                    if proc_h.poll() is not None:
                        log.warning("FFmpeg H PT encerrou — reconstruindo e reiniciando")
                        blocos_atuais = listar_blocos()
                        if blocos_atuais:
                            playlist_h, rot_idx_h, buf_nova = _construir_playlist_rolling(
                                blocos_atuais, rot_idx_h, ROLLING_INICIAIS)
                            buf_h = elapsed + buf_nova
                        proc_h = _iniciar_proc_playlist(playlist_h, STREAM_KEY_H, "H")

                    if not _ev_suplica_gerar.is_set() and (time.time() - ultimo_suplica) >= SUPLICA_INTERVAL:
                        sups_prontas = len(list(DIR_SUPLICAS.glob("suplica_*_h.mp4")))
                        if sups_prontas < SUPLICA_MAX_READY:
                            _ev_suplica_gerar.set()
                            _ev_suplica_pronta.clear()
                            log.info(f"Súplicas PT: disparando geração ({sups_prontas} prontas)")
                        else:
                            log.info(f"Súplicas PT: cap atingido ({sups_prontas}/{SUPLICA_MAX_READY}) — skip")
                        ultimo_suplica = time.time()

                    if _ev_suplica_pronta.is_set():
                        with _lock_suplica:
                            sh = _suplica_caminhos.get("h")
                            _suplica_caminhos["h"] = None
                        _ev_suplica_pronta.clear()
                        if sh and sh.exists():
                            _append_playlist(playlist_h, sh)
                            buf_h += DURACAO_SUPLICA_SEG
                            h_next = blocos[rot_idx_h % len(blocos)]
                            _append_playlist(playlist_h, h_next)
                            buf_h += DURACAO_BLOCO_SEG
                            rot_idx_h = (rot_idx_h + 1) % len(blocos)
                            log.info(f"Suplica PT inserida | buf_restante={buf_h - elapsed:.0f}s")

                    buf_restante = buf_h - elapsed
                    if buf_restante < ROLLING_ANTECIPACAO:
                        h_next = blocos[rot_idx_h % len(blocos)]
                        _append_playlist(playlist_h, h_next)
                        buf_h += DURACAO_BLOCO_SEG
                        rot_idx_h = (rot_idx_h + 1) % len(blocos)
                        log.info(f"Bloco PT appendado (manutenção): {h_next.name} ({buf_h - elapsed:.0f}s)")

                    if yt and bid_h and (time.time() - ultimo_check_bc) >= 120:
                        ultimo_check_bc = time.time()
                        try:
                            itens = yt.liveBroadcasts().list(part="status", id=bid_h).execute().get("items", [])
                            st = itens[0].get("status", {}).get("lifeCycleStatus", "revoked") if itens else "revoked"
                            log.info(f"Watchdog PT: broadcast {bid_h} status={st}")
                            if st in ("complete", "revoked"):
                                log.warning(f"Broadcast PT {bid_h} encerrado ({st}) — criando novo broadcast")
                                _finalizar_broadcast(yt, bid_h)
                                bid_h = criar_broadcast_permanente(yt)
                                with _lock:
                                    _estado["live_id_h"] = bid_h
                                threading.Thread(target=_publicar_apos_golive, args=(yt, bid_h),
                                                 name="PublicaLivePT", daemon=True).start()
                        except Exception as e:
                            log.warning(f"watchdog broadcast PT: {e}")

                    _ev_parar.wait(timeout=10)
            finally:
                _matar_proc(proc_h, "H")
                with _lock:
                    _estado["proc_h"] = None

            if yt:
                try:
                    bid_fim = adotar_broadcast_ativo(yt) or bid_h
                except Exception:
                    bid_fim = bid_h
                if bid_fim:
                    _finalizar_broadcast(yt, bid_fim)
                with _lock:
                    _estado["live_id_h"] = None

            if _ev_parar.is_set():
                break
            log.info("Ciclo PT 6h concluído — aguardando 60s para YouTube salvar VOD...")
            if _ev_parar.wait(timeout=60):
                break
            log.info(f"Reiniciando stream PT (ciclo {ciclo + 1})...")
        return

    # Modo dinâmico (sem stream key fixa)
    yt = get_youtube()
    while not _ev_parar.is_set():
        ciclo += 1
        log.info(f"══════ CICLO PT {ciclo} ══════")
        blocos = listar_blocos()
        while not blocos:
            log.warning("Aguardando blocos PT do GitHub Actions... retry em 60s")
            if _ev_parar.wait(timeout=60):
                return
            blocos = listar_blocos()
        log.error("MODO DINÂMICO PT não suportado — configure STREAM_KEY_H_PT no .env")
        _ev_parar.wait(timeout=600)


# ═══════════════════════════════════════════════════════════════════════
# THREAD: MONITOR
# ═══════════════════════════════════════════════════════════════════════

def loop_monitor():
    while not _ev_parar.is_set():
        try:
            blocos = listar_blocos()
            sups   = list(DIR_SUPLICAS.glob("suplica_*_h.mp4"))
            log.info(f"MONITOR PT | blocos={len(blocos)} | súplicas_prontas={len(sups)}")

            if len(blocos) < BLOCOS_MINIMOS:
                log.warning(f"ALERTA PT: apenas {len(blocos)} bloco(s) disponíveis.")

            stat = os.statvfs(str(BASE_DIR))
            livre_gb = stat.f_bavail * stat.f_frsize / 1e9
            if livre_gb < 5:
                log.warning(f"DISCO: apenas {livre_gb:.1f} GB livre!")
        except Exception as e:
            log.warning(f"MONITOR PT: {e}")
        _ev_parar.wait(timeout=300)


# ═══════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════

def main():
    log.info("═══════════════════════════════════════════════════")
    log.info(" ao_vivo_pt.py — Canal PT — Nossa Senhora Aparecida")
    log.info("═══════════════════════════════════════════════════")

    for d in [DIR_BLOCOS, DIR_SUPLICAS, DIR_INSUMOS_H,
              DIR_MUSICAS_M, DIR_MUSICAS_N]:
        d.mkdir(parents=True, exist_ok=True)

    for tmp in DIR_BLOCOS.glob("*.tmp.mp4"):
        tmp.unlink(missing_ok=True)
        log.info(f"Startup: removido bloco incompleto {tmp.name}")

    log.info("Verificando assets para súplicas PT...")
    garantir_assets_vps()

    threads = [
        threading.Thread(target=loop_suplicas,   name="Suplicas",   daemon=True),
        threading.Thread(target=loop_transmissor, name="Transmissor", daemon=True),
        threading.Thread(target=loop_monitor,     name="Monitor",     daemon=True),
        threading.Thread(target=loop_assembler,   name="Assembler",   daemon=True),
    ]
    for t in threads:
        t.start()
    log.info("Threads PT iniciadas. Sistema operacional.")

    try:
        while True:
            time.sleep(30)
    except KeyboardInterrupt:
        log.info("Encerrando ao_vivo_pt...")
        _ev_parar.set()
        _ev_suplica_gerar.set()
        with _lock:
            _matar_proc(_estado.get("proc_h"), "H")
        for t in threads:
            t.join(timeout=15)
        log.info("ao_vivo_pt.py encerrado.")


if __name__ == "__main__":
    main()
