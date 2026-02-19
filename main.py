import os
import threading
import logging
from flask import Flask
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from groq import Groq

# --- 1. LOGGING SETUP ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', 
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- 2. FLASK SERVER (The Heartbeat) ---
app = Flask(__name__)

@app.route('/')
def health_check():
    # This keeps Render and UptimeRobot happy
    return "AE Strategy Pilot: Online and Ruthless", 200

def run_flask():
    # Render provides the PORT variable automatically
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

# --- 3. BOT LOGIC (The Brain) ---
# Initialize Groq Client
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
client = Groq(api_key=GROQ_API_KEY)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_name = update.effective_user.first_name
    await update.message.reply_text(
        f"Welcome, {user_name}. I am the AE Strategy Pilot.\n\n"
        "I don't do 'motivation.' I do execution. Send me your business problem, "
        "and I'll tell you why you're failing and how to fix it."
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    
    try:
        # Groq AI Logic
        chat_completion = client.chat.completions.create(
            messages=[
                {"role": "system", "content": "You are a ruthless business mentor. Be blunt, honest, and practical. No fluff."},
                {"role": "user", "content": user_text}
            ],
            model="llama3-8b-8192", # Or your preferred model
        )
        response = chat_completion.choices[0].message.content
        await update.message.reply_text(response)
        
    except Exception as e:
        logger.error(f"Error: {e}")
        await update.message.reply_text("My brain hit a snag. Probably a rate limit. Try again in a minute.")

# --- 4. EXECUTION ---
def main():
    # A. Start Flask in background FIRST (daemon=True so it stops when the bot stops)
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    logger.info("✅ Flask heartbeat server started.")

    # B. Setup Telegram Bot
    TOKEN = os.environ.get("TELEGRAM_TOKEN")
    if not TOKEN:
        logger.error("❌ No TELEGRAM_TOKEN found in Environment Variables!")
        return

    application = Application.builder().token(TOKEN).build()

    # C. Handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # D. Start the Bot
    logger.info("🚀 AE Strategy Pilot is now polling...")
    application.run_polling()

if __name__ == "__main__":
    main()
