#!/usr/bin/env python3
"""
renomear_vods_historico.py
Renomeia VODs existentes de lives e os insere em playlists temáticas.
Rodado uma vez via GitHub Actions.

Env vars:
  CANAL                 — ES ou PT
  YOUTUBE_TOKEN_ES      — JSON do token OAuth ES
  YOUTUBE_TOKEN_PT      — JSON do token OAuth PT
  GOOGLE_CREDENTIALS    — service account JSON (para criação de playlists)
"""

import os, json, re, time, sys
from datetime import datetime
import pytz
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

CANAL = os.environ.get("CANAL", "ES").upper()

CONFIGS = {
    "ES": {
        "token_env": "YOUTUBE_TOKEN_ES",
        "fuso": "America/Mexico_City",
        "playlists": {
            0: "La Morenita — Protección y Guerra Espiritual",
            1: "La Morenita — Liberación de Ataduras",
            2: "La Morenita — Restauración Familiar",
            3: "La Morenita — Providencia y Puertas Abiertas",
            4: "La Morenita — Sanación y Curación",
            5: "La Morenita — El Manto Sagrado",
            6: "La Morenita — Milagros y Gratitud",
        },
        "temas": {
            0: "La Morenita — Protección y Guerra Espiritual",
            1: "La Morenita — Liberación de Ataduras",
            2: "La Morenita — Restauración Familiar",
            3: "La Morenita — Providencia y Puertas Abiertas",
            4: "La Morenita — Sanación y Curación",
            5: "La Morenita — El Manto Sagrado",
            6: "La Morenita — Milagros y Gratitud",
        },
        "default_lang": "es",
    },
    "PT": {
        "token_env": "YOUTUBE_TOKEN_PT",
        "fuso": "America/Sao_Paulo",
        "playlists": {
            0: "Nossa Senhora — Proteção e Guerra Espiritual",
            1: "Nossa Senhora — Libertação de Ataduras",
            2: "Nossa Senhora — Restauração Familiar",
            3: "Nossa Senhora — Providência e Portas Abertas",
            4: "Nossa Senhora — Cura e Misericórdia",
            5: "Nossa Senhora — O Manto de Aparecida",
            6: "Nossa Senhora — Milagres e Gratidão",
        },
        "temas": {
            0: "Nossa Senhora — Proteção e Guerra Espiritual",
            1: "Nossa Senhora — Libertação de Ataduras",
            2: "Nossa Senhora — Restauração Familiar",
            3: "Nossa Senhora — Providência e Portas Abertas",
            4: "Nossa Senhora — Cura e Misericórdia",
            5: "Nossa Senhora — O Manto de Aparecida",
            6: "Nossa Senhora — Milagres e Gratidão",
        },
        "default_lang": "pt",
    },
}

cfg = CONFIGS.get(CANAL)
if not cfg:
    print(f"Canal desconhecido: {CANAL}")
    sys.exit(1)

FUSO = pytz.timezone(cfg["fuso"])

# ── Autenticação OAuth ──────────────────────────────────────────────────
token_raw = os.environ.get(cfg["token_env"], "").lstrip("\xef\xbb\xbf﻿").strip()
if not token_raw:
    print(f"Token {cfg['token_env']} não encontrado.")
    sys.exit(1)

# Extrair apenas o primeiro objeto JSON (elimina conteúdo extra após o fechamento)
try:
    t = json.loads(token_raw)
except json.JSONDecodeError:
    import re as _re
    m = _re.search(r'\{.*\}', token_raw, _re.DOTALL)
    if not m:
        print(f"Token {cfg['token_env']} não é JSON válido.")
        sys.exit(1)
    t = json.loads(m.group())
creds = Credentials(
    token=t.get("access_token") or t.get("token"),
    refresh_token=t.get("refresh_token"),
    token_uri="https://oauth2.googleapis.com/token",
    client_id=t.get("client_id"),
    client_secret=t.get("client_secret"),
)
if creds.expired and creds.refresh_token:
    creds.refresh(Request())

yt = build("youtube", "v3", credentials=creds)


# ── Garantir playlists temáticas ────────────────────────────────────────
def garantir_playlists() -> dict:
    existentes = {}
    token = None
    while True:
        resp = yt.playlists().list(part="snippet", mine=True, maxResults=50, pageToken=token).execute()
        for p in resp.get("items", []):
            existentes[p["snippet"]["title"]] = p["id"]
        token = resp.get("nextPageToken")
        if not token:
            break

    ids = {}
    for weekday, nome in cfg["playlists"].items():
        if nome in existentes:
            ids[str(weekday)] = existentes[nome]
            print(f"  Playlist encontrada: {nome} → {existentes[nome]}")
        else:
            r = yt.playlists().insert(
                part="snippet,status",
                body={
                    "snippet": {"title": nome, "defaultLanguage": cfg["default_lang"]},
                    "status": {"privacyStatus": "public"},
                }
            ).execute()
            ids[str(weekday)] = r["id"]
            print(f"  Playlist CRIADA: {nome} → {r['id']}")
    return ids


# ── Listar VODs de lives concluídas ────────────────────────────────────
def listar_vods_lives():
    """Retorna todos os broadcasts completos (VODs) do canal."""
    vods = []
    token = None
    while True:
        resp = yt.liveBroadcasts().list(
            part="id,snippet,status",
            broadcastStatus="completed",
            maxResults=50,
            pageToken=token,
        ).execute()
        for item in resp.get("items", []):
            vods.append(item)
        token = resp.get("nextPageToken")
        if not token:
            break
    print(f"Total de VODs encontrados: {len(vods)}")
    return vods


# ── Detectar se VOD ainda tem título genérico ───────────────────────────
PATTERN_GENERICO = re.compile(r"🔴|🟢|🔵|EN VIVO|AO VIVO|\bLIVE\b|EN DIRECT|IN DIRETTA|NA ŻYWO", re.IGNORECASE)

def precisa_renomear(titulo: str) -> bool:
    return bool(PATTERN_GENERICO.search(titulo))


# ── Obter itens já na playlist (evita duplicatas) ─────────────────────
def ids_na_playlist(playlist_id: str) -> set:
    ids = set()
    token = None
    while True:
        try:
            resp = yt.playlistItems().list(
                part="snippet",
                playlistId=playlist_id,
                maxResults=50,
                pageToken=token,
            ).execute()
            for item in resp.get("items", []):
                ids.add(item["snippet"]["resourceId"]["videoId"])
            token = resp.get("nextPageToken")
            if not token:
                break
        except Exception:
            break
    return ids


# ── Processar ──────────────────────────────────────────────────────────
print(f"\n=== Renomeação histórica de VODs — Canal {CANAL} ===\n")

print("Garantindo playlists temáticas...")
playlists = garantir_playlists()

print("\nListando VODs de lives...")
vods = listar_vods_lives()

renomeados = 0
ja_ok = 0
erros = 0

for vod in vods:
    vid = vod["id"]
    snip = vod["snippet"]
    titulo_atual = snip.get("title", "")

    # Determinar data/hora local a partir de actualStartTime ou publishedAt
    dt_str = snip.get("actualStartTime") or snip.get("publishedAt") or snip.get("scheduledStartTime", "")
    try:
        dt_utc = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        dt_local = dt_utc.astimezone(FUSO)
    except Exception:
        dt_local = datetime.now(FUSO)

    weekday = dt_local.weekday()
    tema = cfg["temas"][weekday]
    titulo_novo = f"{tema} · {dt_local.strftime('%d/%m %Hh')}"[:100]
    playlist_id = playlists.get(str(weekday))

    if precisa_renomear(titulo_atual):
        print(f"\n[{vid}] Renomeando...")
        print(f"  DE: {titulo_atual[:80]}")
        print(f"  PARA: {titulo_novo}")
        try:
            # Buscar snippet completo do vídeo para não sobrescrever campos
            v_resp = yt.videos().list(part="snippet", id=vid).execute()
            if not v_resp.get("items"):
                print(f"  AVISO: vídeo {vid} não encontrado via videos().list — pulando")
                erros += 1
                continue
            v_snip = v_resp["items"][0]["snippet"]
            v_snip["title"] = titulo_novo
            yt.videos().update(
                part="snippet",
                body={"id": vid, "snippet": v_snip},
            ).execute()
            renomeados += 1
            time.sleep(1)
        except Exception as e:
            print(f"  ERRO ao renomear: {e}")
            erros += 1
    else:
        ja_ok += 1
        print(f"[{vid}] OK (já renomeado): {titulo_atual[:60]}")

    # Adicionar à playlist temática se ainda não estiver lá
    if playlist_id:
        try:
            ids_existentes = ids_na_playlist(playlist_id)
            if vid not in ids_existentes:
                yt.playlistItems().insert(
                    part="snippet",
                    body={"snippet": {
                        "playlistId": playlist_id,
                        "resourceId": {"kind": "youtube#video", "videoId": vid},
                    }},
                ).execute()
                print(f"  → Inserido em playlist temática weekday={weekday}")
                time.sleep(0.5)
            else:
                print(f"  → Já está na playlist temática")
        except Exception as e:
            print(f"  AVISO playlist: {e}")

print(f"\n=== Concluído — Canal {CANAL} ===")
print(f"  Renomeados: {renomeados}")
print(f"  Já OK (título único): {ja_ok}")
print(f"  Erros: {erros}")
