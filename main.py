import os
import logging
import requests
import yt_dlp
from bs4 import BeautifulSoup
from supabase import create_client, Client
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

# --- CONFIG ---
TOKEN = os.getenv('TOKEN')
OMDB_API_KEY = os.getenv('OMDB_API_KEY')
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
ADMIN_ID = 5440625394  # <--- දසුන්, ඔයාගේ ID එක මම මෙතනට දැම්මා

# Supabase Client
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)

# --- DATABASE LOGIC ---
def get_user_status(user_id):
    try:
        res = supabase.table("users").select("*").eq("user_id", user_id).execute()
        if not res.data:
            supabase.table("users").insert({"user_id": user_id, "status": "free"}).execute()
            return "free"
        return res.data[0]['status']
    except:
        return "free"

# --- SCRAPER & API FUNCTIONS ---
def scrape_link(url, search_query):
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(f"{url}?s={search_query.replace(' ', '+')}", headers=headers, timeout=5)
        soup = BeautifulSoup(response.text, 'html.parser')
        result = soup.find('h2') or soup.find('h3')
        return result.find('a')['href'] if result and result.find('a') else None
    except: return None

def get_direct_video(url):
    # ඕනෑම වීඩියෝ ලින්ක් එකකින් සෘජු ඩවුන්ලෝඩ් ලින්ක් එක ලබා ගැනීම (High Voltage)
    ydl_opts = {'quiet': True, 'no_warnings': True, 'format': 'best'}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        return {'title': info.get('title'), 'url': info.get('url')}

# --- BOT HANDLERS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    get_user_status(user_id) 
    await update.message.reply_text(
        f"🔥 **Welcome to Flixel AI v5.0** 🔥\n\n"
        f"Hi {update.effective_user.first_name}, මම ඔබේ දියුණු කළ මූවී සහ වීඩියෝ සහායකයා.\n\n"
        f"🎬 **Movies:** නම ටයිප් කරන්න\n"
        f"🎵 **Songs:** 'song [නම]' ලෙස එවන්න\n"
        f"📽️ **Social Media:** වීඩියෝ ලින්ක් එක එවන්න"
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.message.text
    user_id = update.effective_user.id
    status = get_user_status(user_id)

    # 1. Video Scraper (YouTube, FB, Insta, etc.)
    if "http" in query:
        st = await update.message.reply_text("🔎 වීඩියෝව පරීක්ෂා කරමින් පවතී...")
        try:
            data = get_direct_video(query)
            keyboard = [[InlineKeyboardButton("📥 Download File (Direct)", url=data['url'])]]
            await st.edit_text(f"📽️ **Found:** {data['title'][:60]}", reply_markup=InlineKeyboardMarkup(keyboard))
        except: await st.edit_text("❌ වීඩියෝව සොයාගත නොහැකි විය.")

    # 2. Song Search
    elif query.lower().startswith("song "):
        st = await update.message.reply_text("🎵 සිංදුව සොයමින් පවතී...")
        try:
            data = get_direct_video(f"ytsearch1:{query[5:]}")
            keyboard = [[InlineKeyboardButton("📥 Download MP3", url=data['url'])]]
            await st.edit_text(f"🎧 **Found:** {data['title']}", reply_markup=InlineKeyboardMarkup(keyboard))
        except: await st.edit_text("❌ සිංදුව හමු වුණේ නැහැ.")

    # 3. Movie Search with Smart Ads
    else:
        if status == "free":
            await update.message.reply_text("📢 *AD:* Premium ලබාගෙන ඇඩ්ස් අයින් කරන්න! /premium", parse_mode='Markdown')
        
        res = requests.get(f"http://www.omdbapi.com/?s={query}&apikey={OMDB_API_KEY}").json()
        if res.get('Response') == 'True':
            movies = res.get('Search')[:5]
            keyboard = [[InlineKeyboardButton(f"🎬 {m['Title']} ({m['Year']})", callback_data=m['imdbID'])] for m in movies]
            await update.message.reply_text("📽️ මා සොයාගත් ප්‍රතිඵල මෙන්න:", reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            await update.message.reply_text("❌ මූවී එක හමු වුණේ නැහැ.")

async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    movie = requests.get(f"http://www.omdbapi.com/?i={query.data}&apikey={OMDB_API_KEY}").json()
    if movie:
        title = movie.get('Title')
        imdb_id = movie.get('imdbID')
        
        # --- DIRECT STREAMING LOGIC (TELEGRAM IN-APP PLAYER) ---
        direct_stream = f"https://vidsrc.me/embed/movie?imdb={imdb_id}"
        
        c_sub = scrape_link("https://cinesubz.co/", title)
        b_sub = scrape_link("https://www.baiscope.lk/", title)
        yts = f"https://yts.mx/browse-movies/{title.replace(' ', '%20')}/all/all/0/latest/0/all"

        # Buttons Grid
        keyboard = [
            [InlineKeyboardButton("📺 Watch Online (Telegram Player)", url=direct_stream)],
            [InlineKeyboardButton("🚀 Direct Download (High Speed)", url=f"https://fmovies.to/search?keyword={title.replace(' ', '+')}")],
            [InlineKeyboardButton("📥 Torrent File", url=yts)]
        ]
        
        if c_sub: keyboard.append([InlineKeyboardButton("🇱🇰 Cinesubz (Sinhala)", url=c_sub)])
        if b_sub: keyboard.append([InlineKeyboardButton("🇱🇰 Baiscope (Sinhala)", url=b_sub)])

        text = (
            f"🎬 *{title}* ({movie.get('Year')})\n"
            f"⭐️ IMDb: {movie.get('imdbRating')} | ⏳ {movie.get('Runtime')}\n\n"
            f"📝 *Plot:* {movie.get('Plot')[:250]}..."
        )
        
        await query.message.reply_photo(
            photo=movie.get('Poster'), 
            caption=text, 
            reply_markup=InlineKeyboardMarkup(keyboard), 
            parse_mode='Markdown'
        )

# --- ADMIN FUNCTIONS ---
async def set_premium(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    try:
        uid = context.args[0]
        supabase.table("users").update({"status": "premium"}).eq("user_id", uid).execute()
        await update.message.reply_text(f"✅ User {uid} is now Premium!")
    except: await update.message.reply_text("❌ Usage: /premium [user_id]")

if __name__ == '__main__':
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("premium", set_premium))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(button_click))
    print("✅ Flixel v5.0 Ultimate is Live!")
    app.run_polling()
