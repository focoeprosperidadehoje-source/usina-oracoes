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

print("🔐 Autenticando no Google Sheets via Service Account (SHORTS ES)...")
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
        return[melhor_flash, melhor_flash, melhor_flash, melhor_pro, melhor_pro]
    except:
        return['gemini-2.5-flash', 'gemini-2.5-flash', 'gemini-3.1-flash-lite', 'gemini-3.1-flash-lite', 'gemini-2.5-pro']

modelos_cascata = obter_cascata_de_modelos()

# ==============================================================================
# 2. CONFIGURAÇÕES DA FÁBRICA DE SHORTS
# ==============================================================================
ID_PLANILHA = "1KgIjWrLUVlllhlZB1R9fkHGxxZlLsax1aOVGZrYwgnU"

PILARES = {
    0: "Guerra Espiritual y Protección", 1: "Liberación de Vicios y Ataduras",
    2: "Restauración Familiar y Matrimonial", 3: "Providencia y Puertas Abiertas",
    4: "Misericordia y Sanación Física", 5: "El Manto de Guadalupe", 6: "Milagros y Gratitud"
}

# Grade de Shorts e seus respectivos "Ecos" nos vídeos longos
GRADE_SHORTS =[
    {"horario": "08:00", "personagem": "Jesus", "idioma": "ES", "foco": "Mañana: Dirección y fuerza.", "ref": "06:00"},
    {"horario": "13:00", "personagem": "Maria", "idioma": "ES", "foco": "Mediodía: Causas imposibles y consuelo.", "ref": "12:00"},
    {"horario": "19:00", "personagem": "Maria", "idioma": "ES", "foco": "Atardecer: Paz en el hogar y protección.", "ref": "18:00"},
    {"horario": "22:00", "personagem": "Jesus", "idioma": "ES", "foco": "Noche: Dormir en paz y perdón.", "ref": "21:00"}
]

print("📡 Conectando à planilha online...")
planilha = gc.open_by_key(ID_PLANILHA)

# BUSCA POR NOME EXATO (Blindagem contra mudança de ordem das abas)
try:
    aba_shorts = planilha.worksheet("ES_SHORTS")
    aba_longos = planilha.worksheet("ES")
except Exception as e:
    print(f"❌ ERRO FATAL: Abas 'ES_SHORTS' ou 'ES' não encontradas. Verifique os nomes. Detalhe: {e}")
    sys.exit(1)

# ==============================================================================
# 3. RADAR DE ESTOQUE E SCANNER DE BURACOS (SHORTS)
# ==============================================================================
todas_linhas_shorts = aba_shorts.get_all_values()
total_linhas = len(todas_linhas_shorts)

if total_linhas > 500:
    print("🧹 Planilha de Shorts pesada. Iniciando Auto-Limpeza...")
    aba_shorts.delete_rows(2, 100)
    todas_linhas_shorts = aba_shorts.get_all_values()

proxima_linha_vazia = len(todas_linhas_shorts) + 1

valores_coluna_a = [linha[0].strip() for linha in todas_linhas_shorts[1:] if len(linha) > 0]
valores_coluna_b = [linha[1].strip() for linha in todas_linhas_shorts[1:] if len(linha) > 1]

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
data_alvo = None
grade_para_processar =[]

data_check = limite_passado
while data_check <= meta_estoque:
    horarios_presentes = dias_existentes.get(data_check,[])
    if len(horarios_presentes) < 4:
        data_alvo = data_check
        grade_para_processar =[v for v in GRADE_SHORTS if v["horario"] not in horarios_presentes]
        print(f"⚠️ BURACO ENCONTRADO NOS SHORTS: Faltam horários no día {data_alvo}.")
        break
    data_check += datetime.timedelta(days=1)

if not data_alvo:
    print(f"✅ ESTOQUE DE SHORTS ATINGIDO até {meta_estoque - datetime.timedelta(days=1)}. Dormindo.")
    sys.exit(0)

pilar_do_dia = PILARES[data_alvo.weekday()]
print(f"\n📅 DATA ALVO SHORTS: {data_alvo} | Pilar: {pilar_do_dia}")

# Puxa os dados dos vídeos longos para fazer o "Eco"
dados_longos = aba_longos.get_all_values()

# ==============================================================================
# 4. PRODUÇÃO EM MASSA (LOOP PERFEITO + ECO)
# ==============================================================================
esperas_exponenciais =[10, 20, 40, 80, 120]

for video in grade_para_processar:
    horario = video["horario"]
    persona = video["personagem"].upper()
    idioma = video["idioma"]
    foco_teologico = video["foco"]
    horario_ref = video["ref"]
    
    print(f"🎬 PRODUZINDO SHORT: {horario} | Personagem: {persona}")
    
    # --- A ESTRATÉGIA DE ECO (Buscando o título do vídeo longo) ---
    titulo_referencia = ""
    for linha in dados_longos[1:]:
        if len(linha) > 6:
            d_longo = linha[0].strip()
            h_longo = linha[1].strip()
            if d_longo == str(data_alvo) and h_longo == horario_ref:
                titulo_referencia = linha[6].strip() # Coluna G (Titulo)
                break
                
    contexto_eco = f"El video largo correspondiente de hoy tiene el título: '{titulo_referencia}'. El Short DEBE ser un eco de este tema." if titulo_referencia else ""
    
    persona_prompt = "Jesucristo" if persona == 'JESUS' else "la Virgen de Guadalupe (La Morenita)"
    
    # --- ORAÇÕES COM PAUSAS FORÇADAS PARA O EDGE-TTS ---
    if persona == 'JESUS':
        oracao_padrao = "Padre nuestro que estás en el cielo... santificado sea tu nombre... venga a nosotros tu reino... hágase tu voluntad en la tierra como en el cielo... Danos hoy nuestro pan de cada día... perdona nuestras ofensas... como también nosotros perdonamos a los que nos ofenden... no nos dejes caer en la tentación... y líbranos del mal... Amén."
    else:
        oracao_padrao = "Dios te salve, María... llena eres de gracia... el Señor es contigo... bendita tú eres entre todas las mujeres... y bendito es el fruto de tu vientre, Jesús... Santa María, Madre de Dios... ruega por nosotros, pecadores... ahora y en la hora de nuestra muerte... Amén. Santa María de Guadalupe... salva nuestras familias y conserva nuestra fe."

    prompt_principal = f"""
    Actúa como un guía espiritual católico. Crea un guion para un video SHORT de YouTube (máximo 40 segundos de lectura).
    Tema del día: {pilar_do_dia}. Foco: {foco_teologico}. Dirigido a: {persona_prompt}.
    {contexto_eco}
    
    ESTRUCTURA OBLIGATORIA DEL GUION (LOOP PERFECTO):
    1. GANCHO (Inicio): La primera frase del video. OBLIGATORIO empezar con puntos suspensivos en minúscula (ej: "...la paz que tanto buscas."). Debe conectar con el final.
    2. ORACIÓN: Escribe EXACTAMENTE esta oración en el medio: "{oracao_padrao}"
    3. CTA Y LOOP (Final): Invita al oyente a buscar la oración completa en el canal. La última frase OBLIGATORIAMENTE debe terminar con puntos suspensivos (ej: "Cierra los ojos y recibe...").
    
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
    for tentativa in range(5): 
        try:
            modelo_atual = modelos_cascata[tentativa]
            print(f"   ⏳ Escrevendo roteiro do Short (Tentativa {tentativa+1}/5 com {modelo_atual})...")
            response = client.models.generate_content(model=modelo_atual, contents=prompt_principal)
            texto_ia = response.text
            break 
        except Exception as e:
            espera = esperas_exponenciais[tentativa]
            print(f"   ⚠️ Falha na IA (Tentativa {tentativa+1}/5). Aguardando {espera}s...")
            time.sleep(espera)
            
    if not texto_ia:
        print("   ❌ Falha definitiva no roteiro. Pulando este Short.")
        continue

    try:
        t_match = re.search(r'T[IÍ]TULO:\s*(.*?)(?=GUI[OÓ]N:|DESC:|TAGS:|$)', texto_ia, re.IGNORECASE | re.DOTALL)
        g_match = re.search(r'GUI[OÓ]N:\s*(.*?)(?=DESC:|TAGS:|T[IÍ]TULO:|$)', texto_ia, re.IGNORECASE | re.DOTALL)
        d_match = re.search(r'DESC:\s*(.*?)(?=TAGS:|T[IÍ]TULO:|GUI[OÓ]N:|$)', texto_ia, re.IGNORECASE | re.DOTALL)
        tg_match = re.search(r'TAGS:\s*(.*?)(?=T[IÍ]TULO:|GUI[OÓ]N:|DESC:|$)', texto_ia, re.IGNORECASE | re.DOTALL)
        
        titulo_final = t_match.group(1).replace('*', '').replace('"', '').replace('[', '').replace(']', '').strip() if t_match else "Oración Poderosa #Shorts"
        roteiro_final = g_match.group(1).strip() if g_match else texto_ia 
        desc_final = d_match.group(1).strip() if d_match else "¡Visita nuestro canal para la oración completa!"
        tags_final = tg_match.group(1).replace('*', '').replace('[', '').replace(']', '').strip() if tg_match else "shorts, oracion, fe"
        
        # A linha de Shorts tem 12 colunas, mas não usa Tema separado nem Texto_Thumb. Preenchemos com "N/A"
        nova_linha =[
            str(data_alvo), horario, "Pronto p/ Áudio", persona, idioma, 
            pilar_do_dia, titulo_final, roteiro_final, tags_final, desc_final, "N/A", "N/A"
        ]
        
        intervalo = f"A{proxima_linha_vazia}:L{proxima_linha_vazia}"
        aba_shorts.update(values=[nova_linha], range_name=intervalo)
        
        print(f"   ✅ SUCESSO! Short da linha {proxima_linha_vazia} preenchido.")
        
        proxima_linha_vazia += 1 
        time.sleep(5)
        
    except Exception as e:
        print(f"   ❌ Falha ao salvar na planilha: {e}")

print("\n🚀 USINA DE SHORTS CONCLUÍDA! Processo finalizado.")
