import os
import logging
import requests
import yt_dlp
from bs4 import BeautifulSoup
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

# API Keys
TOKEN = os.getenv('TOKEN')
OMDB_API_KEY = os.getenv('OMDB_API_KEY')

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# --- SCRAPER FUNCTIONS ---
def scrape_link(url, search_query):
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        response = requests.get(f"{url}?s={search_query.replace(' ', '+')}", headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        result = soup.find('h2') or soup.find('h3')
        if result and result.find('a'):
            return result.find('a')['href']
    except:
        return None
    return None

def get_yt_audio(query):
    ydl_opts = {
        'format': 'bestaudio/best',
        'default_search': 'ytsearch1:',
        'quiet': True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(query, download=False)
        video_info = info['entries'][0] if 'entries' in info else info
        return {'title': video_info.get('title'), 'url': video_info.get('url')}

# --- BOT LOGIC ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"🚀 **Flixel AI v4.0 - Ultimate Bot**\n\n"
        f"Hi Dasun, මම දැන් තවත් බලවත්!\n\n"
        f"🎬 **Movies:** නම ටයිප් කරන්න\n"
        f"🎵 **Songs:** නම ඉදිරියෙන් 'song' ලෙස ටයිප් කරන්න (Ex: song Hanthana Sihine)\n"
        f"📽️ **Videos:** ලින්ක් එක එවන්න"
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.message.text
    
    # 1. වීඩියෝ ලින්ක් එකක් නම් (Social Media Video Downloader)
    if "http" in query:
        status = await update.message.reply_text("🔎 වීඩියෝව පරීක්ෂා කරමින්...")
        try:
            with yt_dlp.YoutubeDL({'quiet': True}) as ydl:
                info = ydl.extract_info(query, download=False)
                video_url = info.get('url')
                title = info.get('title')
                keyboard = [[InlineKeyboardButton("📥 Download Video", url=video_url)]]
                await status.edit_text(f"📽️ **Video Found:**\n{title[:50]}...", reply_markup=InlineKeyboardMarkup(keyboard))
        except:
            await status.edit_text("❌ වීඩියෝව සොයාගත නොහැකි විය.")
            
    # 2. සින්දුවක් නම් (Song Search)
    elif query.lower().startswith("song "):
        song_name = query[5:]
        status = await update.message.reply_text("🎵 සින්දුව සොයමින් පවතී...")
        try:
            data = get_yt_audio(song_name)
            keyboard = [[InlineKeyboardButton("📥 Download MP3 (Audio)", url=data['url'])]]
            await status.edit_text(f"🎧 **Song Found:**\n{data['title']}", reply_markup=InlineKeyboardMarkup(keyboard))
        except:
            await status.edit_text("❌ සින්දුව සොයාගත නොහැකි විය.")

    # 3. මූවී එකක් නම් (Movie Search)
    else:
        url = f"http://www.omdbapi.com/?s={query}&apikey={OMDB_API_KEY}"
        try:
            res = requests.get(url).json()
            if res.get('Response') == 'True':
                movies = res.get('Search')[:5]
                keyboard = [[InlineKeyboardButton(f"🎬 {m['Title']} ({m['Year']})", callback_data=m['imdbID'])] for m in movies]
                await update.message.reply_text("📽️ මූවී ප්‍රතිඵල මෙන්න:", reply_markup=InlineKeyboardMarkup(keyboard))
            else:
                await update.message.reply_text("❌ මූවී එක හමු වුණේ නැහැ. සින්දුවක් නම් 'song' කෑල්ල මුලට දාන්න.")
        except:
            await update.message.reply_text("⚠️ සර්වර් දෝෂයකි.")

async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    movie = requests.get(f"http://www.omdbapi.com/?i={query.data}&apikey={OMDB_API_KEY}").json()
    
    if movie:
        title = movie.get('Title')
        cinesub_url = scrape_link("https://cinesubz.co/", title)
        baiscope_url = scrape_link("https://www.baiscope.lk/", title)
        yts_url = f"https://yts.mx/browse-movies/{title.replace(' ', '%20')}/all/all/0/latest/0/all"
        fmovies_url = f"https://fmovies.to/search?keyword={title.replace(' ', '+')}"

        keyboard = []
        if cinesub_url: keyboard.append([InlineKeyboardButton("🇱🇰 Cinesubz (Sinhala)", url=cinesub_url)])
        if baiscope_url: keyboard.append([InlineKeyboardButton("🇱🇰 Baiscope (Sinhala)", url=baiscope_url)])
        keyboard.append([InlineKeyboardButton("🌐 Watch Online", url=fmovies_url)])
        keyboard.append([InlineKeyboardButton("📥 Download YTS", url=yts_url)])

        text = f"🎬 *{title}* ({movie.get('Year')})\n⭐ *IMDb:* {movie.get('imdbRating')}\n\n📝 {movie.get('Plot')[:250]}..."
        await query.message.reply_photo(photo=movie.get('Poster'), caption=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

if __name__ == '__main__':
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(button_click))
    print("✅ Flixel Ultimate is Online!")
    app.run_polling()
