import os, re, threading, logging, requests, fitz
from flask import Flask
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from groq import Groq
from supabase import create_client

# --- 1. CONFIG & SYSTEM ---
logging.basicConfig(level=logging.INFO)
server = Flask(__name__) # This MUST be named 'server' for Gunicorn

# Keys from Environment Variables
TG_TOKEN = os.getenv("TELEGRAM_TOKEN")
GROQ_KEY = os.getenv("GROQ_API_KEY")
SUPA_URL = os.getenv("SUPABASE_URL")
SUPA_KEY = os.getenv("SUPABASE_KEY")

groq_client = Groq(api_key=GROQ_KEY)
db = create_client(SUPA_URL, SUPA_KEY)

# --- 2. TOOLS (Blacklist & Dex) ---
async def security_scan(text):
    ca_match = re.search(r'0x[a-fA-F0-9]{40}', text)
    if not ca_match: return None
    ca = ca_match.group(0)
    
    # Check Supabase Blacklist
    check = db.table("blacklist").select("*").eq("target_value", ca).execute()
    if check.data:
        return f"🚨 BLACKLISTED: {check.data[0]['reason']}"

    # Check DexScreener
    try:
        res = requests.get(f"https://api.dexscreener.com/latest/dex/tokens/{ca}").json()
        pair = res.get('pairs', [{}])[0]
        liq = pair.get('liquidity', {}).get('usd', 0)
        return f"📊 DATA: Liq: ${liq:,.0f} | Price: ${pair.get('priceUsd', '0')}"
    except: return None

# --- 3. BOT HANDLERS ---
async def handle_ae(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    content = msg.text or ""

    # PDF Processing
    if msg.document and msg.document.mime_type == "application/pdf":
        status = await msg.reply_text("📑 Analyzing Whitepaper...")
        pdf = await msg.document.get_file()
        path = f"temp_{msg.chat_id}.pdf"
        await pdf.download_to_drive(path)
        doc = fitz.open(path)
        content = "".join([p.get_text() for p in doc])[:8000]
        os.remove(path)
        await status.delete()

    sec_info = await security_scan(content)
    if sec_info: await msg.reply_text(sec_info)

    # Strategy AI
    try:
        ai_res = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": "You are AE Strategy Pilot. ROI-focused, blunt, tactical."},
                {"role": "user", "content": content}
            ]
        )
        await msg.reply_text(ai_res.choices[0].message.content)
    except Exception as e:
        await msg.reply_text("⚠️ Logic error. Check logs.")

# --- 4. EXECUTION ---
@server.route('/')
def live(): return "AE Pilot Live", 200

def start_web():
    server.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8080)))

if __name__ == '__main__':
    threading.Thread(target=start_web, daemon=True).start()
    bot = ApplicationBuilder().token(TG_TOKEN).build()
    bot.add_handler(CommandHandler("start", lambda u, c: u.message.reply_text("⚡ AE Pilot v2.0 READY.")))
    bot.add_handler(MessageHandler(filters.ALL & (~filters.COMMAND), handle_ae))
    bot.run_polling()
