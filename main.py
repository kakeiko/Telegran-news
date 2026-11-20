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
    "🎮 Games (Vazamentos, Anúncios & Indústria)": [
        "https://insider-gaming.com/feed/",          # Maior portal mundial de vazamentos e bastidores
        "https://www.videogameschronicle.com/feed/", # VGC: Notícias oficiais e exclusivas de estúdios
        "https://flowgames.gg/feed/",                # Portal BR focado em novidades
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

# Lista rigorosa de termos banidos para eliminar 100% das ofertas
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
    """Verifica se o texto contém qualquer menção a ofertas/descontos."""
    texto_lower = texto.lower()
    return any(termo in texto_lower for termo in TERMOS_BANIDOS_GAMES)

def coletar_noticias(max_por_tema=8):
    """Coleta manchetes e descrições dos feeds RSS com filtro estrito anti-ofertas."""
    noticias_por_tema = {}
    
    for tema, urls in FEEDS.items():
        noticias_tema = []
        is_games = "Games" in tema
        
        for url in urls:
            try:
                feed = feedparser.parse(url)
                for entry in feed.entries[:max_por_tema * 3]:
                    titulo = entry.get("title", "").strip()
                    link = entry.get("link", "").strip()
                    resumo_bruto = entry.get("summary") or entry.get("description") or ""
                    resumo_limpo = limpar_html_rss(resumo_bruto)
                    
                    if not titulo or not link:
                        continue
                        
                    # Filtro implacável contra promoções em games
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

def montar_prompt(noticias_coletadas):
    """Monta o prompt instruindo a IA a focar apenas em notícias quentes e mini-resumos."""
    prompt_dados = ""
    for tema, itens in noticias_coletadas.items():
        prompt_dados += f"\n### {tema}\n"
        for i, item in enumerate(itens, 1):
            prompt_dados += f"{i}. Título: {item['titulo']}\n   Link: {item['link']}\n"
            if item["contexto"]:
                prompt_dados += f"   Contexto: {item['contexto']}\n"
            
    prompt = f"""Você é o editor-chefe de um boletim diário de tecnologia, games, cultura e política no Telegram.
Abaixo estão as notícias do dia coletadas de fontes especializadas:

{prompt_dados}

REGRAS DE SELEÇÃO:
1. QUANTIDADE: Selecione exatamente as 2 ou 3 notícias mais IMPACTANTES de cada tema.
2. REGRA DE OURO PARA GAMES: PROIBIÇÃO TOTAL de ofertas, descontos, preços de jogos, cupons ou jogos gratuitos para resgate. Queremos APENAS:
   - Vazamentos de builds ou detalhes confidenciais (leaks).
   - Anúncios oficiais de novos jogos e consoles.
   - Demissões, cancelamentos e bastidores de estúdios.
   - Trailers épicos e datas de lançamento aguardadas.
3. IDIOMA: Todo o conteúdo final DEVE estar em Português do Brasil (mesmo que a notícia original venha de fonte internacional como Insider Gaming ou VGC, traduza o título e o resumo perfeitamente).
4. ESTRUTURA VISUAL DE CADA NOTÍCIA:
   🔹 <b><a href="LINK_ORIGINAL">Título Impactante e Traduzido</a></b>
   <i>Mini-resumo de 2 a 3 frases explicando exatamente o que aconteceu, os detalhes revelados e o impacto. Seja informativo e contextualize a história.</i>

5. FORMATAÇÃO TELEGRAM (HTML):
   - Categorias em <b>negrito</b> com emojis.
   - Links com <a href="URL">Texto</a>.
   - Mini-resumos em <i>itálico</i>.
6. Abertura: "☀️ <b>Boletim Diário: As Notícias Mais Quentes</b>"

Responda APENAS com a mensagem pronta para envio, sem tags ```html."""
    return prompt

def limpar_resposta_html(texto):
    texto = texto.strip()
    if texto.startswith("```html"):
        texto = texto[7:]
    elif texto.startswith("```"):
        texto = texto[3:]
    if texto.endswith("```"):
        texto = texto[:-3]
    return texto.strip()

def curar_com_gemini(noticias_coletadas, api_key):
    """Tenta chamar a API do Gemini com os modelos disponíveis."""
    prompt = montar_prompt(noticias_coletadas)
    modelos = [
        "gemini-3.8-flash",
        "gemini-3.5-flash",
        "gemini-3.0-flash",
        "gemini-2.5-flash",
        "gemini-2.0-flash",
        "gemini-1.5-flash"
    ]
    ultimo_erro = None
    
    for modelo in modelos:
        try:
            print(f"Tentando modelo Gemini: {modelo}...")
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{modelo}:generateContent?key={api_key.strip()}"
            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "temperature": 0.35,
                    "maxOutputTokens": 3000
                }
            }
            resp = requests.post(url, json=payload, timeout=40)
            if resp.status_code == 200:
                dados = resp.json()
                texto = dados["candidates"][0]["content"]["parts"][0]["text"]
                print(f"[Sucesso] Resumo gerado via {modelo}!")
                return limpar_resposta_html(texto)
            else:
                ultimo_erro = f"{modelo} retornou {resp.status_code}: {resp.text}"
                print(f"[Aviso] {ultimo_erro}")
        except Exception as e:
            ultimo_erro = str(e)
            print(f"[Aviso] Erro com {modelo}: {e}")
            
    raise Exception(f"Falha em todos os modelos: {ultimo_erro}")

def enviar_telegram(mensagem_html, bot_token, chat_id):
    """Envia a mensagem via API do Telegram com suporte a HTML."""
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    limite = 3900
    partes = []
    
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
            print(f"[Aviso HTML falhou] Enviando como texto plano: {resp.text}")
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
        
    print(f"Status chaves: GEMINI={'OK' if gemini_key else 'NÃO ENCONTRADA'}, ANTHROPIC={'OK' if anthropic_key else 'NÃO ENCONTRADA'}")
    
    print("1/3 Coletando feeds RSS com filtro estrito contra ofertas...")
    noticias = coletar_noticias()
    
    print("2/3 Processando curadoria e mini-resumos com IA...")
    mensagem = None
    erro_detalhe = ""
    
    if gemini_key and gemini_key.strip():
        try:
            mensagem = curar_com_gemini(noticias, gemini_key)
        except Exception as e:
            erro_detalhe = f"Erro Gemini: {e}"
            print(f"[Falha] {erro_detalhe}")
            
    if not mensagem and anthropic_key and anthropic_key.strip():
        try:
            from anthropic import Anthropic
            client = Anthropic(api_key=anthropic_key.strip())
            prompt = montar_prompt(noticias)
            response = client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=3000,
                temperature=0.35,
                messages=[{"role": "user", "content": prompt}]
            )
            mensagem = limpar_resposta_html(response.content[0].text)
        except Exception as e:
            erro_detalhe += f" | Erro Claude: {e}"
            print(f"[Falha Claude] {e}")
            
    if not mensagem:
        motivo = erro_detalhe if erro_detalhe else "Chave GEMINI_API_KEY ausente no GitHub Secrets"
        print(f"[Aviso Fallback] Motivo: {motivo}")
        linhas = [
            "☀️ <b>Boletim Diário: Destaques de Hoje</b>",
            f"⚠️ <i>Nota: IA indisponível ({html.escape(motivo[:100])})</i>\n"
        ]
        for tema, itens in noticias.items():
            linhas.append(f"\n<b>{tema}</b>")
            for item in itens[:3]:
                titulo = html.escape(item['titulo'])
                contexto = html.escape(item['contexto']) if item['contexto'] else "Notícia em destaque."
                linhas.append(f"🔹 <a href=\"{item['link']}\"><b>{titulo}</b></a>\n   <i>{contexto}</i>")
        mensagem = "\n".join(linhas)
        
    print("3/3 Enviando para o Telegram...")
    enviar_telegram(mensagem, telegram_token, telegram_chat_id)
    print("Finalizado com sucesso!")

if __name__ == "__main__":
    main()
