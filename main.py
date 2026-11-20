import os
import sys
import html
import re
import feedparser
import requests

# ==========================================
# 1. FONTES DE NOTÍCIAS (FEEDS RSS POR TEMA)
# ==========================================
FEEDS = {
    "🎮 Games (Indústria, Anúncios & Vazamentos)": [
        "https://www.theenemy.com.br/feed",
        "https://br.ign.com/feed.xml",
        "https://flowgames.gg/feed/",
        "https://jovemnerd.com.br/feed-nerdbunker"
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

# Palavras que eliminam promoções e ofertas automaticamente
PALAVRAS_BANIDAS_GAMES = [
    "promoção", "promocao", "desconto", "oferta", "grátis", "gratis",
    "de graça", "menor preço", "cupom", "saindo por", "custando apenas",
    "vale a pena comprar", "bundle", "steam sale", "playstation store",
    "xbox game pass adiciona", "onde comprar", "review de teclado", "review de mouse"
]

def limpar_html_rss(texto):
    """Limpa tags HTML de resumos de RSS para enviar à IA."""
    if not texto:
        return ""
    texto_puro = re.sub(r'<[^>]+>', '', texto)
    return " ".join(texto_puro.split())[:350]

def coletar_noticias(max_por_tema=8):
    """Coleta manchetes e descrições dos feeds RSS com filtro anti-ofertas."""
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
                        
                    # Filtro contra promoções em games
                    if is_games:
                        titulo_lower = titulo.lower()
                        if any(ban in titulo_lower for ban in PALAVRAS_BANIDAS_GAMES):
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

def montar_prompt(noticias_coletadas):
    """Monta o prompt com dados ricos para o Gemini criar mini-resumos informativos."""
    prompt_dados = ""
    for tema, itens in noticias_coletadas.items():
        prompt_dados += f"\n### {tema}\n"
        for i, item in enumerate(itens, 1):
            prompt_dados += f"{i}. Título: {item['titulo']}\n   Link: {item['link']}\n"
            if item["contexto"]:
                prompt_dados += f"   Contexto inicial: {item['contexto']}\n"
            
    prompt = f"""Você é um editor sênior e curador de notícias para um boletim exclusivo no Telegram.
Abaixo estão notícias coletadas hoje em diversas categorias:

{prompt_dados}

DIRETRIZES FUNDAMENTAIS:
1. SELEÇÃO: Para CADA categoria, escolha exatamente as 2 ou 3 notícias mais QUENTES, IMPACTANTES e RELEVANTES do momento.
2. REGRA DE OURO PARA GAMES: PROIBIDO qualquer tipo de promoção, desconto, cupom ou lista de 'jogos grátis'. Queremos APENAS acontecimentos reais da indústria: vazamentos (leaks), anúncios oficiais de grandes jogos, adiamentos, escândalos, novidades bombásticas de gameplay ou tecnologia (ex: 'GTA 6 teve detalhes vazados', 'Novo console anunciado').
3. ESTRUTURA DE CADA NOTÍCIA:
   - Uma linha com o título da notícia em formato de link HTML:
     🔹 <b><a href="LINK_ORIGINAL">Título Claro e Impactante</a></b>
   - Logo abaixo, um mini-resumo de 2 a 3 frases em Português do Brasil explicando com clareza o que de fato aconteceu, o contexto e por que isso é importante para o leitor. Não seja vago.
4. FORMATAÇÃO TELEGRAM (HTML):
   - Use <b>negrito</b> para categorias e títulos.
   - Use <i>itálico</i> para termos complementares se desejar.
   - Use <a href="URL">Texto</a> para links clicáveis.
   - Emojis bem posicionados para separar as categorias.
5. Inicie com: "☀️ <b>Boletim Diário: As Notícias Mais Quentes</b>"
6. Finalize com uma breve saudação de encerramento.

IMPORTANTE: Responda APENAS com a mensagem pronta para envio no Telegram. Não utilize blocos de código markdown (como ```html) em volta."""
    return prompt

def limpar_resposta_html(texto):
    """Remove blocos de código que a IA possa ter envolvido."""
    texto = texto.strip()
    if texto.startswith("```html"):
        texto = texto[7:]
    elif texto.startswith("```"):
        texto = texto[3:]
    if texto.endswith("```"):
        texto = texto[:-3]
    return texto.strip()

def curar_com_gemini(noticias_coletadas, api_key):
    """Gera o resumo usando o Google Gemini 1.5 Flash (100% Gratuito)."""
    print("Processando curadoria com Google Gemini...")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
    prompt = montar_prompt(noticias_coletadas)
    
    payload = {
        "contents": [{
            "parts": [{"text": prompt}]
        }],
        "generationConfig": {
            "temperature": 0.35,
            "maxOutputTokens": 3000
        }
    }
    
    resp = requests.post(url, json=payload, timeout=45)
    if resp.status_code != 200:
        raise Exception(f"Erro na API do Gemini ({resp.status_code}): {resp.text}")
        
    dados = resp.json()
    texto = dados["candidates"][0]["content"]["parts"][0]["text"]
    return limpar_resposta_html(texto)

def curar_com_claude(noticias_coletadas, api_key):
    """Gera o resumo usando a Anthropic (Claude)."""
    print("Processando curadoria com Anthropic Claude...")
    from anthropic import Anthropic
    client = Anthropic(api_key=api_key)
    prompt = montar_prompt(noticias_coletadas)
    
    response = client.messages.create(
        model="claude-3-5-sonnet-20241022",
        max_tokens=3000,
        temperature=0.35,
        messages=[{"role": "user", "content": prompt}]
    )
    return limpar_resposta_html(response.content[0].text)

def enviar_telegram(mensagem_html, bot_token, chat_id):
    """Envia a mensagem via API do Telegram com suporte a HTML e divide se necessário."""
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    
    # Telegram aceita até 4096 caracteres por mensagem
    limite = 3900
    partes = []
    
    # Divide inteligentemente por quebras de linha para não quebrar tags HTML
    if len(mensagem_html) <= limite:
        partes = [mensagem_html]
    else:
        linhas = mensagem_html.split("\n")
        parte_atual = ""
        for linha in linhas:
            if len(parte_atual) + len(linha) + 1 < limite:
                parte_atual += linha + "\n"
            else:
                partes.append(parte_atual.strip())
                parte_atual = linha + "\n"
        if parte_atual:
            partes.append(parte_atual.strip())
    
    for parte in partes:
        if not parte.strip():
            continue
        payload = {
            "chat_id": chat_id,
            "text": parte,
            "parse_mode": "HTML",
            "disable_web_page_preview": True
        }
        resp = requests.post(url, json=payload, timeout=30)
        if resp.status_code != 200:
            print(f"[Aviso HTML falhou] Tentando enviar em texto plano: {resp.text}")
            payload["parse_mode"] = ""
            requests.post(url, json=payload, timeout=30)
        else:
            print("[Sucesso] Mensagem entregue no Telegram!")

def main():
    print("Iniciando rotina de notícias...")
    
    telegram_token = os.getenv("TELEGRAM_BOT_TOKEN")
    telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID")
    gemini_key = os.getenv("GEMINI_API_KEY")
    anthropic_key = os.getenv("ANTHROPIC_API_KEY")
    
    if not telegram_token or not telegram_chat_id:
        print("Erro: TELEGRAM_BOT_TOKEN e TELEGRAM_CHAT_ID são obrigatórios.")
        sys.exit(1)
        
    print("1/3 Coletando feeds RSS com filtros de notícias reais...")
    noticias = coletar_noticias()
    
    print("2/3 Processando curadoria e mini-resumos com IA...")
    mensagem = None
    
    # Prioridade 1: Gemini (Gratuito)
    if gemini_key:
        try:
            mensagem = curar_com_gemini(noticias, gemini_key)
        except Exception as e:
            print(f"[Aviso] Falha no Gemini: {e}")
            
    # Prioridade 2: Claude (caso configurado)
    if not mensagem and anthropic_key:
        try:
            mensagem = curar_com_claude(noticias, anthropic_key)
        except Exception as e:
            print(f"[Aviso] Falha no Claude: {e}")
            
    # Prioridade 3: Fallback sem IA
    if not mensagem:
        print("[Aviso] Nenhuma chave de IA disponível. Gerando boletim simples...")
        linhas = ["☀️ <b>Boletim Diário: Notícias do Momento</b>\n"]
        for tema, itens in noticias.items():
            linhas.append(f"\n<b>{tema}</b>")
            for item in itens[:3]:
                titulo_escapado = html.escape(item['titulo'])
                linhas.append(f"🔹 <a href=\"{item['link']}\">{titulo_escapado}</a>")
        mensagem = "\n".join(linhas)
        
    print("3/3 Enviando para o Telegram...")
    enviar_telegram(mensagem, telegram_token, telegram_chat_id)
    print("Concluído com sucesso!")

if __name__ == "__main__":
    main()
