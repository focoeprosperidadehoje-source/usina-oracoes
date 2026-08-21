import os, json, time, datetime, gspread
from google.oauth2.service_account import Credentials
from google.oauth2.credentials import Credentials as YTCredentials
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from google.genai import Client

GOOGLE_JSON = os.environ.get("GOOGLE_CREDENTIALS")
YT_TOKEN_JSON = os.environ.get("YOUTUBE_TOKEN_ES")
CHAVE_API_GEMINI   = os.environ.get("GEMINI_API_KEY", "")
CHAVE_API_GEMINI_2 = os.environ.get("GEMINI_API_KEY_2", "")
CHAVES_GEMINI = [k for k in [CHAVE_API_GEMINI, CHAVE_API_GEMINI_2] if k]

creds_sheets = Credentials.from_service_account_info(json.loads(GOOGLE_JSON), scopes=['https://www.googleapis.com/auth/spreadsheets'])
gc = gspread.authorize(creds_sheets)

try: configs = gc.open_by_key("1KgIjWrLUVlllhlZB1R9fkHGxxZlLsax1aOVGZrYwgnU").worksheet("Configuracoes").get_all_records()
except: configs =[]

creds_yt = YTCredentials.from_authorized_user_info(json.loads(YT_TOKEN_JSON))
if creds_yt and creds_yt.expired and creds_yt.refresh_token: creds_yt.refresh(Request())
youtube = build('youtube', 'v3', credentials=creds_yt)
gemini_client = Client(api_key=CHAVES_GEMINI[0], http_options={'api_version': 'v1'})

def _gerar_comunidade(prompt):
    """Tenta cada chave Gemini disponível. Em 429, troca de chave antes de desistir."""
    for chave in CHAVES_GEMINI:
        try:
            c = Client(api_key=chave, http_options={'api_version': 'v1'})
            return c.models.generate_content(model=modelo_comunidade, contents=prompt).text.strip()
        except Exception as e:
            if "429" in str(e) and chave != CHAVES_GEMINI[-1]:
                print(f"[WARN] 429 na chave ...{chave[-6:]}. Tentando chave 2...")
                continue
            raise
    raise RuntimeError("Todas as chaves Gemini falharam.")

def obter_modelo_lite():
    try:
        modelos = gemini_client.models.list()
        lite_models = [m.name for m in modelos if 'generateContent' in m.supported_generation_methods and 'flash-lite' in m.name]
        return sorted(lite_models, reverse=True)[0] if lite_models else 'gemini-2.5-flash'
    except:
        return 'gemini-2.5-flash'

modelo_comunidade = obter_modelo_lite()
print(f"🤖 Modelo de IA selecionado para a Comunidade: {modelo_comunidade}")

canal_response = youtube.channels().list(part='id,contentDetails', mine=True).execute()
MEU_CANAL_ID = canal_response['items'][0]['id']
UPLOADS_PLAYLIST_ID = canal_response['items'][0]['contentDetails']['relatedPlaylists']['uploads']

print("💰 INICIANDO O VENDEDOR")
texto_fixo = next((str(c.get('Texto Fixo', c.get('Texto_Fixo', ''))) for c in configs if str(c.get('Idioma', '')).upper() == 'ES'), "")

LINK_LIVE = f"https://www.youtube.com/channel/{MEU_CANAL_ID}/live"

if texto_fixo:
    limite_24h = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=24)
    # Paginar uploads para cobrir até 50 vídeos recentes
    video_ids = []
    page_token_up = None
    for _ in range(4):
        resp_up = youtube.playlistItems().list(
            part='snippet', playlistId=UPLOADS_PLAYLIST_ID,
            maxResults=50, pageToken=page_token_up
        ).execute()
        video_ids += [item['snippet']['resourceId']['videoId'] for item in resp_up.get('items', [])]
        page_token_up = resp_up.get('nextPageToken')
        if not page_token_up:
            break

    if video_ids:
        videos_req = youtube.videos().list(part='snippet', id=','.join(video_ids[:50])).execute()
        for video in videos_req.get('items',[]):
            v_id, v_titulo = video['id'], video['snippet']['title']
            pub_time = datetime.datetime.strptime(video['snippet']['publishedAt'], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=datetime.timezone.utc)

            if pub_time >= limite_24h:
                try:
                    comentarios = youtube.commentThreads().list(part='snippet', videoId=v_id, maxResults=100).execute()
                    if not any(t['snippet']['topLevelComment']['snippet'].get('authorChannelId', {}).get('value') == MEU_CANAL_ID for t in comentarios.get('items',[])):
                        if "#shorts" in v_titulo.lower():
                            comentario_final = (
                                "🙏 ¡Que esta oración bendiga tu día!\n\n"
                                f"🔴 ESTAMOS EN VIVO AHORA — 24 horas sin parar: tus pedidos y los nombres de "
                                f"tus seres queridos son mencionados en oración de forma continua.\n"
                                f"Únete ahora: {LINK_LIVE} 🔔"
                            )
                        else:
                            link_playlist = "https://www.youtube.com/playlist?list=PLpWSsa4Rjy3ZGBJ-gTbG_v3t_AQXrCK4w"
                            if "mañana" in v_titulo.lower(): link_playlist = "https://www.youtube.com/playlist?list=PLpWSsa4Rjy3YGN93lFtIHAb8zs6tZb9VA"
                            elif "noche" in v_titulo.lower(): link_playlist = "https://www.youtube.com/playlist?list=PLpWSsa4Rjy3afok57i5cNbl7MBCMrT9iD"
                            comentario_final = (
                                f"{texto_fixo}\n\nSigue orando con nosotros aquí: {link_playlist}\n\n"
                                f"🔴 EN VIVO AHORA — 24/7: tus súplicas y los nombres de tus seres queridos "
                                f"son elevados en oración ininterrumpida. Únete: {LINK_LIVE}"
                            )
                        youtube.commentThreads().insert(part="snippet", body={"snippet": {"videoId": v_id, "topLevelComment": {"snippet": {"textOriginal": comentario_final}}}}).execute()
                        print(f"   ✅ Comentário postado no vídeo: {v_titulo[:30]}")
                        time.sleep(2)
                except Exception as e:
                    print(f"   ⚠️ Erro ao comentar em {v_id}: {e}")

print("\n🕊️ INICIANDO O PASTOR DIGITAL")
try:
    respondidos = 0
    page_token_t = None
    # Paginar até 300 threads por execução (3 páginas × 100)
    for _pagina in range(3):
        threads_resp = youtube.commentThreads().list(
            part="snippet,replies",
            allThreadsRelatedToChannelId=MEU_CANAL_ID,
            maxResults=100,
            pageToken=page_token_t
        ).execute()
        for thread in threads_resp.get('items', []):
            top = thread['snippet']['topLevelComment']['snippet']
            autor_id = top.get('authorChannelId', {}).get('value')
            if autor_id == MEU_CANAL_ID:
                continue
            ja_respondi = any(
                r['snippet'].get('authorChannelId', {}).get('value') == MEU_CANAL_ID
                for r in thread.get('replies', {}).get('comments', [])
            )
            if not ja_respondi:
                nome  = top.get('authorDisplayName', 'Hermano(a)')
                texto = top.get('textOriginal', '')
                comment_id = top.get('id')
                prompt = (
                    f"Actúa como guía espiritual católico. Un fiel llamado '{nome}' comentó: '{texto}'. "
                    f"Escribe una respuesta CORTA (máx 3 líneas). "
                    f"Si el comentario es negativo o critica imágenes, ACTIVA EL MODO PACIFICADOR: "
                    f"responde con extrema educación, respetando su visión, pero invítalo al amor de Dios. "
                    f"Si es positivo, agradece y bendice. "
                    f"Si el fiel menciona personas enfermas, situaciones de dolor o pide intercesión, "
                    f"añade orgánicamente UNA frase invitándolo a nuestra transmisión 24/7 donde sus pedidos "
                    f"son mencionados en oración de forma continua: {LINK_LIVE} "
                    f"Tono cálido y esperanzador. SIN comillas."
                )
                try:
                    resposta = _gerar_comunidade(prompt)
                    youtube.comments().insert(
                        part="snippet",
                        body={"snippet": {"parentId": thread['id'], "textOriginal": resposta}}
                    ).execute()
                    print(f"   ✅ Respondido a {nome}")
                    try:
                        youtube.comments().rate(id=comment_id, rating='like').execute()
                        print("   ❤️ Like dado!")
                    except Exception as e:
                        print(f"   ⚠️ Like falhou: {e}")
                    respondidos += 1
                    time.sleep(3)
                except Exception as e:
                    print(f"   ⚠️ Erro ao responder {nome}: {e}")
        page_token_t = threads_resp.get('nextPageToken')
        if not page_token_t:
            break
    print(f"   Total respondido nesta execução: {respondidos}")
except Exception as e:
    print(f"⚠️ PASTOR DIGITAL erro geral: {e}")
print("🚀 ESTÁGIO 6 CONCLUÍDO!")
