import os
import sys
import html
import feedparser
import requests

# ==========================================
# 1. FONTES DE NOTÍCIAS (FEEDS RSS POR TEMA)
# ==========================================
FEEDS = {
    "🎮 Games": [
        "https://www.theenemy.com.br/feed",
        "https://br.ign.com/feed.xml",
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
    "🚀 Tecnologia & Ciência": [
        "https://tecmundo.com.br/rss",
        "https://canaltech.com.br/rss/"
    ]
}

def coletar_noticias(max_por_tema=8):
    """Coleta as manchetes mais recentes de cada tema."""
    noticias_por_tema = {}
    
    for tema, urls in FEEDS.items():
        noticias_tema = []
        for url in urls:
            try:
                feed = feedparser.parse(url)
                for entry in feed.entries[:max_por_tema]:
                    titulo = entry.get("title", "").strip()
                    link = entry.get("link", "").strip()
                    if titulo and link:
                        noticias_tema.append({"titulo": titulo, "link": link})
            except Exception as e:
                print(f"[Aviso] Erro ao buscar feed {url}: {e}")
        
        # Elimina duplicados por título
        unicos = []
        titulos_vistos = set()
        for item in noticias_tema:
            if item["titulo"].lower() not in titulos_vistos:
                unicos.append(item)
                titulos_vistos.add(item["titulo"].lower())
                
        noticias_por_tema[tema] = unicos[:max_por_tema]
        
    return noticias_por_tema

def montar_prompt(noticias_coletadas):
    """Monta a instrução para a IA analisar as notícias."""
    prompt_dados = ""
    for tema, itens in noticias_coletadas.items():
        prompt_dados += f"\n### {tema}\n"
        for item in itens:
            prompt_dados += f"- [{item['titulo']}]({item['link']})\n"
            
    prompt = f"""Você é um editor sênior e curador de notícias para um boletim diário no Telegram.
Abaixo está a lista bruta das notícias mais recentes coletadas em várias categorias:

{prompt_dados}

SUA TAREFA:
1. Para CADA tema, selecione as 2 ou 3 notícias mais relevantes, quentes e impactantes do momento. Ignore clickbaits fracos.
2. Formate cada notícia como um bullet point contendo:
   - Título em negrito e com o link clicável original no formato HTML.
   - Uma breve explicação em 1 frase de por que essa notícia importa ou o que aconteceu.
3. Use formatação HTML limpa e compatível com o Telegram:
   - Use <b>negrito</b> para títulos e nomes de categorias.
   - Use <a href="URL">Título da Notícia</a> para links clicáveis.
   - Use emojis para destacar as seções.
4. Mantenha o tom profissional, direto e empolgante em Português do Brasil.
5. Inicie com uma saudação como "☀️ <b>Boletim Diário: Destaques de Hoje</b>" e termine com uma breve mensagem motivacional.

IMPORTANTE: Responda APENAS com o texto final pronto para envio no Telegram. Não adicione crases de bloco de código (ex: ```html) no início ou no fim."""
    return prompt

def limpar_resposta_html(texto):
    """Remove blocos de código markdown que a IA possa ter adicionado."""
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
            "temperature": 0.4,
            "maxOutputTokens": 2500
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
        max_tokens=2500,
        temperature=0.4,
        messages=[{"role": "user", "content": prompt}]
    )
    return limpar_resposta_html(response.content[0].text)

def enviar_telegram(mensagem_html, bot_token, chat_id):
    """Envia a mensagem via API do Telegram com suporte a HTML."""
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    
    limite = 4000
    partes = [mensagem_html[i:i+limite] for i in range(0, len(mensagem_html), limite)]
    
    for parte in partes:
        payload = {
            "chat_id": chat_id,
            "text": parte,
            "parse_mode": "HTML",
            "disable_web_page_preview": True
        }
        resp = requests.post(url, json=payload, timeout=30)
        if resp.status_code != 200:
            print(f"[Erro Telegram] Tentando enviar sem formatação HTML. Motivo: {resp.text}")
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
        
    print("1/3 Coletando feeds RSS mais recentes...")
    noticias = coletar_noticias()
    
    print("2/3 Processando curadoria...")
    mensagem = None
    
    # Prioridade 1: Gemini (Gratuito)
    if gemini_key:
        try:
            mensagem = curar_com_gemini(noticias, gemini_key)
        except Exception as e:
            print(f"[Aviso] Falha no Gemini: {e}")
            
    # Prioridade 2: Claude (caso configurado e Gemini não esteja disponível)
    if not mensagem and anthropic_key:
        try:
            mensagem = curar_com_claude(noticias, anthropic_key)
        except Exception as e:
            print(f"[Aviso] Falha no Claude: {e}")
            
    # Prioridade 3: Fallback sem IA (envio das manchetes diretas)
    if not mensagem:
        print("[Aviso] Nenhuma chave de IA disponível ou falha na API. Gerando resumo padrão...")
        linhas = ["☀️ <b>Boletim Diário: Principais Notícias</b>\n"]
        for tema, itens in noticias.items():
            linhas.append(f"\n<b>{tema}</b>")
            for item in itens[:3]:
                titulo_escapado = html.escape(item['titulo'])
                linhas.append(f"• <a href=\"{item['link']}\">{titulo_escapado}</a>")
        mensagem = "\n".join(linhas)
        
    print("3/3 Enviando para o Telegram...")
    enviar_telegram(mensagem, telegram_token, telegram_chat_id)
    print("Boletim concluído!")

if __name__ == "__main__":
    main()
