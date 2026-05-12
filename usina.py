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

print("🔐 Autenticando no Google Sheets via Service Account...")
credenciais_dict = json.loads(GOOGLE_JSON)
escopos =['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
credenciais = Credentials.from_service_account_info(credenciais_dict, scopes=escopos)
gc = gspread.authorize(credenciais)

client = Client(api_key=CHAVE_API, http_options={'api_version': 'v1'})

def obter_cascata_de_modelos():
    print("📡 Escaneando servidores do Google pelas IAs mais modernas...")
    try:
        modelos_disponiveis = client.models.list()
        flash_models =[m.name for m in modelos_disponiveis if 'generateContent' in m.supported_generation_methods and 'exp' not in m.name and 'flash' in m.name and '8b' not in m.name]
        pro_models =[m.name for m in modelos_disponiveis if 'generateContent' in m.supported_generation_methods and 'exp' not in m.name and 'pro' in m.name and 'vision' not in m.name]
        
        melhor_flash = sorted(flash_models, reverse=True)[0] if flash_models else 'gemini-2.5-flash'
        melhor_pro = sorted(pro_models, reverse=True)[0] if pro_models else 'gemini-2.5-pro'
        print(f"   ✅ Modelos atualizados: {melhor_flash} e {melhor_pro}")
        return[melhor_flash, melhor_flash, melhor_flash, melhor_pro, melhor_pro]
    except:
        return['gemini-2.5-flash', 'gemini-2.5-flash', 'gemini-3.1-flash-lite', 'gemini-3.1-flash-lite', 'gemini-2.5-pro']

modelos_cascata = obter_cascata_de_modelos()

ID_PLANILHA = "1KgIjWrLUVlllhlZB1R9fkHGxxZlLsax1aOVGZrYwgnU"
PILARES = {
    0: "Guerra Espiritual y Protección (Lunes)", 1: "Liberación de Vicios y Ataduras (Martes)",
    2: "Restauración Familiar y Matrimonial (Miércoles)", 3: "Providencia y Puertas Abiertas (Jueves)",
    4: "Misericordia y Sanación Física (Viernes)", 5: "El Manto de Guadalupe (Sábado)", 6: "Milagros y Gratitud (Domingo)"
}
GRADE_DIARIA =[
    {"horario": "06:00", "personagem": "Jesus", "idioma": "ES", "foco": "Mañana: Consagración, fuerza y protección para el día que nace.", "periodo": "en esta mañana"},
    {"horario": "12:00", "personagem": "Maria", "idioma": "ES", "foco": "Mediodía: Intercesión por la familia, salud y las aflicciones de la jornada.", "periodo": "en este mediodía"},
    {"horario": "18:00", "personagem": "Maria", "idioma": "ES", "foco": "Atardecer: Acogimiento maternal, consuelo y gratitud por el día.", "periodo": "en este atardecer"},
    {"horario": "21:00", "personagem": "Jesus", "idioma": "ES", "foco": "Noche: Entrega del sueño, perdón y descanso profundo en Dios.", "periodo": "en esta noche"}
]

aba = gc.open_by_key(ID_PLANILHA).get_worksheet(0)

todas_linhas = aba.get_all_values()
if len(todas_linhas) > 500:
    print("🧹 Planilha pesada. Iniciando Auto-Limpeza...")
    aba.delete_rows(2, 100)
    todas_linhas = aba.get_all_values()

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
    if len(horarios_presentes) < 4:
        data_alvo = data_check
        grade_para_processar =[v for v in GRADE_DIARIA if v["horario"] not in horarios_presentes]
        break
    data_check += datetime.timedelta(days=1)

if not data_alvo:
    print(f"✅ ESTOQUE ATINGIDO até {meta_estoque - datetime.timedelta(days=1)}. Dormindo.")
    sys.exit(0)

pilar_do_dia = PILARES[data_alvo.weekday()]
print(f"\n📅 DATA ALVO: {data_alvo} | Pilar: {pilar_do_dia}")

esperas_exponenciais =[10, 20, 40, 80, 120]

for video in grade_para_processar:
    horario, persona, idioma, foco_teologico, periodo = video["horario"], video["personagem"].upper(), video["idioma"], video["foco"], video["periodo"]
    if data_alvo.weekday() == 4:
        foco_teologico += " ENFOQUE: Misericordia y Perdón." if horario in["06:00", "12:00"] else " ENFOQUE: La Pasión de Cristo y el Sacrificio."

    print(f"🎬 PRODUZINDO: {horario} | {persona}")
    
    instrucao_abertura = ""
    if "Guerra" in pilar_do_dia: instrucao_abertura = "Haz la ambientación sensorial del momento del día y luego invoca protección contra amenazas o envidias invisibles."
    elif "Vicios" in pilar_do_dia: instrucao_abertura = "Haz la ambientación sensorial del momento del día y luego pide liberación por un ser querido en ataduras."
    elif "Familiar" in pilar_do_dia: instrucao_abertura = "Haz la ambientación sensorial del momento del día y luego evoca el deseo de paz en el hogar."
    elif "Providencia" in pilar_do_dia: instrucao_abertura = "Haz la ambientación sensorial del momento del día y luego reconoce el esfuerzo y la necesidad de puertas abiertas."
    elif "Misericordia" in pilar_do_dia: instrucao_abertura = "Haz la ambientación sensorial del momento del día y luego pide sanación para el cuerpo y perdón para el alma."
    elif "Manto" in pilar_do_dia: instrucao_abertura = "Haz la ambientación sensorial del momento del día y luego pide ser escondido bajo el manto sagrado."
    elif "Milagros" in pilar_do_dia: instrucao_abertura = "Haz la ambientación sensorial del momento del día y luego agradece fuertemente por los milagros."

    persona_prompt = "Jesucristo" if persona == 'JESUS' else "la Virgen de Guadalupe (cariñosamente llamada La Morenita)"

    prompt_tema = f"Actúa como Teólogo. Crea un tema corto (máx 8 palabras) para una oración. Pilar: '{pilar_do_dia}', dirigida a '{persona_prompt}', momento: '{foco_teologico}'. SOLO el tema, sin comillas ni asteriscos."
    tema_gerado = None
    for i in range(5):
        try:
            tema_gerado = client.models.generate_content(model=modelos_cascata[i], contents=prompt_tema).text.replace('*', '').replace('"', '').replace('[', '').replace(']', '').strip()
            break 
        except Exception as e: time.sleep(esperas_exponenciais[i])
            
    if not tema_gerado: continue 
    time.sleep(5)

    regra_meditacao = "OBLIGATORIO: En la descripción (DESC), añade un aviso destacado diciendo que al final del video hay 5 minutos de música celestial para dormir/meditar." if horario in["18:00", "21:00"] else ""
    cta_comentarios = "Pide al oyente que escriba un motivo de gratitud en los comentarios." if horario in["18:00", "21:00"] else "Pide al oyente que escriba su intención o petición para el día en los comentarios."
    regra_persona = "OBLIGATORIO: Como te diriges a Jesucristo, ESTÁ ESTRICTAMENTE PROHIBIDO mencionar a María, la Virgen o Guadalupe." if persona == 'JESUS' else "OBLIGATORIO: Como te diriges a María, DEBES usar las invocaciones 'Virgen de Guadalupe', 'Madre de Guadalupe' y referirte a ella cariñosamente como 'La Morenita'."
    
    prompt_principal = f"""
    Actúa como un guía espiritual y hermano en la fe. Escribe una oración extensa de 1500 a 1800 palabras sobre "{tema_gerado}" dirigida a {persona_prompt}. 
    CONTEXTO: Enfoque: "{foco_teologico}". 
    
    REGLAS CRÍTICAS DE RETENCIÓN, TTS Y MONETIZACIÓN:
    1. AUDIENCIA GLOBAL: Español Latino neutro. PROHIBIDO mencionar países.
    2. HORARIOS: PROHIBIDO mencionar la hora exacta (como 06:00 o 18:00). Usa SOLO la expresión "{periodo}".
    3. GANCHO INICIAL MATADOR (0-60s): NO te presentes. Empieza la primera frase con una AFIRMACIÓN EMPÁTICA sobre el dolor o la esperanza del oyente (Ej: 'Sé que el cansancio pesa en tus hombros hoy...'). LUEGO, conecta con esta estructura: {instrucao_abertura}. LUEGO, haz una promesa de que si se queda hasta el final, encontrará alivio.
    4. PROFUNDIDAD: UN SOLO TEMA central. Párrafos elaborados y profundos. NO hagas listas de pedidos.
    5. RESET DE ATENCIÓN: A la mitad de la oración, antes de pedir por la salud, inserta un 'Reset de Atención' hablado (Ej: 'Presta mucha atención ahora, no dejes que las distracciones te alejen, porque vamos a clamar por tu salud...').
    6. ARCO: Vulnerabilidad -> Súplica -> Entrega/Gratitud. Incluye bloque pidiendo por la salud de los enfermos.
    7. PAUSAS: OBLIGATORIO usar abundantes puntos suspensivos (...) para forzar pausas en la voz.
    8. CENSURA: PROHIBIDO descripciones de violencia física.
    9. CERO INTERJECCIONES: PROHIBIDO usar "¡Ay!", "¡Oh!".
    10. CIERRE: {cta_comentarios} Hazlo sonar como misión de fe, NUNCA pidiendo likes.
    11. ANTI-JSON: Escribe en TEXTO PLANO. PROHIBIDO JSON, llaves {{ }} o asteriscos (*).
    
    {regra_persona}
    {regra_meditacao}
    
    FORMATO EXACTO:
    TITULO:[Título magnético. FORMATO: "[Promesa Urgente o Gatillo de Alivio] - Oración {periodo}". SIN FECHA. SIN ASTERISCOS NI CORCHETES]
    THUMB:[Frase de impacto de MÁXIMO 4 PALABRAS. Promesa urgente. SIN ASTERISCOS NI CORCHETES]
    GUION:[Oración completa de 1500 a 1800 palabras]
    DESC:[Descripción de 3 párrafos con fuerte SEO]
    TAGS:[Etiquetas separadas por comas]
    """
    
    texto_ia = None
    for i in range(5): 
        try:
            texto_ia = client.models.generate_content(model=modelos_cascata[i], contents=prompt_principal).text
            break 
        except Exception as e: time.sleep(esperas_exponenciais[i])
            
    if not texto_ia: continue

    try:
        t_match = re.search(r'T[IÍ]TULO:\s*(.*?)(?=THUMB:|GUI[OÓ]N:|DESC:|TAGS:|$)', texto_ia, re.IGNORECASE | re.DOTALL)
        th_match = re.search(r'THUMB:\s*(.*?)(?=GUI[OÓ]N:|DESC:|TAGS:|T[IÍ]TULO:|$)', texto_ia, re.IGNORECASE | re.DOTALL)
        g_match = re.search(r'GUI[OÓ]N:\s*(.*?)(?=DESC:|TAGS:|T[IÍ]TULO:|THUMB:|$)', texto_ia, re.IGNORECASE | re.DOTALL)
        d_match = re.search(r'DESC:\s*(.*?)(?=TAGS:|T[IÍ]TULO:|THUMB:|GUI[OÓ]N:|$)', texto_ia, re.IGNORECASE | re.DOTALL)
        tg_match = re.search(r'TAGS:\s*(.*?)(?=T[IÍ]TULO:|THUMB:|GUI[OÓ]N:|DESC:|$)', texto_ia, re.IGNORECASE | re.DOTALL)
        
        titulo_final = t_match.group(1).replace('*', '').replace('"', '').replace('[', '').replace(']', '').strip() if t_match else "Título Padrão"
        thumb_final = th_match.group(1).replace('*', '').replace('"', '').replace('[', '').replace(']', '').strip() if th_match else "ORACIÓN PODEROSA"
        roteiro_final = g_match.group(1).strip() if g_match else texto_ia 
        desc_final = d_match.group(1).strip() if d_match else "Descripción Padrão"
        tags_final = tg_match.group(1).replace('*', '').replace('[', '').replace(']', '').strip() if tg_match else "Tags"
        
        nova_linha =[str(data_alvo), horario, "Pronto p/ Áudio", persona, idioma, tema_gerado, titulo_final, roteiro_final, tags_final, desc_final, "Pendente", thumb_final]
        aba.update(values=[nova_linha], range_name=f"A{proxima_linha_vazia}:L{proxima_linha_vazia}")
        print(f"   ✅ SUCESSO! Linha {proxima_linha_vazia} preenchida.")
        proxima_linha_vazia += 1 
        time.sleep(5)
    except Exception as e: print(f"   ❌ Falha ao salvar: {e}")
