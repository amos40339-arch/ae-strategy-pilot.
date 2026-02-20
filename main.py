import os
import threading
import logging
import time
from flask import Flask
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from groq import Groq

# --- 1. SETUP ---
logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
user_conversations = {}

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
client = Groq(api_key=GROQ_API_KEY)

# --- 2. HEARTBEAT ---
@app.route('/')
def health_check():
    return "AE Pilot: Online", 200

def run_flask():
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))

# --- 3. BRAIN ---
async def get_ai_response(user_id, text):
    if user_id not in user_conversations:
        user_conversations[user_id] = [{"role": "system", "content": "You are a ruthless business mentor. Be blunt and practical. Use plain text only."}]
    
    user_conversations[user_id].append({"role": "user", "content": text})
    
    chat_completion = client.chat.completions.create(
        messages=user_conversations[user_id],
        model="llama-3.3-70b-versatile",
    )
    
    response = chat_completion.choices[0].message.content
    user_conversations[user_id].append({"role": "assistant", "content": response})
    return response

# --- 4. HANDLERS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Pilot Active. Send text or short voice notes (5s).")

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    response = await get_ai_response(update.effective_user.id, update.message.text)
    await update.message.reply_text(response)

async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    status_msg = await update.message.reply_text("Processing voice command...")
    file_path = f"v_{user_id}_{int(time.time())}.ogg"
    
    try:
        voice_file = await context.bot.get_file(update.message.voice.file_id)
        await voice_file.download_to_drive(file_path)
        
        with open(file_path, "rb") as file:
            transcription = client.audio.transcriptions.create(
                file=(file_path, file.read()),
                model="whisper-large-v3",
            )
        
        user_text = transcription.text
        await status_msg.edit_text(f"Analyzed: {user_text}")
        
        response = await get_ai_response(user_id, user_text)
        await update.message.reply_text(response)
        
    except Exception as e:
        logger.error(f"Error: {e}")
        await status_msg.edit_text("Clip too long for Free Tier. Keep it under 6 seconds.")
    finally:
        if os.path.exists(file_path):
            os.remove(file_path)

def main():
    threading.Thread(target=run_flask, daemon=True).start()
    TOKEN = os.environ.get("TELEGRAM_TOKEN")
    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    application.add_handler(MessageHandler(filters.VOICE, handle_voice))
    application.run_polling()

if __name__ == "__main__":
    main()
