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

# --- 2. FLASK SERVER (The Heartbeat for Render) ---
app = Flask(__name__)

@app.route('/')
def health_check():
    return "AE Strategy Pilot: Online, Smart, and Ruthless", 200

def run_flask():
    # Render's dynamic port or default 10000
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

# --- 3. MEMORY & AI SETUP ---
# Dictionary to store history: {user_id: [messages]}
user_conversations = {}
# Keep the last 10 messages so the AI doesn't get confused or expensive
MAX_HISTORY = 10

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
client = Groq(api_key=GROQ_API_KEY)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    # Reset memory when someone types /start
    user_conversations[user_id] = [
        {"role": "system", "content": "You are a ruthless business mentor. Be blunt, honest, and practical. No fluff."}
    ]
    await update.message.reply_text(
        "Memory active. I now remember what we talk about.\n\n"
        "Send me your business problem. If you pivot or change the topic, I'll keep up."
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_text = update.message.text
    
    # Initialize history if it's a new user who didn't type /start
    if user_id not in user_conversations:
        user_conversations[user_id] = [
            {"role": "system", "content": "You are a ruthless business mentor. Be blunt and practical."}
        ]
    
    # 1. Add User message to memory
    user_conversations[user_id].append({"role": "user", "content": user_text})

    try:
        # 2. Send FULL history to Groq
        chat_completion = client.chat.completions.create(
            messages=user_conversations[user_id],
            model="llama-3.3-70b-versatile", 
        )
        response = chat_completion.choices[0].message.content
        
        # 3. Add AI response to memory
        user_conversations[user_id].append({"role": "assistant", "content": response})

        # 4. Trim history to stay within limits
        if len(user_conversations[user_id]) > MAX_HISTORY:
            # Keep system prompt + the most recent messages
            user_conversations[user_id] = [user_conversations[user_id][0]] + user_conversations[user_id][-(MAX_HISTORY-1):]

        await update.message.reply_text(response)
        
    except Exception as e:
        logger.error(f"Error: {e}")
        await update.message.reply_text("My brain hit a snag. Try again in a minute.")

# --- 4. EXECUTION ---
def main():
    # Start Flask in background thread first
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    logger.info("✅ Heartbeat server active.")

    TOKEN = os.environ.get("TELEGRAM_TOKEN")
    if not TOKEN:
        logger.error("❌ TELEGRAM_TOKEN missing!")
        return

    application = Application.builder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("🚀 Bot is polling with memory...")
    application.run_polling()

if __name__ == "__main__":
    main()
