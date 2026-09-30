import os
import sys
import json
import time
import re
import datetime
from google.genai import Client
from google.oauth2.service_account import Credentials
import gspread
from zoneinfo import ZoneInfo
import novenas

# ==============================================================================
# 1. PUXANDO AS CHAVES DO COFRE DO GITHUB
# ==============================================================================
CHAVE_API   = os.environ.get("GEMINI_API_KEY", "")
CHAVE_API_2 = os.environ.get("GEMINI_API_KEY_2", "")
CHAVES_GEMINI = [k for k in [CHAVE_API, CHAVE_API_2] if k]
GOOGLE_JSON = os.environ.get("GOOGLE_CREDENTIALS")

print("🔐 Autenticando no Google Sheets via Service Account...")
credenciais_dict = json.loads(GOOGLE_JSON)
escopos =['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
credenciais = Credentials.from_service_account_info(credenciais_dict, scopes=escopos)
gc = gspread.authorize(credenciais)

client = Client(api_key=CHAVE_API, http_options={'api_version': 'v1'})

def obter_cascata_de_modelos():
    print("📡 Escaneando servidores del Google...")
    try:
        modelos = client.models.list()
        # Lite/8b = cota generosa no tier gratuito. Prioridade máxima.
        lite = [m.name for m in modelos if 'generateContent' in m.supported_generation_methods and 'flash' in m.name and ('lite' in m.name or '8b' in m.name)]
        # Flash regular = fallback de último recurso (cota restrita ~20 RPD)
        flash = [m.name for m in modelos if 'generateContent' in m.supported_generation_methods and 'flash' in m.name and 'lite' not in m.name and '8b' not in m.name]
        melhor_lite = sorted(lite, reverse=True)[0] if lite else 'gemini-2.5-flash-lite'
        m_flash = sorted(flash, reverse=True)[0] if flash else 'gemini-2.5-flash'
        return [melhor_lite, melhor_lite, melhor_lite, melhor_lite, m_flash]
    except: return ['gemini-2.5-flash-lite', 'gemini-2.5-flash-lite', 'gemini-2.5-flash-lite', 'gemini-2.5-flash-lite', 'gemini-2.5-flash']

modelos_cascata = obter_cascata_de_modelos()

def _gerar(modelo, prompt):
    """Tenta cada chave Gemini disponível. Em 429, troca de chave antes de desistir."""
    for chave in CHAVES_GEMINI:
        try:
            c = Client(api_key=chave, http_options={'api_version': 'v1'})
            return c.models.generate_content(model=modelo, contents=prompt).text
        except Exception as e:
            if "429" in str(e) and chave != CHAVES_GEMINI[-1]:
                print(f"[WARN] 429 na chave ...{chave[-6:]}. Tentando chave 2...")
                continue
            raise
    raise RuntimeError("Todas as chaves Gemini falharam.")

# ==============================================================================
# CALENDÁRIO CULTURAL E LITÚRGICO (México / Latino)
# ==============================================================================
def calcular_contexto_sazonal(data_alvo):
    """Retorna contexto especial de datas litúrgicas/culturais para o canal ES."""
    ano = data_alvo.year
    mes = data_alvo.month
    dia = data_alvo.day

    # --- Cálculo da Páscoa (algoritmo gaussiano) ---
    a = ano % 19
    b = ano // 100
    c = ano % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    mes_pascoa = (h + l - 7 * m + 114) // 31
    dia_pascoa = ((h + l - 7 * m + 114) % 31) + 1
    pascoa = datetime.date(ano, mes_pascoa, dia_pascoa)

    # Datas móveis derivadas da Páscoa
    quarta_cinzas  = pascoa - datetime.timedelta(days=46)
    sexta_santa    = pascoa - datetime.timedelta(days=2)
    pentecostes    = pascoa + datetime.timedelta(days=49)
    corpus_christi = pascoa + datetime.timedelta(days=60)

    # Día de las Madres — México: 10 de maio (data fixa)
    dia_das_maes = datetime.date(ano, 5, 10)

    # --- Verificações ---
    if data_alvo == quarta_cinzas:
        return "Hoy es Miércoles de Ceniza, inicio de la Cuaresma. El guión debe reflejar el llamado a la conversión, la penitencia y el ayuno."
    if data_alvo == sexta_santa:
        return "Hoy es Viernes Santo, conmemoración de la Pasión y Muerte de Jesucristo. El guión debe ser profundamente meditativo sobre el sacrificio redentor."
    if data_alvo == pascoa:
        return "¡Hoy es Domingo de Resurrección! El guión debe estar lleno de alegría pascual, victoria sobre la muerte y esperanza de vida eterna."
    if data_alvo == pentecostes:
        return "Hoy es Pentecostés, venida del Espíritu Santo. El guión debe invocar los dones del Espíritu y el fuego de la fe."
    if data_alvo == corpus_christi:
        return "Hoy es Corpus Christi, solemnidad del Cuerpo y Sangre de Cristo. El guión debe meditar sobre la Eucaristía como fuente de vida."
    if data_alvo == dia_das_maes:
        return "Hoy es el Día de las Madres en México. El guión debe honrar a las madres, especialmente a la Virgen de Guadalupe como Madre de todos."

    # Datas fixas
    datas_fixas = {
        (11, 1):  "Hoy es el Día de Todos los Santos. El guión debe invocar la intercesión de los santos y la comunión de los fieles.",
        (11, 2):  "Hoy es el Día de los Muertos (Fieles Difuntos). El guión debe consolar a quienes perdieron seres queridos y encomendar las almas al Señor.",
        (12, 8):  "Hoy es la Inmaculada Concepción de María. El guión debe exaltar la pureza y la gracia de la Virgen desde el primer instante de su existencia.",
        (12, 12): "Hoy es el Día de la Virgen de Guadalupe, Patrona de México y de América Latina. El guión debe celebrar las apariciones a Juan Diego y el amor maternal de la Morenita por su pueblo.",
        (12, 25): "Hoy es Navidad, el nacimiento de Jesucristo. El guión debe irradiar la alegría del Emmanuel, Dios-con-nosotros.",
        (12, 31): "Hoy es Víspera de Año Nuevo. El guión debe mezclar gratitud por el año que termina y esperanza renovada para el que comienza.",
        (1, 1):   "Hoy es Año Nuevo, Solemnidad de María Santísima. El guión debe consagrar el nuevo año a Dios y a la Virgen de Guadalupe.",
    }
    return datas_fixas.get((mes, dia), "")

# ==============================================================================
# 2. CONFIGURAÇÕES DA FÁBRICA E NOVA GRADE (06h e 18h)
# ==============================================================================
ID_PLANILHA = "1KgIjWrLUVlllhlZB1R9fkHGxxZlLsax1aOVGZrYwgnU"

PILARES = {
    0: "Guerra Espiritual y Protección", 1: "Liberación de Vicios y Ataduras", 2: "Restauración Familiar y Matrimonial",
    3: "Providencia y Puertas Abiertas", 4: "Misericordia y Sanación Física", 5: "El Manto de Guadalupe", 6: "Milagros y Gratitud"
}

GRADE_DIARIA = [
    # Slot 06:00 — Novenas (novenas.py). Sem retroatividade; só a partir de novenas.ATIVACAO_06H.
    {"horario": "06:00", "personagem": "Maria", "idioma": "ES", "foco": "Morning consecration to Our Lady: protection, direction and strength for the day that begins.", "periodo": novenas.CFG["periodo"], "ativacao": novenas.ATIVACAO_06H},
    {"horario": "18:00", "personagem": "Maria", "idioma": "ES", "foco": "Atardecer y Noche: Acogimiento maternal, entrega de los problemas, descanso profundo y paz.", "periodo": "en este atardecer"}
]

aba = gc.open_by_key(ID_PLANILHA).worksheet("ES")

# AUTO-LIMPEZA
todas_linhas = aba.get_all_values()
if len(todas_linhas) > 500:
    print("🧹 Planilha pesada. Iniciando Auto-Limpeza...")
    aba.delete_rows(2, 100)
    todas_linhas = aba.get_all_values()

proxima_linha_vazia = len(todas_linhas) + 1

# ==============================================================================
# 3. SCANNER DE BURACOS (IGNORA O PASSADO)
# ==============================================================================
valores_coluna_a = [linha[0].strip() for linha in todas_linhas[1:] if len(linha) > 0]
valores_coluna_b = [linha[1].strip() for linha in todas_linhas[1:] if len(linha) > 1]

dias_existentes = {}
agora_local = datetime.datetime.now(ZoneInfo(novenas.TZ))
hoje = agora_local.date()
limite_passado = hoje - datetime.timedelta(days=2)

for d_str, h_str in zip(valores_coluna_a, valores_coluna_b):
    if d_str and h_str:
        try:
            d_obj = datetime.datetime.strptime(d_str, '%Y-%m-%d').date()
            if d_obj >= limite_passado:
                if d_obj not in dias_existentes: dias_existentes[d_obj] = []
                dias_existentes[d_obj].append(h_str)
        except: pass

meta_estoque = hoje + datetime.timedelta(days=5)

def slot_exigido(v, d):
    """Travas do slot 06:00: sem retroatividade (evita upload público imediato de vídeo atrasado)."""
    if v.get("ativacao") and d < v["ativacao"]:
        return False
    if v["horario"] == "06:00":
        if d < hoje: return False
        if d == hoje and agora_local.hour >= 4: return False
        if novenas.plano_do_dia(d) is None: return False
    return True
data_alvo = None
grade_para_processar =[]

data_check = limite_passado
while data_check <= meta_estoque:
    horarios_presentes = dias_existentes.get(data_check,[])
    faltando = [v for v in GRADE_DIARIA if slot_exigido(v, data_check) and v["horario"] not in horarios_presentes]
    if faltando:
        data_alvo = data_check
        grade_para_processar = faltando
        print(f"⚠️ BURACO ENCONTRADO: Faltam horários no día {data_alvo}.")
        break
    data_check += datetime.timedelta(days=1)

if not data_alvo:
    print(f"✅ ESTOQUE ATINGIDO até {meta_estoque - datetime.timedelta(days=1)}. Dormindo.")
    sys.exit(0)

pilar_do_dia = PILARES[data_alvo.weekday()]
contexto_sazonal = calcular_contexto_sazonal(data_alvo)
print(f"\n📅 DATA ALVO: {data_alvo} | Pilar: {pilar_do_dia}")
if contexto_sazonal:
    print(f"🗓️ CONTEXTO SAZONAL: {contexto_sazonal}")

# ==============================================================================
# 4. PRODUÇÃO EM MASSA (COPYWRITING AVANÇADO)
# ==============================================================================
esperas_exponenciais = [10, 20, 40, 80, 120]

def gerar_novena(data_alvo, plano, contexto_sazonal):
    """Linha da planilha para um dia de novena (festa ou pedido) — rito fixo em novenas.py."""
    C = novenas.CFG
    n = plano["dia"]
    categoria = None
    if plano["tipo"] == "festa":
        f = plano["festa"]
        invocacao = f["invocacao"]
        contexto = (f"This is the '{f['nome']}', preparing for: {f['festa']}. Today is day {n} of 9. "
                    f"INTENTION OF THE DAY (the believer's pain): {novenas.INTENCOES_FESTA[n - 1]}.")
    else:
        categoria = novenas.escolher_tema_pedido(gc.open_by_key(ID_PLANILHA), plano["ciclo_inicio"])
        rotulo, descr = novenas.CATEGORIAS[categoria]
        invocacao = C["invocacao_padrao"]
        contexto = (f"This is the '{rotulo}', a 9-day petition novena to Our Lady ({invocacao}). "
                    f"Single theme of the novena: {descr}. Today is day {n} of 9. {novenas.PROGRESSAO_PEDIDO[n]}")
    if data_alvo.weekday() == 4:
        contexto += " TODAY IS FRIDAY: gently touch on Mercy and Forgiveness."
    if contexto_sazonal:
        contexto += f" Season/feast context: {contexto_sazonal}."
    cta_final = ("Invite them to pray the complete novena in the channel playlist and to keep praying with us live 24 hours."
                 if n == 9 else "Invite them to come back tomorrow morning for the next day of the novena (never say an exact hour).")
    prompt = f"""
    You are an empathetic Catholic spiritual guide, faithful to Church doctrine. Write ONLY the VARIABLE parts of a NOVENA video addressed to {invocacao}.
    WRITE EVERYTHING IN {novenas.LANG_NAME}. Natural, native, devotional language — never translated-sounding.
    The fixed rite (sign of the cross, act of contrition, novena prayer, Our Father, Hail Mary, Glory Be) is ALREADY inserted by the system — DO NOT write those prayers.
    CONTEXT: {contexto}
    Time of day: "{C['periodo']}".

    RULES:
    1. GANCHO (120-180 words) — HOOK 3A: (a) EMPATHIC STATEMENT about the pain of the day's intention, NO direct questions; (b) sensory setting of the morning that begins; (c) announce that today is day {n} of the novena and that {invocacao} has a grace for whoever stays until the end.
    2. REFLEXAO (450-600 words): a short Bible passage (cite book and chapter) linked to the intention, and a warm meditation. Include 1 invisible retention hook (anticipation or partial revelation) without breaking the devotional mood.
    3. SUPLICA (350-500 words): personal first-person supplication for the day's intention; MUST include a block of intercession for health (the sick in the family, physical and emotional healing). Arc: vulnerability → intercession → trust.
    4. ENCERRAMENTO (120-180 words): end in STRENGTH and confidence, never in pleading. {cta_final} Also {C['cta_pista']}. FORBIDDEN: "type Amen" style forced engagement.
    5. PROMESSA (max 40 characters): complement of the title, which already starts with the novena name and the day. Do NOT repeat the novena name. {'Focus on the intention of the day.' if plano['tipo'] == 'festa' else C['promessa_regra']} No quotes, no emoji, no date.
    6. NEVER mention exact hours. Use many ellipses (...) for voice pauses. PLAIN TEXT: no JSON, no asterisks, no brackets, no section titles inside the texts.
    7. FORBIDDEN to mention any saint or devotion other than Our Lady, Jesus and God the Father.

    EXACT FORMAT (keep these English labels, in this order; content in {novenas.LANG_NAME}):
    PROMESSA: ...
    GANCHO: ...
    REFLEXAO: ...
    SUPLICA: ...
    ENCERRAMENTO: ...
    DESC: [3 SEO paragraphs: 1st "Novena — {n}/9" + invitation to the 24h live; 2nd emotional description of the day's intention; 3rd keywords and hashtags including #novena]
    TAGS: [comma-separated tags including the word for novena]
    """
    rotulos = ["PROMESSA", "GANCHO", "REFLEXAO", "SUPLICA", "ENCERRAMENTO", "DESC", "TAGS"]
    def _lab(r): return r"(?:^|\n)[ \t>*_#]*" + r + r"[ \t*_]*:"
    padrao_fim = "|".join(_lab(r) for r in rotulos)
    for i in range(5):
        try:
            texto = _gerar(modelos_cascata[i], prompt)
        except Exception as e:
            print(f"   ⚠️ Gemini: {e}"); time.sleep(esperas_exponenciais[i]); continue
        t = texto.replace("REFLEXÃO", "REFLEXAO").replace("SÚPLICA", "SUPLICA")
        partes = {}
        for r in rotulos:
            m = re.search(_lab(r) + r"\s*(.*?)(?=(?:" + padrao_fim + r")|\Z)", t, re.IGNORECASE | re.DOTALL)
            partes[r] = re.sub(r'[*#\[\]{}]', '', m.group(1)).strip() if m else ""
        palavras = sum(len(partes[k].split()) for k in ["GANCHO", "REFLEXAO", "SUPLICA", "ENCERRAMENTO"])
        if all(partes[k] for k in ["GANCHO", "REFLEXAO", "SUPLICA", "ENCERRAMENTO"]) and palavras >= 700:
            break
        print(f"   ⚠️ Resposta incompleta ({palavras} palavras). Nova tentativa...")
        time.sleep(esperas_exponenciais[i])
    else:
        print("   ❌ Novena não gerada nesta execução — o scanner tenta de novo na próxima.")
        return None
    promessa = partes["PROMESSA"].replace('"', '').strip()[:45]
    titulo = novenas.montar_titulo(plano, promessa, categoria, data_alvo)
    roteiro = novenas.montar_roteiro(plano, partes["GANCHO"], partes["REFLEXAO"], partes["SUPLICA"], partes["ENCERRAMENTO"])
    return [str(data_alvo), "06:00", novenas.STATUS_PRONTO, "MARIA", "ES", novenas.tema_codificado(plano, categoria), titulo, roteiro,
            partes["TAGS"] or "novena", partes["DESC"] or f"Novena {n}/9", "Pending", novenas.texto_thumb(plano)]


for video in grade_para_processar:
    horario, persona, idioma, foco_teologico, periodo = video["horario"], video["personagem"].upper(), video["idioma"], video["foco"], video["periodo"]
    if data_alvo.weekday() == 4:
        foco_teologico += " ENFOQUE: Misericordia y Perdón." if horario == "06:00" else " ENFOQUE: La Pasión de Cristo y el Sacrificio."

    print(f"🎬 PRODUZINDO: {horario} | {persona}")

    if horario == "06:00":
        plano = novenas.plano_do_dia(data_alvo)
        if plano and plano["tipo"] in ("festa", "pedido"):
            nova_linha = gerar_novena(data_alvo, plano, contexto_sazonal)
            if nova_linha:
                try:
                    aba.update(values=[nova_linha], range_name=f"A{proxima_linha_vazia}:L{proxima_linha_vazia}")
                    print(f"   ✅ NOVENA salva na linha {proxima_linha_vazia}: {nova_linha[6]}")
                    proxima_linha_vazia += 1
                    time.sleep(5)
                except Exception as e: print(f"   ❌ Falha ao salvar novena: {e}")
            continue
        print(f"   ☀️ Slot 06:00 avulso ({plano.get('motivo') if plano else '-'})")
    
    instrucao_abertura = ""
    if "Guerra" in pilar_do_dia: instrucao_abertura = "Comienza reconociendo una amenaza o envidia invisible, y luego invoca protección."
    elif "Vicios" in pilar_do_dia: instrucao_abertura = "Comienza con el dolor de ver a un ser querido en ataduras, pidiendo liberación."
    elif "Familiar" in pilar_do_dia: instrucao_abertura = "Comienza evocando las fricciones y el deseo de paz en el hogar."
    elif "Providencia" in pilar_do_dia: instrucao_abertura = "Comienza reconociendo el esfuerzo, las deudas o la necesidad de puertas abiertas."
    elif "Misericordia" in pilar_do_dia: instrucao_abertura = "Comienza pidiendo sanación para el cuerpo enfermo y perdón para el alma."
    elif "Manto" in pilar_do_dia: instrucao_abertura = "Comienza pidiendo ser escondido bajo el manto sagrado contra los peligros."
    elif "Milagros" in pilar_do_dia: instrucao_abertura = "Comienza con un fuerte agradecimiento por los milagros y la vida."

    persona_prompt = "Jesucristo" if persona == 'JESUS' else "la Virgen de Guadalupe (cariñosamente llamada La Morenita)"

    prompt_tema = f"Actúa como Teólogo. Crea un tema corto (máx 8 palabras) para una oración. Pilar: '{pilar_do_dia}', dirigida a '{persona_prompt}', momento: '{foco_teologico}'. Estacionalidad: '{contexto_sazonal}'. SOLO el tema, sin comillas ni asteriscos."
    tema_gerado = None
    for i in range(5):
        try:
            tema_gerado = _gerar(modelos_cascata[i], prompt_tema).replace('*', '').replace('"', '').replace('[', '').replace(']', '').strip()
            break 
        except: time.sleep(esperas_exponenciais[i])
            
    if not tema_gerado: continue 
    time.sleep(5)

    regra_meditacao = "OBLIGATORIO: En la descripción (DESC), añade un aviso destacado diciendo que al final del video hay 5 minutos de música celestial para dormir/meditar." if horario == "18:00" else ""
    cta_comentarios = "Pide al oyente que escriba un motivo de gratitud en los comentarios." if horario == "18:00" else "Pide al oyente que escriba su intención o petición para el día en los comentarios."
    regra_persona = "OBLIGATORIO: Como te diriges a Jesucristo, ESTÁ ESTRICTAMENTE PROHIBIDO mencionar a María, la Virgen o Guadalupe." if persona == 'JESUS' else "OBLIGATORIO: Como te diriges a María, DEBES usar las invocaciones 'Virgen de Guadalupe', 'Madre de Guadalupe' y referirte a ella cariñosamente como 'La Morenita'."
    titulo_sufixo = "Oración de la Mañana" if horario == "06:00" else "Oración de la Noche"
    instrucao_titulo = (
        f"TITULO:[Título magnético. OBLIGATORIO empezar con 'La Morenita'. FORMATO: 'La Morenita [Gatillo de dolor del oyente] [promesa urgente] - {titulo_sufixo}'. Ej: 'La Morenita Sana Tu Familia Esta Noche - {titulo_sufixo}'. SIN FECHA. SIN ASTERISCOS NI CORCHETES]"
        if persona == 'MARIA' else
        f"TITULO:[Título magnético. OBLIGATORIO empezar con el dolor o situación del oyente, NUNCA con 'Jesús'. FORMATO: '[Dolor/situación crítica del oyente] — [promesa de alivio urgente] - {titulo_sufixo}'. Ej: 'Tu Familia Está Sufriendo — Haz Esta Oración AHORA - {titulo_sufixo}'. SIN FECHA. SIN ASTERISCOS NI CORCHETES]"
    )
    instrucao_miguel = (
        "Cuando sea natural en la oración, menciona la intercesión del Arcángel San Miguel como guardián y protector espiritual."
        if "Guerra" in pilar_do_dia else ""
    )
    tags_extras = (
        f"virgen de guadalupe, la morenita, oración guadalupe{', arcángel miguel, san miguel arcángel' if 'Guerra' in pilar_do_dia else ''}, coronilla de la divina misericordia"
        if persona == 'MARIA' else
        f"jesús, cristo, oración de la {'mañana' if horario == '06:00' else 'noche'}{', arcángel miguel, san miguel arcángel' if 'Guerra' in pilar_do_dia else ''}"
    )

    prompt_principal = f"""
    Actúa como un guía espiritual y hermano en la fe. Escribe una oración extensa de 1500 a 1800 palabras sobre "{tema_gerado}" dirigida a {persona_prompt}. 
    CONTEXTO: Enfoque: "{foco_teologico}". Estacionalidad: "{contexto_sazonal}".
    REGLAS:
    1. AUDIENCIA GLOBAL: Español Latino neutro. PROHIBIDO mencionar países.
    2. HORARIOS: PROHIBIDO mencionar la hora exacta. Usa SOLO la expresión "{periodo}".
    3. GANCHO INICIAL MATADOR (0-60s): NO te presentes. Empieza la primera frase con una AFIRMACIÓN EMPÁTICA sobre el dolor o la esperanza del oyente. LUEGO, conecta con: {instrucao_abertura}. LUEGO, haz una promesa de alivio si se queda hasta el final.
    4. COFRE SEMÁNTICO (SEO Y RETENCIÓN): Teje de forma natural los conceptos de Sanación, Perdón y Protección. ADEMÁS, elige y usa sutilmente solo 2 o 3 de estas palabras mágicas a lo largo del texto: [Puertas Abiertas, Milagros, Providencia, Misericordia, Descanso Profundo]. NO las uses todas juntas. {instrucao_miguel}
    5. PROFUNDIDAD: UN SOLO TEMA central. Párrafos elaborados.
    6. RESET DE ATENCIÓN: A la mitad de la oración, inserta un 'Reset de Atención' hablado (Ej: 'Presta mucha atención ahora, no dejes que las distracciones te alejen...').
    7. GANCHOS INVISIBLES DE RETENCIÓN: Cada 300 a 400 palabras, incorpora orgánicamente — sin que el fiel perciba la técnica — uno de estos recursos: (a) ANTICIPACIÓN: anuncia que algo importante será revelado pronto, sin revelarlo aún; (b) REVELACIÓN PARCIAL: entrega una parte de la respuesta espiritual y señala que hay más; (c) VALIDACIÓN EMOCIONAL: nombra exactamente lo que el fiel está sintiendo en ese momento, creando reconocimiento profundo; (d) GIRO DE BLOQUE: realiza una transición inesperada de tono — de súplica a gratitud, de dolor a esperanza — que renueve la atención. Los ganchos deben ser invisibles: el fiel no percibe la técnica, solo siente que no puede dejar de escuchar. Nunca rompas el clima devocional.
    8. ARCO: Vulnerabilidad -> Súplica -> Entrega/Gratitud. Incluye bloque pidiendo por la salud de los enfermos.
    9. PAUSAS: OBLIGATORIO usar abundantes puntos suspensivos (...) para forzar pausas en la voz.
    10. CENSURA: PROHIBIDO descripciones de violencia física.
    11. CERO INTERJECCIONES: PROHIBIDO usar "¡Ay!", "¡Oh!".
    12. CIERRE: {cta_comentarios} Hazlo sonar como misión de fe, NUNCA pidiendo likes. Después añade una frase breve invitando a suscribirse al canal: hazla sonar como llamada espiritual (ej: 'Si esta oración tocó tu corazón, únete a nuestra familia de fe — suscríbete para recibir oraciones cada día'). Nunca suena como publicidad. Además, pide con naturalidad que el fiel ENVÍE esta oración a alguien que la necesita (ej.: "Si mientras orábamos pensaste en alguien, envíale esta oración ahora mismo."). Compartir es el pedido principal del final.
    13. ANTI-JSON: Escribe en TEXTO PLANO. PROHIBIDO JSON, llaves {{ }} o asteriscos (*).
    {regra_persona}
    {regra_meditacao}
    FORMATO EXACTO:
    {instrucao_titulo}
    THUMB:[MODELO CAMPEÓN (datos reales de CTR): 2 o 3 palabras = RESULTADO CONCRETO + palabra de urgencia al final (HOY / AHORA). Ej: "MILAGRO HOY", "PUERTAS ABIERTAS AHORA", "SANACIÓN HOY", "FAMILIA RESTAURADA HOY". PROHIBIDO solo palabras de calma/abstractas sin resultado ("PAZ PROFUNDA", "NOCHE SERENA"). SIN ASTERISCOS NI CORCHETES]
    GUION:[Oración completa de 1500 a 1800 palabras]
    DESC:[Descripción de 3 párrafos con fuerte SEO. PRIMER párrafo: invita a las oraciones EN VIVO 24 horas del canal ('Únete a nuestras oraciones en vivo las 24 horas — el canal ora sin parar por ti. Activa la campanita para no perderte ninguna oración'). SEGUNDO párrafo: descripción emocional de esta oración. TERCER párrafo: keywords y hashtags.]
    TAGS:[Etiquetas separadas por comas. Incluye siempre: {tags_extras}]
    """
    
    texto_ia = None
    for i in range(5): 
        try:
            texto_ia = _gerar(modelos_cascata[i], prompt_principal)
            break 
        except: time.sleep(esperas_exponenciais[i])
            
    if not texto_ia: continue

    try:
        t_match = re.search(r'T[IÍ]TULO:\s*(.*?)(?=THUMB:|GUI[OÓ]N:|DESC:|TAGS:|$)', texto_ia, re.IGNORECASE | re.DOTALL)
        th_match = re.search(r'THUMB:\s*(.*?)(?=GUI[OÓ]N:|DESC:|TAGS:|T[IÍ]TULO:|$)', texto_ia, re.IGNORECASE | re.DOTALL)
        g_match = re.search(r'GUI[OÓ]N:\s*(.*?)(?=DESC:|TAGS:|T[IÍ]TULO:|THUMB:|$)', texto_ia, re.IGNORECASE | re.DOTALL)
        d_match = re.search(r'DESC:\s*(.*?)(?=TAGS:|T[IÍ]TULO:|THUMB:|GUI[OÓ]N:|$)', texto_ia, re.IGNORECASE | re.DOTALL)
        tg_match = re.search(r'TAGS:\s*(.*?)(?=T[IÍ]TULO:|THUMB:|GUI[OÓ]N:|DESC:|$)', texto_ia, re.IGNORECASE | re.DOTALL)
        
        titulo_final = t_match.group(1).replace('*', '').replace('"', '').replace('[', '').replace(']', '').strip() if t_match else ""
        thumb_final = th_match.group(1).replace('*', '').replace('"', '').replace('[', '').replace(']', '').strip() if th_match else ""
        roteiro_final = g_match.group(1).strip() if g_match else texto_ia 
        desc_final = d_match.group(1).strip() if d_match else ""
        tags_final = tg_match.group(1).replace('*', '').replace('[', '').replace(']', '').strip() if tg_match else ""
        
        # ═══ PORTÃO DE QUALIDADE (12/07/2026) — texto genérico NUNCA entra ═══
        # Campo fora do formato: 1 retentativa com lembrete; persistindo,
        # fallback determinístico derivado do tema (nunca "Título Padrão").
        if not titulo_final or len(titulo_final) < 10 or not thumb_final or not desc_final:
            print("   ⚠️ Campos fora do formato — retentativa com lembrete de formato...")
            lembrete = (prompt_principal + "\n\nATENCIÓN: tu respuesta anterior vino SIN el "
                        "FORMATO EXACTO. Responde OBLIGATORIAMENTE con las 5 etiquetas "
                        "TITULO:, THUMB:, GUION:, DESC:, TAGS: — cada una presente.")
            texto2 = None
            for i in range(5):
                try:
                    texto2 = _gerar(modelos_cascata[i], lembrete)
                    break
                except: time.sleep(esperas_exponenciais[i])
            if texto2:
                t2  = re.search(r'T[IÍ]TULO:\s*(.*?)(?=THUMB:|GUI[OÓ]N:|DESC:|TAGS:|$)', texto2, re.IGNORECASE | re.DOTALL)
                th2 = re.search(r'THUMB:\s*(.*?)(?=GUI[OÓ]N:|DESC:|TAGS:|T[IÍ]TULO:|$)', texto2, re.IGNORECASE | re.DOTALL)
                g2  = re.search(r'GUI[OÓ]N:\s*(.*?)(?=DESC:|TAGS:|T[IÍ]TULO:|THUMB:|$)', texto2, re.IGNORECASE | re.DOTALL)
                d2  = re.search(r'DESC:\s*(.*?)(?=TAGS:|T[IÍ]TULO:|THUMB:|GUI[OÓ]N:|$)', texto2, re.IGNORECASE | re.DOTALL)
                tg2 = re.search(r'TAGS:\s*(.*?)(?=T[IÍ]TULO:|THUMB:|GUI[OÓ]N:|DESC:|$)', texto2, re.IGNORECASE | re.DOTALL)
                if t2 and (not titulo_final or len(titulo_final) < 10):
                    titulo_final = t2.group(1).replace('*', '').replace('"', '').replace('[', '').replace(']', '').strip()
                if th2 and not thumb_final:
                    thumb_final = th2.group(1).replace('*', '').replace('"', '').replace('[', '').replace(']', '').strip()
                if g2 and (not roteiro_final or len(roteiro_final.split()) < 700):
                    roteiro_final = g2.group(1).strip()
                if d2 and not desc_final:
                    desc_final = d2.group(1).strip()
                if tg2 and not tags_final:
                    tags_final = tg2.group(1).replace('*', '').replace('[', '').replace(']', '').strip()
        if not titulo_final or len(titulo_final) < 10:
            titulo_final = f"{tema_gerado} - {titulo_sufixo}"
        if not thumb_final:
            thumb_final = " ".join(tema_gerado.split()[:4]).upper()
        if not desc_final or len(desc_final) < 80:
            desc_final = (f"{tema_gerado}. Una oración poderosa dirigida a {persona_prompt} en tu {titulo_sufixo.lower()}. "
                          f"Únete a esta oración, deja tu petición en los comentarios y permite que la fe transforme tu día. "
                          f"Comparte esta oración con alguien que la necesite y activa la campanita para no perderte ninguna oración.")
        if not tags_final:
            tags_final = f"oración, fe, protección divina, sanación, {('jesús, cristo' if persona == 'JESUS' else 'virgen de guadalupe, la morenita')}"

        nova_linha =[str(data_alvo), horario, "Pronto p/ Áudio", persona, idioma, tema_gerado, titulo_final, roteiro_final, tags_final, desc_final, "Pendente", thumb_final]
        aba.update(values=[nova_linha], range_name=f"A{proxima_linha_vazia}:L{proxima_linha_vazia}")
        print(f"   ✅ SUCESSO! Linha {proxima_linha_vazia} preenchida.")
        proxima_linha_vazia += 1 
        time.sleep(5)
    except Exception as e: print(f"   ❌ Falha ao salvar: {e}")

