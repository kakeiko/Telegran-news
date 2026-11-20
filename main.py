import os
import sys
import html
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

def coletar_noticias_por_tema(tema, urls, max_itens=10):
    """Coleta notícias de uma categoria específica com filtros anti-ofertas."""
    noticias = []
    is_games = "Games" in tema
    
    for url in urls:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:max_itens]:
                titulo = entry.get("title", "").strip()
                link = entry.get("link", "").strip()
                resumo_bruto = entry.get("summary") or entry.get("description") or ""
                resumo_limpo = limpar_html_rss(resumo_bruto)
                
                if not titulo or not link:
                    continue
                    
                if is_games:
                    if eh_oferta_de_jogo(titulo) or eh_oferta_de_jogo(resumo_limpo):
                        continue
                        
                noticias.append({
                    "titulo": titulo,
                    "link": link,
                    "contexto": resumo_limpo
                })
        except Exception as e:
            print(f"[Aviso] Erro ao buscar feed {url}: {e}")
            
    # Remove duplicados por título
    unicos = []
    vistos = set()
    for item in noticias:
        chave = item["titulo"].lower()
        if chave not in vistos:
            unicos.append(item)
            vistos.add(chave)
            
    return unicos[:max_itens]

def sanitizar_html_telegram(texto):
    """Garante que tags HTML e caracteres especiais (&, <, >) estejam compatíveis com o Telegram."""
    if not texto:
        return ""
    
    # Remove blocos de código se a IA colocar
    texto = texto.strip()
    if texto.startswith("```html"):
        texto = texto[7:]
    elif texto.startswith("```"):
        texto = texto[3:]
    if texto.endswith("```"):
        texto = texto[:-3]
    texto = texto.strip()
    
    # Corrige '&' isolados que quebram o parser do Telegram (transforma em '&amp;')
    # Exceto se já for &amp;, &lt;, &gt;, &quot;
    texto = re.sub(r'&(?!(amp|lt|gt|quot);)', '&amp;', texto)
    
    return texto

def curar_categoria_com_gemini(tema, itens, api_key):
    """Curadoria individual de uma categoria via Gemini."""
    dados_categoria = ""
    for i, it in enumerate(itens, 1):
        dados_categoria += f"{i}. Título: {it['titulo']}\n   Link: {it['link']}\n"
        if it["contexto"]:
            dados_categoria += f"   Contexto: {it['contexto']}\n"
            
    prompt = f"""Você é um editor sênior de notícias para o Telegram.
Abaixo estão as notícias recentes para a categoria: {tema}

{dados_categoria}

SUA TAREFA:
1. Traga TODAS as notícias que forem genuinamente relevantes, impactantes e quentes hoje (sejam 3, 4, 5 ou mais). Descarte apenas as fracas ou sem relevância.
2. REGRA PARA GAMES: NUNCA traga promoções, descontos ou jogos grátis. Apenas novidades, anúncios, vazamentos (leaks) e acontecimentos reais da indústria.
3. IDIOMA: Todo o texto DEVE estar em Português do Brasil (traduza títulos e fatos de fontes internacionais).
4. RESUMO COMPLETO: Cada notícia selecionada deve ter:
   🔹 <b><a href="LINK_ORIGINAL">Título Claro e Traduzido</a></b>
   <i>Mini-resumo completo de 2 a 3 frases explicando o que aconteceu, os detalhes e o contexto. NUNCA deixe frases cortadas pela metade.</i>
5. Inicie sua resposta com: <b>{tema}</b>\n

IMPORTANTE: Responda APENAS com o texto HTML pronto para o Telegram, sem blocos de código ```html."""

    modelos = [
        "gemini-3.8-flash",
        "gemini-3.5-flash",
        "gemini-3.0-flash",
        "gemini-2.5-flash",
        "gemini-2.0-flash",
        "gemini-1.5-flash"
    ]
    
    # Desativa filtros de segurança para que notícias de política/crimes não sejam bloqueadas pela IA
    safety_settings = [
        {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}
    ]
    
    for modelo in modelos:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{modelo}:generateContent?key={api_key.strip()}"
            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "safetySettings": safety_settings,
                "generationConfig": {
                    "temperature": 0.3,
                    "maxOutputTokens": 3000
                }
            }
            resp = requests.post(url, json=payload, timeout=40)
            if resp.status_code == 200:
                dados = resp.json()
                texto = dados["candidates"][0]["content"]["parts"][0]["text"]
                return sanitizar_html_telegram(texto)
        except Exception as e:
            print(f"[Aviso] Modelo {modelo} falhou em {tema}: {e}")
            
    return None

def enviar_para_telegram(mensagem_html, bot_token, chat_id):
    """Envia uma mensagem para o Telegram garantindo fallback limpo sem poluir com tags visíveis."""
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    
    payload = {
        "chat_id": chat_id,
        "text": mensagem_html,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    
    resp = requests.post(url, json=payload, timeout=30)
    if resp.status_code != 200:
        print(f"[Aviso] Telegram rejeitou HTML ({resp.text}). Enviando texto limpo...")
        # Remove tags HTML para que o usuário NUNCA veja <b> ou <a> crus na tela
        texto_limpo = re.sub(r'<[^>]+>', '', mensagem_html)
        texto_limpo = html.unescape(texto_limpo)
        payload["text"] = texto_limpo
        payload["parse_mode"] = ""
        requests.post(url, json=payload, timeout=30)
    else:
        print("[Sucesso] Categoria entregue no Telegram!")

def main():
    print("Iniciando rotina de notícias independente por categorias...")
    
    telegram_token = os.getenv("TELEGRAM_BOT_TOKEN")
    telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID")
    gemini_key = os.getenv("GEMINI_API_KEY")
    
    if not telegram_token or not telegram_chat_id:
        print("Erro: TELEGRAM_BOT_TOKEN e TELEGRAM_CHAT_ID são obrigatórios.")
        sys.exit(1)
        
    print(f"Status Chave Gemini: {'Configurada' if gemini_key else 'Não encontrada'}")
    
    # Processa e envia cada categoria individualmente
    for tema, urls in FEEDS.items():
        print(f"\n--- Processando: {tema} ---")
        itens = coletar_noticias_por_tema(tema, urls)
        
        mensagem_categoria = None
        if gemini_key and itens:
            mensagem_categoria = curar_categoria_com_gemini(tema, itens, gemini_key)
            
        # Fallback local se a IA não responder
        if not mensagem_categoria and itens:
            linhas = [f"<b>{tema}</b>\n"]
            for it in itens[:4]:
                titulo = html.escape(it['titulo'])
                contexto = html.escape(it['contexto']) if it['contexto'] else "Notícia em destaque."
                linhas.append(f"🔹 <a href=\"{it['link']}\"><b>{titulo}</b></a>\n<i>{contexto}</i>\n")
            mensagem_categoria = "\n".join(linhas)
            
        if mensagem_categoria:
            enviar_para_telegram(mensagem_categoria, telegram_token, telegram_chat_id)
            time.sleep(1.2) # Intervalo para manter ordem perfeita e respeitar limites do Telegram
        else:
            print(f"[Aviso] Nenhuma notícia encontrada para {tema}")
            
    print("\nTodos os temas foram processados e enviados com sucesso!")

if __name__ == "__main__":
    main()
