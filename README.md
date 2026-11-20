# 🤖 Bot de Notícias Diárias (Telegram + Google Gemini + GitHub Actions)

Seu jornal diário personalizado no Telegram! Este projeto coleta automaticamente as notícias mais quentes dos seus temas favoritos (**Games, Animes, Política, Programação e Tecnologia**), envia para a IA (Google Gemini 100% gratuito) fazer a curadoria dos destaques mais importantes e despacha o resumo formatado no seu Telegram.

Tudo roda **100% de graça na nuvem** através do GitHub Actions nos horários agendados (08h00 e 18h00) ou sob demanda.

---

## 🚀 Como Ativar Tudo Gratuitamente (Sem Cartão de Crédito)

### 1. Criar o Bot no Telegram (1 minuto)
1. No Telegram, procure por **`@BotFather`** e inicie a conversa.
2. Envie o comando: `/newbot`.
3. Escolha um nome (ex: `Meu Jornal Diário`) e um usuário que termine em `bot` (ex: `meu_jornal_pessoal_bot`).
4. O BotFather vai te dar um **Token de Acesso** (algo como `7123456789:AAH...`). Guarde esse valor.

### 2. Pegar o seu Chat ID no Telegram (30 segundos)
1. Procure no Telegram pelo bot **`@userinfobot`** e clique em **Começar**.
2. Ele vai te responder com o seu `Id` numérico (ex: `123456789`). Guarde esse número.
3. **Importante:** Abra a conversa com o seu próprio bot recém-criado e clique em **Começar / Start** para autorizar o envio de mensagens.

### 3. Pegar a Chave Gratuita do Gemini (Google AI Studio)
1. Acesse: [Google AI Studio](https://aistudio.google.com/).
2. Faça login com sua conta Google comum.
3. Clique no botão azul **Get API key** (ou no menu lateral em **Get API key**).
4. Clique em **Create API key** e copie o código gerado (`AIzaSy...`).
   * *Totalmente gratuito, sem necessidade de cartão de crédito.*

---

## ⚙️ Configurar no GitHub

1. Crie um novo repositório (pode ser **Privado**) no seu GitHub.
2. Suba todos os arquivos desta pasta para lá:
   ```bash
   git init
   git add .
   git commit -m "feat: bot de noticias telegram com gemini"
   git branch -M main
   git remote add origin https://github.com/SEU_USUARIO/SEU_REPOSITORIO.git
   git push -u origin main
   ```
3. No seu repositório no GitHub, vá em:
   * **Settings** > **Secrets and variables** > **Actions** > botão **New repository secret**.
4. Adicione os 3 segredos:
   * `TELEGRAM_BOT_TOKEN`: o token que o `@BotFather` te deu.
   * `TELEGRAM_CHAT_ID`: o seu ID numérico do `@userinfobot`.
   * `GEMINI_API_KEY`: sua chave gratuita gerada no Google AI Studio.

---

## 🧪 Como Testar Imediatamente
1. No seu repositório do GitHub, clique na aba **Actions**.
2. Clique no workflow **"Envio Diário de Notícias Telegram"** na esquerda.
3. Clique no botão **Run workflow** > **Run workflow**.
4. Em menos de 30 segundos, o resumo completo chegará no seu Telegram!
