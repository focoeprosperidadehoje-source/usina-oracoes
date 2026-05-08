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

GOOGLE_JSON = os.environ.get("GOOGLE_CREDENTIALS")
YT_TOKEN_JSON = os.environ.get("YOUTUBE_TOKEN_ES")
HORARIO_ALVO = os.environ.get("HORARIO_ALVO")

print(f"🚀 INICIANDO SERVIDOR MATRIX PARA O HORÁRIO: {HORARIO_ALVO}")

credenciais_dict = json.loads(GOOGLE_JSON)
creds_sheets = Credentials.from_service_account_info(credenciais_dict, scopes=['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive'])
gc = gspread.authorize(creds_sheets)

aba_principal = gc.open_by_key("1KgIjWrLUVlllhlZB1R9fkHGxxZlLsax1aOVGZrYwgnU").get_worksheet(0)

try: configs = gc.open_by_key("1KgIjWrLUVlllhlZB1R9fkHGxxZlLsax1aOVGZrYwgnU").worksheet("Configuracoes").get_all_records()
except: configs =[]

creds_yt = YTCredentials.from_authorized_user_info(json.loads(YT_TOKEN_JSON))
if creds_yt and creds_yt.expired and creds_yt.refresh_token: creds_yt.refresh(Request())
youtube = build('youtube', 'v3', credentials=creds_yt)
drive_service = build_drive('drive', 'v3', credentials=creds_sheets)

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
                    if f['name'].lower().endswith(extensoes):
                        res.append(f)
                else:
                    res.append(f)
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
    
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw_overlay = ImageDraw.Draw(overlay)
    for i in range(960):
        alpha = int((i / 960) * 240) 
        draw_overlay.rectangle([(960 + i, 0), (961 + i, 1080)], fill=(0, 0, 0, alpha))
    img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
    
    draw = ImageDraw.Draw(img)
    cor_barra = "#FFD700" if "06:00" in horario else "#B87333" if "12:00" in horario else "#C0C0C0" if "18:00" in horario else "#00BFFF"
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
        x_text = 960 + ((960 - w) / 2)
        for ax in range(-8, 9, 2):
            for ay in range(-8, 9, 2): draw.text((x_text+ax, y_text+ay), linha, font=font, fill="black")
        draw.text((x_text, y_text), linha, font=font, fill=cores[i % len(cores)])
        y_text += font_size * 1.1
    img.convert("RGB").save(caminho_saida)
    return caminho_saida

dados = aba_principal.get_all_records()
col_status = aba_principal.row_values(1).index('Status') + 1

for index, linha in enumerate(dados, start=2):
    if str(linha.get('Status', '')).strip() == 'Pronto p/ Áudio' and str(linha.get('Idioma', '')).strip().upper() == 'ES' and str(linha.get('Horario', '')).strip() == HORARIO_ALVO:
        data_str, horario_str, titulo, descricao_ia, tags_str, persona, roteiro = str(linha.get('Data', '')), str(linha.get('Horario', '')), str(linha.get('Titulo', '')), str(linha.get('Descricao', '')), str(linha.get('Tags', '')), str(linha.get('Personagem', '')).upper(), str(linha.get('Roteiro', ''))
        texto_thumb = str(linha.get('Texto_Thumb', linha.get('Texto Thumb', ''))).strip() or " ".join(titulo.split()[:3])
        
        print(f"🎬 INICIANDO: Linha {index} - {persona} às {horario_str}")
        
        id_pasta_img = ID_PASTA_JESUS if persona == 'JESUS' else ID_PASTA_MARIA
        id_pasta_thumb = ID_PASTA_THUMB_JESUS_DIA if persona == 'JESUS' and "06:00" in horario_str else ID_PASTA_THUMB_JESUS_NOITE if persona == 'JESUS' else ID_PASTA_THUMB_MARIA_DIA
        voz_escolhida = "es-MX-JorgeNeural" if persona == 'JESUS' else "es-MX-DaliaNeural"
        
        arquivos_img = listar_arquivos(id_pasta_img, ('.jpg', '.jpeg', '.png'))
        if not arquivos_img:
            print(f"   ❌ ERRO: Nenhuma imagem válida na pasta {id_pasta_img}")
            continue
        img_local = baixar_arquivo(random.choice(arquivos_img)['id'], f"{PASTA_TEMP}/img.jpg")
        
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
        brolls_locais =[baixar_arquivo(random.choice(brolls_validos)['id'], f"{PASTA_TEMP}/broll_{i}.mp4") for i in range(min(3, len(brolls_validos)))]

        caminho_mp3, caminho_vtt, caminho_txt = f"{PASTA_TEMP}/audio.mp3", f"{PASTA_TEMP}/legenda.vtt", f"{PASTA_TEMP}/roteiro.txt"
        with open(caminho_txt, "w", encoding="utf-8") as f: f.write(roteiro.replace('*', '').replace('_', '').replace('"', ''))
            
        subprocess.run(["edge-tts", "--voice", voz_escolhida, f"--rate=-{random.randint(15, 20)}%", "--file", caminho_txt, "--write-media", caminho_mp3, "--write-subtitles", caminho_vtt], capture_output=True)
        formatar_vtt(caminho_vtt)
        duracao_audio = obter_duracao(caminho_mp3)
        duracao_total = duracao_audio + 300 if horario_str in["18:00", "21:00"] else duracao_audio

        tempo_acumulado, lista_ts, contador = 0,[], 0
        while tempo_acumulado < duracao_total:
            arquivo_ts = f"{PASTA_TEMP}/chunk_{contador}.ts"
            duracao_padrao = random.randint(8, 15)
            
            if tempo_acumulado >= duracao_audio:
                ativo = random.choice(brolls_locais) if brolls_locais else img_local
                duracao_real = min(duracao_padrao, obter_duracao(ativo)) if ativo.endswith('.mp4') else duracao_padrao
                subprocess.run(f'ffmpeg -y -i "{ativo}" -t {duracao_real} -vf "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2,colorchannelmixer=rr=0.6:gg=0.6:bb=0.6" -c:v libx264 -preset ultrafast -pix_fmt yuv420p -r 24 -an "{arquivo_ts}"', shell=True, capture_output=True)
                tempo_acumulado += duracao_real
            else:
                if contador > 0 and brolls_locais and random.random() < 0.30:
                    ativo = random.choice(brolls_locais)
                    duracao_real = min(duracao_padrao, obter_duracao(ativo))
                    subprocess.run(f'ffmpeg -y -i "{ativo}" -t {duracao_real} -vf "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2" -c:v libx264 -preset ultrafast -pix_fmt yuv420p -r 24 -an "{arquivo_ts}"', shell=True, capture_output=True)
                    tempo_acumulado += duracao_real
                else:
                    ativo = img_local
                    zoom_cmd = "zoompan=z='1.0+0.0004*on':d=400:x='iw/2-(iw/zoom)/2':y='ih/2-(ih/zoom)/2':s=1920x1080:fps=24" if random.choice(['in', 'out']) == 'in' else "zoompan=z='1.15-0.0004*on':d=400:x='iw/2-(iw/zoom)/2':y='ih/2-(ih/zoom)/2':s=1920x1080:fps=24"
                    subprocess.run(f'ffmpeg -y -loop 1 -framerate 24 -i "{ativo}" -t {duracao_padrao} -vf "scale=3840:2160:force_original_aspect_ratio=increase,crop=3840:2160,{zoom_cmd}" -c:v libx264 -preset ultrafast -pix_fmt yuv420p -an "{arquivo_ts}"', shell=True, capture_output=True)
                    tempo_acumulado += duracao_padrao
            lista_ts.append(arquivo_ts)
            contador += 1

        arquivo_concat = f"{PASTA_TEMP}/concat.txt"
        with open(arquivo_concat, "w") as f:
            for ts in lista_ts: f.write(f"file '{ts}'\n")
        video_mudo = f"{PASTA_TEMP}/mudo.mp4"
        subprocess.run(f'ffmpeg -y -f concat -safe 0 -i "{arquivo_concat}" -c copy "{video_mudo}"', shell=True, capture_output=True)

        video_final = f"{PASTA_TEMP}/final.mp4"
        if sfx_local:
            subprocess.run(f'ffmpeg -y -i "{video_mudo}" -i "{caminho_mp3}" -stream_loop -1 -i "{musica_local}" -stream_loop -1 -i "{sfx_local}" -filter_complex "[1:a]apad[v_pad];[2:a]volume=\'if(lt(t,{duracao_audio}),0.10,0.25)\':eval=frame[bgm];[3:a]volume=\'if(lt(t,{duracao_audio}),0.15,0.25)\':eval=frame[sfx];[v_pad][bgm][sfx]amix=inputs=3:duration=longest[aout]" -map 0:v -map "[aout]" -c:v copy -c:a aac -b:a 192k -t {duracao_total} "{video_final}"', shell=True, capture_output=True)
        else:
            subprocess.run(f'ffmpeg -y -i "{video_mudo}" -i "{caminho_mp3}" -stream_loop -1 -i "{musica_local}" -filter_complex "[1:a]apad[v_pad];[2:a]volume=\'if(lt(t,{duracao_audio}),0.10,0.25)\':eval=frame[bgm];[v_pad][bgm]amix=inputs=2:duration=longest[aout]" -map 0:v -map "[aout]" -c:v copy -c:a aac -b:a 192k -t {duracao_total} "{video_final}"', shell=True, capture_output=True)

        thumb_path = criar_thumbnail(thumb_base_local, texto_thumb, horario_str, persona, f"{PASTA_TEMP}/thumb.jpg")
        
        texto_fixo = next((str(c.get('Texto Fixo', c.get('Texto_Fixo', ''))) for c in configs if str(c.get('Idioma', '')).upper() == 'ES'), "")
        tags_limpas = re.sub(r'[^a-zA-Z0-9áéíóúÁÉÍÓÚñÑ ,]', '', tags_str)
        tags_lista = [t.strip()[:30] for t in tags_limpas.split(',') if t.strip()][:15]
        
        # CORREÇÃO APLICADA AQUI: Lógica direta sem a variável tem_extensao
        capitulos = f"\n\n⏱️ Capítulos de la Oración:\n{format_time(0)} Inicio de la Oración\n{format_time(duracao_audio * 0.33)} Súplica y Fe\n{format_time(duracao_audio * 0.66)} Entrega y Gratitud"
        if horario_str in["18:00", "21:00"]: 
            capitulos += f"\n{format_time(duracao_audio)} Meditación y Paz Profunda"
            
        descricao_final = f"{descricao_ia}{capitulos}\n\n{texto_fixo}"
        
        try:
            tz_mexico = pytz.timezone('America/Mexico_City')
            dt_obj = datetime.datetime.strptime(f"{data_str} {horario_str}", "%Y-%m-%d %H:%M")
            publish_at = tz_mexico.localize(dt_obj).isoformat() 
        except:
            publish_at = None
        
        body = {"snippet": {"title": titulo[:100], "description": descricao_final, "tags": tags_lista, "categoryId": "22", "defaultLanguage": "es-419", "defaultAudioLanguage": "es-419"}, "status": {"privacyStatus": "private", "selfDeclaredMadeForKids": False}}
        if publish_at: body["status"]["publishAt"] = publish_at
        
        for _ in range(3):
            try:
                video_id = youtube.videos().insert(part="snippet,status", body=body, media_body=MediaFileUpload(video_final, chunksize=-1, resumable=True, mimetype="video/mp4")).execute().get("id")
                if os.path.exists(thumb_path): youtube.thumbnails().set(videoId=video_id, media_body=MediaFileUpload(thumb_path)).execute()
                if os.path.exists(caminho_vtt): youtube.captions().insert(part="snippet", body={"snippet": {"videoId": video_id, "language": "es-419", "name": "Español", "isDraft": False}}, media_body=MediaFileUpload(caminho_vtt)).execute()
                
                pid = "PLpWSsa4Rjy3YGN93lFtIHAb8zs6tZb9VA" if persona == 'JESUS' and "06:00" in horario_str else "PLpWSsa4Rjy3afok57i5cNbl7MBCMrT9iD" if persona == 'JESUS' and "21:00" in horario_str else "PLpWSsa4Rjy3ZGBJ-gTbG_v3t_AQXrCK4w" if persona == 'MARIA' else None
                if pid: youtube.playlistItems().insert(part="snippet", body={"snippet": {"playlistId": pid, "resourceId": {"kind": "youtube#video", "videoId": video_id}}}).execute()
                
                aba_principal.update_cell(index, col_status, 'Publicado')
                print(f"   🎉 SUCESSO! Vídeo {video_id} publicado.")
                break
            except Exception as e: time.sleep(15)
        break 

print("\n🚀 SERVIDOR MATRIX DESLIGANDO.")
