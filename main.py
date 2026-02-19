import os
import threading
import logging
import time
from flask import Flask
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from groq import Groq

# --- 1. INITIAL SETUP ---
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

# --- 2. FLASK HEARTBEAT (For Render) ---
@app.route('/')
def health_check():
    return "AE Strategy Pilot: Online & Client-Ready", 200

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

# --- 3. THE BRAIN (AI Logic) ---
async def get_ai_response(user_id, text):
    if user_id not in user_conversations:
        # The System Prompt defines the "Ruthless" persona
        user_conversations[user_id] = [
            {"role": "system", "content": "You are a ruthless business mentor. Be blunt, honest, and practical. No fluff. Focus on execution."}
        ]
    
    user_conversations[user_id].append({"role": "user", "content": text})
    
    chat_completion = client.chat.completions.create(
        messages=user_conversations[user_id],
        model="llama-3.3-70b-versatile",
    )
    
    response = chat_completion.choices[0].message.content
    user_conversations[user_id].append({"role": "assistant", "content": response})
    
    # Trim history to keep context sharp
    if len(user_conversations[user_id]) > MAX_HISTORY:
        user_conversations[user_id] = [user_conversations[user_id][0]] + user_conversations[user_id][-(MAX_HISTORY-1):]
    
    return response

# --- 4. HANDLERS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Strategy Pilot Active. Send a text or voice note of your business problem.")

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    response = await get_ai_response(update.effective_user.id, update.message.text)
    await update.message.reply_text(response)

async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    status_msg = await update.message.reply_text("🎤 Hearing you...")
    
    # Unique filename using user ID and timestamp to prevent crashes
    file_path = f"voice_{user_id}_{int(time.time())}.ogg"
    
    try:
        # Get file with 30-second timeout for slow connections
        voice_file = await context.bot.get_file(update.message.voice.file_id, read_timeout=30)
        await voice_file.download_to_drive(file_path)
        
        # Transcribe with Whisper-3
        with open(file_path, "rb") as file:
            transcription = client.audio.transcriptions.create(
                file=(file_path, file.read()),
                model="whisper-large-v3",
            )
        
        user_text = transcription.text
        
        # SHOW TRANSCRIPT IMMEDIATELY (Client trust builder)
        await status_msg.edit_text(f"📝 *You said:* \"{user_text}\"\n\n_Analyzing strategy..._")
        
        # Analyze and send final strategy
        response = await get_ai_response(user_id, user_text)
        await update.message.reply_text(f"🚀 *Strategy:* \n\n{response}", parse_mode="Markdown")
        
    except Exception as e:
        logger.error(f"DETAILED VOICE ERROR: {str(e)}")
        await status_msg.edit_text("❌ Error processing audio. Please try a shorter clip or text.")
    finally:
        # Always clean up the file
        if os.path.exists(file_path):
            os.remove(file_path)

# --- 5. EXECUTION ---
def main():
    # Start Heartbeat
    threading.Thread(target=run_flask, daemon=True).start()
    
    TOKEN = os.environ.get("TELEGRAM_TOKEN")
    application = Application.builder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    application.add_handler(MessageHandler(filters.VOICE, handle_voice))

    logger.info("🚀 System Live: Client-Ready Mode.")
    application.run_polling()

if __name__ == "__main__":
    main()
