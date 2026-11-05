"""
Bloco 4 — Vídeos Relacionados
Para todos os vídeos públicos recentes sem seção de relacionados:
  1. Adiciona "📌 Más/Mais videos..." ao final da descrição (videos.update)
  2. Posta comentário com os links (commentThreads.insert)
Env: GOOGLE_CREDENTIALS, YOUTUBE_TOKEN_ES_JSON (ou _PT_JSON), CANAL
"""

import os, sys, json, time, datetime, re
from zoneinfo import ZoneInfo

from google.oauth2.credentials import Credentials as YTCredentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

# ==============================================================================
# 1. CONFIG
# ==============================================================================
CANAL      = os.environ.get("CANAL", "ES")
MAX_VIDEOS = 10  # máximo processado por run (cota: ~100 unid/vídeo)
DIAS_RETROATIVOS = 30

CONFIGS = {
    'ES': {
        'channel_id':  'UCyPGsztvMnUhDeoI_6H4bsA',
        'token_env':   'YOUTUBE_TOKEN_ES_JSON',
        'marker':      '📌 Más videos que te ayudarán:',
        'section_hdr': '📌 Más videos que te ayudarán:\n',
        'comment_tpl': (
            '🙏 ¡Que estos videos también te acompañen en la oración!\n'
            '{links}\n\n'
            'Dios te bendiga 🕊️'
        ),
    },
    'PT': {
        'channel_id':  'UClATmmCFTo_UDHgfXPjwyqw',
        'token_env':   'YOUTUBE_TOKEN_PT_JSON',
        'marker':      '📌 Mais vídeos que vão te ajudar:',
        'section_hdr': '📌 Mais vídeos que vão te ajudar:\n',
        'comment_tpl': (
            '🙏 Que esses vídeos também te acompanhem na oração!\n'
            '{links}\n\n'
            'Deus abençoe você 🕊️'
        ),
    },
}

# Campos de snippet gravável (não incluir campos somente-leitura)
SNIPPET_WRITEABLE = {'title', 'description', 'tags', 'categoryId',
                     'defaultLanguage', 'defaultAudioLanguage'}

# ==============================================================================
# 2. AUTH
# ==============================================================================
cfg = CONFIGS.get(CANAL)
if not cfg:
    print(f"❌ Canal desconhecido: {CANAL}"); sys.exit(1)

YT_TOKEN_JSON = os.environ.get(cfg['token_env'])
if not YT_TOKEN_JSON:
    print(f"❌ Token {cfg['token_env']} não encontrado."); sys.exit(1)

creds_yt = YTCredentials.from_authorized_user_info(json.loads(YT_TOKEN_JSON.lstrip('\ufeff')))
if creds_yt.expired and creds_yt.refresh_token:
    creds_yt.refresh(Request())
youtube = build('youtube', 'v3', credentials=creds_yt)

# ==============================================================================
# 3. HELPERS
# ==============================================================================
def obter_uploads(channel_id, max_videos=50):
    uploads_pid = 'UU' + channel_id[2:]
    video_ids, page_token = [], None
    while len(video_ids) < max_videos:
        for _ in range(3):
            try:
                resp = youtube.playlistItems().list(
                    part='contentDetails', playlistId=uploads_pid,
                    maxResults=50, pageToken=page_token
                ).execute()
                break
            except Exception as e:
                print(f"[WARN] playlistItems.list: {e}"); time.sleep(10)
        else:
            break
        for item in resp.get('items', []):
            video_ids.append(item['contentDetails']['videoId'])
        page_token = resp.get('nextPageToken')
        if not page_token:
            break
    return video_ids[:max_videos]

def obter_detalhes(video_ids):
    result = {}
    for i in range(0, len(video_ids), 50):
        batch = video_ids[i:i+50]
        for _ in range(3):
            try:
                resp = youtube.videos().list(
                    part='snippet,status', id=','.join(batch)
                ).execute()
                for item in resp.get('items', []):
                    result[item['id']] = item
                break
            except Exception as e:
                print(f"[WARN] videos.list: {e}"); time.sleep(10)
    return result

def atualizar_descricao(video_id, snippet_atual, nova_desc):
    snippet_limpo = {k: v for k, v in snippet_atual.items() if k in SNIPPET_WRITEABLE}
    snippet_limpo['description'] = nova_desc
    for _ in range(3):
        try:
            youtube.videos().update(
                part='snippet',
                body={'id': video_id, 'snippet': snippet_limpo}
            ).execute()
            return True
        except Exception as e:
            print(f"  ⚠️  videos.update: {e}"); time.sleep(15)
    return False

def postar_comentario(video_id, texto):
    for _ in range(3):
        try:
            youtube.commentThreads().insert(
                part='snippet',
                body={
                    'snippet': {
                        'videoId': video_id,
                        'topLevelComment': {
                            'snippet': {'textOriginal': texto}
                        }
                    }
                }
            ).execute()
            return True
        except Exception as e:
            print(f"  ⚠️  commentThreads.insert: {e}"); time.sleep(15)
    return False

# ==============================================================================
# 4. MAIN
# ==============================================================================
def main():
    print(f"\n🔗 Bloco 4 — Vídeos Relacionados — Canal {CANAL}")

    video_ids = obter_uploads(cfg['channel_id'], max_videos=50)
    if not video_ids:
        print("  ❌ Sem vídeos"); return

    detalhes = obter_detalhes(video_ids)

    # Apenas vídeos públicos
    publicos = [
        vid for vid in video_ids
        if detalhes.get(vid, {}).get('status', {}).get('privacyStatus') == 'public'
    ]
    print(f"  → {len(publicos)} vídeos públicos")

    # Corte de data (últimos DIAS_RETROATIVOS dias)
    corte = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=DIAS_RETROATIVOS)
    recentes = []
    for vid in publicos:
        pub_at = detalhes[vid]['snippet'].get('publishedAt', '')
        try:
            dt = datetime.datetime.fromisoformat(pub_at.replace('Z', '+00:00'))
            if dt >= corte:
                recentes.append(vid)
        except:
            recentes.append(vid)
    print(f"  → {len(recentes)} recentes (últimos {DIAS_RETROATIVOS} dias)")

    processados = 0
    for video_id in recentes:
        if processados >= MAX_VIDEOS:
            break

        item = detalhes[video_id]
        snippet = item['snippet']
        titulo = snippet.get('title', '')
        desc = snippet.get('description', '')

        # Pula se já tem a seção
        if cfg['marker'] in desc:
            print(f"  ⏭️  Já tem relacionados: {titulo[:50]}")
            continue

        # Escolhe os 3 mais recentes DIFERENTES deste vídeo
        outros = [v for v in publicos if v != video_id][:3]
        if len(outros) < 2:
            print(f"  ⚠️  Poucos vídeos para relacionar; pulando.")
            continue

        links_parts = []
        for v in outros:
            if v not in detalhes:
                continue
            tit_v = detalhes[v]['snippet'].get('title', '')[:60]
            links_parts.append(f"▶ {tit_v}\n   https://youtu.be/{v}")
        links = '\n\n'.join(links_parts)

        nova_desc = desc.rstrip() + '\n\n' + cfg['section_hdr'] + links

        print(f"\n  📹 {video_id} | {titulo[:50]}")
        ok_desc = atualizar_descricao(video_id, snippet, nova_desc)
        if not ok_desc:
            print(f"  ❌ Falha ao atualizar descrição; pulando.")
            continue
        print(f"  ✅ Descrição atualizada")

        comment_text = cfg['comment_tpl'].format(links=links)
        ok_comment = postar_comentario(video_id, comment_text)
        if ok_comment:
            print(f"  💬 Comentário postado")
        else:
            print(f"  ⚠️  Comentário não foi postado (token sem youtube.force-ssl?)")

        processados += 1
        time.sleep(3)

    print(f"\n🔗 Concluído — {processados} vídeos com relacionados adicionados.")

if __name__ == "__main__":
    main()
