import os
import sys
import json
import time
import re
import datetime
from google.genai import Client
from google.oauth2.service_account import Credentials
import gspread

CHAVE_API = os.environ.get("GEMINI_API_KEY")
GOOGLE_JSON = os.environ.get("GOOGLE_CREDENTIALS")

print("🔐 Autenticando no Google Sheets (SHORTS ES)...")
credenciais_dict = json.loads(GOOGLE_JSON)
creds = Credentials.from_service_account_info(credenciais_dict, scopes=['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive'])
gc = gspread.authorize(creds)
client = Client(api_key=CHAVE_API, http_options={'api_version': 'v1'})

def obter_modelo_lite():
    try:
        modelos = client.models.list()
        lite =[m.name for m in modelos if 'generateContent' in m.supported_generation_methods and 'flash-lite' in m.name]
        return sorted(lite, reverse=True)[0] if lite else 'gemini-2.5-flash'
    except: return 'gemini-2.5-flash'

modelo_usina = obter_modelo_lite()
ID_PLANILHA = "1KgIjWrLUVlllhlZB1R9fkHGxxZlLsax1aOVGZrYwgnU"

PILARES = {
    0: "Guerra Espiritual y Protección", 1: "Liberación de Vicios y Ataduras", 2: "Restauración Familiar y Matrimonial",
    3: "Providencia y Puertas Abiertas", 4: "Misericordia y Sanación Física", 5: "El Manto de Guadalupe", 6: "Milagros y Gratitud"
}

# NOVA GRADE SHORTS: Apenas 14:00 (Maria)
GRADE_SHORTS =[
    {"horario": "14:00", "personagem": "Maria", "idioma": "ES", "foco": "Mediodía: Causas imposibles, sanación física y milagros.", "ref": "18:00"}
]

# CORREÇÃO: BUSCA POR NOME EXATO
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
                if d_obj not in dias_existentes: dias_existentes[d_obj] =[]
                dias_existentes[d_obj].append(h_str)
        except: pass

meta_estoque = hoje + datetime.timedelta(days=5)
data_alvo = None
grade_para_processar =[]

data_check = limite_passado
while data_check <= meta_estoque:
    horarios_presentes = dias_existentes.get(data_check,[])
    if len(horarios_presentes) < len(GRADE_SHORTS):
        data_alvo = data_check
        grade_para_processar = [v for v in GRADE_SHORTS if v["horario"] not in horarios_presentes]
        break
    data_check += datetime.timedelta(days=1)

if not data_alvo:
    print(f"✅ ESTOQUE DE SHORTS ATINGIDO até {meta_estoque - datetime.timedelta(days=1)}. Dormindo.")
    sys.exit(0)

pilar_do_dia = PILARES[data_alvo.weekday()]
print(f"\n📅 DATA ALVO SHORTS: {data_alvo} | Pilar: {pilar_do_dia}")

dados_longos = aba_longos.get_all_values()

for video in grade_para_processar:
    horario, persona, idioma, foco_teologico = video["horario"], video["personagem"].upper(), video["idioma"], video["foco"]
    print(f"🎬 PRODUZINDO SHORT: {horario} | {persona}")
    
    horario_longo_ref = video["ref"]
    titulo_referencia = ""
    for linha in dados_longos[1:]:
        if len(linha) > 6 and linha[0].strip() == str(data_alvo) and linha[1].strip() == horario_longo_ref:
            titulo_referencia = linha[6].strip() 
            break
            
    contexto_eco = f"El video largo correspondiente de hoy tiene el título: '{titulo_referencia}'. El Short DEBE ser un eco de este tema." if titulo_referencia else ""
    persona_prompt = "Jesucristo" if persona == 'JESUS' else "la Virgen de Guadalupe (La Morenita)"
    
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

    EJEMPLO DE LOOP SINTÁCTICO PERFECTO:
    Final (incompleto): "...es por eso que hoy necesitas recibir..."
    Inicio (complemento): "...la gracia que la Virgen guardó especialmente para ti."
    Leídas en secuencia forman: "es por eso que hoy necesitas recibir la gracia que la Virgen guardó especialmente para ti."
    
    REGLAS DE FLUIDEZ Y CENSURA:
    - Escribe frases fluidas. Usa reticencias (...) para marcar pausas de respiración.
    - PROHIBIDO descripciones de violencia física o sangre.
    - El título debe empezar con "Oración Poderosa: " seguido del tema, y terminar con la etiqueta #Shorts.
    - ANTI-JSON: Escribe en TEXTO PLANO. PROHIBIDO usar formato JSON, llaves {{ }} o asteriscos (*).
    
    FORMATO EXACTO:
    TITULO:[Oración Poderosa: Tema - #Shorts]
    GUION:[Guion completo con el efecto loop]
    DESC:[Descripción corta invitando a visitar el canal y las listas de reproducción]
    TAGS:[Etiquetas separadas por comas]
    """
    
    texto_ia = None
    for _ in range(3): 
        try:
            texto_ia = client.models.generate_content(model=modelo_usina, contents=prompt_principal).text
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
        tags_final = tg_match.group(1).replace('*', '').replace('[', '').replace(']', '').strip() if tg_match else "shorts, oracion, fe"
        
        nova_linha = [str(data_alvo), horario, "Pronto p/ Áudio", persona, idioma, pilar_do_dia, titulo_final, roteiro_final, tags_final, desc_final, "N/A", "N/A"]
        aba_shorts.update(values=[nova_linha], range_name=f"A{proxima_linha_vazia}:L{proxima_linha_vazia}")
        print(f"   ✅ SUCESSO! Short da linha {proxima_linha_vazia} preenchido.")
        proxima_linha_vazia += 1 
        time.sleep(3)
    except Exception as e: print(f"   ❌ Falha ao salvar: {e}")
