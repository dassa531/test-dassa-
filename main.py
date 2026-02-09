import os
import logging
import requests
from bs4 import BeautifulSoup
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

# API Keys
TOKEN = os.getenv('TOKEN')
OMDB_API_KEY = os.getenv('OMDB_API_KEY')

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# --- SCRAPER FUNCTION ---
def scrape_link(url, search_query):
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        response = requests.get(f"{url}?s={search_query.replace(' ', '+')}", headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # සයිට් එකේ පළමු සෙවුම් ප්‍රතිඵලය සොයා ගැනීම
        result = soup.find('h2') or soup.find('h3')
        if result and result.find('a'):
            return result.find('a')['href']
    except:
        return None
    return None

# --- BOT LOGIC ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"🚀 **Flixel AI v3.0 - Ultimate Search**\n\nHi Dasun, මූවී එකේ නම එවන්න. මම සිංහල සබ් හෝ ඉංග්‍රීසි මූවී ලින්ක්ස් හොයලා දෙන්නම්!")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.message.text
    url = f"http://www.omdbapi.com/?s={query}&apikey={OMDB_API_KEY}"
    
    try:
        res = requests.get(url).json()
        if res.get('Response') == 'True':
            movies = res.get('Search')[:5]
            keyboard = [[InlineKeyboardButton(f"🎬 {m['Title']} ({m['Year']})", callback_data=m['imdbID'])] for m in movies]
            await update.message.reply_text("📽️ මට හමුවූ ප්‍රතිඵල මෙන්න:", reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            await update.message.reply_text("❌ මූවී එක හමු වුණේ නැහැ.")
    except:
        await update.message.reply_text("⚠️ API Error එකක් ආවා. පසුව උත්සාහ කරන්න.")

async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    movie_id = query.data
    movie = requests.get(f"http://www.omdbapi.com/?i={movie_id}&apikey={OMDB_API_KEY}").json()
    
    if movie:
        title = movie.get('Title')
        year = movie.get('Year')
        
        # Scrape Local Sites
        cinesub_url = scrape_link("https://cinesubz.co/", title)
        baiscope_url = scrape_link("https://www.baiscope.lk/", title)
        
        # International Fallback Links
        yts_url = f"https://yts.mx/browse-movies/{title.replace(' ', '%20')}/all/all/0/latest/0/all"
        fmovies_url = f"https://fmovies.to/search?keyword={title.replace(' ', '+')}"

        keyboard = []
        
        # 1. සිංහල සබ් තිබේ නම් ඒවා පෙන්වීම
        if cinesub_url:
            keyboard.append([InlineKeyboardButton("🇱🇰 Cinesubz (Sinhala Sub)", url=cinesub_url)])
        if baiscope_url:
            keyboard.append([InlineKeyboardButton("🇱🇰 Baiscope (Sinhala Sub)", url=baiscope_url)])
            
        # 2. සිංහල සබ් නැතිනම් හෝ අමතරව ඉංග්‍රීසි මූවී බලන්න ලින්ක්ස්
        keyboard.append([InlineKeyboardButton("🌐 Watch Online (English)", url=fmovies_url)])
        keyboard.append([InlineKeyboardButton("📥 Download Torrent (YTS)", url=yts_url)])

        text = (
            f"🎬 *{title}* ({year})\n"
            f"⭐ *IMDb:* {movie.get('imdbRating')}\n"
            f"🌍 *Language:* {movie.get('Language')}\n\n"
            f"📝 *Plot:* {movie.get('Plot')[:300]}..."
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
    print("✅ Flixel v3.0 is Online!")
    app.run_polling()
