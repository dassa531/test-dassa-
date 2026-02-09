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

logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)

# --- ADVANCED SCRAPER FOR CINESUBZ ---
def get_cinesubz_player(movie_title):
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        search_url = f"https://cinesubz.co/?s={movie_title.replace(' ', '+')}"
        response = requests.get(search_url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # පළමු සෙවුම් ප්‍රතිඵලය ලබා ගැනීම
        result = soup.find('h2') or soup.find('h3')
        if result and result.find('a'):
            movie_page_url = result.find('a')['href']
            
            # මූවී පේජ් එකට ගිහින් Embed Player එක සෙවීම
            page_res = requests.get(movie_page_url, headers=headers, timeout=10)
            page_soup = BeautifulSoup(page_res.text, 'html.parser')
            
            # මෙහිදී සයිට් එකේ ඇති Player Iframe එක හෝ Link එක සොයයි
            # සටහන: බොහෝ විට මෙය Direct ලින්ක් එකක් ලෙස ලබා දිය හැක
            return movie_page_url # දැනට සයිට් එකේ පේජ් එක ලබා දෙයි
    except:
        return None
    return None

# --- BOT HANDLERS ---
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.message.text
    # මූවී සර්ච් එක (OMDb හරහා)
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
        
        # English Direct Player (No Subs)
        eng_player = f"https://vidsrc.me/embed/movie?imdb={imdb_id}"
        
        # Sinhala Sub Page (From Scraper)
        cinesub_link = get_cinesubz_player(title)

        keyboard = [
            [InlineKeyboardButton("📺 Watch Online (English - No Ads)", url=eng_player)]
        ]
        
        if cinesub_link:
            # මේ ලින්ක් එක ටෙලිග්‍රෑම් එක ඇතුළේ 'Instant View' හෝ 'In-App Browser' එකේ ලස්සනට ප්ලේ වෙයි
            keyboard.append([InlineKeyboardButton("🇱🇰 Watch with Sinhala Subtitles", url=cinesub_link)])
        
        keyboard.append([InlineKeyboardButton("📥 Download Torrent", url=f"https://yts.mx/browse-movies/{title.replace(' ', '%20')}/all/all/0/latest/0/all")])

        text = (
            f"🎬 *{title}* ({movie.get('Year')})\n"
            f"⭐️ IMDb: {movie.get('imdbRating')}\n\n"
            f"🍿 **දැන් ඔබට ටෙලිග්‍රෑම් එක ඇතුළෙම නැරඹිය හැක.**\n"
            f"සිංහල සබ්ටයිටල් අවශ්‍ය නම් දෙවන බටන් එක ක්ලික් කරන්න."
        )
        
        await query.message.reply_photo(
            photo=movie.get('Poster'), 
            caption=text, 
            reply_markup=InlineKeyboardMarkup(keyboard), 
            parse_mode='Markdown'
        )

if __name__ == '__main__':
    app = Application.builder().token(TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(button_click))
    app.run_polling()
