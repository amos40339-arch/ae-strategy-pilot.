import os
import threading
import requests
import logging
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from groq import Groq

# --- 1. FLASK WEB SERVER (THE "ALIVE" SIGNAL) ---
server = Flask(__name__)

@server.route('/')
def health_check():
    return "AE Intelligence is Online", 200

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    server.run(host='0.0.0.0', port=port)

# --- 2. CONFIGURATION & AI CLIENT ---
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
NEWS_URL = "https://free-crypto-news.vercel.app/api/news?limit=3"

client = Groq(api_key=GROQ_API_KEY)
logging.basicConfig(level=logging.INFO)

SYSTEM_PROMPT = (
    "You are the Lead Crypto Market Analyst for AE Intelligence. "
    "Role: Provide blunt, cynical, data-driven audits. "
    "Focus: 1. Investor Concerns, 2. Technical Gaps, 3. Sentiment Score (0-100%)."
)

# --- 3. BOT LOGIC ---

async def ai_audit(text: str):
    try:
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": text}],
            temperature=0.1
        )
        return completion.choices[0].message.content
    except:
        return "⚠️ Rate limit reached. Try again in 60s."

async def transcribe_audio(file_path: str):
    try:
        with open(file_path, "rb") as file:
            return client.audio.transcriptions.create(file=(file_path, file.read()), model="whisper-large-v3-turbo", response_format="text")
    except Exception as e:
        return f"❌ Audio Error: {str(e)}"

# --- 4. HANDLERS ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⚡ **AE INTELLIGENCE v2.0** ⚡\nSend an AMA Audio or Text for Audit.")

async def handle_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("📡 Processing...")
    media = update.message.voice or update.message.audio or update.message.document
    
    file = await media.get_file()
    file_path = f"temp_{media.file_id}"
    await file.download_to_drive(file_path)

    if update.message.voice or update.message.audio:
        content = await transcribe_audio(file_path)
    else:
        with open(file_path, 'r') as f: content = f.read()

    analysis = await ai_audit(content)
    await update.message.reply_text(f"📝 **AUDIT REPORT:**\n\n{analysis}")
    os.remove(file_path)

# --- 5. DEPLOYMENT START ---
if __name__ == '__main__':
    # Start Flask in background to keep server awake
    threading.Thread(target=run_flask, daemon=True).start()

    # Run Telegram Bot
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), lambda u, c: ai_audit(u.message.text)))
    app.add_handler(MessageHandler(filters.VOICE | filters.AUDIO | filters.Document.TEXT, handle_media))
    
    print("AE Intelligence Engine LIVE.")
    app.run_polling()
