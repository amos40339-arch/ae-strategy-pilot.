import os
import threading
import logging
import time
from flask import Flask
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from groq import Groq

# --- 1. SETUP & LOGGING ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', 
    level=logging.INFO
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
user_conversations = {}
MAX_HISTORY = 10

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
client = Groq(api_key=GROQ_API_KEY)

# --- 2. FLASK HEARTBEAT ---
@app.route('/')
def health_check():
    return "AE Strategy Pilot: Online & Heavy-Duty Mode", 200

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

# --- 3. THE BRAIN (AI Logic) ---
async def get_ai_response(user_id, text):
    if user_id not in user_conversations:
        user_conversations[user_id] = [
            {"role": "system", "content": "You are a ruthless business mentor and crypto AMA auditor. Be blunt, strategic, and practical. Focus on ROI and execution logic."}
        ]
    
    user_conversations[user_id].append({"role": "user", "content": text})
    
    chat_completion = client.chat.completions.create(
        messages=user_conversations[user_id],
        model="llama-3.3-70b-versatile",
    )
    
    response = chat_completion.choices[0].message.content
    user_conversations[user_id].append({"role": "assistant", "content": response})
    
    if len(user_conversations[user_id]) > MAX_HISTORY:
        user_conversations[user_id] = [user_conversations[user_id][0]] + user_conversations[user_id][-(MAX_HISTORY-1):]
    
    # We return the response and will wrap it in HTML tags in the handler
    return response

# --- 4. HANDLERS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("<b>Pilot Active.</b> Ready for text or heavy voice audits.", parse_mode=ParseMode.HTML)

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    response = await get_ai_response(update.effective_user.id, update.message.text)
    # BOLDING: We wrap the whole response in <b> tags
    await update.message.reply_text(f"<b>{response}</b>", parse_mode=ParseMode.HTML)

async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    status_msg = await update.message.reply_text("📥 <b>Receiving long-form audio...</b>", parse_mode=ParseMode.HTML)
    
    file_path = f"voice_{user_id}_{int(time.time())}.ogg"
    
    try:
        # HEAVY-DUTY TIMEOUTS for long audio
        voice_file = await context.bot.get_file(
            update.message.voice.file_id, 
            read_timeout=120, 
            write_timeout=120
        )
        await voice_file.download_to_drive(file_path)
        
        await status_msg.edit_text("⚙️ <b>Transcribing segment...</b>", parse_mode=ParseMode.HTML)

        with open(file_path, "rb") as file:
            transcription = client.audio.transcriptions.create(
                file=(file_path, file.read()),
                model="whisper-large-v3",
            )
        
        user_text = transcription.text
        await status_msg.edit_text(f"📝 <b>Segment Captured.</b> Analyzing strategy...", parse_mode=ParseMode.HTML)
        
        # ANALYSIS
        response = await get_ai_response(user_id, user_text)
        # BOLDING the output here too
        await update.message.reply_text(f"🚀 <b>STRATEGY AUDIT:</b>\n\n<b>{response}</b>", parse_mode=ParseMode.HTML)
        
    except Exception as e:
        logger.error(f"HEAVY VOICE ERROR: {str(e)}")
        await status_msg.edit_text("❌ <b>Error:</b> File too large or connection timed out.")
    finally:
        if os.path.exists(file_path):
            os.remove(file_path)

# --- 5. EXECUTION ---
def main():
    threading.Thread(target=run_flask, daemon=True).start()
    
    TOKEN = os.environ.get("TELEGRAM_TOKEN")
    # Setting global defaults for the application
    application = Application.builder().token(TOKEN).read_timeout(60).write_timeout(60).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    application.add_handler(MessageHandler(filters.VOICE, handle_voice))

    logger.info("🚀 System Live: HTML Bolding & Audio Extension Active.")
    application.run_polling()

if __name__ == "__main__":
    main()
