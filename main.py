import os
import logging
import requests
import datetime
import google.generativeai as genai
from bs4 import BeautifulSoup
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

# --- CONFIGURATION ---
TOKEN = os.getenv('TOKEN')
OMDB_API_KEY = os.getenv('OMDB_API_KEY')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')

genai.configure(api_key=GEMINI_API_KEY)
ai_model = genai.GenerativeModel('gemini-2.0-flash')

logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)

# භාෂාව අනුව මැසේජ් පද්ධතිය
STRINGS = {
    "si": {
        "welcome": "🚀 **Flixel AI v26.0**\n\nමම ඔයාට ඕනෑම මූවී එකක් සොයා දෙන බොට් කෙනෙක්.\n\n🔍 **සෙවුම් විධානයන්:**\n• නම එවන්න (Movie Search)\n• නළුවා අනුව: `/actor [නම]`\n• වසර අනුව: `/year [වසර]`\n• AI සෙවුම: `/ai [විස්තරය]`",
        "desc_title": "📝 **කතාව:**",
        "select_option": "✅ පහතින් තෝරාගන්න:",
        "watch": "📺 ඔන්ලයින් බලන්න",
        "download": "📥 ඩවුන්ලෝඩ්",
        "sub": "🇱🇰 සිංහල උපසිරැසි",
        "results": "📽️ සෙවුම් ප්‍රතිඵල:",
        "not_found": "❌ කිසිවක් සොයාගත නොහැකි විය."
    },
    "en": {
        "welcome": "🚀 **Flixel AI v26.0**\n\nI am a bot that helps you find any movie.\n\n🔍 **Search Commands:**\n• Send Name (Movie Search)\n• By Actor: `/actor [name]`\n• By Year: `/year [year]`\n• AI Search: `/ai [description]`",
        "desc_title": "📝 **Description:**",
        "select_option": "✅ Select an option below:",
        "watch": "📺 Watch Online",
        "download": "📥 Download",
        "sub": "🇱🇰 Sinhala Subtitle",
        "results": "📽️ Search Results:",
        "not_found": "❌ No results found."
    }
}

# --- HELPER FUNCTIONS ---
def get_lang(context, user_id):
    return context.user_data.get(user_id, "en")

def has_sinhala_sub(movie_name):
    try:
        search_url = f"https://subscene.com/subtitles/searchbytitle?query={movie_name.replace(' ', '+')}"
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(search_url, headers=headers, timeout=5)
        return "Sinhala" in response.text or "sinhala" in response.text
    except: return False

def get_yts_links(movie_title):
    try:
        yts_url = f"https://yts.mx/api/v2/list_movies.json?query_term={movie_title}"
        data = requests.get(yts_url).json()
        if data['data']['movie_count'] > 0:
            movie = data['data']['movies'][0]
            return movie.get('torrents', [])
        return []
    except: return []

# --- HANDLERS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton("🇱🇰 සිංහල", callback_data="setlang_si"),
                 InlineKeyboardButton("🇺🇸 English", callback_data="setlang_en")]]
    await update.message.reply_text("👋 Hello! Please select your language / කරුණාකර භාෂාව තෝරාගන්න:", 
                                  reply_markup=InlineKeyboardMarkup(keyboard))

async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    data = query.data
    await query.answer()

    if data.startswith("setlang_"):
        lang = data.split("_")[1]
        context.user_data[user_id] = lang
        s = STRINGS[lang]
        await query.edit_message_text(s["welcome"], parse_mode='Markdown')

    elif data.startswith("select_"):
        lang = get_lang(context, user_id)
        s = STRINGS[lang]
        imdb_id = data.split("_")[1]
        
        # Get Full Details from OMDB (plot='full')
        m = requests.get(f"http://www.omdbapi.com/?i={imdb_id}&plot=full&apikey={OMDB_API_KEY}").json()
        title = m.get('Title')
        plot = m.get('Plot', 'N/A')
        
        yts_torrents = get_yts_links(title)
        show_sub = has_sinhala_sub(title)
        
        keyboard = [[InlineKeyboardButton(s["watch"], url=f"https://vidsrc.me/embed/movie?imdb={imdb_id}")]]
        
        if yts_torrents:
            for t in yts_torrents:
                btn_label = f"{s['download']} {t['quality']} ({t['size']})"
                keyboard.append([InlineKeyboardButton(btn_label, url=t['url'])])
        
        if show_sub:
            sub_url = f"https://subscene.com/subtitles/searchbytitle?query={title.replace(' ', '+')}"
            keyboard.append([InlineKeyboardButton(s["sub"], url=sub_url)])
        
        # Caption with Description
        caption = (
            f"🎬 *{title}* ({m.get('Year')})\n"
            f"⭐ IMDb: {m.get('imdbRating')} | 🕒 {m.get('Runtime')}\n"
            f"🎭 Cast: {m.get('Actors')}\n\n"
            f"{s['desc_title']}\n{plot[:500]}...\n\n"
            f"{s['select_option']}"
        )
        await query.message.reply_photo(photo=m.get('Poster'), caption=caption, 
                                      reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def handle_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = get_lang(context, user_id)
    s = STRINGS[lang]
    user_input = update.message.text
    
    url = f"http://www.omdbapi.com/?s={user_input.replace(' ', '+')}&apikey={OMDB_API_KEY}"
    res = requests.get(url).json()
    
    if res.get('Response') == 'True':
        movies = res.get('Search')[:8]
        keyboard = [[InlineKeyboardButton(f"🎬 {m['Title']} ({m['Year']})", callback_data=f"select_{m['imdbID']}")] for m in movies]
        await update.message.reply_text(f"{s['results']}", reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await update.message.reply_text(s["not_found"])

# --- MAIN ---
if __name__ == '__main__':
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_click))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_search))
    print("🚀 Flixel AI v26.0 Live!")
    app.run_polling()
