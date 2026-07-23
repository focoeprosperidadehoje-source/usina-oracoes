import os, sys, json, time, re, datetime
from google.genai import Client
from google.oauth2.service_account import Credentials
import gspread

CHAVE_API   = os.environ.get("GEMINI_API_KEY", "")
CHAVE_API_2 = os.environ.get("GEMINI_API_KEY_2", "")
CHAVES_GEMINI = [k for k in [CHAVE_API, CHAVE_API_2] if k]
GOOGLE_JSON = os.environ.get("GOOGLE_CREDENTIALS")

print("🔐 Autenticando no Google Sheets (SHORTS ES)...")
credenciais_dict = json.loads(GOOGLE_JSON)
creds = Credentials.from_service_account_info(credenciais_dict, scopes=['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive'])
gc = gspread.authorize(creds)
client = Client(api_key=CHAVE_API, http_options={'api_version': 'v1'})

def obter_modelo_lite():
    try:
        modelos = client.models.list()
        lite = [m.name for m in modelos if 'generateContent' in m.supported_generation_methods and ('flash-lite' in m.name or '8b' in m.name)]
        return sorted(lite, reverse=True)[0] if lite else 'gemini-2.5-flash-lite'
    except: return 'gemini-2.5-flash-lite'

modelo_usina = obter_modelo_lite()

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

ID_PLANILHA = "1KgIjWrLUVlllhlZB1R9fkHGxxZlLsax1aOVGZrYwgnU"

PILARES = {
    0: "Guerra Espiritual y Protección", 1: "Liberación de Vicios y Ataduras", 2: "Restauración Familiar y Matrimonial",
    3: "Providencia y Puertas Abiertas", 4: "Misericordia y Sanación Física", 5: "El Manto de Guadalupe", 6: "Milagros y Gratitud"
}

GRADE_SHORTS = [
    {"horario": "14:00", "personagem": "Maria", "idioma": "ES", "foco": "Mediodía: Causas imposibles, sanación física y milagros.", "ref": "18:00"}
]

# Short de divulgação da live — gerado apenas às segundas-feiras
GRADE_SHORTS_PROMO = {
    "horario": "09:00", "personagem": "Maria", "idioma": "ES",
    "foco": "Promover la oración EN VIVO 24 horas del canal.", "ref": None, "tipo": "promo_live"
}

aba_shorts = gc.open_by_key(ID_PLANILHA).worksheet("ES_SHORTS")
aba_longos = gc.open_by_key(ID_PLANILHA).worksheet("ES")

todas_linhas = aba_shorts.get_all_values()
if len(todas_linhas) > 500:
    aba_shorts.delete_rows(2, 100)
    todas_linhas = aba_shorts.get_all_values()

proxima_linha_vazia = len(todas_linhas) + 1
valores_coluna_a = [linha[0].strip() for linha in todas_linhas[1:] if len(linha) > 0]
valores_coluna_b = [linha[1].strip() for linha in todas_linhas[1:] if len(linha) > 1]

dias_existentes = {}
hoje = datetime.date.today()
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

gaps = []
data_check = limite_passado
while data_check <= meta_estoque:
    horarios_presentes = dias_existentes.get(data_check, [])
    horarios_faltando = [v for v in GRADE_SHORTS if v["horario"] not in horarios_presentes]
    if data_check.weekday() == 0 and GRADE_SHORTS_PROMO["horario"] not in horarios_presentes:
        horarios_faltando = [GRADE_SHORTS_PROMO] + horarios_faltando
    if horarios_faltando:
        gaps.append((data_check, horarios_faltando))
    data_check += datetime.timedelta(days=1)

if not gaps:
    print(f"✅ ESTOQUE DE SHORTS ATINGIDO até {meta_estoque - datetime.timedelta(days=1)}. Dormindo.")
    sys.exit(0)

dados_longos = aba_longos.get_all_values()

for data_alvo, grade_para_processar in gaps:
    pilar_do_dia = PILARES[data_alvo.weekday()]
    print(f"\n📅 DATA ALVO SHORTS: {data_alvo} | Pilar: {pilar_do_dia}")
    for video in grade_para_processar:
        horario, persona, idioma, foco_teologico = video["horario"], video["personagem"].upper(), video["idioma"], video["foco"]
        print(f"🎬 PRODUZINDO SHORT: {horario} | {persona}")

        is_promo = video.get("tipo") == "promo_live"

        horario_longo_ref = video.get("ref")
        titulo_referencia = ""
        if horario_longo_ref:
            for linha in dados_longos[1:]:
                if len(linha) > 6 and linha[0].strip() == str(data_alvo) and linha[1].strip() == horario_longo_ref:
                    titulo_referencia = linha[6].strip()
                    break

        contexto_eco = f"El video largo correspondiente de hoy tiene el título: '{titulo_referencia}'. El Short DEBE ser un eco de este tema." if titulo_referencia else ""
        persona_prompt = "Jesucristo" if persona == 'JESUS' else "la Virgen de Guadalupe (La Morenita)"
        prefixo_titulo_short = "Oración Poderosa con La Morenita:" if persona == 'MARIA' else "Oración Poderosa con Jesús:"

        if is_promo:
            prompt_principal = f"""
        Actúa como guía espiritual católico. Crea el guion de un SHORT de YouTube (máximo 40 segundos) cuyo ÚNICO objetivo es invitar a unirse a la transmisión EN VIVO de oraciones 24 horas del canal, donde La Morenita (Virgen de Guadalupe) intercede sin parar.

        ESTRUCTURA OBLIGATORIA:
        1. GANCHO (inicio con "..."): Frase de urgencia espiritual invitando a la live. Ej: "...en este momento, La Morenita está intercediendo por ti EN VIVO..."
        2. CUERPO (10-15 segundos): ¿Por qué necesitas entrar ahora? Alguien está orando por exactamente lo que tú estás pasando.
        3. CTA FINAL: "Entra al canal AHORA — busca el video EN VIVO y únete a la familia de fe."

        REGLAS:
        - Máximo 40 segundos de lectura (≈100 palabras)
        - Usa puntos suspensivos (...) para pausas de respiración
        - Tono: urgencia maternal, nunca comercial
        - ANTI-JSON: solo texto plano, sin asteriscos ni corchetes

        FORMATO EXACTO:
        TITULO:[Oración EN VIVO con La Morenita: Tu Milagro Te Espera AHORA #Shorts]
        GUION:[guion completo]
        DESC:[PRIMERA LÍNEA: '¡Únete AHORA! La Morenita ora EN VIVO las 24 horas por ti — entra al canal ahora mismo.' SEGUNDA LÍNEA: Invitar a las playlists de oraciones del canal. TERCERA LÍNEA: hashtags #Shorts #OraciónEnVivo #LaMorenita #VirgenDeGuadalupe]
        TAGS:[shorts, oración en vivo, la morenita, virgen de guadalupe, milagros, oración 24 horas, en vivo ahora, intercesión]
        """
        else:
            if persona == 'JESUS':
                oracao_padrao = "Padre nuestro que estás en el cielo... santificado sea tu nombre... venga a nosotros tu reino... hágase tu voluntad en la tierra como en el cielo... Danos hoy nuestro pan de cada día... perdona nuestras ofensas... como también nosotros perdonamos a los que nos ofenden... no nos dejes caer en la tentación... y líbranos del mal... Amén."
            else:
                oracao_padrao = "Dios te salve, María... llena eres de gracia... el Señor es contigo... bendita tú eres entre todas las mujeres... y bendito es el fruto de tu vientre Jesús... Santa María, Madre de Dios... ruega por nosotros, pecadores... ahora y en la hora de nuestra muerte... Amén. Santa María de Guadalupe... salva nuestras familias y conserva nuestra fe."

            prompt_principal = f"""
        Actúa como un guía espiritual católico. Crea un guion para un video SHORT de YouTube (máximo 40 segundos de lectura).
        Tema del día: {pilar_do_dia}. Foco: {foco_teologico}. Dirigido a: {persona_prompt}.
        {contexto_eco}

        ESTRUCTURA OBLIGATORIA DEL GUION (LOOP PERFECTO):
        1. GANCHO (Inicio): La primera frase del video. OBLIGATORIO empezar con puntos suspensivos en minúscula ("..."). Es el complemento sintáctico de la frase final — juntas forman una sola frase continua y completa. Usa palabras de urgencia como "Milagro" o "Sanación".
        2. ORACIÓN: Escribe EXACTAMENTE esta oración en el medio: "{oracao_padrao}"
        3. FRASE DE LOOP (Final): La última frase del video. OBLIGATORIAMENTE debe ser SINTÁCTICAMENTE INCOMPLETA — una cláusula abierta cuyo complemento natural es exactamente la frase inicial. El oyente no percibe el corte porque el cerebro une fin e inicio como una sola frase continua.
        4. CTA LIVE (1 frase, después del loop): Una frase ultra-breve invitando a la oración EN VIVO 24 horas del canal. Ej: "Estamos EN VIVO ahora mismo — únete al canal y recibe tu milagro."

        EJEMPLO DE LOOP SINTÁCTICO PERFECTO:
        Final (incompleto): "...es por eso que hoy necesitas recibir..."
        Inicio (complemento): "...la gracia que la Virgen guardó especialmente para ti."
        Leídas en secuencia forman: "es por eso que hoy necesitas recibir la gracia que la Virgen guardó especialmente para ti."

        REGLAS DE FLUIDEZ Y CENSURA:
        - Escribe frases fluidas. Usa reticencias (...) para marcar pausas de respiración.
        - PROHIBIDO descripciones de violencia física o sangre.
        - El título debe comenzar con "{prefixo_titulo_short}" seguido del tema, y terminar con la etiqueta #Shorts.
        - ANTI-JSON: Escribe en TEXTO PLANO. PROHIBIDO usar formato JSON, llaves {{ }} o asteriscos (*).

        FORMATO EXACTO:
        TITULO:[Oración Poderosa: Tema - #Shorts]
        GUION:[Guion completo con el efecto loop]
        DESC:[Descripción corta. PRIMERA LÍNEA: invitar urgentemente a la oración EN VIVO 24h ('¡Únete AHORA! Oramos EN VIVO las 24 horas por ti — entra al canal y recibe tu milagro'). SEGUNDA LÍNEA: invitar a las listas de reproducción. TERCERA LÍNEA: hashtags.]
        TAGS:[Etiquetas separadas por comas]
        """

        texto_ia = None
        for _ in range(3):
            try:
                texto_ia = _gerar(modelo_usina, prompt_principal)
                break
            except: time.sleep(10)

        if not texto_ia: continue

        try:
            t_match = re.search(r'T[IÍ]TULO:\s*(.*?)(?=GUI[OÓ]N:|DESC:|TAGS:|$)', texto_ia, re.IGNORECASE | re.DOTALL)
            g_match = re.search(r'GUI[OÓ]N:\s*(.*?)(?=DESC:|TAGS:|T[IÍ]TULO:|$)', texto_ia, re.IGNORECASE | re.DOTALL)
            d_match = re.search(r'DESC:\s*(.*?)(?=TAGS:|T[IÍ]TULO:|GUI[OÓ]N:|$)', texto_ia, re.IGNORECASE | re.DOTALL)
            tg_match = re.search(r'TAGS:\s*(.*?)(?=T[IÍ]TULO:|GUI[OÓ]N:|DESC:|$)', texto_ia, re.IGNORECASE | re.DOTALL)

            titulo_final = t_match.group(1).replace('*', '').replace('"', '').replace('[', '').replace(']', '').strip() if t_match else "Oración Poderosa #Shorts"
            roteiro_final = g_match.group(1).strip() if g_match else texto_ia
            desc_final = d_match.group(1).strip() if d_match else "¡Visita nuestro canal para la oración completa!"
            tags_final = tg_match.group(1).replace('*', '').replace('[', '').replace(']', '').strip() if tg_match else "shorts, oracion, fe, la morenita, virgen de guadalupe, oración en vivo"

            nova_linha = [str(data_alvo), horario, "Pronto p/ Áudio", persona, idioma, pilar_do_dia, titulo_final, roteiro_final, tags_final, desc_final, "N/A", "N/A"]
            aba_shorts.update(values=[nova_linha], range_name=f"A{proxima_linha_vazia}:L{proxima_linha_vazia}")
            print(f"   ✅ SUCESSO! Short da linha {proxima_linha_vazia} preenchido.")
            proxima_linha_vazia += 1
            time.sleep(3)
        except Exception as e: print(f"   ❌ Falha ao salvar: {e}")
