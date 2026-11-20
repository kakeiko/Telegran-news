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
    "🎮 Games": [
        "https://insider-gaming.com/feed/",          # Maior portal mundial de vazamentos e bastidores
        "https://www.videogameschronicle.com/feed/", # VGC: Notícias oficiais e exclusivas de estúdios
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

def coletar_noticias(max_por_tema=6):
    """Coleta manchetes e descrições dos feeds RSS com filtro estrito anti-ofertas."""
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
    """Monta o prompt com instruções claras de síntese completa."""
    prompt_dados = ""
    for tema, itens in noticias_coletadas.items():
        prompt_dados += f"\n### {tema}\n"
        for i, item in enumerate(itens, 1):
            prompt_dados += f"{i}. Título: {item['titulo']}\n   Link: {item['link']}\n"
            if item["contexto"]:
                prompt_dados += f"   Contexto: {item['contexto']}\n"
            
    prompt = f"""Você é o editor-chefe de um boletim diário no Telegram.
Abaixo estão as notícias do dia coletadas de fontes especializadas:

{prompt_dados}

REGRAS OBRIGATÓRIAS:
1. QUANTIDADE: Selecione exatamente 2 notícias mais IMPACTANTES de cada tema.
2. REGRA DE GAMES: Zero promoções/descontos. Apenas grandes novidades, vazamentos, anúncios ou polêmicas.
3. IDIOMA: Português do Brasil impecável em tudo (traduza títulos e resumos de fontes internacionais).
4. RESUMO COMPLETO: Cada notícia deve ter 2 frases completas e conclusivas explicando o fato. NUNCA corte a frase no meio.
5. FORMATAÇÃO:
   - Use o separador "---" entre cada categoria para facilitar a leitura.
   - Para cada notícia:
     🔹 <b><a href="LINK_ORIGINAL">Título Claro e Traduzido</a></b>
     <i>Mini-resumo objetivo de 2 frases explicando o acontecimento e o contexto.</i>
6. Inicie com: "☀️ <b>Boletim Diário: As Notícias Mais Quentes</b>\n"

Responda APENAS com a mensagem pronta em formato HTML para Telegram (sem crases ```html)."""
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
    """Chama a API do Gemini com capacidade expandida de tokens (8192)."""
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
            resp = requests.post(url, json=payload, timeout=50)
            if resp.status_code == 200:
                dados = resp.json()
                texto = dados["candidates"][0]["content"]["parts"][0]["text"]
                print(f"[Sucesso] Resumo gerado via {modelo} com sucesso!")
                return limpar_resposta_html(texto)
            else:
                ultimo_erro = f"{modelo} retornou {resp.status_code}: {resp.text}"
                print(f"[Aviso] {ultimo_erro}")
        except Exception as e:
            ultimo_erro = str(e)
            print(f"[Aviso] Erro com {modelo}: {e}")
            
    raise Exception(f"Falha em todos os modelos: {ultimo_erro}")

def enviar_telegram(mensagem_html, bot_token, chat_id):
    """Envia mensagens ao Telegram dividindo por blocos de seções para nunca quebrar tags."""
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    
    # Se couber em uma única mensagem (até 3800 caracteres), envia direto
    if len(mensagem_html) <= 3800:
        blocos = [mensagem_html]
    else:
        # Divide por categorias (separador '---' ou linha em branco dupla)
        secoes = mensagem_html.split("\n---")
        blocos = []
        bloco_atual = ""
        for sec in secoes:
            sec = sec.strip()
            if not sec:
                continue
            if len(bloco_atual) + len(sec) + 10 < 3800:
                bloco_atual += ("\n\n" if bloco_atual else "") + sec
            else:
                if bloco_atual:
                    blocos.append(bloco_atual)
                bloco_atual = sec
        if bloco_atual:
            blocos.append(bloco_atual)
            
    for i, bloco in enumerate(blocos, 1):
        if not bloco.strip():
            continue
        payload = {
            "chat_id": chat_id,
            "text": bloco,
            "parse_mode": "HTML",
            "disable_web_page_preview": True
        }
        resp = requests.post(url, json=payload, timeout=30)
        if resp.status_code != 200:
            print(f"[Aviso HTML bloco {i} falhou] Enviando como texto: {resp.text}")
            payload["parse_mode"] = ""
            requests.post(url, json=payload, timeout=30)
        else:
            print(f"[Sucesso] Bloco {i}/{len(blocos)} entregue no Telegram!")

def main():
    print("Iniciando rotina de notícias...")
    
    telegram_token = os.getenv("TELEGRAM_BOT_TOKEN")
    telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID")
    gemini_key = os.getenv("GEMINI_API_KEY")
    anthropic_key = os.getenv("ANTHROPIC_API_KEY")
    
    if not telegram_token or not telegram_chat_id:
        print("Erro: TELEGRAM_BOT_TOKEN e TELEGRAM_CHAT_ID são obrigatórios.")
        sys.exit(1)
        
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
                max_tokens=4000,
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
        linhas = [
            "☀️ <b>Boletim Diário: Destaques de Hoje</b>\n",
            f"⚠️ <i>Nota: IA indisponível ({html.escape(motivo[:100])})</i>\n"
        ]
        for tema, itens in noticias.items():
            linhas.append(f"\n<b>{tema}</b>")
            for item in itens[:2]:
                titulo = html.escape(item['titulo'])
                contexto = html.escape(item['contexto']) if item['contexto'] else "Notícia em destaque."
                linhas.append(f"🔹 <a href=\"{item['link']}\"><b>{titulo}</b></a>\n   <i>{contexto}</i>")
        mensagem = "\n".join(linhas)
        
    print("3/3 Enviando para o Telegram...")
    enviar_telegram(mensagem, telegram_token, telegram_chat_id)
    print("Finalizado com sucesso!")

if __name__ == "__main__":
    main()
