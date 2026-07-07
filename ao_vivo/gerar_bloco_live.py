#!/usr/bin/env python3
"""
gerar_bloco_live.py — GitHub Actions: gera múltiplos blocos por execução

Executado 3x/dia pelo gerador_blocos_es.yml. Cada execução:
  1. Busca até 100 comentários do canal ES (1 chamada YouTube API)
  2. Gemini Lite classifica em 4-5 grupos temáticos (1 chamada)
  3. Para cada grupo: gera roteiro com nomes reais + oração grossa (1 chamada lite)
  4. Edge TTS sintetiza áudio → audio_YYYYMMDD_HHMM_NN.mp3
  5. Assembler no VPS monta os blocos H com videos_base/

Resultado: 4-5 áudios por execução × 3x/dia = ~15 blocos/dia = ~7,5h de conteúdo.
"""

import os
import sys
import json
import random
import asyncio
import re
from datetime import datetime
from pathlib import Path

import pytz
import edge_tts
from google import genai
from google.genai import types as genai_types
from google.oauth2.service_account import Credentials as SACredentials
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials as OAuthCredentials
from googleapiclient.discovery import build


# ═══════════════════════════════════════════════════════════════════════
# CONFIG
# ═══════════════════════════════════════════════════════════════════════

FUSO       = pytz.timezone("America/Mexico_City")
VOZ        = "es-MX-DaliaNeural"
VOZ_RATE   = "-20%"
VOZ_PITCH  = "-10Hz"
CANAL_ID   = "UCyPGsztvMnUhDeoI_6H4bsA"
DIR_BLOCOS = Path("blocos")
MAX_GRUPOS = 5   # máximo de blocos por execução (controla timeout do Actions)

# Lite para tarefas curtas (classificação, fallback); full para roteiros longos
MODELOS_LITE = ["gemini-2.5-flash-lite", "gemini-2.0-flash-lite"]
MODELOS_FULL = ["gemini-2.5-flash-lite", "gemini-2.5-flash"]   # lite-first

CHAVES = [k for k in [
    os.environ.get("GEMINI_KEY_LIVE_CONTENT_1", ""),
    os.environ.get("GEMINI_KEY_LIVE_CONTENT_2", ""),
    os.environ.get("GEMINI_API_KEY", ""),
] if k]

PILARES = {
    0: "Guerra Espiritual y Protección Divina",
    1: "Liberación de Vicios y Ataduras",
    2: "Restauración Familiar y Matrimonial",
    3: "Providencia Divina y Puertas Abiertas",
    4: "Misericordia Divina y Sanación Física",
    5: "El Manto Sagrado de Guadalupe — La Morenita",
    6: "Milagros y Gratitud",
}

# Fallback total (sem nenhuma API disponível)
GRUPOS_HARDCODED = [
    {"tema": "sanacion",     "label": "Sanación y Salud",         "nombres": [], "suplica_comun": "por enfermedades, dolores y recuperación de nuestros hermanos enfermos",    "num_fieles": 0},
    {"tema": "liberacion",   "label": "Liberación de Ataduras",   "nombres": [], "suplica_comun": "por la liberación del alcohol, las drogas y las ataduras del pecado",       "num_fieles": 0},
    {"tema": "familia",      "label": "Restauración Familiar",    "nombres": [], "suplica_comun": "por matrimonios en crisis, hijos pródigos y paz en los hogares",            "num_fieles": 0},
    {"tema": "prosperidad",  "label": "Provisión y Trabajo",      "nombres": [], "suplica_comun": "por la provisión económica, empleo y liberación de deudas",                "num_fieles": 0},
    {"tema": "proteccion",   "label": "Protección Espiritual",    "nombres": [], "suplica_comun": "por protección contra el mal, la envidia y todo peligro",                  "num_fieles": 0},
]


# ═══════════════════════════════════════════════════════════════════════
# GEMINI — chamada unificada
# ═══════════════════════════════════════════════════════════════════════

def _chamar_gemini(prompt: str, modelos: list, max_tokens: int = 2048) -> str:
    """Itera chaves × modelos até obter resposta. Lança RuntimeError se tudo falhar."""
    for chave in CHAVES:
        for modelo in modelos:
            try:
                client = genai.Client(api_key=chave)
                resp = client.models.generate_content(
                    model=modelo,
                    contents=prompt,
                    config=genai_types.GenerateContentConfig(max_output_tokens=max_tokens),
                )
                return resp.text.strip()
            except Exception as e:
                print(f"  [WARN] {modelo} [{chave[-6:]}]: {str(e)[:80]}")
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
    p = _pascoa(ano)
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
# YOUTUBE API
# ═══════════════════════════════════════════════════════════════════════

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
        print(f"  [WARN] YouTube readonly: {e}")
        return None

def buscar_comentarios_canal(yt) -> list[str]:
    """Busca até 100 comentários por relevância. Retorna textos brutos."""
    if not yt:
        return []
    try:
        resp = yt.commentThreads().list(
            part="snippet",
            allThreadsRelatedToChannelId=CANAL_ID,
            maxResults=100,
            order="relevance",
        ).execute()
        textos = []
        for item in resp.get("items", []):
            s = item["snippet"]["topLevelComment"]["snippet"]
            texto = s.get("textOriginal", "").strip()
            if texto and len(texto) > 10:
                textos.append(texto[:200])  # trunca comentários longos
        print(f"  Comentários obtidos: {len(textos)}")
        return textos
    except Exception as e:
        print(f"  [WARN] buscar_comentarios: {e}")
        return []


# ═══════════════════════════════════════════════════════════════════════
# CLASSIFICAÇÃO EM GRUPOS — 1 chamada Gemini Lite
# ═══════════════════════════════════════════════════════════════════════

def _limpar_json(texto: str) -> str:
    """Remove markdown e extrai JSON puro."""
    texto = re.sub(r'```(?:json)?', '', texto)
    texto = re.sub(r'```', '', texto)
    inicio = texto.find('[')
    fim = texto.rfind(']')
    if inicio != -1 and fim != -1:
        return texto[inicio:fim+1]
    return texto.strip()

def classificar_grupos(comentarios: list[str], pilar_hoje: str) -> list[dict]:
    """
    Converte comentários brutos em grupos temáticos via 1 chamada Gemini Lite.
    Fallback 1: Gemini gera grupos sem comentários (1 chamada lite).
    Fallback 2: GRUPOS_HARDCODED (sem nenhuma chamada).
    """
    if len(comentarios) >= 5:
        lista_str = "\n".join(f"- {c}" for c in comentarios[:80])
        prompt = f"""Analiza estos comentarios de fieles católicos hispanos en un canal de oración.
Extrae nombre propio (si existe) y clasifica la súplica de cada comentario.
Agrupa en máximo 5 temas (ej: sanación, liberación, familia, economía, protección).

Devuelve SOLO JSON válido sin markdown ni texto adicional:
[{{"tema":"slug","label":"Nombre del grupo","nombres":["nombre1","nombre2"],"suplica_comun":"petición común en max 15 palabras","num_fieles":N}}]

REGLAS:
- Solo nombres propios que aparecen en los comentarios; no inventar
- suplica_comun: máximo 15 palabras describiendo el pedido común
- Mínimo 3 grupos, máximo 5

COMENTARIOS:
{lista_str}"""
        try:
            raw = _chamar_gemini(prompt, MODELOS_LITE, max_tokens=1024)
            grupos = json.loads(_limpar_json(raw))
            if isinstance(grupos, list) and len(grupos) >= 2:
                print(f"  Grupos classificados: {len(grupos)}")
                for g in grupos:
                    n = len(g.get("nombres", []))
                    print(f"    [{g.get('tema','')}] {g.get('num_fieles',0)} fiéis, {n} nomes")
                return grupos[:MAX_GRUPOS]
            print("  [WARN] JSON inválido ou poucos grupos — usando fallback")
        except Exception as e:
            print(f"  [WARN] classificar_grupos: {e}")

    # Fallback 1: Gemini gera grupos temáticos sem comentários reais
    print("  [Fallback 1] Gerando grupos temáticos via Gemini...")
    prompt_fb = f"""Crea 4 grupos de intención de oración frecuentes entre fieles latinoamericanos.
El pilar espiritual de hoy es: {pilar_hoje}
Devuelve SOLO JSON válido:
[{{"tema":"slug","label":"Nombre","nombres":[],"suplica_comun":"petición en max 15 palabras","num_fieles":0}}]"""
    try:
        raw = _chamar_gemini(prompt_fb, MODELOS_LITE, max_tokens=512)
        grupos = json.loads(_limpar_json(raw))
        if isinstance(grupos, list) and len(grupos) >= 2:
            print(f"  Grupos fallback: {len(grupos)}")
            return grupos[:MAX_GRUPOS]
    except Exception as e:
        print(f"  [WARN] fallback grupos: {e}")

    # Fallback 2: hardcoded
    print("  [Fallback 2] Usando grupos hardcoded.")
    return GRUPOS_HARDCODED[:MAX_GRUPOS]


# ═══════════════════════════════════════════════════════════════════════
# GERAÇÃO DE ROTEIRO — 1 chamada Gemini Lite por bloco
# ═══════════════════════════════════════════════════════════════════════

def _periodo(hora: int) -> str:
    if hora < 6:   return "de la madrugada"
    if hora < 12:  return "de la mañana"
    if hora < 14:  return "del mediodía"
    if hora < 19:  return "de la tarde"
    return "de la noche"

def _formatar_nomes(nomes: list) -> str:
    nomes = [n for n in nomes if n and len(n) >= 2]
    if not nomes:
        return "cada hermano que ora con nosotros en este momento"
    if len(nomes) == 1:
        return nomes[0]
    return ", ".join(nomes[:-1]) + f" y {nomes[-1]}"

def gerar_roteiro_grupo(grupo: dict, contexto: str, pilar: str,
                        agora: datetime, num_bloco: int) -> str:
    hora = agora.hour
    periodo = _periodo(hora)
    nomes_str = _formatar_nomes(grupo.get("nombres", []))
    suplica   = grupo.get("suplica_comun", "por las necesidades de nuestros hermanos")
    label     = grupo.get("label", "Oración de Intercesión")
    tem_nomes = len([n for n in grupo.get("nombres", []) if n and len(n) >= 2]) > 0

    nota_nomes = (
        f"Menciona cada nombre con ternura maternal: {nomes_str}"
        if tem_nomes else
        "No hay nombres específicos — habla de 'cada hermano que ora ahora mismo'"
    )

    prompt = f"""Eres Nuestra Señora de Guadalupe, La Morenita del Tepeyac, hablando en primera persona.
Hora: {agora.strftime('%H:%M')} {periodo} | Bloco #{num_bloco} | Grupo: {label}
Contexto litúrgico del día: {contexto}
Pilar espiritual de hoy: {pilar}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ESTRUCTURA (27 minutos — entre 3200 y 3600 palabras):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[APERTURA — primeros 90 segundos — OBLIGATORIA]
Abre citando a los hermanos que pidieron intercesión:
"{nota_nomes}"
Súplica común de este grupo: "{suplica}"
Cierra la apertura con: "Vine a interceder por ustedes {periodo}..."

[CUERPO PRINCIPAL — ~22 minutos]
- Voz cálida y maternal — autoridad espiritual suave
- Entreteje el pilar "{pilar}" con el tema de intercessão "{label}"
- Ave María completa con pausa después de Jesús:
  "...y bendito es el fruto de tu vientre Jesús... Santa María, Madre de Dios..."
- Bloco de intercesión por la salud (obligatorio): "Pongo mis manos sobre todo aquel que sufre..."
- Ganchos de retención orgánicos cada ~350 palabras (el fiel no percibe la técnica):
  • Antecipación: "Lo que viene ahora en esta oración..."
  • Revelación: "Esta gracia tiene un nombre..."
  • Validación: "Si sientes algo en tu corazón ahora mismo, es señal de que..."
  • Virada: "Pero lo que tu Madre del Cielo quiere decirte sobre esto es..."

[DOS CTAs SUTILES — solo en transiciones naturales, nunca durante la oración]
CTA 1 (~minuto 10): "Si esta oración está tocando tu corazón, compártela con quien la necesita..."
CTA 2 (~minuto 22): "Quédate, lo que viene ahora es para ti..."

[CIERRE — últimos 3 minutos]
- Bendición final como Madre del Cielo
- Termina en FUERZA — el fiel sale protegido, nunca desesperado
- LOOP SINTÁTICO OBLIGATORIO: la última frase queda sintáticamente incompleta
  para unirse con la primera frase del próximo bloco sin que el oyente perciba el corte

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
REGLAS ABSOLUTAS:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
- NUNCA markdown, asteriscos, guiones, numeraciones ni títulos — solo texto corrido
- NUNCA comenzar frase con la palabra "Oración"
- NUNCA "Escribe Amén en los comentarios"
- NUNCA mencionar otros canales o marcas
- Solo texto que Guadalupe habla en voz alta — sin instrucciones de producción
- Entre 3200 y 3600 palabras
"""

    texto = _chamar_gemini(prompt, MODELOS_FULL, max_tokens=8192)
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
    print(f"  TTS: {saida.name} ({saida.stat().st_size // 1024} KB)")


# ═══════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════

def _gh_error(msg: str):
    linha = msg.replace("\n", " | ").replace("\r", "")[:500]
    print(f"::error::{linha}", flush=True)


def main():
    print("=" * 60)
    print("gerar_bloco_live.py — Canal ES — Múltiplos Blocos")
    print("=" * 60)

    DIR_BLOCOS.mkdir(parents=True, exist_ok=True)
    agora    = datetime.now(FUSO)
    contexto = calcular_contexto_sazonal(agora)
    pilar    = PILARES.get(agora.weekday(), "Oración e Intercesión")
    ts_base  = agora.strftime("%Y%m%d_%H%M")

    print(f"Hora local: {agora.strftime('%Y-%m-%d %H:%M')} (Mexico City)")
    print(f"Contexto litúrgico: {contexto}")
    print(f"Pilar do dia: {pilar}")

    # ── 1. Comentários (1 chamada YouTube API) ────────────────────────
    print("\n[1/3] Buscando comentários do canal ES...")
    yt = get_youtube_readonly()
    comentarios = buscar_comentarios_canal(yt)

    # ── 2. Classificar em grupos (1 chamada Gemini Lite) ─────────────
    print("\n[2/3] Classificando em grupos temáticos...")
    grupos = classificar_grupos(comentarios, pilar)
    print(f"  Total de blocos a gerar: {len(grupos)}")

    # ── 3. Roteiro + TTS para cada grupo (1 chamada Gemini por bloco) ─
    print(f"\n[3/3] Gerando blocos...")
    gerados = 0
    for i, grupo in enumerate(grupos):
        label = grupo.get("label", f"Grupo {i+1}")
        print(f"\n  ── Bloco {i+1}/{len(grupos)}: {label} ──")
        try:
            num_bloco = int(agora.strftime("%j")) * MAX_GRUPOS + i + 1
            roteiro = gerar_roteiro_grupo(grupo, contexto, pilar, agora, num_bloco)
            palavras = len(roteiro.split())
            print(f"  Roteiro: {palavras} palavras")

            if palavras < 1800:
                print(f"  [WARN] Roteiro muito curto — pulando")
                continue

            ts      = f"{ts_base}_{i+1:02d}"
            destino = DIR_BLOCOS / f"audio_{ts}.mp3"
            gerar_audio(roteiro, destino)
            gerados += 1
            print(f"  ✅ {destino.name}")

        except Exception as e:
            print(f"  [ERRO] Bloco {i+1} ({label}): {e}")
            continue

    # ── Resumo ────────────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print(f"Concluído: {gerados}/{len(grupos)} blocos em blocos/")
    print(f"VPS monta os .mp4 com videos_base/ automaticamente.")

    if gerados == 0:
        _gh_error("Nenhum bloco gerado — todos os grupos falharam.")
        sys.exit(1)


if __name__ == "__main__":
    import traceback
    try:
        main()
    except Exception as exc:
        _gh_error(f"FALHA: {exc}")
        print(traceback.format_exc(), flush=True)
        sys.exit(1)
