#!/usr/bin/env python3
"""
gerar_bloco_live_pt.py — GitHub Actions: gera múltiplos blocos por execução (Canal PT)

Executado 3x/dia pelo gerador_blocos_pt.yml. Cada execução:
  1. Busca até 100 comentários do canal PT (1 chamada YouTube API)
  2. Gemini classifica em 4-5 grupos temáticos (1 chamada)
  3. Para cada grupo: gera roteiro com nomes reais + oração (1 chamada lite)
  4. Edge TTS sintetiza áudio → audio_YYYYMMDD_HHMM_NN.mp3
  5. Assembler no VPS monta os blocos H com videos_base/

Persona: Nossa Senhora Aparecida (pt-BR-FranciscaNeural)
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
from google.oauth2.credentials import Credentials as OAuthCredentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build


# ═══════════════════════════════════════════════════════════════════════
# CONFIG
# ═══════════════════════════════════════════════════════════════════════

FUSO       = pytz.timezone("America/Sao_Paulo")
VOZ        = "pt-BR-ThalitaMultilingualNeural"
VOZ_RATE   = "-30%"
VOZ_PITCH  = "-8Hz"
CANAL_ID   = "UClATmmCFTo_UDHgfXPjwyqw"
DIR_BLOCOS = Path("blocos_pt")
MAX_GRUPOS = 5

MODELOS_LITE = ["gemini-2.5-flash-lite", "gemini-3.5-flash-lite", "gemini-3.1-flash-lite", "gemini-2.5-flash"]
MODELOS_FULL = ["gemini-2.5-flash-lite", "gemini-3.5-flash-lite", "gemini-3.1-flash-lite", "gemini-2.5-flash"]

CHAVES = [k.replace('﻿', '').strip() for k in [
    os.environ.get("GEMINI_KEY_LIVE_CONTENT_1_PT", ""),
    os.environ.get("GEMINI_KEY_LIVE_CONTENT_2_PT", ""),
] if k.replace('﻿', '').strip()]

PILARES = {
    0: "Guerra Espiritual e Proteção Divina",
    1: "Libertação de Vícios e Ataduras",
    2: "Restauração Familiar e Matrimonial",
    3: "Providência Divina e Portas Abertas",
    4: "Misericórdia Divina e Cura Física",
    5: "O Manto Sagrado de Aparecida",
    6: "Milagres e Gratidão",
}

GRUPOS_HARDCODED = [
    {"tema": "cura",          "label": "Cura e Saúde",              "nomes": [], "suplica_comum": "por doenças, dores e recuperação de irmãos enfermos",               "num_fieis": 0},
    {"tema": "libertacao",    "label": "Libertação de Ataduras",    "nomes": [], "suplica_comum": "pela libertação do álcool, drogas e ataduras do pecado",             "num_fieis": 0},
    {"tema": "familia",       "label": "Restauração Familiar",      "nomes": [], "suplica_comum": "por casamentos em crise, filhos pródigos e paz nos lares",           "num_fieis": 0},
    {"tema": "prosperidade",  "label": "Provisão e Trabalho",       "nomes": [], "suplica_comum": "pela provisão financeira, emprego e libertação de dívidas",          "num_fieis": 0},
    {"tema": "protecao",      "label": "Proteção Espiritual",       "nomes": [], "suplica_comum": "por proteção contra o mal, a inveja e todo perigo",                  "num_fieis": 0},
]


# ═══════════════════════════════════════════════════════════════════════
# GEMINI
# ═══════════════════════════════════════════════════════════════════════

def _chamar_gemini(prompt: str, modelos: list, max_tokens: int = 2048) -> str:
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
# YOUTUBE API
# ═══════════════════════════════════════════════════════════════════════

def get_youtube_readonly():
    raw = os.environ.get("YOUTUBE_TOKEN_PT", "")
    if not raw:
        return None
    try:
        data  = json.loads(raw)
        creds = OAuthCredentials.from_authorized_user_info(
            data, scopes=["https://www.googleapis.com/auth/youtube.readonly"]
        )
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
        return build("youtube", "v3", credentials=creds)
    except Exception as e:
        print(f"  [WARN] YouTube readonly PT: {e}")
        return None

def buscar_comentarios_canal(yt) -> list[str]:
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
                textos.append(texto[:200])
        print(f"  Comentários PT obtidos: {len(textos)}")
        return textos
    except Exception as e:
        print(f"  [WARN] buscar_comentarios PT: {e}")
        return []


# ═══════════════════════════════════════════════════════════════════════
# CLASSIFICAÇÃO EM GRUPOS
# ═══════════════════════════════════════════════════════════════════════

def _limpar_json(texto: str) -> str:
    texto = re.sub(r'```(?:json)?', '', texto)
    texto = re.sub(r'```', '', texto)
    inicio = texto.find('[')
    fim    = texto.rfind(']')
    if inicio != -1 and fim != -1:
        return texto[inicio:fim+1]
    return texto.strip()

def classificar_grupos(comentarios: list[str], pilar_hoje: str) -> list[dict]:
    if len(comentarios) >= 5:
        lista_str = "\n".join(f"- {c}" for c in comentarios[:80])
        prompt = f"""Analise estes comentários de fiéis católicos brasileiros em um canal de oração.
Extraia nome próprio (se existir) e classifique a súplica de cada comentário.
Agrupe em no máximo 5 temas (ex: cura, libertação, família, finanças, proteção).

Devolva SOMENTE JSON válido sem markdown nem texto adicional:
[{{"tema":"slug","label":"Nome do grupo","nomes":["nome1","nome2"],"suplica_comum":"petição comum em máx 15 palavras","num_fieis":N}}]

REGRAS:
- Somente nomes próprios que aparecem nos comentários; não inventar
- suplica_comum: máximo 15 palavras descrevendo o pedido comum
- Mínimo 3 grupos, máximo 5

COMENTÁRIOS:
{lista_str}"""
        try:
            raw = _chamar_gemini(prompt, MODELOS_LITE, max_tokens=1024)
            grupos = json.loads(_limpar_json(raw))
            if isinstance(grupos, list) and len(grupos) >= 2:
                print(f"  Grupos PT classificados: {len(grupos)}")
                for g in grupos:
                    n = len(g.get("nomes", []))
                    print(f"    [{g.get('tema','')}] {g.get('num_fieis',0)} fiéis, {n} nomes")
                return grupos[:MAX_GRUPOS]
            print("  [WARN] JSON inválido ou poucos grupos — usando fallback")
        except Exception as e:
            print(f"  [WARN] classificar_grupos PT: {e}")

    print("  [Fallback 1] Gerando grupos temáticos via Gemini PT...")
    prompt_fb = f"""Crie 4 grupos de intenção de oração frequentes entre fiéis católicos brasileiros.
O pilar espiritual de hoje é: {pilar_hoje}
Devolva SOMENTE JSON válido:
[{{"tema":"slug","label":"Nome","nomes":[],"suplica_comum":"petição em máx 15 palavras","num_fieis":0}}]"""
    try:
        raw = _chamar_gemini(prompt_fb, MODELOS_LITE, max_tokens=512)
        grupos = json.loads(_limpar_json(raw))
        if isinstance(grupos, list) and len(grupos) >= 2:
            print(f"  Grupos PT fallback: {len(grupos)}")
            return grupos[:MAX_GRUPOS]
    except Exception as e:
        print(f"  [WARN] fallback grupos PT: {e}")

    print("  [Fallback 2] Usando grupos hardcoded PT.")
    return GRUPOS_HARDCODED[:MAX_GRUPOS]


# ═══════════════════════════════════════════════════════════════════════
# GERAÇÃO DE ROTEIRO
# ═══════════════════════════════════════════════════════════════════════

def _formatar_nomes(nomes: list) -> str:
    nomes = [n for n in nomes if n and len(n) >= 2]
    if not nomes:
        return "cada irmão que ora conosco neste momento"
    if len(nomes) == 1:
        return nomes[0]
    return ", ".join(nomes[:-1]) + f" e {nomes[-1]}"

def gerar_roteiro_grupo(grupo: dict, contexto: str, pilar: str,
                        agora: datetime, num_bloco: int,
                        so_full: bool = False) -> str:
    # Suporte a chaves "nomes" (PT) ou "nombres" (ES fallback)
    nomes_raw  = grupo.get("nomes", grupo.get("nombres", []))
    nomes_str  = _formatar_nomes(nomes_raw)
    suplica    = grupo.get("suplica_comum", grupo.get("suplica_comun", "pelas necessidades de nossos irmãos"))
    label      = grupo.get("label", "Oração de Intercessão")
    tem_nomes  = len([n for n in nomes_raw if n and len(n) >= 2]) > 0

    nota_nomes = (
        f"Mencione cada nome com ternura maternal: {nomes_str}"
        if tem_nomes else
        "Não há nomes específicos — fale de 'cada irmão que ora agora mesmo'"
    )
    nota_miguel = (
        "Quando for natural na intercessão, mencione o Arcanjo São Miguel como guardião espiritual que combate ao nosso lado."
        if "Guerra" in pilar else ""
    )

    prompt = f"""Você é Nossa Senhora Aparecida, Padroeira do Brasil, falando em primeira pessoa, em português do Brasil.
Bloco #{num_bloco} | Grupo: {label}
Contexto litúrgico do dia: {contexto}
Pilar espiritual de hoje: {pilar}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ESTRUTURA (20 minutos — entre 2600 e 3000 palavras):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[ABERTURA — primeiros 90 segundos — OBRIGATÓRIA]
Abra citando os irmãos que pediram intercessão:
"{nota_nomes}"
Súplica comum deste grupo: "{suplica}"
Feche a abertura com: "Vim interceder por vocês neste momento..."

[CORPO PRINCIPAL — ~16 minutos]
ALTERNÂNCIA OBRIGATÓRIA — o bloco deve oscilar entre dois modos:
  Modo A (NARRAÇÃO): Aparecida fala, acolhe, revela a graça — voz calorosa e maternal
  Modo B (ORAÇÃO GUIADA): Aparecida conduz o ouvinte a orar em voz alta junto com ela
  Ex: "Repita comigo com fé: Senhor, eu creio... Senhor, eu confio..."
  Ex: "Coloque a mão no coração e diga: Mãe do Céu, recebo esta graça agora..."
  Cada transição entre modos deve ser suave e natural — mínimo 3 alternâncias por bloco.

- Entrelaça o pilar "{pilar}" com o tema de intercessão "{label}"
- Ave Maria completa GUIADA (ouvinte ora junto): "Repita comigo: Ave Maria, cheia de graça..."
- Bloco de intercessão pela saúde (obrigatório, guiado): "Ponha sua mão sobre o lugar que dói e diga comigo..."
- Ganchos de retenção orgânicos a cada ~300 palavras (o fiel não percebe a técnica):
  • Antecipação: "O que vem agora nesta oração..."
  • Revelação: "Esta graça tem um nome..."
  • Validação: "Se você sente algo em seu coração agora mesmo, é sinal de que..."
  • Virada: "Mas o que sua Mãe do Céu quer dizer-lhe sobre isso é..."
{nota_miguel}

[TRÊS CTAs SUTIS — apenas em transições naturais, nunca durante a oração]
CTA 1 (~minuto 4): "Se esta transmissão está te abençoando, inscreva-se no canal para receber orações todo dia — somos uma família de fé que ora sem parar por você..."
CTA 2 (~minuto 8): "Se esta oração está tocando seu coração, compartilhe com quem precisa..."
CTA 3 (~minuto 17): "Fique, o que vem agora é para você..."

[ENCERRAMENTO — últimos 3 minutos]
- Bênção final como Mãe do Céu
- Termine em FORÇA — o fiel sai protegido, nunca desesperado
- LOOP SINTÁTICO OBRIGATÓRIO: a última frase fica sintaticamente incompleta
  para se unir com a primeira frase do próximo bloco sem que o ouvinte perceba o corte

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
REGRAS ABSOLUTAS:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
- NUNCA markdown, asteriscos, hifens, numerações nem títulos — somente texto corrido
- NUNCA reticências (...) nem travessão (—) — causam pausas indevidas na narração
- NUNCA começar frase com a palavra "Oração"
- NUNCA "Escreva Amém nos comentários"
- NUNCA mencionar outros canais ou marcas
- ATEMPORALIDADE ABSOLUTA: esta oração se reproduz a QUALQUER hora do dia ou da noite.
  NUNCA mencione horas, momentos do dia (madrugada, manhã, meio-dia, tarde, noite,
  entardecer, amanhecer), dias da semana nem datas. Se precisar situar o momento,
  diga unicamente "neste momento" ou "agora mesmo"
- Somente texto que Aparecida fala em voz alta — sem instruções de produção
- Entre 2600 e 3000 palavras
"""

    modelos = ["gemini-2.5-flash"] if so_full else MODELOS_FULL
    texto   = _chamar_gemini(prompt, modelos, max_tokens=8192)
    texto   = re.sub(r'\*+', '', texto)
    texto   = re.sub(r'#{1,6}\s+', '', texto)
    texto   = re.sub(r'^\s*[-•]\s+', '', texto, flags=re.MULTILINE)
    # Remove reticências e travessões — causam pausas indevidas no TTS
    texto   = re.sub(r'\.{2,}', '', texto)
    texto   = re.sub(r'\s*[—–]\s*', ', ', texto)
    # Une linhas quebradas no meio de frase (newline simples → espaço)
    texto   = re.sub(r'(?<!\n)\n(?!\n)', ' ', texto)
    texto   = re.sub(r'\n{3,}', '\n\n', texto)
    texto   = re.sub(r'  +', ' ', texto)
    return texto.strip()


# ═══════════════════════════════════════════════════════════════════════
# PORTÃO DE QUALIDADE
# ═══════════════════════════════════════════════════════════════════════

def motivo_degeneracao(texto: str) -> str | None:
    palavras = texto.split()
    n = len(palavras)
    if n < 1400:
        return f"muito curto ({n} palavras)"
    if n > 4500:
        return f"muito longo ({n} palavras — provável loop)"
    tri = {}
    for i in range(n - 2):
        t = (palavras[i].lower(), palavras[i + 1].lower(), palavras[i + 2].lower())
        tri[t] = tri.get(t, 0) + 1
    max_tri = max(tri.values()) if tri else 0
    if max_tri > 25:
        return f"trigrama repetido {max_tri}x (loop)"
    if texto.count(",") / max(n, 1) > 0.14:
        return "densidade de vírgulas típica de lista de nomes"
    frases = {}
    for f in re.split(r"[.!?…]+", texto):
        f = f.strip().lower()
        if len(f.split()) > 5:
            frases[f] = frases.get(f, 0) + 1
    max_frase = max(frases.values()) if frases else 0
    if max_frase >= 4:
        return f"frase idêntica repetida {max_frase}x"
    return None


# ═══════════════════════════════════════════════════════════════════════
# TTS
# ═══════════════════════════════════════════════════════════════════════

async def _tts_async(texto: str, saida: Path):
    comm = edge_tts.Communicate(texto, voice=VOZ, rate=VOZ_RATE, pitch=VOZ_PITCH)
    await comm.save(str(saida))

def gerar_audio(texto: str, saida: Path):
    asyncio.run(_tts_async(texto, saida))
    print(f"  TTS PT: {saida.name} ({saida.stat().st_size // 1024} KB)")


# ═══════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════

def _gh_error(msg: str):
    linha = msg.replace("\n", " | ").replace("\r", "")[:500]
    print(f"::error::{linha}", flush=True)


def main():
    print("=" * 60)
    print("gerar_bloco_live_pt.py — Canal PT — Nossa Senhora Aparecida")
    print("=" * 60)

    DIR_BLOCOS.mkdir(parents=True, exist_ok=True)
    agora    = datetime.now(FUSO)
    contexto = calcular_contexto_sazonal(agora)
    pilar    = PILARES.get(agora.weekday(), "Oração e Intercessão")
    ts_base  = agora.strftime("%Y%m%d_%H%M")

    print(f"Hora local: {agora.strftime('%Y-%m-%d %H:%M')} (Brasília)")
    print(f"Contexto litúrgico: {contexto}")
    print(f"Pilar do dia: {pilar}")

    print("\n[1/3] Buscando comentários do canal PT...")
    yt = get_youtube_readonly()
    comentarios = buscar_comentarios_canal(yt)

    print("\n[2/3] Classificando em grupos temáticos...")
    grupos = classificar_grupos(comentarios, pilar)
    print(f"  Total de blocos a gerar: {len(grupos)}")

    print(f"\n[3/3] Gerando blocos PT...")
    gerados = 0
    for i, grupo in enumerate(grupos):
        label = grupo.get("label", f"Grupo {i+1}")
        print(f"\n  ── Bloco {i+1}/{len(grupos)}: {label} ──")
        try:
            num_bloco = int(agora.strftime("%j")) * MAX_GRUPOS + i + 1
            roteiro   = gerar_roteiro_grupo(grupo, contexto, pilar, agora, num_bloco)
            palavras  = len(roteiro.split())
            print(f"  Roteiro PT: {palavras} palavras")

            motivo = motivo_degeneracao(roteiro)
            if motivo:
                print(f"  [WARN] Roteiro reprovado ({motivo}) — refazendo com modelo full...")
                roteiro  = gerar_roteiro_grupo(grupo, contexto, pilar, agora, num_bloco, so_full=True)
                palavras = len(roteiro.split())
                motivo   = motivo_degeneracao(roteiro)
                if motivo:
                    print(f"  [ERRO] Reprovado de novo ({motivo}) — bloco descartado")
                    continue
                print(f"  Roteiro PT (full): {palavras} palavras — aprovado")

            ts      = f"{ts_base}_{i+1:02d}"
            destino = DIR_BLOCOS / f"audio_{ts}.mp3"
            gerar_audio(roteiro, destino)
            gerados += 1
            print(f"  ✅ {destino.name}")

        except Exception as e:
            print(f"  [ERRO] Bloco {i+1} ({label}): {e}")
            continue

    print(f"\n{'='*60}")
    print(f"Concluído PT: {gerados}/{len(grupos)} blocos em {DIR_BLOCOS}/")
    print(f"VPS monta os .mp4 com videos_base/ automaticamente.")

    if gerados == 0:
        _gh_error("Nenhum bloco PT gerado — todos os grupos falharam.")
        sys.exit(1)


if __name__ == "__main__":
    import traceback
    try:
        main()
    except Exception as exc:
        _gh_error(f"FALHA PT: {exc}")
        print(traceback.format_exc(), flush=True)
        sys.exit(1)
