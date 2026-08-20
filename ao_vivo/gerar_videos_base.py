#!/usr/bin/env python3
"""
gerar_videos_base.py — GitHub Actions: cria vídeos slideshow para videos_base/ da live ES

Baixa imagens de Guadalupe (ou Aparecida para PT) do Drive,
aplica blur-fill 1920x1080 com a santa CENTRALIZADA (compatível com
transmissão dupla — YouTube corta o centro 607px para vertical),
e encoda vídeos mudos de ~10min (40 imagens × 15s).

Variáveis de ambiente:
  GOOGLE_CREDENTIALS_ES  — JSON da service account
  NUM_VIDEOS             — quantos vídeos criar (padrão: 8)
  DRIVE_FOLDER_ID        — pasta de imagens (padrão: Guadalupe H)
  VIDEO_PREFIX           — prefixo do nome do arquivo de saída (padrão: guadalupe)
"""

import os
import sys
import json
import math
import random
import datetime
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageFilter
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

# ─── Config ────────────────────────────────────────────────────────────
# Pasta padrão: Guadalupe horizontal (ES). Sobrescrever via env para PT/outros.
DRIVE_FOLDER_ID = os.environ.get("DRIVE_FOLDER_ID") or "1FSpmGvSZDleU4gUJePAj4t5h0ZoVSmEo"
VIDEO_PREFIX    = os.environ.get("VIDEO_PREFIX") or "guadalupe"
NUM_VIDEOS      = int(os.environ.get("NUM_VIDEOS") or "8")
IMG_POR_VIDEO   = 40        # imagens por vídeo → 40 × 15s = 600s = 10min
SEG_POR_IMAGEM  = 15        # duração de cada imagem em segundos
TARGET_W        = 1920
TARGET_H        = 1080
DIR_SAIDA       = Path("videos_base")


# ─── Drive ─────────────────────────────────────────────────────────────

def get_drive():
    raw  = os.environ.get("GOOGLE_CREDENTIALS_ES", "")
    info = json.loads(raw)
    creds = Credentials.from_service_account_info(
        info, scopes=["https://www.googleapis.com/auth/drive.readonly"]
    )
    return build("drive", "v3", credentials=creds)


def listar_imagens(drive, folder_id: str) -> list[dict]:
    items, token = [], None
    while True:
        resp = drive.files().list(
            q=f"'{folder_id}' in parents and trashed=false and (mimeType contains 'image/')",
            fields="nextPageToken, files(id, name)",
            pageToken=token,
            pageSize=500,
        ).execute()
        items.extend(resp.get("files", []))
        token = resp.get("nextPageToken")
        if not token:
            break
    print(f"  Imagens na pasta Drive: {len(items)}")
    return items


def baixar_imagem(drive, file_id: str, dest: Path):
    content = drive.files().get_media(fileId=file_id).execute()
    dest.write_bytes(content)


# ─── Processamento de imagem ────────────────────────────────────────────

def blur_fill(src: Path, dest: Path, w: int = TARGET_W, h: int = TARGET_H):
    """
    Cria imagem 1920x1080 com blur-fill + santa centralizada.

    Background: imagem escalonada para COBRIR 1920x1080, depois blur forte.
    Foreground: imagem escalonada para CABER em 1920x1080 (aspect ratio mantido),
                colada centralizada sobre o background.

    Com a santa no centro horizontal: o crop automático do YouTube para 9:16
    (607px centrais de 1920px) mostra a santa sem cortar.
    """
    img = Image.open(src).convert("RGB")
    iw, ih = img.size

    # Background — escala para cobrir, crop central, blur
    scale_bg = max(w / iw, h / ih)
    bg_w = round(iw * scale_bg)
    bg_h = round(ih * scale_bg)
    bg   = img.resize((bg_w, bg_h), Image.LANCZOS)
    left = (bg_w - w) // 2
    top  = (bg_h - h) // 2
    bg   = bg.crop((left, top, left + w, top + h))
    bg   = bg.filter(ImageFilter.GaussianBlur(radius=28))

    # Foreground — escala para caber (letterbox), cola centralizada
    scale_fg = min(w / iw, h / ih)
    fg_w = round(iw * scale_fg)
    fg_h = round(ih * scale_fg)
    fg   = img.resize((fg_w, fg_h), Image.LANCZOS)
    x    = (w - fg_w) // 2
    y    = (h - fg_h) // 2
    bg.paste(fg, (x, y))

    dest.parent.mkdir(parents=True, exist_ok=True)
    bg.save(str(dest), "JPEG", quality=88)


# ─── Criação do vídeo slideshow ─────────────────────────────────────────

def criar_slideshow(imagens: list[Path], saida: Path):
    """Encoda vídeo mudo 1920x1080 com keyframe a cada 2s (compatível com stream copy)."""
    if saida.exists():
        print(f"  {saida.name} já existe — pulando.")
        return

    concat = saida.with_suffix(".concat.txt")
    linhas = ["ffconcat version 1.0"]
    for img in imagens:
        linhas.append(f"file '{img.resolve()}'")
        linhas.append(f"duration {SEG_POR_IMAGEM}")
    # Última entrada sem duration fecha o concat corretamente
    linhas.append(f"file '{imagens[-1].resolve()}'")
    concat.write_text("\n".join(linhas))

    tmp = saida.with_suffix(".tmp.mp4")
    cmd = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0", "-i", str(concat),
        "-vf", f"scale={TARGET_W}:{TARGET_H},setsar=1,fps=30",
        "-c:v", "libx264", "-preset", "faster", "-crf", "22",
        "-g", "60", "-keyint_min", "30",
        "-pix_fmt", "yuv420p",
        "-an",
        str(tmp),
    ]

    print(f"  FFmpeg: {saida.name} ({len(imagens)} imagens × {SEG_POR_IMAGEM}s)...", flush=True)
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
    concat.unlink(missing_ok=True)

    if result.returncode != 0:
        tmp.unlink(missing_ok=True)
        print(f"  [ERRO] FFmpeg:\n{result.stderr[-400:]}")
        raise RuntimeError(f"FFmpeg falhou para {saida.name}")

    tmp.rename(saida)
    mb = saida.stat().st_size // (1024 * 1024)
    print(f"  ✅ {saida.name} pronto ({mb} MB)")


# ─── Main ───────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print(f"gerar_videos_base.py — {VIDEO_PREFIX.upper()} — {NUM_VIDEOS} vídeos")
    print(f"Pasta Drive: {DRIVE_FOLDER_ID}")
    print("=" * 60)

    DIR_SAIDA.mkdir(parents=True, exist_ok=True)

    drive = get_drive()
    todas = listar_imagens(drive, DRIVE_FOLDER_ID)

    if not todas:
        print("[ERRO] Nenhuma imagem encontrada na pasta Drive.")
        sys.exit(1)

    random.shuffle(todas)
    total_videos = min(NUM_VIDEOS, math.ceil(len(todas) / IMG_POR_VIDEO))
    print(f"Criando {total_videos} vídeos (max {IMG_POR_VIDEO} imagens cada)...")

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        criados = 0

        for v in range(total_videos):
            batch = todas[v * IMG_POR_VIDEO : (v + 1) * IMG_POR_VIDEO]
            if len(batch) < 10:
                print(f"  Lote {v+1}: {len(batch)} imagens — mínimo 10, pulando.")
                break

            print(f"\n── Vídeo {v+1}/{total_videos} ({len(batch)} imagens) ──")

            # Baixa e processa imagens
            imgs_proc = []
            for i, f in enumerate(batch):
                ext  = Path(f["name"]).suffix.lower() or ".jpg"
                raw  = tmp / f"raw_{v:02d}_{i:03d}{ext}"
                proc = tmp / f"proc_{v:02d}_{i:03d}.jpg"
                try:
                    baixar_imagem(drive, f["id"], raw)
                    blur_fill(raw, proc)
                    imgs_proc.append(proc)
                except Exception as e:
                    print(f"  [WARN] {f['name']}: {e}")

            if len(imgs_proc) < 10:
                print("  Menos de 10 imagens processadas — lote pulado.")
                continue

            ts    = datetime.datetime.utcnow().strftime("%Y%m%d")
            saida = DIR_SAIDA / f"{VIDEO_PREFIX}_{ts}_{v+1:02d}.mp4"
            try:
                criar_slideshow(imgs_proc, saida)
                criados += 1
            except Exception as e:
                print(f"  [ERRO] vídeo {v+1}: {e}")

    print(f"\n{'='*60}")
    print(f"Concluído: {criados}/{total_videos} vídeos em {DIR_SAIDA}/")
    if criados == 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
