# -*- coding: utf-8 -*-
"""novenas.py — Slot 06:00 (Novenas) — gerado a partir do padrão do PT (aprovado por Leandro em 2026-09-25). Somente personas marianas do canal."""
import datetime

CFG = {
 "canal": "ES", "tz": "America/Mexico_City", "lang_name": "Mexican Spanish (español de México)",
 "ativacao": datetime.date(2026, 9, 30), "epoca_pedidos": datetime.date(2026, 9, 30),
 "status_pronto": "Pronto p/ Áudio", "invocacao_padrao": "La Morenita",
 "promessa_regra": 'MUST start with "La Morenita". Ex: "La Morenita Sana Tu Hogar", "La Morenita Abre Tus Puertas".',
 "festas": [
   {"id": "guadalupe", "inicio": (12, 3), "nome": "Novena a la Virgen de Guadalupe", "invocacao": "Virgen de Guadalupe, La Morenita",
    "festa": "Fiesta de Nuestra Señora de Guadalupe, Emperatriz de América (12 de diciembre)"},
   {"id": "navidad", "inicio": (12, 16), "nome": "Novena de Navidad con la Virgen María", "invocacao": "Virgen de Guadalupe",
    "festa": "Navidad (25 de diciembre) — las Posadas: María y José buscando posada"},
 ],
 "intencoes_festa": ["la sanación de las enfermedades y la salud de quien amas", "la unión y restauración de tu familia",
   "la reconciliación, el perdón y la paz", "la liberación de vicios y ataduras", "la protección y el futuro de tus hijos",
   "el trabajo, el sustento y las puertas abiertas", "la protección espiritual de tu hogar contra todo mal",
   "las causas imposibles y desesperadas", "la gratitud por las gracias recibidas y la consagración a la Virgen"],
 "categorias": {
   "saude": ("Novena para la Sanación y la Salud", "enfermedades, salud física, tratamientos y cirugías"),
   "familia": ("Novena por la Restauración de la Familia", "peleas, distancia y restauración de la familia y del matrimonio"),
   "emprego": ("Novena para Conseguir Trabajo", "desempleo, trabajo, sustento y puertas abiertas"),
   "dividas": ("Novena para Salir de las Deudas", "deudas, apuros económicos y providencia divina"),
   "filhos": ("Novena por los Hijos", "protección, camino y conversión de los hijos"),
   "vicios": ("Novena para la Liberación de Vicios", "vicios, dependencias y ataduras de quienes amamos"),
   "ansiedade": ("Novena para Vencer la Ansiedad", "ansiedad, angustia, tristeza profunda y paz interior"),
   "protecao": ("Novena de Protección Espiritual", "protección contra el mal, la envidia y los ataques espirituales"),
   "causas": ("Novena para Causas Imposibles", "causas imposibles, urgentes y desesperadas"),
   "luto": ("Novena de Consuelo en el Duelo", "duelo, nostalgia y consuelo por la pérdida de un ser querido")},
 "meses": ["Enero","Febrero","Marzo","Abril","Mayo","Junio","Julio","Agosto","Septiembre","Octubre","Noviembre","Diciembre"],
 "completa": "(Completa)", "dia_label": "Día {n}", "thumb_fmt": "NOVENA DÍA {n}",
 "data_no_titulo_festa": True, "data_fmt": "Hoy {d} de {m}",
 "periodo": "en esta mañana",
 "desc_link": "📿 Reza la novena completa, todos los días en orden: {url}",
 "cap_titulo": "⏱️ Capítulos de la Novena:",
 "cap": ["Apertura e Intención del Día", "Reflexión de la Palabra", "Oración de la Novena", "Súplica del Día", "Padre Nuestro, Ave María y Gloria", "Cierre y Bendición"],
 "sinal_da_cruz": "En el nombre del Padre... y del Hijo... y del Espíritu Santo... Amén...",
 "ato_contricao": ("Recemos juntos el acto de contrición... Señor mío Jesucristo... Dios y Hombre verdadero... Creador, Padre y Redentor mío... "
   "por ser Tú quien eres, bondad infinita... y porque te amo sobre todas las cosas... me pesa de todo corazón haberte ofendido... "
   "Propongo firmemente, con tu gracia, nunca más pecar... y alejarme de las ocasiones de pecado... Amén..."),
 "pai_nosso": ("Padre nuestro, que estás en el cielo... santificado sea tu Nombre... venga a nosotros tu reino... hágase tu voluntad en la tierra como en el cielo... "
   "Danos hoy nuestro pan de cada día... perdona nuestras ofensas... como también nosotros perdonamos a los que nos ofenden... "
   "no nos dejes caer en la tentación... y líbranos del mal... Amén..."),
 "ave_maria": ("Dios te salve, María... llena eres de gracia... el Señor es contigo... Bendita tú eres entre todas las mujeres... "
   "y bendito es el fruto de tu vientre Jesús... Santa María, Madre de Dios... ruega por nosotros, pecadores... ahora y en la hora de nuestra muerte... Amén..."),
 "gloria": "Gloria al Padre... y al Hijo... y al Espíritu Santo... Como era en el principio, ahora y siempre, por los siglos de los siglos... Amén...",
 "oracoes_festa": {
   "guadalupe": ("Recemos ahora la oración de esta novena... Oh Virgen de Guadalupe... Morenita del Tepeyac... "
     "tú que le dijiste a Juan Diego: ¿No estoy yo aquí, que soy tu Madre?... ven hoy a mi vida... "
     "Mira mis dolores... las necesidades de mi familia... y todo lo que no puedo cargar solo... "
     "En este día de tu novena te entrego mi intención... y confío en que, por tu intercesión, tu Hijo Jesús hará lo mejor para mí... "
     "Cúbreme con tu manto de estrellas... protege mi hogar... sana lo que está herido... y llévame siempre más cerca de Jesús... Amén..."),
   "navidad": ("Recemos ahora la oración de esta novena... Oh María... Madre que esperaba al Niño... "
     "tú que junto a San José tocaste puertas buscando posada... prepara también mi corazón para recibir a Jesús... "
     "En este día de la novena te entrego mi intención y a mi familia... que la luz de Belén entre en nuestra casa... y traiga paz... sanación... y unión... Amén...")},
 "oracao_festa_generica": "Recemos ahora la oración de esta novena... Oh {inv}... en este día de tu novena te entrego mi intención... preséntala a tu Hijo Jesús... Amén...",
 "oracao_pedido": ("Recemos ahora la oración de esta novena... Oh Virgen de Guadalupe... Madre de Dios y Madre nuestra... "
   "en esta novena vengo a tus pies con una petición que pesa en mi corazón... Tú conoces mi dolor... antes de que yo lo diga... "
   "En este día de la novena te entrego mi intención... y te pido que la lleves a tu Hijo Jesús... como llevaste la petición de los novios en Caná... "
   "Que se haga la voluntad de Dios... y que yo tenga fuerza para esperar con fe... Amén..."),
 "jaculatoria": "{inv}... ruega por nosotros...",
 "cta_pista": "invite them to write in the comments their intention or the name of the person they entrust to La Morenita, because these intentions are prayed in our 24-hour live stream",
}

# ─────────────────────── MOTOR (idêntico em todos os canais) ───────────────────────
import datetime

CANAL = CFG["canal"]
TZ = CFG["tz"]
ATIVACAO_06H = CFG["ativacao"]
EPOCA_PEDIDOS = CFG["epoca_pedidos"]
FESTAS = CFG["festas"]
INTENCOES_FESTA = CFG["intencoes_festa"]
CATEGORIAS = CFG["categorias"]
ROTACAO_FALLBACK = ["saude", "familia", "emprego", "ansiedade", "filhos", "protecao", "vicios", "dividas", "causas", "luto"]
JANELA_ANTI_REPETICAO = 3
MIN_COMENTARIOS_RANKING = 5
STATUS_PRONTO = CFG["status_pronto"]
LANG_NAME = CFG["lang_name"]
PROGRESSAO_PEDIDO = {
    1: "Day of SURRENDER: present the pain honestly and open the heart.",
    2: "Day of SURRENDER: admit what we cannot carry alone.",
    3: "Day of SURRENDER: forgive and let go of what weighs, to receive grace.",
    4: "Day of PERSEVERANCE: keep faith even when nothing seems to change.",
    5: "Day of PERSEVERANCE: the strength of Mary at the foot of the cross.",
    6: "Day of PERSEVERANCE: fight discouragement and the voice of fear.",
    7: "Day of TRUST: signs that grace is already on its way.",
    8: "Day of TRUST: give thanks in advance for what God will do.",
    9: "Day of GRATITUDE and CONSECRATION: entrust life and the cause to Our Lady.",
}
ABA_NOVENAS = "NOVENAS"
ABA_TEMAS = "TEMAS_COMENTARIOS"


def _festas_do_ano(ano):
    out = []
    for f in FESTAS:
        ini = datetime.date(ano, f["inicio"][0], f["inicio"][1])
        out.append((ini, ini + datetime.timedelta(days=8), ini + datetime.timedelta(days=9), f))
    return sorted(out, key=lambda x: x[0])


def _festa_em(d):
    for ano in (d.year - 1, d.year):
        for ini, fim, dia_festa, f in _festas_do_ano(ano):
            if ini <= d <= fim:
                return ("festa", f, (d - ini).days + 1, ini)
            if d == dia_festa:
                return ("dia_festa", f, None, ini)
    return None


def _proxima_festa_inicio(d):
    for ano in (d.year, d.year + 1):
        for ini, _, _, _ in _festas_do_ano(ano):
            if ini >= d:
                return ini
    return None


def plano_do_dia(d):
    if d < ATIVACAO_06H:
        return None
    fe = _festa_em(d)
    if fe:
        tipo, f, n, ini = fe
        if tipo == "festa":
            return {"tipo": "festa", "dia": n, "festa": f, "ciclo_inicio": ini}
        return {"tipo": "avulsa", "motivo": f"dia da festa ({f['id']})"}
    if d < EPOCA_PEDIDOS:
        return {"tipo": "avulsa", "motivo": "antes da época de pedidos"}
    cursor = EPOCA_PEDIDOS
    guard = 0
    while cursor <= d and guard < 2000:
        guard += 1
        fe_c = _festa_em(cursor)
        if fe_c:
            cursor = fe_c[3] + datetime.timedelta(days=10)
            continue
        prox = _proxima_festa_inicio(cursor)
        fim_ciclo = cursor + datetime.timedelta(days=8)
        if prox is None or fim_ciclo < prox:
            if cursor <= d <= fim_ciclo:
                return {"tipo": "pedido", "dia": (d - cursor).days + 1, "ciclo_inicio": cursor}
            cursor = fim_ciclo + datetime.timedelta(days=1)
        else:
            if cursor <= d < prox:
                return {"tipo": "avulsa", "motivo": "intervalo antes de novena de festa"}
            cursor = prox
    return {"tipo": "avulsa", "motivo": "fallback"}


def nome_mes(d):
    return f"{CFG['meses'][d.month - 1]} {d.year}"


def nome_playlist(plano, categoria=None):
    if plano["tipo"] == "festa":
        return f"{plano['festa']['nome']} {plano['ciclo_inicio'].year} {CFG['completa']}"
    if plano["tipo"] == "pedido":
        return f"{CATEGORIAS[categoria][0]} — {nome_mes(plano['ciclo_inicio'])}"
    return None


def montar_titulo(plano, promessa, categoria=None, data=None):
    """[Palavra-chave de busca] + [Dia N] + 🙏 + [Dor/Promessa]."""
    promessa = (promessa or "").strip().strip(".").strip()
    n = plano["dia"]
    dia_lbl = CFG["dia_label"].format(n=n)
    if plano["tipo"] == "festa":
        base = f"{plano['festa']['nome']} {dia_lbl} 🙏"
        if CFG.get("data_no_titulo_festa") and data is not None:
            base += " " + CFG["data_fmt"].format(d=data.day, m=CFG["meses"][data.month - 1])
            base += " |"
    else:
        base = f"{CATEGORIAS[categoria][0]} – {dia_lbl} 🙏"
    titulo = f"{base} {promessa}".strip()
    if len(titulo) > 100:
        titulo = base.rstrip(" |")
    return titulo


def texto_thumb(plano):
    return CFG["thumb_fmt"].format(n=plano["dia"])


def tema_codificado(plano, categoria=None):
    chave = plano["festa"]["id"] if plano["tipo"] == "festa" else categoria
    return f"NOVENA|{nome_playlist(plano, categoria)}|{plano['dia']}|{plano['tipo']}|{chave}"


def montar_roteiro(plano, gancho, reflexao, suplica, encerramento):
    if plano["tipo"] == "festa":
        f = plano["festa"]
        oracao = CFG["oracoes_festa"].get(f["id"], CFG["oracao_festa_generica"]).format(inv=f["invocacao"])
        jac = CFG["jaculatoria"].format(inv=f["invocacao"])
    else:
        oracao = CFG["oracao_pedido"]
        jac = CFG["jaculatoria"].format(inv=CFG["invocacao_padrao"])
    partes = [gancho.strip(), CFG["sinal_da_cruz"], CFG["ato_contricao"], reflexao.strip(), oracao,
              suplica.strip(), CFG["pai_nosso"], CFG["ave_maria"], CFG["gloria"], jac,
              encerramento.strip(), CFG["sinal_da_cruz"]]
    return "\n\n".join(p for p in partes if p)


def _aba(planilha, nome, cabecalho):
    try:
        return planilha.worksheet(nome)
    except Exception:
        ws = planilha.add_worksheet(title=nome, rows=1000, cols=len(cabecalho))
        ws.update(values=[cabecalho], range_name="A1")
        return ws


def escolher_tema_pedido(planilha, ciclo_inicio):
    ws_nov = _aba(planilha, ABA_NOVENAS, ["Canal", "Inicio", "Tipo", "Categoria", "Fonte", "Criado_em"])
    linhas = ws_nov.get_all_values()[1:]
    ciclo_str = str(ciclo_inicio)
    do_canal = [l for l in linhas if len(l) >= 4 and l[0] == CANAL and l[2] == "pedido"]
    for l in do_canal:
        if l[1] == ciclo_str and l[3] in CATEGORIAS:
            return l[3]
    usados = [l[3] for l in sorted(do_canal, key=lambda x: x[1]) if l[1] < ciclo_str][-JANELA_ANTI_REPETICAO:]
    escolha, fonte = None, "fallback"
    try:
        ws_t = _aba(planilha, ABA_TEMAS, ["Canal", "Data", "Categoria", "Contagem"])
        rows = [r for r in ws_t.get_all_values()[1:] if len(r) >= 4 and r[0] == CANAL]
        if rows:
            ultima = max(r[1] for r in rows)
            dt_ult = datetime.datetime.strptime(ultima, "%Y-%m-%d").date()
            if (ciclo_inicio - dt_ult).days <= 30:
                lote = []
                for r in rows:
                    if r[1] == ultima and r[2] in CATEGORIAS:
                        try: lote.append((r[2], int(r[3])))
                        except ValueError: pass
                if sum(c for _, c in lote) >= MIN_COMENTARIOS_RANKING:
                    for cat, cnt in sorted(lote, key=lambda x: -x[1]):
                        if cnt > 0 and cat not in usados:
                            escolha, fonte = cat, f"comentarios {ultima}"
                            break
    except Exception as e:
        print(f"[WARN] Ranking de comentários indisponível: {e}")
    if not escolha:
        idx = len(do_canal)
        for i in range(len(ROTACAO_FALLBACK)):
            cand = ROTACAO_FALLBACK[(idx + i) % len(ROTACAO_FALLBACK)]
            if cand not in usados:
                escolha = cand
                break
    ws_nov.append_row([CANAL, ciclo_str, "pedido", escolha, fonte,
                       datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M")])
    print(f"📿 Novo ciclo de pedido {ciclo_str}: '{escolha}' ({fonte})")
    return escolha
