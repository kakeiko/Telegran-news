import os
import sys
import html
import json
import re
import time
import feedparser
import requests

# ==========================================
# 1. FONTES DE NOTÍCIAS (FEEDS RSS POR TEMA)
# ==========================================
FEEDS = {
    "🎮 Games": [
        "https://insider-gaming.com/feed/",          # Vazamentos, leaks e bastidores
        "https://www.videogameschronicle.com/feed/", # VGC: Notícias oficiais e exclusivas
        "https://flowgames.gg/feed/",                # Portal BR de novidades
        "https://www.theenemy.com.br/feed"
    ],
    "⛩️ Animes & Mangás": [
        "https://www.animenewsnetwork.com/all/rss.xml?ann-edition=pt",
        "https://otakupt.com/feed/"
    ],
    "🏛️ Política & Economia": [
        "https://g1.globo.com/rss/g1/politica/",
        "https://rss.uol.com.br/feed/politica.xml"
    ],
    "💻 Programação & Dev": [
        "https://news.ycombinator.com/rss",
        "https://dev.to/feed"
    ],
    "🚀 Tecnologia & Inovação": [
        "https://tecmundo.com.br/rss",
        "https://canaltech.com.br/rss/"
    ]
}

# Bloqueio rigoroso contra promoções/ofertas em Games
TERMOS_BANIDOS_GAMES = [
    "promoção", "promocao", "desconto", "oferta", "ofertas", "grátis", "gratis",
    "de graça", "menor preço", "menor preco", "cupom", "cupons", "saindo por",
    "custando apenas", "vale a pena comprar", "bundle", "steam sale",
    "playstation store", "ps store", "xbox store", "epic games store",
    "onde comprar", "review de", "análise de headset", "análise de teclado",
    "custo-benefício", "barato", "baratos", "economize", "preço baixo",
    "compre agora", "por apenas", "está em oferta", "jogos com até",
    "jogos por menos de", "jogos gratuitos", "jogo grátis", "resgatar de graça",
    "resgate", "resgate grátis", "cashback", "amazon prime gaming", "ps plus de",
    "game pass de", "em promoção", "com desconto", "off", "por r$", "preço histórico"
]

def limpar_html_rss(texto):
    """Limpa tags HTML de resumos de RSS para enviar à IA."""
    if not texto:
        return ""
    texto_puro = re.sub(r'<[^>]+>', '', texto)
    return " ".join(texto_puro.split())[:350]

def eh_oferta_de_jogo(texto):
    texto_lower = texto.lower()
    return any(termo in texto_lower for termo in TERMOS_BANIDOS_GAMES)

def coletar_noticias(max_por_tema=8):
    """Coleta notícias dos feeds com filtro anti-ofertas em Games."""
    noticias_por_tema = {}
    
    for tema, urls in FEEDS.items():
        noticias_tema = []
        is_games = "Games" in tema
        
        for url in urls:
            try:
                feed = feedparser.parse(url)
                for entry in feed.entries[:max_por_tema * 2]:
                    titulo = entry.get("title", "").strip()
                    link = entry.get("link", "").strip()
                    resumo_bruto = entry.get("summary") or entry.get("description") or ""
                    resumo_limpo = limpar_html_rss(resumo_bruto)
                    
                    if not titulo or not link:
                        continue
                        
                    if is_games:
                        if eh_oferta_de_jogo(titulo) or eh_oferta_de_jogo(resumo_limpo):
                            continue
                            
                    noticias_tema.append({
                        "titulo": titulo,
                        "link": link,
                        "contexto": resumo_limpo
                    })
            except Exception as e:
                print(f"[Aviso] Erro ao buscar feed {url}: {e}")
        
        # Elimina duplicados por título
        unicos = []
        titulos_vistos = set()
        for item in noticias_tema:
            chave = item["titulo"].lower()
            if chave not in titulos_vistos:
                unicos.append(item)
                titulos_vistos.add(chave)
                
        noticias_por_tema[tema] = unicos[:max_por_tema]
        
    return noticias_por_tema

def obter_modelos_disponiveis(api_key):
    """Consulta a API do Google para descobrir automaticamente o modelo Flash mais recente disponível."""
    candidatos_preferidos = [
        "gemini-3.8-flash",
        "gemini-3.5-flash",
        "gemini-3.0-flash",
        "gemini-2.5-flash",
        "gemini-2.0-flash",
        "gemini-1.5-flash"
    ]
    
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key.strip()}"
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            dados = resp.json()
            modelos_conta = [
                m["name"].replace("models/", "")
                for m in dados.get("models", [])
                if "generateContent" in m.get("supportedGenerationMethods", []) and "flash" in m.get("name", "").lower()
            ]
            print(f"[Modelos Flash disponíveis na sua conta]: {modelos_conta}")
            
            # Prioriza a versão mais recente encontrada na lista de candidatos
            for cand in candidatos_preferidos:
                if cand in modelos_conta:
                    return [cand] + [m for m in modelos_conta if m != cand]
                    
            if modelos_conta:
                modelos_conta.sort(reverse=True)
                return modelos_conta
    except Exception as e:
        print(f"[Aviso] Consulta dinâmica de modelos: {e}")
        
    return candidatos_preferidos

def montar_prompt_json(noticias_coletadas):
    """Cria o prompt solicitando resposta estritamente em JSON para evitar erros de formatação."""
    prompt_dados = ""
    for tema, itens in noticias_coletadas.items():
        prompt_dados += f"\n### TEMA: {tema}\n"
        for i, item in enumerate(itens, 1):
            prompt_dados += f"{i}. Título: {item['titulo']}\n   Link: {item['link']}\n"
            if item["contexto"]:
                prompt_dados += f"   Contexto: {item['contexto']}\n"
            
    prompt = f"""Você é o editor-chefe de notícias para um canal de tecnologia, games, animes e atualidades.
Abaixo estão as notícias coletadas hoje:

{prompt_dados}

SUA MISSÃO:
1. Para CADA tema, selecione as notícias que forem verdadeiramente importantes, relevantes e quentes hoje (sem limite fixo, traga de 3 a 5 notícias impactantes por categoria).
2. REGRA DE GAMES: PROIBIDO qualquer tipo de promoção, desconto, lista de jogos grátis ou cupom. Apenas novidades, anúncios de estúdios, vazamentos (leaks) e acontecimentos reais da indústria.
3. IDIOMA: Todo o conteúdo (título e resumo) DEVE estar em Português do Brasil de excelente qualidade.
4. RESUMO: Cada notícia selecionada deve ter um resumo informativo de 2 a 3 frases completas explicando com clareza o que aconteceu.

Você DEVE responder EXCLUSIVAMENTE um objeto JSON válido no seguinte formato:
{{
  "categorias": [
    {{
      "tema": "🎮 Games",
      "noticias": [
        {{
          "titulo": "Título traduzido e impactante",
          "link": "URL_ORIGINAL_DA_NOTICIA",
          "resumo": "Mini-resumo completo de 2 a 3 frases explicando o acontecimento."
        }}
      ]
    }}
  ]
}}"""
    return prompt

def curar_com_gemini_json(noticias_coletadas, api_key):
    """Executa a curadoria usando automaticamente o modelo mais avançado suportado pela chave."""
    prompt = montar_prompt_json(noticias_coletadas)
    modelos = obter_modelos_disponiveis(api_key)
    
    safety_settings = [
        {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}
    ]
    
    for modelo in modelos:
        try:
            print(f"Tentando curadoria com o modelo: {modelo}...")
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{modelo}:generateContent?key={api_key.strip()}"
            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "safetySettings": safety_settings,
                "generationConfig": {
                    "responseMimeType": "application/json",
                    "temperature": 0.25,
                    "maxOutputTokens": 8192
                }
            }
            resp = requests.post(url, json=payload, timeout=60)
            if resp.status_code == 200:
                dados = resp.json()
                texto_json = dados["candidates"][0]["content"]["parts"][0]["text"]
                print(f"[Sucesso Absoluto] Notícias processadas com o modelo mais recente: {modelo}!")
                return json.loads(texto_json)
            else:
                print(f"[Aviso] Modelo {modelo} retornou status {resp.status_code}")
        except Exception as e:
            print(f"[Aviso] Falha com {modelo}: {e}")
            
    return None

def formatar_e_enviar_telegram(dados_json, noticias_brutas, bot_token, chat_id):
    """Formata o HTML com segurança máxima via Python e envia uma mensagem por categoria."""
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    
    if dados_json and "categorias" in dados_json:
        categorias = dados_json["categorias"]
        print(f"Enviando {len(categorias)} categorias para o Telegram...")
        
        for idx, cat in enumerate(categorias, 1):
            tema = cat.get("tema", "Notícias")
            noticias = cat.get("noticias", [])
            
            if not noticias:
                continue
                
            linhas = [f"<b>{html.escape(tema)}</b>\n"]
            for n in noticias:
                titulo = html.escape(n.get("titulo", "").strip())
                resumo = html.escape(n.get("resumo", "").strip())
                link = n.get("link", "").strip()
                
                linhas.append(f"🔹 <a href=\"{link}\"><b>{titulo}</b></a>")
                linhas.append(f"<i>{resumo}</i>\n")
                
            mensagem_html = "\n".join(linhas)
            
            payload = {
                "chat_id": chat_id,
                "text": mensagem_html,
                "parse_mode": "HTML",
                "disable_web_page_preview": True
            }
            
            resp = requests.post(url, json=payload, timeout=30)
            if resp.status_code == 200:
                print(f"[Sucesso] Mensagem {idx}/{len(categorias)} ({tema}) entregue!")
            else:
                print(f"[Aviso] Falha no HTML de {tema}. Enviando texto limpo...")
                payload["text"] = re.sub(r'<[^>]+>', '', mensagem_html)
                payload["parse_mode"] = ""
                requests.post(url, json=payload, timeout=30)
                
            time.sleep(1.0)
            
    else:
        print("[Aviso] Usando fallback local das notícias...")
        for tema, itens in noticias_brutas.items():
            linhas = [f"<b>{html.escape(tema)}</b>\n"]
            for it in itens[:4]:
                titulo = html.escape(it["titulo"])
                contexto = html.escape(it["contexto"]) if it["contexto"] else "Notícia em destaque."
                linhas.append(f"🔹 <a href=\"{it['link']}\"><b>{titulo}</b></a>")
                linhas.append(f"<i>{contexto}</i>\n")
                
            mensagem_html = "\n".join(linhas)
            payload = {
                "chat_id": chat_id,
                "text": mensagem_html,
                "parse_mode": "HTML",
                "disable_web_page_preview": True
            }
            requests.post(url, json=payload, timeout=30)
            time.sleep(1.0)

def main():
    print("Iniciando rotina de notícias...")
    
    telegram_token = os.getenv("TELEGRAM_BOT_TOKEN")
    telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID")
    gemini_key = os.getenv("GEMINI_API_KEY")
    
    if not telegram_token or not telegram_chat_id:
        print("Erro: TELEGRAM_BOT_TOKEN e TELEGRAM_CHAT_ID são obrigatórios.")
        sys.exit(1)
        
    print("1/3 Coletando feeds RSS com filtro anti-ofertas...")
    noticias = coletar_noticias()
    
    print("2/3 Detectando modelo mais recente e gerando curadoria com IA...")
    dados_json = None
    if gemini_key:
        dados_json = curar_com_gemini_json(noticias, gemini_key)
        
    print("3/3 Despachando categorias completas para o Telegram...")
    formatar_e_enviar_telegram(dados_json, noticias, telegram_token, telegram_chat_id)
    print("Processo concluído com êxito!")

if __name__ == "__main__":
    main()
