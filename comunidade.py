import os, json, time, datetime, gspread
from google.oauth2.service_account import Credentials
from google.oauth2.credentials import Credentials as YTCredentials
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from google.genai import Client

GOOGLE_JSON = os.environ.get("GOOGLE_CREDENTIALS")
YT_TOKEN_JSON = os.environ.get("YOUTUBE_TOKEN_ES")
CHAVE_API_GEMINI = os.environ.get("GEMINI_API_KEY")

creds_sheets = Credentials.from_service_account_info(json.loads(GOOGLE_JSON), scopes=['https://www.googleapis.com/auth/spreadsheets'])
gc = gspread.authorize(creds_sheets)

try: configs = gc.open_by_key("1KgIjWrLUVlllhlZB1R9fkHGxxZlLsax1aOVGZrYwgnU").worksheet("Configuracoes").get_all_records()
except: configs =[]

creds_yt = YTCredentials.from_authorized_user_info(json.loads(YT_TOKEN_JSON))
if creds_yt and creds_yt.expired and creds_yt.refresh_token: creds_yt.refresh(Request())
youtube = build('youtube', 'v3', credentials=creds_yt)
gemini_client = Client(api_key=CHAVE_API_GEMINI, http_options={'api_version': 'v1'})

canal_response = youtube.channels().list(part='id,contentDetails', mine=True).execute()
MEU_CANAL_ID = canal_response['items'][0]['id']
UPLOADS_PLAYLIST_ID = canal_response['items'][0]['contentDetails']['relatedPlaylists']['uploads']

print("💰 INICIANDO O VENDEDOR")
texto_fixo = next((str(c.get('Texto Fixo', c.get('Texto_Fixo', ''))) for c in configs if str(c.get('Idioma', '')).upper() == 'ES'), "")

if texto_fixo:
    limite_24h = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=24)
    playlist_req = youtube.playlistItems().list(part='snippet', playlistId=UPLOADS_PLAYLIST_ID, maxResults=15).execute()
    video_ids = [item['snippet']['resourceId']['videoId'] for item in playlist_req.get('items',[])]
    
    if video_ids:
        videos_req = youtube.videos().list(part='snippet', id=','.join(video_ids)).execute()
        for video in videos_req.get('items',[]):
            v_id, v_titulo = video['id'], video['snippet']['title']
            pub_time = datetime.datetime.strptime(video['snippet']['publishedAt'], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=datetime.timezone.utc)
            
            if pub_time >= limite_24h:
                try:
                    comentarios = youtube.commentThreads().list(part='snippet', videoId=v_id, maxResults=100).execute()
                    if not any(t['snippet']['topLevelComment']['snippet'].get('authorChannelId', {}).get('value') == MEU_CANAL_ID for t in comentarios.get('items',[])):
                        
                        if "#shorts" in v_titulo.lower():
                            comentario_final = "🙏 ¡Que esta oración rápida bendiga tu día! Visita nuestro canal para las oraciones completas y listas de reproducción."
                        else:
                            link_playlist = "https://www.youtube.com/playlist?list=PLpWSsa4Rjy3ZGBJ-gTbG_v3t_AQXrCK4w" 
                            if "mañana" in v_titulo.lower(): link_playlist = "https://www.youtube.com/playlist?list=PLpWSsa4Rjy3YGN93lFtIHAb8zs6tZb9VA"
                            elif "noche" in v_titulo.lower(): link_playlist = "https://www.youtube.com/playlist?list=PLpWSsa4Rjy3afok57i5cNbl7MBCMrT9iD"
                            comentario_final = f"{texto_fixo}\n\nSigue orando con nosotros aquí: {link_playlist}"
                            
                        youtube.commentThreads().insert(part="snippet", body={"snippet": {"videoId": v_id, "topLevelComment": {"snippet": {"textOriginal": comentario_final}}}}).execute()
                        print(f"   ✅ Comentário postado no vídeo: {v_titulo[:30]}")
                        time.sleep(2)
                except: pass

print("\n🕊️ INICIANDO O PASTOR DIGITAL")
try:
    threads = youtube.commentThreads().list(part="snippet,replies", allThreadsRelatedToChannelId=MEU_CANAL_ID, maxResults=15).execute()
    for thread in threads.get('items',[]):
        top = thread['snippet']['topLevelComment']['snippet']
        autor_id = top.get('authorChannelId', {}).get('value')
        if autor_id == MEU_CANAL_ID: continue
        
        ja_respondi = any(r['snippet'].get('authorChannelId', {}).get('value') == MEU_CANAL_ID for r in thread.get('replies', {}).get('comments',[]))
        if not ja_respondi:
            nome, texto = top.get('authorDisplayName', 'Hermano(a)'), top.get('textOriginal', '')
            comment_id = top.get('id')
            
            prompt = f"Actúa como guía espiritual católico. Un fiel llamado '{nome}' comentó: '{texto}'. Escribe una respuesta CORTA (máx 3 líneas). Si el comentario es negativo o critica imágenes, ACTIVA EL MODO PACIFICADOR: responde con extrema educación, diciendo que respetamos su visión, pero invítalo a unirse en el amor a Dios. Si es positivo, agradece y bendice. Tono cálido. SIN comillas."
            
            try:
                resposta = gemini_client.models.generate_content(model='gemini-3.1-flash-lite', contents=prompt).text.strip()
                youtube.comments().insert(part="snippet", body={"snippet": {"parentId": thread['id'], "textOriginal": resposta}}).execute()
                print(f"   ✅ Respondido a {nome}")
                
                try:
                    youtube.comments().rate(id=comment_id, rating='like').execute()
                    print("   ❤️ Like dado no comentário!")
                except Exception as e: print(f"   ⚠️ Não foi possível dar like: {e}")
                
                time.sleep(3)
            except: pass
except: pass
print("🚀 ESTÁGIO 6 CONCLUÍDO!")
