import os
import sys
import json
import time
import re
import datetime
from google.genai import Client
from google.oauth2.service_account import Credentials
import gspread

# ==============================================================================
# 1. PUXANDO AS CHAVES DO COFRE DO GITHUB
# ==============================================================================
CHAVE_API = os.environ.get("GEMINI_API_KEY")
GOOGLE_JSON = os.environ.get("GOOGLE_CREDENTIALS")

print("🔐 Autenticando no Google Sheets via Service Account...")
credenciais_dict = json.loads(GOOGLE_JSON)
escopos =['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
credenciais = Credentials.from_service_account_info(credenciais_dict, scopes=escopos)
gc = gspread.authorize(credenciais)

client = Client(api_key=CHAVE_API, http_options={'api_version': 'v1'})

# ==============================================================================
# 2. CONFIGURAÇÕES DA FÁBRICA E BRIEFING TEOLÓGICO
# ==============================================================================
ID_PLANILHA = "1KgIjWrLUVlllhlZB1R9fkHGxxZlLsax1aOVGZrYwgnU"

PILARES = {
    0: "Guerra Espiritual y Protección (Lunes)",
    1: "Liberación de Vicios y Ataduras (Martes)",
    2: "Restauración Familiar y Matrimonial (Miércoles)",
    3: "Providencia y Puertas Abiertas (Jueves)",
    4: "Misericordia y Sanación Física (Viernes)",
    5: "El Manto de Guadalupe (Sábado)",
    6: "Milagros y Gratitud (Domingo)"
}

GRADE_DIARIA =[
    {"horario": "06:00", "personagem": "Jesus", "idioma": "ES", "foco": "Mañana: Consagración, fuerza y protección para el día que nace."},
    {"horario": "12:00", "personagem": "Maria", "idioma": "ES", "foco": "Mediodía: Intercesión por la familia, salud y las aflicciones de la jornada."},
    {"horario": "18:00", "personagem": "Maria", "idioma": "ES", "foco": "Atardecer: Acogimiento maternal, consuelo y gratitud por el día."},
    {"horario": "21:00", "personagem": "Jesus", "idioma": "ES", "foco": "Noche: Entrega del sueño, perdón y descanso profundo en Dios."}
]

print("📡 Conectando à planilha online...")
planilha = gc.open_by_key(ID_PLANILHA)
aba = planilha.get_worksheet(0)

# ==============================================================================
# 3. SCANNER DE BURACOS (LEITURA COMPLETA DE COLUNAS - SEM PONTO CEGO)
# ==============================================================================
valores_coluna_a = aba.col_values(1)
valores_coluna_b = aba.col_values(2)
proxima_linha_vazia = len(valores_coluna_b) + 1 

dias_existentes = {}
hoje = datetime.date.today()

# Mapeia apenas as datas de HOJE para o futuro (Ignora o passado para não duplicar)
for d_str, h_str in zip(valores_coluna_a[1:], valores_coluna_b[1:]):
    d_str, h_str = d_str.strip(), h_str.strip()
    if d_str and h_str:
        try:
            d_obj = datetime.datetime.strptime(d_str, '%Y-%m-%d').date()
            if d_obj >= hoje:
                if d_obj not in dias_existentes:
                    dias_existentes[d_obj] = []
                dias_existentes[d_obj].append(h_str)
        except:
            pass

meta_estoque = hoje + datetime.timedelta(days=4) # Meta: 5 dias de frente
data_alvo = None
grade_para_processar =[]

data_check = hoje
while data_check <= meta_estoque:
    horarios_presentes = dias_existentes.get(data_check, [])
    if len(horarios_presentes) < 4:
        data_alvo = data_check
        grade_para_processar = [v for v in GRADE_DIARIA if v["horario"] not in horarios_presentes]
        print(f"⚠️ BURACO ENCONTRADO: Faltam horários no día {data_alvo}.")
        break
    data_check += datetime.timedelta(days=1)

if not data_alvo:
    print(f"✅ ESTOQUE ATINGIDO! A planilha já tem vídeos completos até {meta_estoque}.")
    print("💤 O robô vai voltar a dormir para economizar cota. Até amanhã!")
    sys.exit(0)

dia_da_semana = data_alvo.weekday()
pilar_do_dia = PILARES[dia_da_semana]

print(f"\n📅 DATA ALVO DEFINIDA: {data_alvo} | Pilar: {pilar_do_dia}")
print(f"🎯 O robô vai empezar a escribir exactamente en la Línea {proxima_linha_vazia}...\n")

# ==============================================================================
# 4. PRODUÇÃO EM MASSA (CASCATA DE IA + COPYWRITING AVANÇADO)
# ==============================================================================
esperas_exponenciais =[10, 20, 40, 80, 120]
modelos_cascata =['gemini-2.5-flash', 'gemini-2.5-flash', 'gemini-3.1-flash-lite', 'gemini-3.1-flash-lite', 'gemini-2.5-pro']

for video in grade_para_processar:
    horario = video["horario"]
    persona = video["personagem"].upper() # CORREÇÃO: Forçando maiúsculas para evitar o erro de Maria
    idioma = video["idioma"]
    foco_teologico = video["foco"]
    
    if dia_da_semana == 4: 
        if horario in["06:00", "12:00"]:
            foco_teologico += " ENFOQUE: Misericordia y Perdón (Tono suave y esperanzador)."
        else:
            foco_teologico += " ENFOQUE: La Pasión de Cristo y el Sacrificio (Tono profundo y reflexivo)."

    print(f"🎬 PRODUZINDO SLOT: {horario} | Personagem: {persona}")
    
    instrucao_abertura = ""
    if "Guerra" in pilar_do_dia: instrucao_abertura = "Comienza reconociendo una amenaza, envidia o dificultad invisible, y luego invoca la protección divina."
    elif "Vicios" in pilar_do_dia: instrucao_abertura = "Comienza con el dolor de ver a un ser querido perdido en ataduras o vicios, pidiendo liberación."
    elif "Familiar" in pilar_do_dia: instrucao_abertura = "Comienza evocando las fricciones y el deseo de paz y unión dentro del hogar."
    elif "Providencia" in pilar_do_dia: instrucao_abertura = "Comienza reconociendo el esfuerzo, las deudas o la necesidad urgente de puertas abiertas."
    elif "Misericordia" in pilar_do_dia: instrucao_abertura = "Comienza pidiendo sanación para el cuerpo enfermo y perdón para el alma."
    elif "Manto" in pilar_do_dia: instrucao_abertura = "Comienza pidiendo ser escondido y blindado bajo el manto sagrado contra los peligros del mundo."
    elif "Milagros" in pilar_do_dia: instrucao_abertura = "Comienza con un fuerte y alegre agradecimiento por los milagros y la vida."

    # INJEÇÃO DE IDENTIDADE
    persona_prompt = "Jesucristo" if persona == 'JESUS' else "la Virgen de Guadalupe (cariñosamente llamada La Morenita)"

    tema_gerado = None
    prompt_tema = f"""
    Actúa como un Teólogo católico. Crea un tema corto (máximo 8 palabras) para una oración. 
    El enfoque principal (pilar) es '{pilar_do_dia}', la oración está dirigida a '{persona_prompt}' y el momento del día es '{foco_teologico}'. 
    Responde SOLO con el tema, sin comillas ni asteriscos.
    """
    
    for tentativa in range(5):
        try:
            modelo_atual = modelos_cascata[tentativa]
            resp_tema = client.models.generate_content(model=modelo_atual, contents=prompt_tema)
            tema_gerado = resp_tema.text.replace('*', '').replace('"', '').strip()
            print(f"   ✨ Tema Criado ({modelo_atual}): {tema_gerado}")
            break 
        except Exception as e:
            espera = esperas_exponenciais[tentativa]
            print(f"   ⚠️ Falha na IA (Tentativa {tentativa+1}/5). Aguardando {espera}s...")
            time.sleep(espera)
            
    if not tema_gerado:
        print("   ❌ Falha definitiva no tema. Pulando este vídeo.")
        continue 

    time.sleep(5)

    regra_meditacao = "OBLIGATORIO: En la descripción (DESC), añade un aviso destacado diciendo que al final del video hay 5 minutos de música celestial para dormir/meditar." if horario in["18:00", "21:00"] else ""
    cta_comentarios = "Pide al oyente que escriba un motivo de gratitud en los comentarios." if horario in["18:00", "21:00"] else "Pide al oyente que escriba su intención o petición para el día en los comentarios."
    
    # REGRA DE BLINDAGEM DE PERSONAGEM
    regra_persona = "OBLIGATORIO: Como te diriges a Jesucristo, ESTÁ ESTRICTAMENTE PROHIBIDO mencionar a María, la Virgen o Guadalupe." if persona == 'JESUS' else "OBLIGATORIO: Como te diriges a María, DEBES usar las invocaciones 'Virgen de Guadalupe', 'Madre de Guadalupe' y referirte a ella cariñosamente como 'La Morenita'."

    titulo_sufixo = ""
    if horario == "06:00": titulo_sufixo = "Oración de la Mañana"
    elif horario == "12:00": titulo_sufixo = "Oración del Mediodía"
    elif horario == "18:00": titulo_sufixo = "Oración Mariana"
    elif horario == "21:00": titulo_sufixo = "Oración de la Noche"

    texto_ia = None
    prompt_principal = f"""
    Actúa como un guía espiritual y hermano en la fe, con profundo conocimiento teológico pero lenguaje cercano, cálido y devocional.
    Escribe una oración extensa y profunda de aproximadamente 1500 a 1800 palabras sobre el tema "{tema_gerado}" dirigida a {persona_prompt}. 
    
    CONTEXTO OBLIGATORIO DEL HORARIO Y PILAR:
    Esta oración será publicada a las {horario}. El enfoque teológico DEBE ser: "{foco_teologico}". 
    
    REGLAS CRÍTICAS DE RETENCIÓN, TTS Y MONETIZACIÓN:
    1. AUDIENCIA GLOBAL: Tu audiencia es toda Latinoamérica y el mundo hispanohablante. PROHIBIDO mencionar países específicos. Usa un Español Latino neutro.
    2. GANCHO INICIAL MATADOR (0-60s): NO te presentes. Empieza la primera frase tocando directamente en el dolor o la esperanza del fiel con empatía profunda. Luego, conecta con esta estructura: {instrucao_abertura}
    3. PROFUNDIDAD Y EMOCIÓN: Concéntrate en UN SOLO TEMA central. Escribe párrafos elaborados y profundos (no te limites a una sola frase por párrafo, pero tampoco los hagas gigantescos).
    4. ARCO EN 3 ACTOS: Divide la oración en Vulnerabilidad -> Súplica -> Entrega/Gratitud.
    5. BLOCO DE SALUD Y FAMILIA ADAPTADO: Dentro del desarrollo (Movimiento 2), debes incluir obligatoriamente un bloque de 2 a 3 párrafos dedicado a pedir por la salud de los enfermos y la unión familiar. Este bloque NO debe ser genérico; DEBES adaptarlo orgánicamente al pilar del día ({pilar_do_dia}) y dirigirlo exclusivamente a la persona correcta ({persona_prompt}). Usa un lenguaje devocional y cálido, nunca clínico.
    6. PAUSAS NATURALES: OBLIGATORIO usar abundantes puntos suspensivos (...) a lo largo de la oración para forzar pausas reflexivas en la voz.
    7. CENSURA GRÁFICA: PROHIBIDO usar descripciones gráficas de violencia física. Usa metáforas suaves.
    8. CERO INTERJECCIONES: PROHIBIDO usar "¡Ay!", "¡Oh!", o exclamaciones teatrales.
    9. CIERRE Y VELOCITY: Termina la oración invitando sutilmente al oyente a dejar su petición en los comentarios (como un libro de intenciones) y a compartir esta luz. {cta_comentarios} Hazlo sonar como una misión de fe, NUNCA como un YouTuber pidiendo likes.
    10. FORMATO ESTRICTO (ANTI-JSON): Escribe en TEXTO PLANO. ESTÁ ESTRICTAMENTE PROHIBIDO usar formato JSON, diccionarios, código, llaves {{ }} o comillas. NO uses asteriscos (*).
    
    {regra_persona}
    {regra_meditacao}
    
    DEBES usar EXACTAMENTE este formato con estas palabras clave en mayúsculas al inicio de cada sección:
    TITULO:[Escribe aquí un título magnético. FORMATO OBLIGATORIO: "[Promesa Urgente o Gatillo de Alivio] - {titulo_sufixo}". NO PONGAS LA FECHA. SIN ASTERISCOS NI CORCHETES]
    THUMB:[Escribe aquí una frase de impacto de MÁXIMO 4 PALABRAS. DEBE ser una promesa urgente o alivio inmediato CONTEXTUALIZADO con el tema. NUNCA uses títulos descriptivos. SIN ASTERISCOS NI CORCHETES]
    GUION:[Escribe aquí la oración completa de aproximadamente 1500 a 1800 palabras siguiendo las regras]
    DESC:[Escribe aquí una descripción de 3 párrafos con fuerte SEO, usando palabras clave de cola larga relacionadas a la oración, sanación y fe]
    TAGS:[Escribe aquí las etiquetas separadas por comas]
    """
    
    for tentativa in range(5): 
        try:
            modelo_atual = modelos_cascata[tentativa]
            print(f"   ⏳ Escrevendo roteiro otimizado (Tentativa {tentativa+1}/5 com {modelo_atual})...")
            response = client.models.generate_content(model=modelo_atual, contents=prompt_principal)
            texto_ia = response.text
            break 
        except Exception as e:
            espera = esperas_exponenciais[tentativa]
            print(f"   ⚠️ Falha na IA (Tentativa {tentativa+1}/5). Aguardando {espera}s...")
            time.sleep(espera)
            
    if not texto_ia:
        print("   ❌ Falha definitiva no roteiro. Pulando este vídeo.")
        continue

    try:
        titulo_match = re.search(r'TITULO:\s*(.*?)(?=THUMB:|GUION:|DESC:|TAGS:|$)', texto_ia, re.IGNORECASE | re.DOTALL)
        thumb_match = re.search(r'THUMB:\s*(.*?)(?=GUION:|DESC:|TAGS:|TITULO:|$)', texto_ia, re.IGNORECASE | re.DOTALL)
        guion_match = re.search(r'GUION:\s*(.*?)(?=DESC:|TAGS:|TITULO:|THUMB:|$)', texto_ia, re.IGNORECASE | re.DOTALL)
        desc_match = re.search(r'DESC:\s*(.*?)(?=TAGS:|TITULO:|THUMB:|GUION:|$)', texto_ia, re.IGNORECASE | re.DOTALL)
        tags_match = re.search(r'TAGS:\s*(.*?)(?=TITULO:|THUMB:|GUION:|DESC:|$)', texto_ia, re.IGNORECASE | re.DOTALL)
        
        titulo_final = titulo_match.group(1).replace('*', '').replace('"', '').replace('[', '').replace(']', '').strip() if titulo_match else "Título Padrão"
        thumb_final = thumb_match.group(1).replace('*', '').replace('"', '').replace('[', '').replace(']', '').strip() if thumb_match else "ORACIÓN PODEROSA"
        roteiro_final = guion_match.group(1).strip() if guion_match else texto_ia 
        desc_final = desc_match.group(1).strip() if desc_match else "Descripción Padrão"
        tags_final = tags_match.group(1).replace('*', '').replace('[', '').replace(']', '').strip() if tags_match else "Tags"
        
        nova_linha = [
            str(data_alvo), horario, "Pronto p/ Áudio", persona, idioma, 
            tema_gerado, titulo_final, roteiro_final, tags_final, desc_final, "Pendente", thumb_final
        ]
        
        intervalo = f"A{proxima_linha_vazia}:L{proxima_linha_vazia}"
        aba.update(values=[nova_linha], range_name=intervalo)
        
        print(f"   ✅ SUCESSO! Linha {proxima_linha_vazia} preenchida perfeitamente.")
        
        proxima_linha_vazia += 1 
        time.sleep(5)
        
    except Exception as e:
        print(f"   ❌ Falha ao salvar na planilha: {e}")

print("\n🚀 FÁBRICA CONCLUÍDA! Processo finalizado.")
