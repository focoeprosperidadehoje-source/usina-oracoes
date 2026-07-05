#!/usr/bin/env python3
"""
gerar_bloco_live.py — GitHub Actions: gera um par de blocos base (H+V, 27min)

Executado 3x/dia pelo gerador_blocos_es.yml. Ao final, salva os arquivos em
blocos/ para que o workflow faça rsync para o VPS.

Fluxo:
  1. Busca comentários recentes do canal ES via YouTube Data API
  2. Gemini gera roteiro devocional (~3200 palavras, ~27min de áudio)
  3. edge-tts sintetiza o áudio
  4. FFmpeg encoda blocos H (1920×1080) e V (1080×1920)

Assets (imagens + música) ficam em cache via actions/cache para evitar
redownload a cada execução.
"""

import os
import sys
import json
import random
import asyncio
import subprocess
import re
from datetime import datetime
from pathlib import Path
from io import BytesIO

import pytz
import edge_tts
from google import genai
from google.oauth2.service_account import Credentials as SACredentials
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials as OAuthCredentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload


# ═══════════════════════════════════════════════════════════════════════
# CONFIG
# ═══════════════════════════════════════════════════════════════════════

FUSO         = pytz.timezone("America/Mexico_City")
VOZ          = "es-MX-DaliaNeural"
VOZ_RATE     = "-20%"
VOZ_PITCH    = "-10Hz"
CANAL_ID     = "UCyPGsztvMnUhDeoI_6H4bsA"

DURACAO_BLOCO_SEG = 27 * 60   # 1620s

MODELOS = ["gemini-2.5-flash-lite", "gemini-2.0-flash-lite", "gemini-2.5-flash"]
CHAVES  = [k for k in [
    os.environ.get("GEMINI_KEY_LIVE_CONTENT_1", ""),
    os.environ.get("GEMINI_KEY_LIVE_CONTENT_2", ""),
    os.environ.get("GEMINI_API_KEY", ""),   # fallback — chave principal
] if k]

# Pastas de assets (cache do GitHub Actions)
DIR_ASSETS    = Path("assets")
DIR_IMGS_H    = DIR_ASSETS / "imagens_h"     # Maria Guadalupe horizontal
DIR_IMGS_V    = DIR_ASSETS / "imagens_v"     # Maria Guadalupe vertical
DIR_MUSICAS_M = DIR_ASSETS / "musicas_m"
DIR_MUSICAS_N = DIR_ASSETS / "musicas_n"

# Saída
DIR_BLOCOS    = Path("blocos")

# IDs Google Drive
DRIVE_IMGS_H_ID  = "1FSpmGvSZDleU4gUJePAj4t5h0ZoVSmEo"
DRIVE_IMGS_V_ID  = "1wKwlerA2SXA27Na_4KMU3x0aaDPqAtBY"
DRIVE_MUSICAS_M_ID = "1gxZA1TlQPzuf737XOo_n8blfOThnddgm"
DRIVE_MUSICAS_N_ID = "1VPmJ5JHXZ6ky0yRwVgqLmRZrl3HhtK3u"

PILARES = {
    0: "Guerra Espiritual y Protección Divina",
    1: "Liberación de Vicios y Ataduras",
    2: "Restauración Familiar y Matrimonial",
    3: "Providencia Divina y Puertas Abiertas",
    4: "Misericordia Divina y Sanación Física",
    5: "El Manto Sagrado de Guadalupe — La Morenita",
    6: "Milagros y Gratitud",
}


# ═══════════════════════════════════════════════════════════════════════
# GEMINI
# ═══════════════════════════════════════════════════════════════════════

def rodar_gemini(prompt: str) -> str:
    for chave in CHAVES:
        for modelo in MODELOS:
            try:
                client = genai.Client(api_key=chave)
                resp = client.models.generate_content(model=modelo, contents=prompt)
                return resp.text.strip()
            except Exception as e:
                msg = str(e)
                print(f"[WARN] Gemini {modelo} [{chave[-6:]}]: {msg[:100]}")
    raise RuntimeError("Todos os modelos Gemini falharam.")


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
# GOOGLE APIS
# ═══════════════════════════════════════════════════════════════════════

def _gcp_info() -> dict:
    raw = os.environ.get("GOOGLE_CREDENTIALS_ES", "")
    if not raw:
        raise RuntimeError("GOOGLE_CREDENTIALS_ES não encontrado")
    return json.loads(raw)

def get_drive():
    creds = SACredentials.from_service_account_info(
        _gcp_info(), scopes=["https://www.googleapis.com/auth/drive.readonly"]
    )
    creds.refresh(Request())
    return build("drive", "v3", credentials=creds)

def get_youtube_readonly():
    raw = os.environ.get("YOUTUBE_TOKEN_ES", "")
    if not raw:
        return None
    try:
        data = json.loads(raw)
        creds = OAuthCredentials.from_authorized_user_info(
            data, scopes=["https://www.googleapis.com/auth/youtube.readonly"]
        )
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
        return build("youtube", "v3", credentials=creds)
    except Exception as e:
        print(f"[WARN] YouTube readonly: {e}")
        return None


# ═══════════════════════════════════════════════════════════════════════
# DOWNLOAD DE ASSETS (executado somente se não estiver em cache)
# ═══════════════════════════════════════════════════════════════════════

def baixar_pasta_drive(drive, folder_id: str, dest: Path, exts=(".mp3", ".jpg", ".png", ".jpeg")):
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
            for _ in range(4):
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
                    print(f"  [WARN] {nome}: {e}")
        page_token = resp.get("nextPageToken")
        if not page_token:
            break
    print(f"  Drive ↓ {n} arquivo(s) em {dest.name}")

def garantir_assets():
    """Baixa assets do Drive se as pastas de cache estiverem vazias."""
    drive = get_drive()
    imgs_h = list(DIR_IMGS_H.glob("*.jpg")) + list(DIR_IMGS_H.glob("*.png"))
    if len(imgs_h) < 5:
        print("Baixando imagens Guadalupe horizontal...")
        baixar_pasta_drive(drive, DRIVE_IMGS_H_ID, DIR_IMGS_H, (".jpg", ".png", ".jpeg"))
    imgs_v = list(DIR_IMGS_V.glob("*.jpg")) + list(DIR_IMGS_V.glob("*.png"))
    if len(imgs_v) < 5:
        print("Baixando imagens Guadalupe vertical...")
        baixar_pasta_drive(drive, DRIVE_IMGS_V_ID, DIR_IMGS_V, (".jpg", ".png", ".jpeg"))
    if not list(DIR_MUSICAS_M.glob("*.mp3")):
        print("Baixando músicas manhã...")
        baixar_pasta_drive(drive, DRIVE_MUSICAS_M_ID, DIR_MUSICAS_M)
    if not list(DIR_MUSICAS_N.glob("*.mp3")):
        print("Baixando músicas noite...")
        baixar_pasta_drive(drive, DRIVE_MUSICAS_N_ID, DIR_MUSICAS_N)
    print("Assets OK.")


# ═══════════════════════════════════════════════════════════════════════
# FONTES DE CONTEÚDO
# ═══════════════════════════════════════════════════════════════════════

def buscar_comentarios_canal(yt) -> list[dict]:
    if not yt:
        return []
    try:
        resp = yt.commentThreads().list(
            part="snippet",
            allThreadsRelatedToChannelId=CANAL_ID,
            maxResults=80,
            order="relevance",
        ).execute()
        comentarios = []
        for item in resp.get("items", []):
            s = item["snippet"]["topLevelComment"]["snippet"]
            texto = s.get("textOriginal", "").strip()
            if texto and len(texto) > 15:
                comentarios.append(texto)
        print(f"Comentários ES: {len(comentarios)}")
        return comentarios
    except Exception as e:
        print(f"[WARN] buscar_comentarios: {e}")
        return []


# ═══════════════════════════════════════════════════════════════════════
# GERAÇÃO DO ROTEIRO
# ═══════════════════════════════════════════════════════════════════════

def gerar_roteiro(contexto: str, comentarios: list[str], num_bloco: int) -> str:
    agora  = datetime.now(FUSO)
    hora   = agora.hour
    if hora < 6:
        periodo = "de la madrugada"
    elif hora < 12:
        periodo = "de la mañana"
    elif hora < 14:
        periodo = "del mediodía"
    elif hora < 19:
        periodo = "de la tarde"
    else:
        periodo = "de la noche"

    pilar = PILARES.get(agora.weekday(), "Oración e Intercesión")

    if comentarios:
        amostra = random.sample(comentarios, min(8, len(comentarios)))
        bloco_contexto = (
            "TEMAS QUE MAIS MOVEM OS FIÉIS DO CANAL (extraídos de comentários reais):\n"
            + "\n".join(f"  • {c[:120]}" for c in amostra)
        )
    else:
        bloco_contexto = (
            f"Pilar teológico do dia: {pilar}\n"
            "Sem comentários disponíveis — usar pilar como fio condutor."
        )

    prompt = f"""Eres Nuestra Señora de Guadalupe, La Morenita del Tepeyac, hablando en primera persona.
Momento: {agora.strftime('%H:%M')} {periodo} — Bloco #{num_bloco}
Contexto litúrgico/cultural del día: {contexto}
Pilar teológico de hoy: {pilar}

{bloco_contexto}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ESTRUCTURA DEL ROTEIRO (27 minutos, 3200-3600 palabras):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[APERTURA — primeros 60 segundos]
1. Afirmación empática sobre la realidad del fiel en este {periodo}
2. Ambientación sensorial: luz, silencio, presencia divina
3. Promesa: "Vine a interceder por ti esta {periodo}..."

[CUERPO PRINCIPAL — ~22 minutos]
4. Voz cálida y maternal de La Morenita — autoridad espiritual suave
5. Entreteje el pilar del día con los temas que mueven a los fieles del canal
6. Ave María completa con pausa después de Jesús:
   "...y bendito es el fruto de tu vientre Jesús... Santa María, Madre de Dios..."
7. Bloco de intercesión por la salud: "Pongo mis manos sobre todo aquel que sufre..."
8. Ganchos de retención a cada ~350 palabras (organicamente):
   • Antecipación: "Lo que viene ahora es la parte más poderosa..."
   • Revelación: "Esta gracia tiene un nombre..."
   • Validación: "Si sientes calor en tu corazón, es señal de que..."
   • Virada: "Pero lo que tu Madre del Cielo quiere decirte es..."

[DOS CTAs SUTILES — solo en transiciones, nunca durante la oración]
CTA 1 (minuto ~10): "Si esta oración está llegando a tu corazón, dale like..."
CTA 2 (minuto ~22): "Comparte esta transmisión con quien necesita el manto de Guadalupe..."

[CIERRE — últimos 3 minutos]
9. Bendición final como Madre del Cielo
10. Termina en fuerza — el fiel sale protegido, no desesperado
11. LOOP SINTÁTICO: la última frase queda sintáticamente incompleta para unirse
    con la primera frase del próximo bloco — el oyente no percibe la ruptura

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
REGLAS ABSOLUTAS:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
- NUNCA markdown, asteriscos, guiones, títulos — solo texto corrido
- NUNCA comenzar frase con la palabra "Oración"
- NUNCA "Escribe Amén en los comentarios"
- NUNCA mencionar otros canales o marcas
- Solo texto que Guadalupe habla — sin instrucciones de producción
- Máximo 3800 palabras
- Persona: La Morenita (no "Virgen de Guadalupe" como nombre principal)
"""

    texto = rodar_gemini(prompt)
    texto = re.sub(r'\*+', '', texto)
    texto = re.sub(r'#{1,6}\s+', '', texto)
    texto = re.sub(r'^\s*[-•]\s+', '', texto, flags=re.MULTILINE)
    texto = re.sub(r'\n{3,}', '\n\n', texto)
    return texto.strip()


# ═══════════════════════════════════════════════════════════════════════
# TTS
# ═══════════════════════════════════════════════════════════════════════

async def _tts_async(texto: str, saida: Path):
    comm = edge_tts.Communicate(texto, voice=VOZ, rate=VOZ_RATE, pitch=VOZ_PITCH)
    await comm.save(str(saida))

def gerar_audio(texto: str, saida: Path):
    asyncio.run(_tts_async(texto, saida))
    tam = saida.stat().st_size // 1024
    print(f"TTS: {saida.name} ({tam} KB)")


# ═══════════════════════════════════════════════════════════════════════
# FFMPEG — ENCODE H + V
# ═══════════════════════════════════════════════════════════════════════

def _run_ffmpeg(cmd: list[str], label: str):
    print(f"FFmpeg [{label}]: iniciando...")
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"FFmpeg [{label}] falhou:\n{r.stderr[-800:]}")
    print(f"FFmpeg [{label}]: OK")

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
        return int(float(r.stdout.strip()))
    except Exception:
        return DURACAO_BLOCO_SEG

def _build_concat(imgs: list[Path], tmp: Path, n_needed: int, secs_img: int = 8) -> Path:
    random.shuffle(imgs)
    imgs_loop = [imgs[i % len(imgs)] for i in range(n_needed + 2)]
    linhas = ["ffconcat version 1.0"]
    for img in imgs_loop:
        linhas.append(f"file '{img.resolve()}'")
        linhas.append(f"duration {secs_img}")
    linhas.append(f"file '{imgs_loop[-1].resolve()}'")
    tmp.write_text("\n".join(linhas))
    return tmp

def montar_bloco(audio: Path, saida: Path, dur: int, res: str, imgs_dir: Path):
    imgs = list(imgs_dir.glob("*.jpg")) + list(imgs_dir.glob("*.png"))
    if not imgs:
        raise RuntimeError(f"Sem imagens em {imgs_dir}")

    w, h = res.split("x")
    n_needed = dur // 8 + 5
    concat_file = saida.with_suffix(".concat.txt")
    _build_concat(imgs, concat_file, n_needed)

    musica = _musica_periodo()
    if musica:
        extra_inputs = ["-i", musica]
        afiltro = (
            "[1:a]volume=1.0[pray];"
            f"[2:a]volume=0.13,aloop=loop=-1:size=2e+09,atrim=duration={dur}[mus];"
            "[pray][mus]amix=inputs=2:duration=first:dropout_transition=3[aout]"
        )
    else:
        extra_inputs = []
        afiltro = "[1:a]volume=1.0[aout]"

    vfiltro = (
        f"[0:v]scale={w}:{h}:force_original_aspect_ratio=increase,"
        f"crop={w}:{h},setsar=1,fps=30[vout]"
    )

    cmd = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0", "-i", str(concat_file),
        "-i", str(audio),
        *extra_inputs,
        "-filter_complex", f"{vfiltro};{afiltro}",
        "-map", "[vout]", "-map", "[aout]",
        "-t", str(dur),
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "22",
        "-c:a", "aac", "-b:a", "128k", "-ar", "44100",
        "-r", "30", "-pix_fmt", "yuv420p",
        str(saida),
    ]
    _run_ffmpeg(cmd, f"{res} {saida.name}")
    concat_file.unlink(missing_ok=True)


# ═══════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════

def main():
    print("=" * 60)
    print("gerar_bloco_live.py — Canal ES — Iniciando")
    print("=" * 60)

    for d in [DIR_BLOCOS, DIR_IMGS_H, DIR_IMGS_V, DIR_MUSICAS_M, DIR_MUSICAS_N]:
        d.mkdir(parents=True, exist_ok=True)

    # 1. Garantir assets em cache
    print("\n[1/5] Verificando assets...")
    garantir_assets()

    # 2. Comentários do canal (fonte de conteúdo)
    print("\n[2/5] Buscando comentários do canal ES...")
    yt = get_youtube_readonly()
    comentarios = buscar_comentarios_canal(yt)

    # 3. Roteiro
    print("\n[3/5] Gerando roteiro via Gemini...")
    agora = datetime.now(pytz.timezone("America/Mexico_City"))
    contexto = calcular_contexto_sazonal(agora)
    ts = agora.strftime("%Y%m%d_%H")
    num_bloco = int(agora.strftime("%j")) * 3 + (agora.hour // 8)  # índice sequencial único

    roteiro = gerar_roteiro(contexto, comentarios, num_bloco)
    palavras = len(roteiro.split())
    print(f"Roteiro: {palavras} palavras")
    if palavras < 2000:
        msg = f"Roteiro muito curto: {palavras} palavras (mínimo 2000). Gemini retornou texto insuficiente."
        print(f"[ERRO] {msg}")
        _gh_error(msg)
        sys.exit(1)

    # 4. TTS
    print("\n[4/5] Gerando áudio (TTS)...")
    audio_path = Path(f"audio_{ts}.mp3")
    gerar_audio(roteiro, audio_path)
    dur = _duracao_audio(audio_path)
    print(f"Duração do áudio: {dur // 60}min {dur % 60}s")

    # 5. Encode H + V
    print("\n[5/5] Encodando blocos H e V...")
    bloco_h = DIR_BLOCOS / f"bloco_{ts}_h.mp4"
    bloco_v = DIR_BLOCOS / f"bloco_{ts}_v.mp4"

    montar_bloco(audio_path, bloco_h, dur, "1920x1080", DIR_IMGS_H)
    montar_bloco(audio_path, bloco_v, dur, "1080x1920", DIR_IMGS_V)
    audio_path.unlink(missing_ok=True)

    tam_h = bloco_h.stat().st_size // (1024 * 1024)
    tam_v = bloco_v.stat().st_size // (1024 * 1024)
    print(f"\n✅ Blocos prontos:")
    print(f"   H: {bloco_h.name} ({tam_h} MB)")
    print(f"   V: {bloco_v.name} ({tam_v} MB)")


def _gh_error(msg: str):
    """Emite anotação ::error:: visível na página pública do GitHub Actions."""
    # Limpa newlines para caber em uma linha de anotação
    linha = msg.replace("\n", " | ").replace("\r", "")[:500]
    print(f"::error::{linha}", flush=True)


if __name__ == "__main__":
    import traceback
    try:
        main()
    except Exception as exc:
        tb = traceback.format_exc()
        _gh_error(f"FALHA gerar_bloco_live.py: {exc} | {tb}")
        print(tb, flush=True)
        sys.exit(1)
