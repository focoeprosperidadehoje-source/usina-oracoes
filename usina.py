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
    0: "Protección y Liberación (Lunes)",
    1: "Salud y Sanación (Martes)",
    2: "Familia y Relaciones (Miércoles)",
    3: "Prosperidad y Trabajo (Jueves)",
    4: "Perdón y Pasión de Cristo (Viernes)",
    5: "Consagración a María (Sábado)",
    6: "Gratitud y Resurrección (Domingo)"
}

GRADE_DIARIA =[
    {"horario": "06:00", "personagem": "Jesus", "idioma": "ES", "foco": "Mañana: Consagración, fuerza y protección para el día que nace."},
    {"horario": "14:00", "personagem": "Maria", "idioma": "ES", "foco": "Tarde: Intercesión por la familia, salud y las aflicciones del medio día."},
    {"horario": "18:00", "personagem": "Maria", "idioma": "ES", "foco": "Atardecer: Acogimiento maternal, Ave María y gratitud por el día."},
    {"horario": "21:00", "personagem": "Jesus", "idioma": "ES", "foco": "Noche: Entrega del sueño, perdón y descanso profundo en Dios."}
]

print("📡 Conectando à planilha online...")
planilha = gc.open_by_key(ID_PLANILHA)
aba = planilha.get_worksheet(0)

# ==============================================================================
# 3. RADAR DE 16 LINHAS E SCANNER DE BURACOS
# ==============================================================================
todas_linhas = aba.get_all_values()
total_linhas = len(todas_linhas)
proxima_linha_vazia = total_linhas + 1

# Pega apenas as últimas 16 linhas para não sobrecarregar a memória
ultimas_linhas = todas_linhas[-16:] if total_linhas > 16 else todas_linhas[1:]

dias_existentes = {}
hoje = datetime.date.today()
maior_data = hoje - datetime.timedelta(days=1)

for linha in ultimas_linhas:
    if len(linha) >= 2:
        d_str = linha[0].strip()
        h_str = linha[1].strip()
        if d_str and h_str:
            try:
                d_obj = datetime.datetime.strptime(d_str, '%Y-%m-%d').date()
                if d_obj not in dias_existentes:
                    dias_existentes[d_obj] = []
                dias_existentes[d_obj].append(h_str)
                if d_obj > maior_data:
                    maior_data = d_obj
            except:
                pass

meta_estoque = hoje + datetime.timedelta(days=2) # Hoje + 2 dias de frente
data_alvo = None
grade_para_processar =[]

# 1. Procurar buracos nos dias existentes
for d_obj in sorted(dias_existentes.keys()):
    horarios = dias_existentes[d_obj]
    if 0 < len(horarios) < 4:
        data_alvo = d_obj
        grade_para_processar =[v for v in GRADE_DIARIA if v["horario"] not in horarios]
        print(f"⚠️ BURACO ENCONTRADO: Faltam horários no dia {data_alvo}.")
        break

# 2. Se não achou buraco, verifica se precisa criar o próximo dia
if not data_alvo:
    if maior_data < meta_estoque:
        data_alvo = maior_data + datetime.timedelta(days=1)
        grade_para_processar = GRADE_DIARIA
    else:
        print(f"✅ ESTOQUE ATINGIDO! A planilha já tem vídeos completos até {maior_data}.")
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
    persona = video["personagem"]
    idioma = video["idioma"]
    foco_teologico = video["foco"]
    
    if dia_da_semana == 4: 
        if horario in["06:00", "14:00"]:
            foco_teologico += " ENFOQUE: Misericordia y Perdón (Tono suave y esperanzador)."
        else:
            foco_teologico += " ENFOQUE: La Pasión de Cristo y el Sacrificio (Tono profundo y reflexivo)."

    print(f"🎬 PRODUZINDO SLOT: {horario} | Personagem: {persona}")
    
    instrucao_abertura = ""
    if "Protección" in pilar_do_dia: instrucao_abertura = "Comienza reconociendo una amenaza o dificultad invisible, y luego invoca la protección divina."
    elif "Salud" in pilar_do_dia: instrucao_abertura = "Comienza con una profunda gratitud por el cuerpo y el aliento de vida, antes de pedir sanación."
    elif "Familia" in pilar_do_dia: instrucao_abertura = "Comienza evocando una escena cotidiana y cálida del hogar y la familia."
    elif "Prosperidad" in pilar_do_dia: instrucao_abertura = "Comienza reconociendo el esfuerzo, el sudor del trabajo diario y la necesidad de la providencia."
    elif "Perdón" in pilar_do_dia: instrucao_abertura = "Comienza contemplando el amor incondicional y la necesidad de purificar el alma."
    elif "Consagración" in pilar_do_dia: instrucao_abertura = "Comienza con una imagen poética y maternal de la Virgen María cubriéndonos con su manto."
    elif "Gratitud" in pilar_do_dia: instrucao_abertura = "Comienza con un fuerte y alegre agradecimiento por el milagro de la vida."

    tema_gerado = None
    prompt_tema = f"""
    Actúa como un Teólogo católico. Crea un tema corto (máximo 8 palabras) para una oración. 
    El enfoque principal (pilar) es '{pilar_do_dia}', la oración está dirigida a '{persona}' y el momento del día es '{foco_teologico}'. 
    Responde SOLO con el tema, sin comillas.
    """
    
    for tentativa in range(5):
        try:
            modelo_atual = modelos_cascata[tentativa]
            resp_tema = client.models.generate_content(model=modelo_atual, contents=prompt_tema)
            tema_gerado = resp_tema.text.strip()
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

    regra_meditacao = ""
    if horario in["18:00", "21:00"]:
        regra_meditacao = "OBLIGATORIO: En la descripción (DESC), añade un aviso destacado diciendo que al final del video hay 5 minutos de música celestial para dormir/meditar. Además, añade un 4º Capítulo en los Timestamps llamado 'Meditación y Paz Profunda'."

    texto_ia = None
    prompt_principal = f"""
    Actúa como un guía espiritual y hermano en la fe, con profundo conocimiento teológico pero lenguaje cercano, cálido y devocional.
    Escribe una oración extensa y profunda de aproximadamente 1500 a 1800 palabras sobre el tema "{tema_gerado}" para {persona}. 
    
    CONTEXTO OBLIGATORIO DEL HORARIO Y PILAR:
    Esta oración será publicada a las {horario}. El enfoque teológico DEBE ser: "{foco_teologico}". 
    
    REGLAS CRÍTICAS DE RETENCIÓN, TTS Y MONETIZACIÓN:
    1. AUDIENCIA GLOBAL: Tu audiencia es toda Latinoamérica y el mundo hispanohablante. PROHIBIDO mencionar países específicos. Usa un Español Latino neutro.
    2. GANCHO INICIAL (0-60s): NO te presentes. Empieza directamente con esta estructura: {instrucao_abertura}
    3. PROFUNDIDAD: Concéntrate en UN SOLO TEMA central. PROHIBIDO hacer "listas de supermercado" pidiendo por muchas cosas diferentes. Profundiza en la emoción.
    4. ARCO EN 3 ACTOS: Divide la oración en Vulnerabilidad -> Súplica -> Entrega/Gratitud.
    5. RITMO DE AUDIO Y PAUSAS: Escribe en párrafos cortos (máximo 3 líneas). OBLIGATORIO usar abundantes puntos suspensivos (...) a lo largo de la oración para forzar pausas dramáticas y reflexivas en la voz.
    6. CENSURA GRÁFICA: PROHIBIDO usar descripciones gráficas de violencia física. Usa metáforas suaves.
    7. CERO INTERJECCIONES: PROHIBIDO usar "¡Ay!", "¡Oh!", o exclamaciones teatrales.
    8. CIERRE Y LLAMADO ESPIRITUAL SUTIL: Termina la oración invitando sutilmente al oyente a dejar su petición en los comentarios (como un libro de intenciones) y a compartir esta luz. Hazlo sonar como una misión de fe, NUNCA como un YouTuber pidiendo likes.
    
    {regra_meditacao}
    
    DEBES usar EXACTAMENTE este formato con estas palabras clave en mayúsculas:
    TITULO:[Escribe aquí un título magnético y chamativo]
    THUMB:[Escribe aquí una frase de impacto de MÁXIMO 4 PALABRAS para usar en la miniatura del video]
    GUION:[Escribe aquí la oración completa de aproximadamente 1500 a 1800 palabras siguiendo las reglas]
    DESC:[Escribe aquí una descripción de 3 párrafos con fuerte SEO, seguida obligatoriamente de los Capítulos/Timestamps (ej: 00:00 Inicio, 03:00 Oración, 07:00 Bendición)]
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
        
        titulo_final = titulo_match.group(1).strip() if titulo_match else "Título Padrão"
        thumb_final = thumb_match.group(1).strip() if thumb_match else "ORACIÓN PODEROSA"
        roteiro_final = guion_match.group(1).strip() if guion_match else texto_ia 
        desc_final = desc_match.group(1).strip() if desc_match else "Descripción Padrão"
        tags_final = tags_match.group(1).strip() if tags_match else "Tags"
        
        nova_linha =[
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
