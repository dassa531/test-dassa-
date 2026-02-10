import os
import logging
import requests
import datetime
import google.generativeai as genai
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from deep_translator import GoogleTranslator

# --- CONFIGURATION ---
TOKEN = os.getenv('TOKEN')
OMDB_API_KEY = os.getenv('OMDB_API_KEY')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')

# Gemini 2.0 Flash Setup
genai.configure(api_key=GEMINI_API_KEY)
ai_model = genai.GenerativeModel('gemini-2.0-flash')

logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)

# Trackers
ai_usage_tracker = {}
GENRES = ["Action", "Comedy", "Horror", "Sci-Fi", "Drama", "Animation", "Romance"]

def to_english(text):
    try: return GoogleTranslator(source='auto', target='en').translate(text)
    except: return text

# --- 1. START COMMAND ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_text = (
        f"🚀 **Flixel AI v16.0**\n\n"
        f"Hi {update.effective_user.first_name}, මම ඔයාට ඕනෑම මූවී එකක් සොයා දෙන බොට් කෙනෙක්.\n\n"
        f"🔍 **සෙවීමට:** මූවී නම ටයිප් කර එවන්න.\n"
        f"🧠 **AI සෙවුම:** `/ai [දර්ශනය]`\n\n"
        f"📢 **භාෂාව තෝරාගන්න / Select Language:**"
    )
    keyboard = [[InlineKeyboardButton("🇱🇰 Sinhala", callback_data="lang_si"),
                 InlineKeyboardButton("🇺🇸 English", callback_data="lang_en")]]
    await update.message.reply_text(welcome_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

# --- 2. MAIN MENU ---
async def show_main_menu(update_or_query, context):
    keyboard = [[InlineKeyboardButton("🔥 Trending", callback_data="trending")],
                [InlineKeyboardButton("🎭 Genre", callback_data="show_genres")]]
    text = "🚀 **Flixel AI Menu**\nමූවී නම ටයිප් කරන්න හෝ පහතින් තෝරන්න:"
    if isinstance(update_or_query, Update):
        await update_or_query.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await update_or_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

# --- 3. AI SEARCH (Gemini 2.0 Flash) ---
async def ai_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    today = str(datetime.date.today())
    if user_id not in ai_usage_tracker or ai_usage_tracker[user_id]['date'] != today:
        ai_usage_tracker[user_id] = {'count': 0, 'date': today}

    if ai_usage_tracker[user_id]['count'] >= 5:
        await update.message.reply_text("❌ අද දිනට AI සීමාව අවසන්.")
        return

    if not context.args:
        await update.message.reply_text("🎬 උදා: `/ai ship hitting iceberg`")
        return

    status = await update.message.reply_text("🧠 Gemini 2.0 Flash පරීක්ෂා කරයි...")
    try:
        query = to_english(' '.join(context.args))
        response = ai_model.generate_content(f"Movie name for: {query}. Return ONLY the title.")
        movie_name = response.text.strip()
        ai_usage_tracker[user_id]['count'] += 1
        await status.edit_text(f"💡 චිත්‍රපටය: **{movie_name}**")
        await perform_search(update, movie_name, "📽️ ප්‍රතිඵල මෙන්න:")
    except:
        await status.edit_text("❌ AI එකට සොයාගත නොහැකි විය.")

# --- 4. SEARCH LOGIC ---
async def perform_search(update_or_query, query, success_text):
    search_term = to_english(query)
    url = f"http://www.omdbapi.com/?s={search_term.replace(' ', '+')}&apikey={OMDB_API_KEY}"
    res = requests.get(url).json()

    if res.get('Response') == 'True':
        movies = res.get('Search')[:8]
        keyboard = [[InlineKeyboardButton(f"🎬 {m['Title']} ({m['Year']})", callback_data=f"select_{m['imdbID']}")] for m in movies]
        if isinstance(update_or_query, Update):
            await update_or_query.message.reply_text(success_text, reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            await update_or_query.message.reply_text(success_text, reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        if isinstance(update_or_query, Update): await update_or_query.message.reply_text("❌ සොයාගත නොහැකි විය.")

# --- 5. BUTTON HANDLER (Subtitle Fix) ---
async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    await query.answer()

    if data.startswith("lang_"): await show_main_menu(query, context)
    elif data == "trending": await perform_search(query, "2026", "🔥 Trending:")
    elif data == "show_genres":
        keyboard = [[InlineKeyboardButton(g, callback_data=f"genre_{g.lower()}")] for g in GENRES]
        await query.edit_message_text("🎭 තෝරන්න:", reply_markup=InlineKeyboardMarkup(keyboard))
    elif data.startswith("genre_"): await perform_search(query, data.split("_")[1], "🎬 ප්‍රතිඵල:")

    elif data.startswith("select_"):
        imdb_id = data.split("_")[1]
        m = requests.get(f"http://www.omdbapi.com/?i={imdb_id}&apikey={OMDB_API_KEY}").json()
        title = m.get('Title')
        
        # සැබෑ උපසිරැසි ලින්ක් සකස් කිරීම
        sub_search_url = f"https://www.opensubtitles.org/en/search/sublanguageid-all/idmovie-{imdb_id.replace('tt','')}"
        sin_sub_url = f"https://subscene.com/subtitles/searchbytitle?query={title.replace(' ', '%20')}"

        text = f"🎬 *{title}* ({m.get('Year')})\n⭐ IMDb: {m.get('imdbRating')}\n\n✅ තෝරාගන්න:"
        keyboard = [
            [InlineKeyboardButton("📺 Watch Online", url=f"https://vidsrc.me/embed/movie?imdb={imdb_id}")],
            [InlineKeyboardButton("📥 Download Movie", url=f"https://yts.mx/browse-movies/{title.replace(' ', '%20')}")],
            [InlineKeyboardButton("🇱🇰 Sinhala Subtitles", url=sin_sub_url)],
            [InlineKeyboardButton("🌍 Global Subtitles", url=sub_search_url)]
        ]
        await query.message.reply_photo(photo=m.get('Poster'), caption=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

# --- 6. MAIN ---
if __name__ == '__main__':
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("ai", ai_search))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, lambda u, c: perform_search(u, u.message.text, "📽️ සෙවුම් ප්‍රතිඵල:")))
    app.add_handler(CallbackQueryHandler(button_click))
    print("🚀 Flixel AI v16.0 Live!")
    app.run_polling()
