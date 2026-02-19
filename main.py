import os
import requests
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

# Credentials from Environment Variables
TOKEN = os.environ.get("TELEGRAM_TOKEN")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

# 1. Start Command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome = (
        "🚀 **AE Strategy Pilot Active**\n\n"
        "I am your strategic partner. I don't do 'nice'—I do 'results.'\n\n"
        "• Send a **Voice Note**: I'll transcribe and give you a ruthless strategy.\n"
        "• Send a **Text Message**: We'll brainstorm your next move."
    )
    await update.message.reply_text(welcome, parse_mode="Markdown")

# 2. Text Interaction (Brainstorming)
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    chat_resp = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
        json={
            "model": "llama-3.3-70b-versatile",
            "messages": [
                {"role": "system", "content": "You are the AE Strategic Partner. Be blunt, professional, and practical. Analyze the user's input and provide a ruthless path to execution."},
                {"role": "user", "content": user_text}
            ]
        }
    )
    strategy = chat_resp.json()['choices'][0]['message']['content']
    await update.message.reply_text(strategy)

# 3. Audio Interaction (Transcription + Strategy)
async def handle_audio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    status = await update.message.reply_text("📥 AE Pilot is listening...")
    audio_file = update.message.voice or update.message.audio
    file = await context.bot.get_file(audio_file.file_id)
    file_bytes = await file.download_as_bytearray()

    # Transcribe
    files = {'file': ('audio.ogg', file_bytes)}
    trans_resp = requests.post(
        "https://api.groq.com/openai/v1/audio/transcriptions",
        headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
        files=files,
        data={"model": "whisper-large-v3"}
    )
    transcript = trans_resp.json().get("text", "Error transcribing.")

    # Strategy
    await status.edit_text("🧠 Analyzing strategy...")
    chat_resp = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
        json={
            "model": "llama-3.3-70b-versatile",
            "messages": [
                {"role": "system", "content": "You are the AE Strategic Partner. Provide a SUMMARY, RUTHLESS ANALYSIS, and 3 NEXT STEPS."},
                {"role": "user", "content": f"Analyze this transcript: {transcript}"}
            ]
        }
    )
    strategy = chat_resp.json()['choices'][0]['message']['content']
    await status.edit_text(f"📝 **TRANSCRIPT:**\n{transcript}\n\n---\n\n{strategy}", parse_mode="Markdown")

if __name__ == '__main__':
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, handle_audio))
    app.run_polling()
