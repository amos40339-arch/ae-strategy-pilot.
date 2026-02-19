import os
import threading
import logging
from flask import Flask
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from groq import Groq

# --- 1. SETUP ---
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
user_conversations = {}
MAX_HISTORY = 10

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
client = Groq(api_key=GROQ_API_KEY)

@app.route('/')
def health_check():
    return "AE Strategy Pilot: Online", 200

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

# --- 2. THE BRAIN ---
async def get_ai_response(user_id, text):
    if user_id not in user_conversations:
        user_conversations[user_id] = [{"role": "system", "content": "You are a ruthless business mentor. Be blunt and practical."}]
    
    user_conversations[user_id].append({"role": "user", "content": text})
    
    chat_completion = client.chat.completions.create(
        messages=user_conversations[user_id],
        model="llama-3.3-70b-versatile",
    )
    
    response = chat_completion.choices[0].message.content
    user_conversations[user_id].append({"role": "assistant", "content": response})
    
    if len(user_conversations[user_id]) > MAX_HISTORY:
        user_conversations[user_id] = [user_conversations[user_id][0]] + user_conversations[user_id][-(MAX_HISTORY-1):]
    
    return response

# --- 3. HANDLERS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Pilot Active. Send text or voice.")

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    response = await get_ai_response(update.effective_user.id, update.message.text)
    await update.message.reply_text(response)

async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    status_msg = await update.message.reply_text("🎤 Thinking...")
    
    file_path = "user_voice.ogg"
    try:
        voice_file = await context.bot.get_file(update.message.voice.file_id)
        await voice_file.download_to_drive(file_path)
        
        with open(file_path, "rb") as file:
            transcription = client.audio.transcriptions.create(
                file=(file_path, file.read()),
                model="whisper-large-v3",
            )
        
        user_text = transcription.text
        response = await get_ai_response(update.effective_user.id, user_text)
        await status_msg.edit_text(f"📝 *You said:* {user_text}\n\n🔥 *Strategy:* {response}", parse_mode="Markdown")
        
    except Exception as e:
        logger.error(f"Voice Error: {e}")
        await status_msg.edit_text("Couldn't process audio. Try text.")
    finally:
        if os.path.exists(file_path):
            os.remove(file_path)

# --- 4. EXECUTION ---
def main():
    threading.Thread(target=run_flask, daemon=True).start()
    
    TOKEN = os.environ.get("TELEGRAM_TOKEN")
    application = Application.builder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    # FIXED LINE: Wrapped filters.VOICE inside MessageHandler
    application.add_handler(MessageHandler(filters.VOICE, handle_voice))

    logger.info("🚀 Pilot Live.")
    application.run_polling()

if __name__ == "__main__":
    main()
