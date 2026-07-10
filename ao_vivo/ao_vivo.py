#!/usr/bin/env python3
"""
ao_vivo.py — Live 24/7 Canal ES — Arquitetura Pivot (2026-07-03)
Voz: Dalia Neural (es-MX-DaliaNeural)

Threads:
  TRANSMISSOR — ciclos 6h, dual RTMP, rotação de blocos base
  SUPLICAS    — segmento 2-3min de intercessão personalizada a cada bloco
  MONITOR     — saúde do disco e alertas de estoque mínimo

Blocos base (27min H+V) chegam via rsync do GitHub Actions 3×/dia.
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
from datetime import datetime
from pathlib import Path
from io import BytesIO

import pytz
from dotenv import load_dotenv
from google import genai
from google.oauth2.service_account import Credentials as SACredentials
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials as OAuthCredentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
import edge_tts

load_dotenv()


# ═══════════════════════════════════════════════════════════════════════
# LOGGING
# ═══════════════════════════════════════════════════════════════════════

LOG_FILE = Path("/root/ao_vivo_es/ao_vivo.log")
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(threadName)s — %(message)s",
    handlers=[
        logging.FileHandler(str(LOG_FILE)),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger("ao_vivo_es")


# ═══════════════════════════════════════════════════════════════════════
# CONSTANTES E CONFIGURAÇÃO
# ═══════════════════════════════════════════════════════════════════════

CANAL_ID       = os.environ.get("CANAL_ID_ES", "UCyPGsztvMnUhDeoI_6H4bsA")
PLAYLIST_LIVES = os.environ.get("PLAYLIST_ID_LIVES_ES", "PLUDymPRcCipI")
FUSO           = pytz.timezone(os.environ.get("FUSO", "America/Mexico_City"))

# ── Modo Permanente ──────────────────────────────────────────────────────
# Se STREAM_KEY_H e STREAM_KEY_V estiverem no .env, o robô transmite
# diretamente sem criar broadcasts via API (zero consumo de cota diária).
# Configure UMA VEZ no YouTube Studio e salve no .env do VPS.
STREAM_KEY_H   = os.environ.get("STREAM_KEY_H", "")
STREAM_KEY_V   = os.environ.get("STREAM_KEY_V", "")
INGEST_URL     = os.environ.get("INGEST_URL", "rtmp://a.rtmp.youtube.com/live2")
BROADCAST_ID_H = os.environ.get("BROADCAST_ID_H", "")  # para leitura do chat
BROADCAST_ID_V = os.environ.get("BROADCAST_ID_V", "")
MODO_PERMANENTE = bool(STREAM_KEY_H)   # True = sem chamadas API (V opcional)

BASE_DIR       = Path("/root/ao_vivo_es")
DIR_BLOCOS      = BASE_DIR / "blocos"          # áudio mp3 chega do GitHub Actions via rsync; H mp4 gerado aqui
DIR_SUPLICAS    = BASE_DIR / "suplicas"        # segmentos curtos gerados no VPS
DIR_INSUMOS_H   = BASE_DIR / "insumos_h"      # imagens Guadalupe 16:9 (para súplicas H)
DIR_INSUMOS_V   = BASE_DIR / "insumos_v"      # imagens Guadalupe 9:16 (para súplicas V)
DIR_MUSICAS_M   = BASE_DIR / "musicas" / "manha"
DIR_MUSICAS_N   = BASE_DIR / "musicas" / "noite"
DIR_VIDEOS_BASE = BASE_DIR / "videos_base"    # cortes de 10min dos vídeos longos (base visual da live)

PLAYLIST_H_FILE = BASE_DIR / "playlist_h.txt"
PLAYLIST_V_FILE = BASE_DIR / "playlist_v.txt"
YT_TOKEN_FILE   = BASE_DIR / "youtube_token.json"
GCP_CREDS_FILE  = BASE_DIR / "google_credentials_es.json"

# IDs Google Drive — assets para súplicas no VPS
DRIVE_INSUMOS_H_ID  = "1FSpmGvSZDleU4gUJePAj4t5h0ZoVSmEo"  # Maria Guadalupe horizontal
DRIVE_INSUMOS_V_ID  = "1wKwlerA2SXA27Na_4KMU3x0aaDPqAtBY"  # Maria Guadalupe vertical
DRIVE_MUSICAS_M_ID  = "1gxZA1TlQPzuf737XOo_n8blfOThnddgm"
DRIVE_MUSICAS_N_ID  = "1VPmJ5JHXZ6ky0yRwVgqLmRZrl3HhtK3u"

# Timing
DURACAO_BLOCO_SEG    = 27 * 60       # 27min — duração de cada bloco base
DURACAO_SUPLICA_SEG  = 160           # ~2.7min — estimativa de súplica
SUPLICA_GERAR_OFFSET = 22 * 60       # iniciar geração da súplica em T+22min no bloco
TRANSICAO_ANTECIP    = 90            # append próximo conteúdo 90s antes do fim do bloco
DURACAO_CICLO_SEG    = 6 * 3600      # 6h por broadcast
BLOCOS_MINIMOS       = 1             # mínimo de blocos para iniciar transmissão

# TTS e Gemini
VOZ           = "es-MX-DaliaNeural"
VOZ_RATE      = "-20%"
VOZ_PITCH     = "-10Hz"
MODELOS_LIVE  = ["gemini-2.5-flash-lite", "gemini-2.0-flash-lite", "gemini-2.5-flash"]

CHAVES_CONTEUDO = [c for c in [
    os.environ.get("GEMINI_KEY_LIVE_CONTENT_1", ""),
    os.environ.get("GEMINI_KEY_LIVE_CONTENT_2", ""),
    os.environ.get("GEMINI_API_KEY", ""),
] if c]

CHAVES_CHAT = [c for c in [
    os.environ.get("GEMINI_KEY_LIVE_CHAT_1", ""),
    os.environ.get("GEMINI_KEY_LIVE_CHAT_2", ""),
    os.environ.get("GEMINI_KEY_LIVE_CHAT_3", ""),
    os.environ.get("GEMINI_API_KEY", ""),
] if c]

PILARES = {
    0: "Guerra Espiritual y Protección Divina",
    1: "Liberación de Vicios y Ataduras",
    2: "Restauración Familiar y Matrimonial",
    3: "Providencia Divina y Puertas Abiertas",
    4: "Misericordia Divina y Sanación Física",
    5: "El Manto Sagrado de Guadalupe",
    6: "Milagros y Gratitud",
}

RTMP_BASE = "rtmp://a.rtmp.youtube.com/live2"
FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_ALT  = "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"

# Estado global compartilhado entre threads
_estado = {
    "live_id_h": None,
    "live_id_v": None,
    "proc_h": None,
    "proc_v": None,
}
_lock = threading.Lock()
_lock_suplica = threading.Lock()
_suplica_caminhos = {"h": None, "v": None}

_ev_suplica_gerar = threading.Event()
_ev_suplica_pronta = threading.Event()
_ev_parar = threading.Event()

_rotation_idx = 0


# ═══════════════════════════════════════════════════════════════════════
# GEMINI
# ═══════════════════════════════════════════════════════════════════════

def rodar_gemini(prompt: str, usa_chat: bool = False) -> str:
    chaves = CHAVES_CHAT if usa_chat else CHAVES_CONTEUDO
    for modelo in MODELOS_LIVE:
        for chave in chaves:
            try:
                client = genai.Client(api_key=chave)
                resp = client.models.generate_content(model=modelo, contents=prompt)
                return resp.text.strip()
            except Exception as e:
                msg = str(e)
                log.warning(f"Gemini {modelo} [{chave[-6:]}]: {msg[:100]}")
                if "503" in msg or "unavailable" in msg.lower():
                    break
    log.error("Todos os modelos/chaves Gemini falharam.")
    return ""


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
        (1, 1):   "Año Nuevo — Solemnidad de Santa María Madre de Dios",
        (2, 2):   "Fiesta de la Candelaria",
        (3, 19):  "San José — Patrono de la Familia Universal",
        (5, 10):  "Día de las Madres (México)",
        (8, 15):  "Asunción de la Virgen María",
        (11, 1):  "Día de Todos los Santos",
        (11, 2):  "Día de los Muertos",
        (12, 8):  "Inmaculada Concepción de la Virgen María",
        (12, 12): "Nuestra Señora de Guadalupe — Fiesta Principal",
        (12, 24): "Nochebuena — Vigilia de Navidad",
        (12, 25): "Navidad — Nacimiento del Señor",
    }
    if (data.month, data.day) in fixas:
        return fixas[(data.month, data.day)]
    diff = (data.date() - p.date()).days
    moveis = {
        -46: "Miércoles de Ceniza — Inicio de la Cuaresma",
        -7:  "Domingo de Ramos",
        -2:  "Viernes Santo — Pasión y Muerte del Señor",
         0:  "¡Pascua de Resurrección!",
        49:  "Pentecostés",
        60:  "Corpus Christi",
    }
    if diff in moveis:
        return moveis[diff]
    if data.weekday() == 4:
        return "Viernes — Jornada de Misericordia y Perdón"
    return PILARES.get(data.weekday(), "Jornada de Oración e Intercesión")


# ═══════════════════════════════════════════════════════════════════════
# GOOGLE APIS — CREDENCIAIS
# ═══════════════════════════════════════════════════════════════════════

def _load_gcp_info() -> dict:
    if GCP_CREDS_FILE.exists():
        return json.loads(GCP_CREDS_FILE.read_text())
    return json.loads(os.environ["GOOGLE_CREDENTIALS_ES"])

def _creds_drive() -> SACredentials:
    creds = SACredentials.from_service_account_info(
        _load_gcp_info(),
        scopes=["https://www.googleapis.com/auth/drive.readonly"]
    )
    creds.refresh(Request())
    return creds

def _creds_youtube() -> OAuthCredentials:
    raw = os.environ.get("YOUTUBE_TOKEN_ES") or YT_TOKEN_FILE.read_text()
    data = json.loads(raw)
    creds = OAuthCredentials.from_authorized_user_info(
        data, scopes=["https://www.googleapis.com/auth/youtube"]
    )
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        YT_TOKEN_FILE.write_text(creds.to_json())
        log.info("YouTube token renovado.")
    return creds

def get_drive():
    return build("drive", "v3", credentials=_creds_drive())

def get_youtube():
    return build("youtube", "v3", credentials=_creds_youtube())


# ═══════════════════════════════════════════════════════════════════════
# DRIVE — DOWNLOAD DE ASSETS
# ═══════════════════════════════════════════════════════════════════════

def _baixar_pasta_drive(drive, folder_id: str, dest: Path, exts=(".mp3", ".jpg", ".png", ".jpeg")):
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
    """Baixa músicas e imagens para geração de súplicas. Executado uma vez na inicialização."""
    try:
        drive = get_drive()
        imgs_h = list(DIR_INSUMOS_H.glob("*.jpg")) + list(DIR_INSUMOS_H.glob("*.png"))
        if len(imgs_h) < 5:
            log.info("Baixando imagens Guadalupe horizontal...")
            _baixar_pasta_drive(drive, DRIVE_INSUMOS_H_ID, DIR_INSUMOS_H, (".jpg", ".png", ".jpeg"))
        imgs_v = list(DIR_INSUMOS_V.glob("*.jpg")) + list(DIR_INSUMOS_V.glob("*.png"))
        if len(imgs_v) < 5:
            log.info("Baixando imagens Guadalupe vertical...")
            _baixar_pasta_drive(drive, DRIVE_INSUMOS_V_ID, DIR_INSUMOS_V, (".jpg", ".png", ".jpeg"))
        if not list(DIR_MUSICAS_M.glob("*.mp3")):
            log.info("Baixando músicas manhã...")
            _baixar_pasta_drive(drive, DRIVE_MUSICAS_M_ID, DIR_MUSICAS_M)
        if not list(DIR_MUSICAS_N.glob("*.mp3")):
            log.info("Baixando músicas noite...")
            _baixar_pasta_drive(drive, DRIVE_MUSICAS_N_ID, DIR_MUSICAS_N)
        log.info("Assets VPS: OK")
    except Exception as e:
        log.warning(f"garantir_assets_vps: {e} — continuando sem assets do Drive")


# ═══════════════════════════════════════════════════════════════════════
# BLOCOS — ROTAÇÃO E PLAYLIST
# ═══════════════════════════════════════════════════════════════════════

MIN_BLOCO_BYTES = 10 * 1024 * 1024  # 10 MB — blocos reais têm no mínimo ~30 MB

def listar_blocos() -> list[tuple[Path, Path]]:
    """Lista pares (h, v) disponíveis em DIR_BLOCOS, ordenados por nome.
    V é opcional — se não existir, retorna H como fallback (V stream desativado).
    Ignora arquivos menores que MIN_BLOCO_BYTES (concat .txt renomeados ou corrompidos)."""
    hs = sorted(DIR_BLOCOS.glob("*_h.mp4"))
    resultado = []
    for h in hs:
        try:
            if h.stat().st_size < MIN_BLOCO_BYTES:
                log.debug(f"Bloco ignorado (muito pequeno): {h.name} ({h.stat().st_size} bytes)")
                continue
        except OSError:
            continue
        v = Path(str(h).replace("_h.mp4", "_v.mp4"))
        resultado.append((h, v if v.exists() else h))
    return resultado

def _proximo_bloco() -> tuple[Path, Path]:
    global _rotation_idx
    blocos = listar_blocos()
    if not blocos:
        raise RuntimeError("Sem blocos disponíveis em DIR_BLOCOS!")
    _rotation_idx = (_rotation_idx + 1) % len(blocos)
    h, v = blocos[_rotation_idx]
    log.info(f"Próximo bloco: {h.name}")
    return h, v

def _construir_playlist_ciclo(blocos: list, duracao_seg: int, tipo: str,
                              inicio: int | None = None) -> Path:
    """Cria playlist ffconcat em BASE_DIR cobrindo duracao_seg com blocos em loop.
    tipo: 'h' ou 'v'. Entradas relativas a BASE_DIR (onde FFmpeg é executado).
    FFmpeg concat + ffconcat header: paths relativos à pasta do arquivo playlist.
    P0-C (BUG 13): inicia do índice rotativo global (não de blocos[0]) — após
    crash ou novo ciclo o espectador não volta a ouvir o primeiro bloco."""
    global _rotation_idx
    if inicio is None:
        inicio = _rotation_idx % len(blocos)
        _rotation_idx = (_rotation_idx + 1) % len(blocos)
    playlist = BASE_DIR / f"_playlist_{tipo}.txt"
    linhas   = ["ffconcat version 1.0"]
    total    = 0
    idx      = 0
    margem   = 1800  # 30 min extra de segurança
    while total < duracao_seg + margem:
        h_path, v_path = blocos[(inicio + idx) % len(blocos)]
        path = h_path if tipo == "h" else v_path
        try:
            rel = path.relative_to(BASE_DIR)
        except ValueError:
            rel = path
        linhas.append(f"file '{rel}'")
        total += 1680  # ~28 min por bloco (estimativa conservadora)
        idx   += 1
    playlist.write_text("\n".join(linhas))
    n = len(linhas) - 1
    log.info(f"Playlist {tipo.upper()}: {n} entradas (início no bloco #{inicio}), ~{total // 60}min estimados → {playlist.name}")
    return playlist


def _resetar_playlist(path: Path, primeiro: Path):
    try:
        rel = primeiro.relative_to(path.parent)
    except ValueError:
        rel = primeiro
    path.write_text(f"ffconcat version 1.0\nfile '{rel}'\n")

def _append_playlist(path: Path, arquivo: Path):
    try:
        rel_a = arquivo.relative_to(path.parent)
    except ValueError:
        rel_a = arquivo
    with open(path, "a") as f:
        f.write(f"file '{rel_a}'\n")
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
    palavras = ["ora", "reza", "oren", "necesito", "pido", "intercede",
                "enfermo", "trabajo", "familia", "matrimonio", "sanación",
                "liberación", "milagro", "ayuda", "dolor", "vicio", "Virgen"]
    resultado = []
    for m in msgs:
        if any(p in m["texto"].lower() for p in palavras):
            resultado.append({"nome": m["autor"], "pedido": m["texto"][:200]})
        if len(resultado) >= max_s:
            break
    return resultado

def nomes_ficticios(n: int = 5) -> list[dict]:
    nomes = ["María", "Carlos", "Ana", "Roberto", "Patricia", "Miguel",
             "Rosa", "Fernando", "Elena", "Juan", "Sofía", "Carmen"]
    pedidos = [
        "la salud de su madre enferma",
        "trabajo urgente para su familia",
        "la restauración de su matrimonio",
        "liberación de una adicción",
        "un milagro económico urgente",
        "protección sobre su hogar e hijos",
    ]
    return [{"nome": random.choice(nomes), "pedido": random.choice(pedidos)} for _ in range(n)]


# ═══════════════════════════════════════════════════════════════════════
# SÚPLICAS — ROTEIRO E VÍDEO
# ═══════════════════════════════════════════════════════════════════════

def _gerar_roteiro_suplica(suplicantes: list[dict]) -> str:
    linhas = "\n".join(f"  - {s['nome']}: {s['pedido']}" for s in suplicantes)
    agora = datetime.now(FUSO)
    hora = agora.hour
    periodo = "de la mañana" if hora < 12 else ("del mediodía" if hora < 14 else
              "de la tarde" if hora < 19 else "de la noche")

    prompt = (
        f"Eres Nuestra Señora de Guadalupe, La Morenita, hablando en primera persona.\n"
        f"Es {agora.strftime('%H:%M')} {periodo}. Vas a interceder por estas almas en 2-3 minutos.\n\n"
        f"Intenciones de los fieles:\n{linhas}\n\n"
        f"Instrucciones:\n"
        f"- MENCIONA a cada persona por nombre con su intención específica\n"
        f"- Tono maternal y cálido, 380-450 palabras\n"
        f"- Incluye una bendición breve al final\n"
        f"- Solo texto corrido, sin markdown, sin títulos\n"
        f"- La última frase queda sintáticamente incompleta para unirse fluidamente\n"
        f"  con la siguiente oración que viene en la transmisión"
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
    hora = datetime.now(FUSO).hour
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

def _montar_suplica(audio: Path, saida: Path, dur: int, res: str, imgs_dir: Path):
    imgs = list(imgs_dir.glob("*.jpg")) + list(imgs_dir.glob("*.png"))
    if not imgs:
        # fallback para imagens da outra pasta
        outro = DIR_INSUMOS_V if imgs_dir == DIR_INSUMOS_H else DIR_INSUMOS_H
        imgs = list(outro.glob("*.jpg")) + list(outro.glob("*.png"))
    if not imgs:
        # cor sólida como último recurso
        cmd = ["ffmpeg", "-y",
               "-f", "lavfi", "-i", f"color=c=0x1a0a2e:s={res}:r=30",
               "-i", str(audio), "-t", str(dur),
               "-c:v", "libx264", "-preset", "veryfast", "-crf", "28",
               "-c:a", "aac", "-b:a", "128k", "-pix_fmt", "yuv420p", str(saida)]
        _run_ffmpeg(cmd, f"suplica cor {saida.name}")
        return

    w, h = res.split("x")
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
        inputs = ["-i", str(audio), "-i", musica]
        afiltro = (
            "[1:a]volume=1.0[pray];"
            f"[2:a]volume=0.12,aloop=loop=-1:size=2e+09,atrim=duration={dur}[mus];"
            "[pray][mus]amix=inputs=2:duration=first[aout]"
        )
    else:
        inputs = ["-i", str(audio)]
        afiltro = "[1:a]volume=1.0[aout]"

    vfiltro = (
        f"[0:v]scale={w}:{h}:force_original_aspect_ratio=increase,"
        f"crop={w}:{h},setsar=1,fps=30[vout]"
    )
    cmd = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0", "-i", str(concat_file),
        *inputs,
        "-filter_complex", f"{vfiltro};{afiltro}",
        "-map", "[vout]", "-map", "[aout]",
        "-t", str(dur),
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "26",
        "-c:a", "aac", "-b:a", "128k", "-r", "30", "-pix_fmt", "yuv420p",
        str(saida),
    ]
    _run_ffmpeg(cmd, f"suplica {res} {saida.name}")
    concat_file.unlink(missing_ok=True)


# ═══════════════════════════════════════════════════════════════════════
# YOUTUBE — LIVES
# ═══════════════════════════════════════════════════════════════════════

def criar_live(yt, sufixo: str = "") -> tuple[str, str, str]:
    agora_utc = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    hora_local = datetime.now(FUSO).hour
    if hora_local < 12:
        tema = "Fuerza y Restauración para tu Familia"
    elif hora_local < 18:
        tema = "Protección Divina bajo el Manto Sagrado"
    else:
        tema = "Descanso Profundo — La Morenita vela por ti"

    titulo = f"🌹 {tema} | Guadalupe en Vivo 24/7"
    descricao = (
        "🙏 Transmisión continua de oración con Nuestra Señora de Guadalupe, La Morenita.\n\n"
        "Deja tu pedido en los comentarios — tu Madre del Cielo te está escuchando.\n\n"
        "💝 Apoya esta misión de oración continua:\n"
        "👉 https://www.paypal.com/donate/?hosted_button_id=P5E5EBVM2HWGS\n\n"
        "📿 Artículos bendecidos:\n"
        "• Rosario de Guadalupe → https://amzn.to/40ewSZU\n"
        "• Biblia Letra Súper Gigante → https://amzn.to/4afDGLy\n\n"
        "🔔 Activa la campanita · 👍 Dale like · ➡️ Visita el canal"
    )

    broadcast = yt.liveBroadcasts().insert(
        part="snippet,status,contentDetails",
        body={
            "snippet": {
                "title": titulo,
                "description": descricao,
                "scheduledStartTime": agora_utc,
            },
            "status": {
                "privacyStatus": "public",
                "selfDeclaredMadeForKids": False,
            },
            "contentDetails": {
                "enableAutoStart": True,
                "enableAutoStop": True,
                "latencyPreference": "normal",
                "monitorStream": {"enableMonitorStream": False},
                "selfDeclaredMadeWithAlteredContent": True,
            },
        }
    ).execute()
    bid = broadcast["id"]

    stream = yt.liveStreams().insert(
        part="snippet,cdn",
        body={
            "snippet": {"title": f"es_live_{sufixo}"},
            "cdn": {"frameRate": "30fps", "ingestionType": "rtmp", "resolution": "1080p"},
        }
    ).execute()
    sid = stream["id"]
    sk  = stream["cdn"]["ingestionInfo"]["streamName"]
    ing = stream["cdn"]["ingestionInfo"]["ingestionAddress"]

    yt.liveBroadcasts().bind(part="id,contentDetails", id=bid, streamId=sid).execute()

    try:
        yt.playlistItems().insert(
            part="snippet",
            body={
                "snippet": {
                    "playlistId": PLAYLIST_LIVES,
                    "resourceId": {"kind": "youtube#video", "videoId": bid},
                }
            }
        ).execute()
        log.info(f"Live {bid} adicionada à playlist")
    except Exception as e:
        log.warning(f"Playlist insert: {e}")

    log.info(f"Live criada: {bid} | sk: {sk[:12]}...")
    return bid, sk, ing

def encerrar_live(yt, bid: str):
    try:
        yt.liveBroadcasts().transition(
            broadcastStatus="complete", id=bid, part="id,status"
        ).execute()
        log.info(f"Live {bid} encerrada.")
    except Exception as e:
        log.warning(f"encerrar_live {bid}: {e}")


# ═══════════════════════════════════════════════════════════════════════
# P0-B — BROADCAST AUTOMÁTICO POR CICLO (MODO PERMANENTE)
# Broadcast encerrado pelo YouTube NÃO volta sozinho (madrugada 09→10/07
# ficou 100% offline). Cada ciclo de 6h cria broadcast novo via API:
# NÃO LISTADO + autoStart/autoStop, vinculado à stream key permanente,
# vai a PÚBLICO ~5min após o go-live (não queima notificação dos vídeos).
# ═══════════════════════════════════════════════════════════════════════

# Fórmula de título aprovada: [La Morenita] + [Milagro/Sanación/Liberación
# conforme pilar do dia] + urgência. Nunca genérico. (weekday: 0=lunes)
TITULOS_LIVE = {
    0: "🔴 La Morenita Te Protege AHORA de Todo Ataque — Oración Poderosa EN VIVO",
    1: "🔴 La Morenita Rompe HOY Esa Atadura — Liberación Poderosa EN VIVO",
    2: "🔴 La Morenita Restaura Tu Familia HOY — Milagro de Reconciliación EN VIVO",
    3: "🔴 La Morenita Abre HOY Puertas Cerradas — Milagro de Providencia EN VIVO",
    4: "🔴 La Morenita Sana Tu Cuerpo AHORA — Milagro de Sanación EN VIVO",
    5: "🔴 El Manto de La Morenita Te Cubre AHORA — Protección y Milagros EN VIVO",
    6: "🔴 La Morenita Tiene un Milagro para Ti HOY — Recíbelo EN VIVO",
}

DESCRICAO_LIVE = (
    "🙏 Transmisión continua de oración con Nuestra Señora de Guadalupe, La Morenita.\n\n"
    "Deja tu pedido en los comentarios — tu Madre del Cielo te está escuchando.\n\n"
    "💝 Apoya esta misión de oración continua:\n"
    "👉 https://www.paypal.com/donate/?hosted_button_id=P5E5EBVM2HWGS\n\n"
    "📿 Artículos bendecidos:\n"
    "• Rosario de Guadalupe → https://amzn.to/40ewSZU\n"
    "• Biblia Letra Súper Gigante → https://amzn.to/4afDGLy\n\n"
    "🔔 Activa la campanita · 👍 Dale like · ➡️ Visita el canal"
)

_stream_id_cache = {"id": None}


def _titulo_live_do_dia() -> str:
    return TITULOS_LIVE[datetime.now(FUSO).weekday()]


def _stream_id_da_chave(yt) -> str:
    """Localiza o liveStream ID da stream key permanente (cacheado).
    Aceita override via STREAM_ID_H no .env caso a key default não seja
    listável pela API."""
    if _stream_id_cache["id"]:
        return _stream_id_cache["id"]
    sid_env = os.environ.get("STREAM_ID_H", "")
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
        log.warning(f"STREAM_KEY_H não achada por nome — usando único liveStream da conta ({sid})")
        _stream_id_cache["id"] = sid
        return sid
    raise RuntimeError(
        f"liveStream da STREAM_KEY_H não encontrado ({len(itens)} streams na conta) "
        "— defina STREAM_ID_H no .env"
    )


def criar_broadcast_permanente(yt) -> str:
    """Cria broadcast NÃO LISTADO com autoStart/autoStop, vinculado à stream
    key permanente. Idioma do vídeo = espanhol (ativa legendas automáticas)."""
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
                "enableAutoStop": True,
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
        snip["defaultLanguage"]      = "es"
        snip["defaultAudioLanguage"] = "es"
        yt.videos().update(part="snippet", body={"id": bid, "snippet": snip}).execute()
    except Exception as e:
        log.warning(f"idioma do broadcast {bid}: {e}")
    log.info(f"Broadcast criado (não listado, autoStart): {bid} — {titulo}")
    return bid


def _publicar_apos_golive(yt, bid: str, espera_seg: int = 300, timeout_seg: int = 1800):
    """Espera o broadcast entrar AO VIVO (autoStart) e o torna PÚBLICO após
    espera_seg. Contorno: a API de lives não tem notifySubscribers — o go-live
    acontece NÃO LISTADO (não dispara sino) e a troca posterior de visibilidade
    normalmente não notifica. VALIDAR empiricamente no 1º ciclo."""
    t0 = time.time()
    ao_vivo = False
    while time.time() - t0 < timeout_seg:
        if _ev_parar.wait(timeout=30):
            return
        try:
            itens = yt.liveBroadcasts().list(part="status", id=bid).execute().get("items", [])
            if not itens:
                log.warning(f"publicar: broadcast {bid} não encontrado")
                return
            st = itens[0]["status"]["lifeCycleStatus"]
            if st == "live":
                ao_vivo = True
                break
            if st in ("complete", "revoked"):
                log.warning(f"publicar: broadcast {bid} já encerrado ({st})")
                return
        except Exception as e:
            log.warning(f"publicar: poll {bid}: {e}")
    if not ao_vivo:
        log.warning(f"publicar: {bid} não entrou ao vivo em {timeout_seg // 60}min — permanece não listado")
        return
    if _ev_parar.wait(timeout=espera_seg):
        return
    try:
        yt.liveBroadcasts().update(
            part="status",
            body={"id": bid, "status": {"privacyStatus": "public",
                                        "selfDeclaredMadeForKids": False}},
        ).execute()
        log.info(f"Broadcast {bid} agora PÚBLICO (go-live foi não listado — validar sino)")
    except Exception as e:
        log.error(f"publicar: falha ao tornar {bid} público: {e}")


def _finalizar_broadcast(yt, bid: str):
    """Encerra o broadcast do ciclo (salva VOD) e insere o VOD na playlist de
    lives (playlistItems.insert é silencioso — não notifica)."""
    try:
        yt.liveBroadcasts().transition(broadcastStatus="complete", id=bid,
                                       part="id,status").execute()
        log.info(f"Broadcast {bid} encerrado — VOD em processamento.")
    except Exception as e:
        log.warning(f"finalizar {bid}: transition ({e}) — autoStop pode já ter encerrado")
    try:
        yt.playlistItems().insert(
            part="snippet",
            body={"snippet": {
                "playlistId": PLAYLIST_LIVES,
                "resourceId": {"kind": "youtube#video", "videoId": bid},
            }},
        ).execute()
        log.info(f"VOD {bid} adicionado à playlist de lives.")
    except Exception as e:
        log.warning(f"finalizar {bid}: playlistItems.insert ({e})")


# ═══════════════════════════════════════════════════════════════════════
# FFMPEG — STREAMING
# ═══════════════════════════════════════════════════════════════════════

def _detectar_fonte() -> str:
    for f in [FONT_PATH, FONT_ALT, "/usr/share/fonts/truetype/ttf-dejavu/DejaVuSans-Bold.ttf"]:
        if Path(f).exists():
            return f
    return ""

def _cmd_stream(arquivo: Path, sk: str, ing: str, res: str, bitrate: str) -> list[str]:
    """Comando FFmpeg com stream_loop -1: repete o bloco indefinidamente.
    Elimina freeze de transição — o código reinicia o processo para trocar de bloco."""
    font  = _detectar_fonte()
    fsize = "52" if res.startswith("1920") else "38"
    clock = (
        f"drawtext=fontfile={font}:text='%{{localtime\\:%T}}':"
        f"fontcolor=white:fontsize={fsize}:x=w-tw-30:y=30:"
        f"shadowcolor=black:shadowx=2:shadowy=2:box=1:boxcolor=black@0.4:boxborderw=6"
    ) if font else "drawtext=text='%{localtime\\:%T}':fontcolor=white:fontsize=48:x=w-tw-30:y=30"

    return [
        "ffmpeg", "-re",
        "-i", str(arquivo),
        "-vf", clock,
        "-c:v", "libx264", "-preset", "veryfast", "-tune", "zerolatency",
        "-pix_fmt", "yuv420p",
        "-b:v", bitrate, "-maxrate", bitrate, "-bufsize", "6000k",
        "-g", "60", "-keyint_min", "60",
        "-c:a", "aac", "-b:a", "128k", "-ar", "44100",
        "-f", "flv", f"{ing}/{sk}",
    ]

def _iniciar_proc(arquivo: Path, sk: str, ing: str, res: str, bitrate: str, nome: str) -> subprocess.Popen:
    cmd = _cmd_stream(arquivo, sk, ing, res, bitrate)
    # CRÍTICO: stderr=PIPE enche o buffer de 64KB em ~20-40s → FFmpeg bloqueia no write
    # e para de enviar RTMP sem crashar (poll() continua None → crash detection nunca dispara)
    # Solução: redirecionar stderr para arquivo de log (sem limite de buffer)
    log_ffmpeg = BASE_DIR / f"ffmpeg_{nome.lower()}.log"
    stderr_f = open(log_ffmpeg, "wb", buffering=0)
    p = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=stderr_f)
    p._stderr_f = stderr_f  # manter referência para fechar ao encerrar
    log.info(f"FFmpeg {nome} iniciado PID {p.pid} → {log_ffmpeg.name}")
    return p

def _iniciar_proc_playlist(playlist: Path, sk: str, ing: str,
                            res: str, bitrate: str, nome: str) -> subprocess.Popen:
    """Lança FFmpeg com playlist ffconcat — transições sem gap entre blocos.
    cwd=BASE_DIR para que os paths relativos da playlist sejam resolvidos corretamente."""
    font  = _detectar_fonte()
    fsize = "52" if res.startswith("1920") else "38"
    clock = (
        f"drawtext=fontfile={font}:text='%{{localtime\\:%T}}':"
        f"fontcolor=white:fontsize={fsize}:x=w-tw-30:y=30:"
        f"shadowcolor=black:shadowx=2:shadowy=2:box=1:boxcolor=black@0.4:boxborderw=6"
    ) if font else "drawtext=text='%{localtime\\:%T}':fontcolor=white:fontsize=48:x=w-tw-30:y=30"

    try:
        rel_playlist = str(playlist.relative_to(BASE_DIR))
    except ValueError:
        rel_playlist = str(playlist)

    cmd = [
        "ffmpeg", "-re",
        "-f", "concat", "-safe", "0",
        "-i", rel_playlist,
        "-vf", clock,
        "-c:v", "libx264", "-preset", "veryfast", "-tune", "zerolatency",
        "-pix_fmt", "yuv420p",
        "-b:v", bitrate, "-maxrate", bitrate, "-bufsize", "6000k",
        "-g", "60", "-keyint_min", "60",
        "-c:a", "aac", "-b:a", "128k", "-ar", "44100",
        "-f", "flv", f"{ing}/{sk}",
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

        log.info("Súplicas: iniciando geração...")
        try:
            with _lock:
                bid_h = _estado.get("live_id_h")

            msgs = buscar_msgs_chat(yt, bid_h) if bid_h else []
            suplicantes = extrair_suplicantes(msgs) or nomes_ficticios(5)

            roteiro = _gerar_roteiro_suplica(suplicantes)
            if not roteiro:
                log.warning("Súplica: roteiro vazio — pulando")
                _ev_suplica_pronta.set()
                continue

            ts = datetime.now(FUSO).strftime("%Y%m%d_%H%M%S")
            audio_path = DIR_SUPLICAS / f"suplica_{ts}.mp3"
            asyncio.run(_tts_async(roteiro, audio_path))

            if not audio_path.exists() or audio_path.stat().st_size < 1024:
                log.warning("Súplica: áudio inválido — pulando")
                _ev_suplica_pronta.set()
                continue

            dur = _duracao_audio(audio_path)
            sh = DIR_SUPLICAS / f"suplica_{ts}_h.mp4"
            sv = DIR_SUPLICAS / f"suplica_{ts}_v.mp4"

            _montar_suplica(audio_path, sh, dur, "1920x1080", DIR_INSUMOS_H)
            _montar_suplica(audio_path, sv, dur, "1080x1920", DIR_INSUMOS_V)
            audio_path.unlink(missing_ok=True)

            with _lock_suplica:
                _suplica_caminhos["h"] = sh
                _suplica_caminhos["v"] = sv

            _ev_suplica_pronta.set()
            log.info(f"Súplica pronta: {sh.name} ({dur}s)")

        except Exception as e:
            log.error(f"Súplica: erro: {e}")
            _ev_suplica_pronta.set()


# ═══════════════════════════════════════════════════════════════════════
# THREAD: ASSEMBLER — combina audio_*.mp3 (GitHub Actions) + videos_base/
# ═══════════════════════════════════════════════════════════════════════

def _montar_bloco_h(audio: Path) -> Path:
    """Monta bloco H: cortes de videos_base/ (mudo) + áudio de oração da Morenita."""
    ts     = audio.stem.replace("audio_", "")  # YYYYMMDD_HH
    saida  = DIR_BLOCOS / f"bloco_{ts}_h.mp4"
    if saida.exists():
        return saida

    videos = sorted(DIR_VIDEOS_BASE.glob("*.mp4"))
    if not videos:
        raise RuntimeError(f"Sem vídeos em {DIR_VIDEOS_BASE} — coloque os cortes lá.")

    # Duração estimada pelo tamanho do mp3 (~128kbps → ~1 min por 960KB)
    try:
        r = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(audio)],
            capture_output=True, text=True, timeout=15
        )
        dur = max(int(float(r.stdout.strip())), 1200)
    except Exception:
        dur = DURACAO_BLOCO_SEG

    # Concat embaralhado dos vídeos base para cobrir dur + margem
    vids_shuffled = list(videos)
    random.shuffle(vids_shuffled)
    concat_file = saida.with_suffix(".vconcat.txt")
    linhas = ["ffconcat version 1.0"]
    total  = 0
    idx    = 0
    while total < dur + 300:
        linhas.append(f"file '{vids_shuffled[idx % len(vids_shuffled)]}'")
        total += 600   # ~10 min por clip (estimativa conservadora)
        idx   += 1
    concat_file.write_text("\n".join(linhas))

    # Música de fundo (opcional)
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
        "[0:v]scale=1920:1080:force_original_aspect_ratio=increase,"
        "crop=1920:1080,setsar=1,fps=30[vout]"
    )

    # P0-A (BUG 14): nice -n 19 + -threads 2 — o Assembler NUNCA disputa CPU
    # com o transmissor. Encode saturava as 4 vCPU -> FFmpeg H caía abaixo de
    # 1.0x -> YouTube encerrava o broadcast a cada workflow (3x/dia).
    cmd = [
        "nice", "-n", "19",
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0", "-i", str(concat_file),
        "-i", str(audio),
        *extra_inp,
        "-filter_complex", f"{vfiltro};{afiltro}",
        "-map", "[vout]", "-map", "[aout]",
        "-t", str(dur),
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "28",
        "-c:a", "aac", "-b:a", "128k", "-ar", "44100",
        "-r", "30", "-pix_fmt", "yuv420p",
        "-threads", "2",
        str(saida),
    ]
    log.info(f"Assembler: montando {saida.name} ({dur//60}min, {len(vids_shuffled)} vídeos base)...")
    # timeout ampliado: com -threads 2 + nice o encode pode levar bem mais tempo
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=2700)
    concat_file.unlink(missing_ok=True)
    if result.returncode != 0:
        saida.unlink(missing_ok=True)
        raise RuntimeError(f"FFmpeg assembler falhou: {result.stderr[-600:]}")
    mb = saida.stat().st_size // (1024 * 1024)
    log.info(f"Assembler: {saida.name} pronto ({mb} MB)")
    return saida


def loop_assembler():
    """Monitora DIR_BLOCOS por novos audio_*.mp3, monta blocos H com videos_base/."""
    log.info("Assembler iniciado — aguardando audio_*.mp3 em blocos/")
    while not _ev_parar.is_set():
        try:
            for audio in sorted(DIR_BLOCOS.glob("audio_*.mp3")):
                ts      = audio.stem.replace("audio_", "")
                bloco_h = DIR_BLOCOS / f"bloco_{ts}_h.mp4"
                if bloco_h.exists():
                    audio.unlink(missing_ok=True)
                    continue
                try:
                    _montar_bloco_h(audio)
                    audio.unlink(missing_ok=True)
                    log.info(f"Assembler: {bloco_h.name} adicionado à rotação.")
                except Exception as e:
                    log.error(f"Assembler erro ({audio.name}): {e}")
        except Exception as e:
            log.error(f"loop_assembler erro: {e}")
        _ev_parar.wait(timeout=60)
    log.info("Assembler encerrado.")


# ═══════════════════════════════════════════════════════════════════════
# THREAD: TRANSMISSOR
# ═══════════════════════════════════════════════════════════════════════

def _loop_blocos(proc_h, proc_v, sk_h, sk_v, ing_h, ing_v, max_seg=None):
    """Loop de rotação de blocos. max_seg=None → eterno (modo permanente)."""
    global _rotation_idx
    ciclo_start = time.time()

    while not _ev_parar.is_set():
        blocos = listar_blocos()
        if not blocos:
            log.warning("Sem blocos disponíveis, aguardando 60s...")
            if _ev_parar.wait(timeout=60): return proc_h, proc_v
            continue

        h0, v0 = blocos[_rotation_idx % len(blocos)]
        log.info(f"Iniciando bloco: {h0.name}")
        _matar_proc(proc_h, "H")
        _matar_proc(proc_v, "V")
        proc_h = _iniciar_proc(h0, sk_h, ing_h, "1920x1080", "3500k", "H")
        if sk_v:
            proc_v = _iniciar_proc(v0, sk_v, ing_v, "1080x1920", "2500k", "V")
        else:
            proc_v = None
            log.info("FFmpeg V desativado (sem STREAM_KEY_V configurada)")
        with _lock:
            _estado["proc_h"] = proc_h
            _estado["proc_v"] = proc_v

        bloco_start    = time.time()
        suplica_gerada = False

        while not _ev_parar.is_set():
            now     = time.time()
            elapsed = now - bloco_start

            if elapsed >= SUPLICA_GERAR_OFFSET and not suplica_gerada:
                _ev_suplica_gerar.set()
                _ev_suplica_pronta.clear()
                suplica_gerada = True

            if elapsed >= DURACAO_BLOCO_SEG:
                _rotation_idx += 1
                _limpar_suplicas_antigas()
                break

            if max_seg and (now - ciclo_start) >= max_seg:
                return proc_h, proc_v

            if proc_h.poll() is not None:
                # FFmpeg encerrou (fim do bloco ou crash) — reiniciar imediatamente
                stderr_h = b""
                try:
                    lf = BASE_DIR / "ffmpeg_h.log"
                    if lf.exists(): stderr_h = lf.read_bytes()[-500:]
                except: pass
                log.info(f"FFmpeg H encerrou — reiniciando ({stderr_h.decode('utf-8', errors='ignore')[-100:].strip()})")
                # Avançar para o próximo bloco na rotação
                blocos = listar_blocos()
                if blocos:
                    _rotation_idx = (_rotation_idx + 1) % len(blocos)
                    h0, v0 = blocos[_rotation_idx]
                proc_h = _iniciar_proc(h0, sk_h, ing_h, "1920x1080", "3500k", "H")
                with _lock: _estado["proc_h"] = proc_h
                bloco_start = time.time()  # reset timer para o novo bloco
                suplica_gerada = False
                continue  # não dormir — já verificar na próxima iteração

            if proc_v and proc_v.poll() is not None:
                log.info("FFmpeg V encerrou — reiniciando")
                if sk_v:
                    proc_v = _iniciar_proc(v0, sk_v, ing_v, "1080x1920", "2500k", "V")
                    with _lock: _estado["proc_v"] = proc_v
                continue

            time.sleep(2)  # era 15s — reduzido para detectar fim de bloco rapidamente

    return proc_h, proc_v


def loop_transmissor():
    global _rotation_idx
    ciclo = 0

    # ── Modo Permanente: chaves fixas do .env, zero chamadas API ────────
    # Ciclos de 6h: stream vai offline → YouTube salva VOD → reinicia na mesma chave
    if MODO_PERMANENTE:
        sk_v_ativo = STREAM_KEY_V if STREAM_KEY_V else None
        log.info("Modo PERMANENTE: usando stream keys fixas (sem criar broadcasts via API)")
        log.info(f"  sk_h={STREAM_KEY_H[:8]}...  sk_v={'(desativado)' if not sk_v_ativo else STREAM_KEY_V[:8]+'...'}")
        with _lock:
            _estado["live_id_h"] = BROADCAST_ID_H
            _estado["live_id_v"] = BROADCAST_ID_V

        # P0-B: cliente YouTube para auto-recriação de broadcast a cada ciclo.
        # Sem API o stream continua, mas se o YouTube encerrar o broadcast o
        # canal fica offline até intervenção manual (madrugada 09→10/07).
        yt = None
        try:
            yt = get_youtube()
            log.info("YouTube API OK — broadcast novo a cada ciclo de 6h.")
        except Exception as e:
            log.error(f"YouTube API indisponível ({e}) — SEM auto-broadcast!")

        while not _ev_parar.is_set():
            ciclo += 1
            log.info(f"Transmissor — ciclo {ciclo} de 6h (playlist contínua — sem gap entre blocos)")
            proc_h = proc_v = None

            # Aguardar blocos disponíveis
            blocos = listar_blocos()
            while not blocos and not _ev_parar.is_set():
                log.warning("Sem blocos disponíveis — aguardando 60s...")
                _ev_parar.wait(timeout=60)
                blocos = listar_blocos()
            if _ev_parar.is_set():
                break

            # P0-B: broadcast novo (não listado, autoStart) ANTES do FFmpeg subir
            bid_h = None
            if yt:
                try:
                    bid_h = criar_broadcast_permanente(yt)
                    with _lock:
                        _estado["live_id_h"] = bid_h
                    threading.Thread(target=_publicar_apos_golive, args=(yt, bid_h),
                                     name="PublicaLive", daemon=True).start()
                except Exception as e:
                    log.error(f"criar_broadcast_permanente: {e} — ciclo segue só com a stream key")

            # Construir playlists cobrindo 6h (blocos repetidos em loop se necessário)
            playlist_h = _construir_playlist_ciclo(blocos, DURACAO_CICLO_SEG, "h")
            proc_h     = _iniciar_proc_playlist(playlist_h, STREAM_KEY_H, INGEST_URL,
                                                 "1920x1080", "3500k", "H")
            playlist_v = None
            if sk_v_ativo:
                playlist_v = _construir_playlist_ciclo(blocos, DURACAO_CICLO_SEG, "v")
                proc_v     = _iniciar_proc_playlist(playlist_v, sk_v_ativo, INGEST_URL,
                                                     "1080x1920", "2500k", "V")

            # Monitorar ciclo de 6h sem reiniciar FFmpeg entre blocos
            ciclo_start     = time.time()
            ultimo_check_bc = time.time()
            try:
                while not _ev_parar.is_set():
                    elapsed = time.time() - ciclo_start
                    if elapsed >= DURACAO_CICLO_SEG:
                        log.info(f"Ciclo {ciclo}: 6h completas — encerrando FFmpeg para salvar VOD.")
                        break

                    if proc_h.poll() is not None:
                        # FFmpeg encerrou antes do fim (crash ou fim da playlist)
                        log.warning("FFmpeg H encerrou antes do fim do ciclo — recriando playlist e reiniciando")
                        blocos_atuais = listar_blocos()
                        if blocos_atuais:
                            resto = max(DURACAO_CICLO_SEG - int(elapsed), 1800)
                            playlist_h = _construir_playlist_ciclo(blocos_atuais, resto, "h")
                        proc_h = _iniciar_proc_playlist(playlist_h, STREAM_KEY_H, INGEST_URL,
                                                         "1920x1080", "3500k", "H")

                    if proc_v and proc_v.poll() is not None:
                        log.warning("FFmpeg V encerrou — recriando")
                        if sk_v_ativo and playlist_v:
                            proc_v = _iniciar_proc_playlist(playlist_v, sk_v_ativo, INGEST_URL,
                                                             "1080x1920", "2500k", "V")

                    # P0-B: watchdog do broadcast — se o YouTube encerrar no
                    # meio do ciclo, cria outro (autoStart religa sozinho)
                    if yt and bid_h and (time.time() - ultimo_check_bc) >= 120:
                        ultimo_check_bc = time.time()
                        try:
                            itens = yt.liveBroadcasts().list(part="status", id=bid_h).execute().get("items", [])
                            st = itens[0]["status"]["lifeCycleStatus"] if itens else "revoked"
                            if st in ("complete", "revoked"):
                                log.warning(f"Broadcast {bid_h} encerrado no meio do ciclo — criando novo")
                                _finalizar_broadcast(yt, bid_h)
                                bid_h = criar_broadcast_permanente(yt)
                                with _lock:
                                    _estado["live_id_h"] = bid_h
                                threading.Thread(target=_publicar_apos_golive, args=(yt, bid_h),
                                                 name="PublicaLive", daemon=True).start()
                        except Exception as e:
                            log.warning(f"watchdog broadcast: {e}")

                    _ev_parar.wait(timeout=10)
            finally:
                _matar_proc(proc_h, "H")
                _matar_proc(proc_v, "V")
                with _lock:
                    _estado["proc_h"] = None
                    _estado["proc_v"] = None

            # P0-B: encerra broadcast (salva VOD) + insere VOD na playlist
            if yt and bid_h:
                _finalizar_broadcast(yt, bid_h)
                with _lock:
                    _estado["live_id_h"] = None

            if _ev_parar.is_set():
                break
            # Stream offline → YouTube processa e salva VOD deste ciclo
            log.info("Ciclo 6h concluído — aguardando 60s para YouTube salvar VOD...")
            if _ev_parar.wait(timeout=60):
                break
            log.info(f"Reiniciando stream (ciclo {ciclo + 1})...")
        return

    # ── Modo Dinâmico: cria broadcast via API a cada 6h ─────────────────
    yt = get_youtube()

    while not _ev_parar.is_set():
        ciclo += 1
        log.info(f"══════ CICLO {ciclo} ══════")

        # Aguardar bloco disponível
        blocos = listar_blocos()
        while not blocos:
            log.warning("Aguardando blocos do GitHub Actions (rsync)... retry em 60s")
            if _ev_parar.wait(timeout=60):
                return
            blocos = listar_blocos()

        proc_h = proc_v = bid_h = bid_v = None

        try:
            ts = datetime.now(FUSO).strftime("%d/%m %H:%M")
            try:
                bid_h, sk_h, ing_h = criar_live(yt, f"H-{ciclo}")
                bid_v, sk_v, ing_v = criar_live(yt, f"V-{ciclo}")
            except Exception as e_api:
                msg = str(e_api)
                if "userRequestsExceedRateLimit" in msg or "rateLimitExceeded" in msg:
                    log.error(f"COTA ESGOTADA — aguardando 60 minutos antes de tentar novamente...")
                    if _ev_parar.wait(timeout=3600): return
                    continue
                raise

            with _lock:
                _estado["live_id_h"] = bid_h
                _estado["live_id_v"] = bid_v

            log.info("Aguardando 15s para broadcast ativar...")
            time.sleep(15)

            # Loop de blocos dentro do ciclo de 6h (reutiliza _loop_blocos)
            proc_h, proc_v = _loop_blocos(proc_h, proc_v,
                                           sk_h, sk_v, ing_h, ing_v,
                                           max_seg=DURACAO_CICLO_SEG)

        except Exception as e:
            log.error(f"Transmissor ciclo {ciclo}: {e}")

        finally:
            _matar_proc(proc_h, "H")
            _matar_proc(proc_v, "V")
            with _lock:
                _estado["proc_h"] = None
                _estado["proc_v"] = None
                _estado["live_id_h"] = None
                _estado["live_id_v"] = None
            if bid_h:
                encerrar_live(yt, bid_h)
            if bid_v:
                encerrar_live(yt, bid_v)

            if not _ev_parar.is_set():
                log.info("Pausa 30s antes do próximo ciclo...")
                _ev_parar.wait(timeout=30)


# ═══════════════════════════════════════════════════════════════════════
# THREAD: MONITOR
# ═══════════════════════════════════════════════════════════════════════

def loop_monitor():
    while not _ev_parar.is_set():
        try:
            blocos = listar_blocos()
            sups   = list(DIR_SUPLICAS.glob("suplica_*_h.mp4"))
            log.info(f"MONITOR | blocos={len(blocos)} | súplicas_prontas={len(sups)}")

            if len(blocos) < BLOCOS_MINIMOS:
                log.warning(
                    f"ALERTA: apenas {len(blocos)} bloco(s) disponíveis. "
                    "Aguardando rsync do GitHub Actions..."
                )

            # Verificar espaço em disco
            stat = os.statvfs(str(BASE_DIR))
            livre_gb = stat.f_bavail * stat.f_frsize / 1e9
            if livre_gb < 5:
                log.warning(f"DISCO: apenas {livre_gb:.1f} GB livre!")

        except Exception as e:
            log.warning(f"MONITOR: {e}")

        _ev_parar.wait(timeout=300)


# ═══════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════

def main():
    log.info("═══════════════════════════════════════════════════")
    log.info(" ao_vivo.py — Canal ES — Arquitetura Pivot 2026    ")
    log.info("═══════════════════════════════════════════════════")

    for d in [DIR_BLOCOS, DIR_SUPLICAS, DIR_INSUMOS_H, DIR_INSUMOS_V,
              DIR_MUSICAS_M, DIR_MUSICAS_N]:
        d.mkdir(parents=True, exist_ok=True)

    log.info("Verificando assets para súplicas...")
    garantir_assets_vps()

    threads = [
        threading.Thread(target=loop_suplicas,    name="Suplicas",    daemon=True),
        threading.Thread(target=loop_transmissor,  name="Transmissor",  daemon=True),
        threading.Thread(target=loop_monitor,      name="Monitor",      daemon=True),
        threading.Thread(target=loop_assembler,    name="Assembler",    daemon=True),
    ]
    for t in threads:
        t.start()
    log.info("Threads iniciadas. Sistema operacional.")

    try:
        while True:
            time.sleep(30)
    except KeyboardInterrupt:
        log.info("Encerrando...")
        _ev_parar.set()
        _ev_suplica_gerar.set()
        with _lock:
            _matar_proc(_estado.get("proc_h"), "H")
            _matar_proc(_estado.get("proc_v"), "V")
        for t in threads:
            t.join(timeout=15)
        log.info("ao_vivo.py encerrado.")


if __name__ == "__main__":
    main()
