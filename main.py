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
        "https://www.videogameschronicle.com/feed/", # VGC: Notícias e exclusivas
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
    return " ".join(texto_puro.split())[:400]

def eh_oferta_de_jogo(texto):
    texto_lower = texto.lower()
    return any(termo in texto_lower for termo in TERMOS_BANIDOS_GAMES)

def coletar_noticias(max_por_tema=12):
    """Coleta um volume amplo de notícias para permitir curadoria rica sem limite rígido."""
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
        
        # Elimina duplicados
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
    """Monta o prompt para seleção livre de todas as notícias impactantes."""
    prompt_dados = ""
    for tema, itens in noticias_coletadas.items():
        prompt_dados += f"\n### {tema}\n"
        for i, item in enumerate(itens, 1):
            prompt_dados += f"{i}. Título: {item['titulo']}\n   Link: {item['link']}\n"
            if item["contexto"]:
                prompt_dados += f"   Contexto: {item['contexto']}\n"
            
    prompt = f"""Você é o editor-chefe de um serviço diário de notícias no Telegram.
Abaixo está o compilado do que está acontecendo hoje em diversas áreas:

{prompt_dados}

DIRETRIZES FUNDAMENTAIS:
1. SEM LIMITE FIXO DE NOTÍCIAS: Traga TODAS as notícias que forem genuinamente importantes, quentes, bombásticas e de impacto hoje. Não se limite a 2 ou 3; se houver 4, 5 ou mais acontecimentos de peso, traga todos. Apenas descarte matérias fracas, irrelevantes ou 'encher linguiça'.
2. REGRA DE GAMES: Proibido qualquer tipo de oferta, desconto, lista de jogos grátis ou cupom. Queremos apenas fatos da indústria: vazamentos (leaks), anúncios oficiais, novidades de gameplay, datas de lançamento e polêmicas de estúdios.
3. IDIOMA: Todo o boletim deve estar em Português do Brasil de alto padrão (traduza títulos e resumos de matérias internacionais).
4. RESUMOS COMPLETOS: Cada notícia deve conter um mini-resumo de 2 a 3 frases completas explicando com clareza o que aconteceu. Não corte frases.
5. FORMATO DE SEPARAÇÃO POR MENSAGEM:
   Para que cada tema seja enviado em uma mensagem separada no Telegram, use a linha especial "===CATEGORIA===" antes de cada categoria.

EXEMPLO DE ESTRUTURA EXIGIDA:

===CATEGORIA===
<b>🎮 Games</b>

🔹 <b><a href="URL">Título da Notícia</a></b>
<i>Mini-resumo explicativo completo de 2 a 3 frases sobre o acontecimento.</i>

🔹 <b><a href="URL">Segundo Título da Notícia</a></b>
<i>Mini-resumo explicativo completo...</i>

===CATEGORIA===
<b>⛩️ Animes & Mangás</b>

🔹 <b><a href="URL">Título...</a></b>
<i>Mini-resumo...</i>

Responda APENAS com o texto formatado dessa forma, sem tags ```html no início ou fim."""
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
    """Chama a API do Gemini com 8192 tokens para processar o volume completo."""
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
                    "temperature": 0.3,
                    "maxOutputTokens": 8192
                }
            }
            resp = requests.post(url, json=payload, timeout=60)
            if resp.status_code == 200:
                dados = resp.json()
                texto = dados["candidates"][0]["content"]["parts"][0]["text"]
                print(f"[Sucesso] Curadoria completa gerada via {modelo}!")
                return limpar_resposta_html(texto)
            else:
                ultimo_erro = f"{modelo} retornou {resp.status_code}: {resp.text}"
                print(f"[Aviso] {ultimo_erro}")
        except Exception as e:
            ultimo_erro = str(e)
            print(f"[Aviso] Erro com {modelo}: {e}")
            
    raise Exception(f"Falha em todos os modelos: {ultimo_erro}")

def enviar_telegram(mensagem_formatada, bot_token, chat_id):
    """Envia cada categoria em uma mensagem dedicada no Telegram para evitar cortes e poluição visual."""
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    
    # Divide pelas seções marcadas
    if "===CATEGORIA===" in mensagem_formatada:
        partes_brutas = mensagem_formatada.split("===CATEGORIA===")
    else:
        partes_brutas = [mensagem_formatada]
        
    mensagens_para_enviar = [p.strip() for p in partes_brutas if p.strip()]
    
    # Se houver cabeçalho inicial antes da primeira categoria, mantém
    print(f"Enviando {len(mensagens_para_enviar)} mensagens temáticas para o Telegram...")
    
    for idx, msg in enumerate(mensagens_para_enviar, 1):
        # Garante que cada mensagem respeite o limite do Telegram (3900 caracteres)
        subpartes = []
        if len(msg) > 3900:
            linhas = msg.split("\n")
            atual = ""
            for l in linhas:
                if len(atual) + len(l) + 1 < 3800:
                    atual += l + "\n"
                else:
                    subpartes.append(atual.strip())
                    atual = l + "\n"
            if atual:
                subpartes.append(atual.strip())
        else:
            subpartes = [msg]
            
        for sub in subpartes:
            payload = {
                "chat_id": chat_id,
                "text": sub,
                "parse_mode": "HTML",
                "disable_web_page_preview": True
            }
            resp = requests.post(url, json=payload, timeout=30)
            if resp.status_code != 200:
                print(f"[Aviso HTML falhou] Enviando sem formatação: {resp.text}")
                payload["parse_mode"] = ""
                requests.post(url, json=payload, timeout=30)
            else:
                print(f"[Sucesso] Mensagem {idx}/{len(mensagens_para_enviar)} entregue!")
            # Pequeno intervalo para garantir a ordem cronológica correta no app do Telegram
            time.sleep(0.8)

def main():
    print("Iniciando rotina de notícias...")
    
    telegram_token = os.getenv("TELEGRAM_BOT_TOKEN")
    telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID")
    gemini_key = os.getenv("GEMINI_API_KEY")
    anthropic_key = os.getenv("ANTHROPIC_API_KEY")
    
    if not telegram_token or not telegram_chat_id:
        print("Erro: TELEGRAM_BOT_TOKEN e TELEGRAM_CHAT_ID são obrigatórios.")
        sys.exit(1)
        
    print("1/3 Coletando feeds RSS ampliados...")
    noticias = coletar_noticias()
    
    print("2/3 Processando curadoria sem limite rígido com IA...")
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
                max_tokens=6000,
                temperature=0.3,
                messages=[{"role": "user", "content": prompt}]
            )
            mensagem = limpar_resposta_html(response.content[0].text)
        except Exception as e:
            erro_detalhe += f" | Erro Claude: {e}"
            print(f"[Falha Claude] {e}")
            
    if not mensagem:
        motivo = erro_detalhe if erro_detalhe else "Chave GEMINI_API_KEY ausente no GitHub Secrets"
        print(f"[Aviso Fallback] Motivo: {motivo}")
        blocos = []
        for tema, itens in noticias.items():
            bloco_linhas = [f"<b>{tema}</b>"]
            for item in itens[:4]:
                titulo = html.escape(item['titulo'])
                contexto = html.escape(item['contexto']) if item['contexto'] else "Destaque do dia."
                bloco_linhas.append(f"🔹 <a href=\"{item['link']}\"><b>{titulo}</b></a>\n   <i>{contexto}</i>")
            blocos.append("\n".join(bloco_linhas))
        mensagem = "\n===CATEGORIA===\n".join(blocos)
        
    print("3/3 Enviando mensagens por categoria para o Telegram...")
    enviar_telegram(mensagem, telegram_token, telegram_chat_id)
    print("Envio completo e finalizado com sucesso!")

if __name__ == "__main__":
    main()
