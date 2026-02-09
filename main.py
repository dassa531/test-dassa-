import os
import logging
import requests
import yt_dlp
from bs4 import BeautifulSoup
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

# --- CONFIG ---
TOKEN = os.getenv('TOKEN')
OMDB_API_KEY = os.getenv('OMDB_API_KEY')
ADMIN_ID = 5440625394  # දසුන්ගේ ID එක

logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)

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
    # yt-dlp පාවිච්චි කරලා direct links ගැනීම
    ydl_opts = {'quiet': True, 'no_warnings': True, 'format': 'best'}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        return {'title': info.get('title'), 'url': info.get('url')}

# --- BOT HANDLERS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"🔥 **Welcome to Flixel AI v5.0** 🔥\n\n"
        f"Hi {update.effective_user.first_name}, මම ඔබේ දියුණු කළ මූවී සහ වීඩියෝ සහායකයා.\n\n"
        f"🎬 **Movies:** නම ටයිප් කරන්න\n"
        f"🎵 **Songs:** 'song [නම]' ලෙස එවන්න\n"
        f"📽️ **Social Media:** වීඩියෝ ලින්ක් එක එවන්න"
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.message.text

    # 1. Social Media Video Downloader (FB, YT, Insta, etc)
    if "http" in query:
        st = await update.message.reply_text("🔎 වීඩියෝව පරීක්ෂා කරමින් පවතී...")
        try:
            data = get_direct_video(query)
            keyboard = [[InlineKeyboardButton("📥 Download Video", url=data['url'])]]
            await st.edit_text(f"📽️ **Found:** {data['title'][:60]}", reply_markup=InlineKeyboardMarkup(keyboard))
        except: 
            await st.edit_text("❌ වීඩියෝව සොයාගත නොහැකි විය. ලින්ක් එක නිවැරදිදැයි බලන්න.")

    # 2. Song Downloader
    elif query.lower().startswith("song "):
        st = await update.message.reply_text("🎵 සිංදුව සොයමින් පවතී...")
        try:
            data = get_direct_video(f"ytsearch1:{query[5:]}")
            keyboard = [[InlineKeyboardButton("📥 Download MP3", url=data['url'])]]
            await st.edit_text(f"🎧 **Found:** {data['title']}", reply_markup=InlineKeyboardMarkup(keyboard))
        except: 
            await st.edit_text("❌ සිංදුව හමු වුණේ නැහැ.")

    # 3. Movie Search
    else:
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
        
        # --- DIRECT STREAMING LOGIC ---
        direct_stream = f"https://vidsrc.me/embed/movie?imdb={imdb_id}"
        
        c_sub = scrape_link("https://cinesubz.co/", title)
        b_sub = scrape_link("https://www.baiscope.lk/", title)
        yts = f"https://yts.mx/browse-movies/{title.replace(' ', '%20')}/all/all/0/latest/0/all"

        keyboard = [
            [InlineKeyboardButton("📺 Watch Online (In-App Player)", url=direct_stream)],
            [InlineKeyboardButton("🚀 Fast Download Link", url=f"https://fmovies.to/search?keyword={title.replace(' ', '+')}")],
            [InlineKeyboardButton("📥 Torrent File", url=yts)]
        ]
        
        if c_sub: keyboard.append([InlineKeyboardButton("🇱🇰 Cinesubz (Sinhala Sub)", url=c_sub)])
        if b_sub: keyboard.append([InlineKeyboardButton("🇱🇰 Baiscope (Sinhala Sub)", url=b_sub)])

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

if __name__ == '__main__':
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(button_click))
    print("✅ Flixel v5.0 (No Database) is Online!")
    app.run_polling()
