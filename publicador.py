import os, random, re, datetime, time, subprocess, pytz, json, gspread
from google.oauth2.service_account import Credentials
from google.oauth2.credentials import Credentials as YTCredentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.auth.transport.requests import Request
from PIL import Image, ImageDraw, ImageFont
import textwrap
from googleapiclient.discovery import build as build_drive

os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

# 1. PUXANDO AS CHAVES DO COFRE DO GITHUB
GOOGLE_JSON = os.environ.get("GOOGLE_CREDENTIALS")
YT_TOKEN_JSON = os.environ.get("YOUTUBE_TOKEN_ES")
HORARIO_ALVO = os.environ.get("HORARIO_ALVO")

print(f"🚀 INICIANDO SERVIDOR MATRIX PARA O HORÁRIO: {HORARIO_ALVO}")

# 2. AUTENTICAÇÃO PLANILHA E DRIVE (Invisível)
credenciais_dict = json.loads(GOOGLE_JSON)
creds_sheets = Credentials.from_service_account_info(credenciais_dict, scopes=['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive'])
gc = gspread.authorize(creds_sheets)

aba_principal = gc.open_by_key("1KgIjWrLUVlllhlZB1R9fkHGxxZlLsax1aOVGZrYwgnU").get_worksheet(0)
try: configs = gc.open_by_key("1KgIjWrLUVlllhlZB1R9fkHGxxZlLsax1aOVGZrYwgnU").worksheet("Configuracoes").get_all_records()
except: configs =[]

# 3. AUTENTICAÇÃO YOUTUBE (Com Renovação Automática)
creds_yt = YTCredentials.from_authorized_user_info(json.loads(YT_TOKEN_JSON))
if creds_yt and creds_yt.expired and creds_yt.refresh_token: 
    print("🔄 Renovando o Token do YouTube...")
    creds_yt.refresh(Request())
youtube = build('youtube', 'v3', credentials=creds_yt)
drive_service = build_drive('drive', 'v3', credentials=creds_sheets)

# 4. PASTAS TEMPORÁRIAS DO SERVIDOR LINUX
PASTA_TEMP = "/tmp/fabrica_dark"
os.makedirs(PASTA_TEMP, exist_ok=True)

# IDs REAIS DO SEU DRIVE
ID_PASTA_JESUS = "1kSl8xFW9_4Q_03XKq1c2dunovvlo3urH"
ID_PASTA_MARIA = "1FSpmGvSZDleU4gUJePAj4t5h0ZoVSmEo"
ID_PASTA_BROLLS = "1mY-ISStykefXFfLdyxKkci3_KpL0bS1z"
ID_PASTA_MUSICAS = "1gxZA1TlQPzuf737XOo_n8blfOThnddgm"
ID_PASTA_AVE_MARIA = "1VPmJ5JHXZ6ky0yRwVgqLmRZrl3HhtK3u"
ID_PASTA_SFX = "1CxSDrCzVatG0bZwTVIN6yDKLO7umIgaX"
ID_PASTA_THUMB_JESUS_DIA = "1d1KcGUy895ccivgio9QxVbIzSdNeCTN5"
ID_PASTA_THUMB_JESUS_NOITE = "1BFOWc6rNlhSpNAOatF2aWK7hEjPqMMzk"
ID_PASTA_THUMB_MARIA_DIA = "1HQZdx0DYsJNFIqoeYW6dXiNs6QXbCor_"

# --- FUNÇÕES DE INTELIGÊNCIA ---
def baixar_arquivo(file_id, destino):
    request = drive_service.files().get_media(fileId=file_id)
    with open(destino, 'wb') as f: f.write(request.execute())
    return destino

def listar_arquivos(folder_id, extensoes=None):
    res =[]
    page_token = None
    while True:
        try:
            response = drive_service.files().list(q=f"'{folder_id}' in parents and trashed=false", spaces='drive', fields='nextPageToken, files(id, name)', pageToken=page_token).execute()
            for f in response.get('files',[]):
                if extensoes:
                    if f['name'].lower().endswith(extensoes): res.append(f)
                else: res.append(f)
            page_token = response.get('nextPageToken', None)
            if not page_token: break
        except Exception as e:
            print(f"   ⚠️ Erro ao ler pasta {folder_id}: {e}")
            time.sleep(5)
            break
    return res

def obter_duracao(arquivo):
    try: return float(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1', arquivo], capture_output=True, text=True).stdout.strip())
    except: return 600 

def filtro_broll(nome, horario):
    n = nome.lower()
    if "06:00" in horario or "12:00" in horario: return any(x in n for x in ["dia", "velas"])
    elif "18:00" in horario: return any(x in n for x in["velas", "flores", "noite"])
    elif "21:00" in horario: return any(x in n for x in ["noite", "cosmos", "velas"])
    return True

def formatar_vtt(caminho_vtt):
    if not os.path.exists(caminho_vtt): return
    with open(caminho_vtt, 'r', encoding='utf-8') as f: linhas = f.readlines()
    with open(caminho_vtt, 'w', encoding='utf-8') as f:
        for l in linhas:
            if '-->' in l or l.strip() == '' or l.startswith('WEBVTT'): f.write(l)
            else: f.write(textwrap.fill(l.strip(), width=40) + '\n')

def format_time(seconds):
    return f"{int(seconds // 60):02d}:{int(seconds % 60):02d}"

def criar_thumbnail(img_path, texto_curto, horario, persona, caminho_saida):
    img = Image.open(img_path).convert("RGBA")
    img_ratio = img.width / img.height
    if img_ratio > 1920/1080:
        nw = int(img.height * (1920/1080))
        off = (img.width - nw) / 2
        img = img.crop((off, 0, img.width - off, img.height))
    else:
        nh = int(img.width / (1920/1080))
        off = (img.height - nh) / 2
        img = img.crop((0, off, img.width, img.height - off))
    img = img.resize((1920, 1080))
    
    draw = ImageDraw.Draw(img)
    
    # BARRA VERTICAL GROSSA (120px) COM NOVAS CORES
    if "06:00" in horario: cor_barra = "#FFD700" # Dourado
    elif "12:00" in horario: cor_barra = "#FF8C00" # Laranja
    elif "18:00" in horario: cor_barra = "#228B22" # Verde
    else: cor_barra = "#00BFFF" # Azul Diamante
    draw.rectangle([(0, 0), (120, 1080)], fill=cor_barra)
    
    texto = texto_curto.upper()
    font_size = 200
    while font_size > 50:
        try: font = ImageFont.truetype("Anton.ttf", font_size)
        except: break
        linhas = textwrap.wrap(texto, width=10, break_long_words=False)[:3]
        if max([draw.textbbox((0, 0), l, font=font)[2] - draw.textbbox((0, 0), l, font=font)[0] for l in linhas] + [0]) <= 860: break
        font_size -= 5 
        
    y_text = (1080 - (len(linhas) * font_size * 1.1)) / 2
    cores = ["white", "#FFD700", "white"] 
    
    for i, linha in enumerate(linhas):
        w = draw.textbbox((0, 0), linha, font=font)[2] - draw.textbbox((0, 0), linha, font=font)[0]
        x_text = 960 + ((960 - w) / 2) # Centralizado na metade direita
        cor_atual = cores[i % len(cores)]
        
        # CONTORNO PRETO GROSSO (Stroke) - SEM GRADIENTE NO FUNDO
        draw.text((x_text, y_text), linha, font=font, fill=cor_atual, stroke_width=12, stroke_fill="black")
        y_text += font_size * 1.1
        
    img.convert("RGB").save(caminho_saida)
    return caminho_saida

# ==============================================================================
# 5. INICIANDO A FÁBRICA (TRATOR DE UPLOAD MATRIX)
# ==============================================================================
print("\n📡 Buscando roteiros prontos na planilha...")
dados = aba_principal.get_all_records()
col_status = aba_principal.row_values(1).index('Status') + 1

for index, linha in enumerate(dados, start=2):
    status = str(linha.get('Status', '')).strip()
    idioma = str(linha.get('Idioma', '')).strip().upper()
    horario_str = str(linha.get('Horario', '')).strip()
    
    # O SERVIDOR MATRIX SÓ PROCESSA O SEU HORÁRIO ESPECÍFICO
    if status == 'Pronto p/ Áudio' and idioma == 'ES' and horario_str == HORARIO_ALVO:
        data_str = str(linha.get('Data', ''))
        titulo = str(linha.get('Titulo', ''))
        descricao_ia = str(linha.get('Descricao', ''))
        tags_str = str(linha.get('Tags', ''))
        persona = str(linha.get('Personagem', '')).upper()
        roteiro = str(linha.get('Roteiro', ''))
        
        texto_thumb = str(linha.get('Texto_Thumb', linha.get('Texto Thumb', ''))).strip()
        if not texto_thumb:
            palavras_titulo = titulo.split()
            texto_thumb = " ".join(palavras_titulo[:3]) if len(palavras_titulo) >= 3 else titulo
            
        print(f"\n==================================================")
        print(f"🎬 INICIANDO PRODUÇÃO TOTAL | Linha {index} - {persona} às {horario_str} ({data_str})")
        
        if not roteiro.strip():
            print("   ❌ ERRO: O roteiro está vazio. Pulando...")
            continue
            
        roteiro_limpo = roteiro.replace('*', '').replace('_', '').replace('"', '')
        
        # --- A. ESCOLHER ATIVOS E VOZ ---
        print("   📥 Baixando ativos do Google Drive...")
        if persona == 'JESUS':
            id_pasta_img = ID_PASTA_JESUS
            id_pasta_thumb = ID_PASTA_THUMB_JESUS_DIA if "06:00" in horario_str else ID_PASTA_THUMB_JESUS_NOITE
            voz_escolhida = "es-MX-JorgeNeural"
        else:
            id_pasta_img = ID_PASTA_MARIA
            id_pasta_thumb = ID_PASTA_THUMB_MARIA_DIA
            voz_escolhida = "es-MX-DaliaNeural"
            
        arquivos_img = listar_arquivos(id_pasta_img, ('.jpg', '.jpeg', '.png'))
        if not arquivos_img:
            print(f"   ❌ ERRO: Nenhuma imagem válida na pasta {id_pasta_img}")
            continue
        
        random.shuffle(arquivos_img)
        imgs_locais =[]
        for i in range(min(25, len(arquivos_img))):
            imgs_locais.append(baixar_arquivo(arquivos_img[i]['id'], f"{PASTA_TEMP}/img_{i}.jpg"))
        
        arquivos_thumb = listar_arquivos(id_pasta_thumb, ('.jpg', '.jpeg', '.png'))
        if not arquivos_thumb:
            print(f"   ❌ ERRO: Nenhuma imagem base de thumb na pasta {id_pasta_thumb}")
            continue
        thumb_base_local = baixar_arquivo(random.choice(arquivos_thumb)['id'], f"{PASTA_TEMP}/thumb_base.jpg")

        id_pasta_musica = ID_PASTA_AVE_MARIA if "18:00" in horario_str else ID_PASTA_MUSICAS
        arquivos_musica = listar_arquivos(id_pasta_musica, ('.mp3', '.wav'))
        if not arquivos_musica:
            print(f"   ❌ ERRO: Nenhuma música na pasta {id_pasta_musica}")
            continue
        musica_local = baixar_arquivo(random.choice(arquivos_musica)['id'], f"{PASTA_TEMP}/musica.mp3")
        
        arquivos_sfx = listar_arquivos(ID_PASTA_SFX, ('.mp3', '.wav'))
        sfx_file = next((f for f in arquivos_sfx if ("passaro" in f['name'].lower() if "06:00" in horario_str or "12:00" in horario_str else "vento" in f['name'].lower())), None)
        sfx_local = baixar_arquivo(sfx_file['id'], f"{PASTA_TEMP}/sfx.mp3") if sfx_file else None

        brolls_validos =[f for f in listar_arquivos(ID_PASTA_BROLLS, ('.mp4', '.mov')) if filtro_broll(f['name'], horario_str)]
        random.shuffle(brolls_validos)
        brolls_locais =[]
        for i in range(min(6, len(brolls_validos))):
            brolls_locais.append(baixar_arquivo(brolls_validos[i]['id'], f"{PASTA_TEMP}/broll_{i}.mp4"))

        # --- B. GERAR ÁUDIO E LEGENDAS ---
        caminho_mp3 = f"{PASTA_TEMP}/audio.mp3"
        caminho_vtt = f"{PASTA_TEMP}/legenda.vtt"
        caminho_txt = f"{PASTA_TEMP}/roteiro.txt"
        
        with open(caminho_txt, "w", encoding="utf-8") as f: f.write(roteiro_limpo)
            
        velocidade_voz = random.randint(15, 20)
        param_rate = f"--rate=-{velocidade_voz}%"
        print(f"   🎙️ Gerando Voz Neural ({voz_escolhida} a {param_rate} vel) y Legendas...")
        
        subprocess.run(["edge-tts", "--voice", voz_escolhida, param_rate, "--file", caminho_txt, "--write-media", caminho_mp3, "--write-subtitles", caminho_vtt], capture_output=True)
        formatar_vtt(caminho_vtt)
        duracao_audio = obter_duracao(caminho_mp3)
        
        tem_extensao = horario_str in["18:00", "21:00"]
        duracao_total_video = duracao_audio + 300 if tem_extensao else duracao_audio
        
        print(f"   ⏱️ Duração da Oração: {duracao_audio:.2f}s | Duração Total do Vídeo: {duracao_total_video:.2f}s")

        # --- C. RENDERIZAR VÍDEO ---
        print("   🎞️ Fabricando os blocos visuais (Zoom 4K e B-Rolls)...")
        tempo_acumulado = 0
        lista_ts =[]
        contador_chunk = 0
        
        baralho_imgs_uso = imgs_locais.copy()
        baralho_brolls_uso = brolls_locais.copy()
        random.shuffle(baralho_imgs_uso)
        random.shuffle(baralho_brolls_uso)
        
        while tempo_acumulado < duracao_total_video:
            arquivo_ts = f"{PASTA_TEMP}/chunk_{contador_chunk}.ts"
            duracao_padrao = random.randint(8, 12)
            
            if tempo_acumulado >= duracao_audio:
                if not baralho_brolls_uso:
                    baralho_brolls_uso = brolls_locais.copy()
                    random.shuffle(baralho_brolls_uso)
                ativo = baralho_brolls_uso.pop() if brolls_locais else imgs_locais[0]
                duracao_real = min(duracao_padrao, obter_duracao(ativo)) if ativo.endswith('.mp4') else duracao_padrao
                subprocess.run(f'ffmpeg -y -i "{ativo}" -t {duracao_real} -vf "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2,colorchannelmixer=rr=0.6:gg=0.6:bb=0.6" -c:v libx264 -preset ultrafast -pix_fmt yuv420p -r 24 -an "{arquivo_ts}"', shell=True, capture_output=True)
                tempo_acumulado += duracao_real
            else:
                if contador_chunk > 0 and brolls_locais and random.random() < 0.30:
                    if not baralho_brolls_uso:
                        baralho_brolls_uso = brolls_locais.copy()
                        random.shuffle(baralho_brolls_uso)
                    ativo = baralho_brolls_uso.pop()
                    duracao_real = min(duracao_padrao, obter_duracao(ativo))
                    subprocess.run(f'ffmpeg -y -i "{ativo}" -t {duracao_real} -vf "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2" -c:v libx264 -preset ultrafast -pix_fmt yuv420p -r 24 -an "{arquivo_ts}"', shell=True, capture_output=True)
                    tempo_acumulado += duracao_real
                else:
                    if not baralho_imgs_uso:
                        baralho_imgs_uso = imgs_locais.copy()
                        random.shuffle(baralho_imgs_uso)
                    ativo = baralho_imgs_uso.pop()
                    efeito_zoom = random.choice(['in', 'out'])
                    zoom_cmd = "zoompan=z='1.0+0.0004*on':d=400:x='iw/2-(iw/zoom)/2':y='ih/2-(ih/zoom)/2':s=1920x1080:fps=24" if efeito_zoom == 'in' else "zoompan=z='1.15-0.0004*on':d=400:x='iw/2-(iw/zoom)/2':y='ih/2-(ih/zoom)/2':s=1920x1080:fps=24"
                    subprocess.run(f'ffmpeg -y -loop 1 -framerate 24 -i "{ativo}" -t {duracao_padrao} -vf "scale=3840:2160:force_original_aspect_ratio=increase,crop=3840:2160,{zoom_cmd}" -c:v libx264 -preset ultrafast -pix_fmt yuv420p -an "{arquivo_ts}"', shell=True, capture_output=True)
                    tempo_acumulado += duracao_padrao
            lista_ts.append(arquivo_ts)
            contador_chunk += 1

        print("   🔥 Mixando Áudio y finalizando o vídeo...")
        arquivo_concat = f"{PASTA_TEMP}/concat.txt"
        with open(arquivo_concat, "w") as f:
            for ts in lista_ts: f.write(f"file '{ts}'\n")
        video_mudo = f"{PASTA_TEMP}/mudo.mp4"
        subprocess.run(f'ffmpeg -y -f concat -safe 0 -i "{arquivo_concat}" -c copy "{video_mudo}"', shell=True, capture_output=True)

        video_final = f"{PASTA_TEMP}/final.mp4"
        if sfx_local:
            subprocess.run(f'ffmpeg -y -i "{video_mudo}" -i "{caminho_mp3}" -stream_loop -1 -i "{musica_local}" -stream_loop -1 -i "{sfx_local}" -filter_complex "[1:a]apad[v_pad];[2:a]volume=\'if(lt(t,{duracao_audio}),0.10,0.25)\':eval=frame[bgm];[3:a]volume=\'if(lt(t,{duracao_audio}),0.15,0.25)\':eval=frame[sfx];[v_pad][bgm][sfx]amix=inputs=3:duration=longest[aout]" -map 0:v -map "[aout]" -c:v copy -c:a aac -b:a 192k -t {duracao_total_video} "{video_final}"', shell=True, capture_output=True)
        else:
            subprocess.run(f'ffmpeg -y -i "{video_mudo}" -i "{caminho_mp3}" -stream_loop -1 -i "{musica_local}" -filter_complex "[1:a]apad[v_pad];[2:a]volume=\'if(lt(t,{duracao_audio}),0.10,0.25)\':eval=frame[bgm];[v_pad][bgm]amix=inputs=2:duration=longest[aout]" -map 0:v -map "[aout]" -c:v copy -c:a aac -b:a 192k -t {duracao_total_video} "{video_final}"', shell=True, capture_output=True)

        # --- D. UPLOAD YOUTUBE ---
        print("   🖼️ Gerando Thumbnail...")
        thumb_path = criar_thumbnail(thumb_base_local, texto_thumb, horario_str, persona, f"{PASTA_TEMP}/thumb.jpg")

        texto_fixo_canal = ""
        for config in configs:
            if str(config.get('Idioma', '')).upper() == 'ES':
                texto_fixo_canal = str(config.get('Texto Fixo', config.get('Texto_Fixo', config.get('Links', ''))))
                break
                
        tags_limpas = re.sub(r'[^a-zA-Z0-9áéíóúÁÉÍÓÚñÑ ,]', '', tags_str)
        tags_lista = [t.strip()[:30] for t in tags_limpas.split(',') if t.strip()][:15]
        
        capitulos = f"\n\n⏱️ Capítulos de la Oración:\n{format_time(0)} Inicio de la Oración\n{format_time(duracao_audio * 0.33)} Súplica y Fe\n{format_time(duracao_audio * 0.66)} Entrega y Gratitud"
        if tem_extensao: capitulos += f"\n{format_time(duracao_audio)} Meditación y Paz Profunda"
            
        descricao_final = f"{descricao_ia}{capitulos}\n\n{texto_fixo_canal}"
        
        try:
            tz_mexico = pytz.timezone('America/Mexico_City')
            dt_obj = datetime.datetime.strptime(f"{data_str} {horario_str}", "%Y-%m-%d %H:%M")
            publish_at = tz_mexico.localize(dt_obj).isoformat() 
        except:
            publish_at = None
        
        body = {"snippet": {"title": titulo[:100], "description": descricao_final, "tags": tags_lista, "categoryId": "22", "defaultLanguage": "es-419", "defaultAudioLanguage": "es-419"}, "status": {"privacyStatus": "private", "selfDeclaredMadeForKids": False}}
        if publish_at: body["status"]["publishAt"] = publish_at
        
        print(f"   ⏳ Subindo vídeo (Agendado para {data_str} às {horario_str} - México)...")
        
        for _ in range(3):
            try:
                video_id = youtube.videos().insert(part="snippet,status", body=body, media_body=MediaFileUpload(video_final, chunksize=-1, resumable=True, mimetype="video/mp4")).execute().get("id")
                print(f"   ✅ Vídeo enviado! ID: {video_id}")
                
                if os.path.exists(thumb_path): youtube.thumbnails().set(videoId=video_id, media_body=MediaFileUpload(thumb_path)).execute()
                if os.path.exists(caminho_vtt): youtube.captions().insert(part="snippet", body={"snippet": {"videoId": video_id, "language": "es-419", "name": "Español", "isDraft": False}}, media_body=MediaFileUpload(caminho_vtt)).execute()
                
                pid = "PLpWSsa4Rjy3YGN93lFtIHAb8zs6tZb9VA" if persona == 'JESUS' and "06:00" in horario_str else "PLpWSsa4Rjy3afok57i5cNbl7MBCMrT9iD" if persona == 'JESUS' and "21:00" in horario_str else "PLpWSsa4Rjy3ZGBJ-gTbG_v3t_AQXrCK4w" if persona == 'MARIA' else None
                if pid: youtube.playlistItems().insert(part="snippet", body={"snippet": {"playlistId": pid, "resourceId": {"kind": "youtube#video", "videoId": video_id}}}).execute()
                
                aba_principal.update_cell(index, col_status, 'Publicado')
                print(f"   🎉 SUCESSO TOTAL! Linha {index} finalizada.")
                break
            except Exception as e: time.sleep(15)
        break # O Matrix faz 1 e desliga

print("\n🚀 SERVIDOR MATRIX DESLIGANDO.")
