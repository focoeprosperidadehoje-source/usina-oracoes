import os
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

# ==============================================================================
# 2. AUTENTICAÇÃO INVISÍVEL (SEM POP-UP)
# ==============================================================================
print("🔐 Autenticando no Google Sheets via Service Account...")
credenciais_dict = json.loads(GOOGLE_JSON)
escopos =['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
credenciais = Credentials.from_service_account_info(credenciais_dict, scopes=escopos)
gc = gspread.authorize(credenciais)

client = Client(api_key=CHAVE_API, http_options={'api_version': 'v1'})

# ==============================================================================
# 3. CONFIGURAÇÕES DA FÁBRICA
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
    {"horario": "06:00", "personagem": "Jesus", "idioma": "ES"},
    {"horario": "14:00", "personagem": "Maria", "idioma": "ES"},
    {"horario": "18:00", "personagem": "Maria", "idioma": "ES"},
    {"horario": "21:00", "personagem": "Jesus", "idioma": "ES"}
]

print("📡 Conectando à planilha online...")
planilha = gc.open_by_key(ID_PLANILHA)
aba = planilha.get_worksheet(0)

# ==============================================================================
# 4. LÓGICA DE DATA AUTOMÁTICA (O MOTOR PERPÉTUO)
# ==============================================================================
dados = aba.get_all_records()

ultima_data_str = None
if len(dados) > 0:
    ultima_data_str = str(dados[-1].get('Data', '')).strip()

if ultima_data_str:
    try:
        ultima_data = datetime.datetime.strptime(ultima_data_str, '%Y-%m-%d').date()
        data_alvo = ultima_data + datetime.timedelta(days=1)
    except:
        data_alvo = datetime.date.today()
else:
    data_alvo = datetime.date.today()

dia_da_semana = data_alvo.weekday()
pilar_do_dia = PILARES[dia_da_semana]

print(f"\n📅 DATA ALVO DEFINIDA: {data_alvo} | Pilar: {pilar_do_dia}")
print("⚙️ Iniciando a produção dos 4 vídeos do dia...\n")

# ==============================================================================
# 5. PRODUÇÃO EM MASSA
# ==============================================================================
for video in GRADE_DIARIA:
    horario = video["horario"]
    persona = video["personagem"]
    idioma = video["idioma"]
    
    print(f"🎬 PRODUZINDO SLOT: {horario} | Personagem: {persona}")
    
    prompt_tema = f"""
    Actúa como un Teólogo católico. Crea un tema corto (máximo 8 palabras) para una oración. 
    El enfoque principal (pilar) es '{pilar_do_dia}' y la oración está dirigida a '{persona}'. 
    Responde SOLO con el tema, sin comillas.
    """
    try:
        resp_tema = client.models.generate_content(model='gemini-2.5-flash', contents=prompt_tema)
        tema_gerado = resp_tema.text.strip()
        print(f"   ✨ Tema Criado: {tema_gerado}")
    except Exception as e:
        print(f"   ❌ Erro no tema: {e}")
        continue

    time.sleep(3)

    prompt_principal = f"""
    Actúa como un Sacerdote y Teólogo mexicano. 
    Escribe una oración de aproximadamente 1500 palabras sobre el tema "{tema_gerado}" para {persona}. 
    Asegúrate de concluir el razonamiento y la oración de forma natural y completa.
    Idioma: Español de México. NO guion de cine.
    
    DEBES usar EXACTAMENTE este formato con estas palabras clave en mayúsculas:
    TITULO:[Escribe aquí un título magnético y chamativo]
    GUION:[Escribe aquí la oración completa de 1500 palabras]
    DESC:[Escribe aquí una descripción persuasiva para YouTube]
    TAGS:[Escribe aquí las etiquetas separadas por comas]
    """
    
    try:
        print(f"   ⏳ Escrevendo roteiro de 1500 palabras...")
        response = client.models.generate_content(model='gemini-2.5-flash', contents=prompt_principal)
        texto_ia = response.text
        
        titulo_match = re.search(r'TITULO:\s*(.*?)(?=GUION:|DESC:|TAGS:|$)', texto_ia, re.IGNORECASE | re.DOTALL)
        guion_match = re.search(r'GUION:\s*(.*?)(?=DESC:|TAGS:|TITULO:|$)', texto_ia, re.IGNORECASE | re.DOTALL)
        desc_match = re.search(r'DESC:\s*(.*?)(?=TAGS:|TITULO:|GUION:|$)', texto_ia, re.IGNORECASE | re.DOTALL)
        tags_match = re.search(r'TAGS:\s*(.*?)(?=TITULO:|GUION:|DESC:|$)', texto_ia, re.IGNORECASE | re.DOTALL)
        
        titulo_final = titulo_match.group(1).strip() if titulo_match else "Título Padrão"
        roteiro_final = guion_match.group(1).strip() if guion_match else texto_ia 
        desc_final = desc_match.group(1).strip() if desc_match else "Descrição Padrão"
        tags_final = tags_match.group(1).strip() if tags_match else "Tags"
        
        nova_linha =[
            str(data_alvo), horario, "Pronto p/ Áudio", persona, idioma, 
            tema_gerado, titulo_final, roteiro_final, tags_final, desc_final, "Pendente"
        ]
        
        aba.append_row(nova_linha)
        print(f"   ✅ SUCESSO! Linha adicionada na planilha.")
        time.sleep(5)
        
    except Exception as e:
        print(f"   ❌ Falha ao gerar conteúdo: {e}")

print("\n🚀 FÁBRICA CONCLUÍDA! 4 novos vídeos foram roteirizados.")
