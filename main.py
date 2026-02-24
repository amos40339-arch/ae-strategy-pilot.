import os
import logging
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from groq import Groq

# --- CONFIGURATION (PUT YOUR KEYS HERE) ---
TELEGRAM_TOKEN = "YOUR_TELEGRAM_BOT_TOKEN"
GROQ_API_KEY = "YOUR_GROQ_API_KEY"

# Free Crypto News API (No Key Needed)
NEWS_URL = "https://free-crypto-news.vercel.app/api/news?limit=3"

# Initialize Groq Client
client = Groq(api_key=GROQ_API_KEY)

# Logging Setup
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

SYSTEM_PROMPT = (
    "You are the Lead Crypto Market Analyst for AE Intelligence. "
    "Role: Provide blunt, data-driven audits. "
    "Constraint: If information is not in the text/audio, say 'DATA NOT FOUND.' "
    "Tone: Professional, cynical, alert to scams (Rug pulls, Dev dumping). "
    "Analyze for: 1. Investor Concerns, 2. Technical Gaps, 3. Sentiment Score (0-100%)."
)

# --- AI LOGIC ---

async def ai_audit(text: str):
    """Llama 3 Audit via Groq (Free Tier Optimized)"""
    try:
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"AUDIT THIS: {text}"}
            ],
            temperature=0.1
        )
        return completion.choices[0].message.content
    except Exception as e:
        return "⚠️ Rate limit reached. Wait 60 seconds."

async def transcribe_audio(file_path: str):
    """Whisper Transcription via Groq"""
    try:
        with open(file_path, "rb") as file:
            transcription = client.audio.transcriptions.create(
                file=(file_path, file.read()),
                model="whisper-large-v3-turbo",
                response_format="text",
            )
        return transcription
    except Exception as e:
        return f"❌ Transcription Failed: {str(e)}"

# --- TELEGRAM COMMANDS ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """The Professional Menu"""
    keyboard = [
        [InlineKeyboardButton("📰 Latest Market News", callback_query_data='news')],
        [InlineKeyboardButton("🛡️ How to Audit", callback_query_data='help')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "⚡ **AE INTELLIGENCE v2.0 (GROQ ENGINE)** ⚡\n\n"
        "Forward an **AMA Voice Note**, **Text File**, or **Chat Log** here.\n"
        "I will audit it for scams and sentiment immediately.",
        reply_markup=reply_markup, parse_mode='Markdown'
    )

async def news_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Market Pulse with AI Impact Analysis"""
    try:
        res = requests.get(NEWS_URL).json()
        report = "📰 **MARKET PULSE (AI IMPACT ANALYSIS)**\n\n"
        
        for art in res:
            title = art['title']
            # AI interprets the news impact
            impact = client.chat.completions.create(
                model="llama3-8b-8192", # Using smaller model for speed
                messages=[{"role": "user", "content": f"Explain crypto impact of this in 2 sentences: {title}"}],
                temperature=0.1
            ).choices[0].message.content
            report += f"🔹 **{title}**\n💡 {impact}\n\n"
        
        await update.message.reply_text(report, parse_mode='Markdown')
    except:
        await update.message.reply_text("❌ News feed currently down.")

async def handle_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles Text Files, Audio, and Voice Notes"""
    # 1. Check if it's Audio or Voice
    media = update.message.voice or update.message.audio or update.message.document
    if not media: return

    status_msg = await update.message.reply_text("📡 **AE Intelligence Processing...**")
    
    file = await media.get_file()
    file_path = f"temp_{media.file_id}"
    await file.download_to_drive(file_path)

    # 2. Transcribe if Audio
    if update.message.voice or update.message.audio:
        content = await transcribe_audio(file_path)
    else: # If it's a .txt file
        with open(file_path, 'r') as f: content = f.read()

    # 3. Audit the Content
    await status_msg.edit_text("🔍 **Analyzing for Red Flags...**")
    analysis = await ai_audit(content)
    
    await update.message.reply_text(f"📝 **STRATEGIC AUDIT REPORT:**\n\n{analysis}")
    os.remove(file_path)

# --- INITIALIZATION ---
if __name__ == '__main__':
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("news", news_command))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), lambda u, c: handle_media(u, c)))
    app.add_handler(MessageHandler(filters.VOICE | filters.AUDIO | filters.Document.TEXT, handle_media))
    
    print("AE Intelligence is ONLINE.")
    app.run_polling()
