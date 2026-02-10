import os
import logging
import asyncio
import requests
import google.generativeai as genai
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

# --- CONFIGURATION ---
TOKEN = os.getenv('TOKEN')
OMDB_API_KEY = os.getenv('OMDB_API_KEY')
TMDB_API_KEY = os.getenv('TMDB_API_KEY')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
SMART_LINK = "https://otieu.com/4/10513841" # Monetag Smart Link

# Gemini Setup
genai.configure(api_key=GEMINI_API_KEY)
ai_model = genai.GenerativeModel('gemini-2.0-flash')

logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)

STRINGS = {
    "si": {
        "welcome": "👋 ආයුබෝවන් {name}!\n\n🚀 **Flixel AI v50.0** වෙත සාදරයෙන් පිළිගනිමු.\nමම මූවී සොයා දෙන **filxel** [2026-02-08] නිල බොට්.",
        "ads_disclaimer": "⚠️ **දැනුම්දීමයි:** අපේ සේවාව නොමිලේ දෙන නිසා දැන්වීම් (Ads) භාවිතා කරනවා. 🙏",
        "commands": "🔍 **සෙවුම් ක්‍රම:**\n• නම එවන්න - මූවී සෙවීමට\n• `/series [නම]` - ටීවී සීරීස්\n• `/actor [නම]` - නළුවා අනුව\n• `/year [වසර]` - වසර අනුව\n• `/ai` - AI සෙවුම",
        "ad_msg": "⚠️ **Security Check!**\n\nපහත බටන් එක ක්ලික් කර ඇඩ් එක බලන අතරතුර අපි ඔබේ මූවී එක සූදානම් කරනවා. තත්පර 6කින් මෙය Unlock වේවි.",
        "unlock": "🔓 Unlock Content (Multi-Server)",
        "watch_1": "📺 Server 1 (vidsrc.me)",
        "watch_2": "📺 Server 2 (vidsrc.xyz)",
        "watch_3": "📺 Server 3 (MultiEmbed)",
        "results": "📽️ සෙවුම් ප්‍රතිඵල:",
        "genres_msg": "🎭 කැමති මූවී වර්ගයක් තෝරන්න:",
        "not_found": "❌ සොයාගත නොහැකි විය. කරුණාකර නිවැරදි නම එවන්න."
    },
    "en": {
        "welcome": "👋 Hello {name}!\n\nWelcome to 🚀 **Flixel AI v50.0**.\nOfficial **filxel** [2026-02-08] movie bot.",
        "ads_disclaimer": "⚠️ **Note:** We use ads to keep this service free. 🙏",
        "commands": "🔍 **Search Commands:**\n• Send name - Search Movies\n• `/series [name]` - TV Series\n• `/actor [name]` - By Actor\n• `/year [year]` - By Year\n• `/ai` - AI Search",
        "ad_msg": "⚠️ **Security Check!**\n\nClick below. Your movie will be automatically displayed in 6 seconds.",
        "unlock": "🔓 Unlock Content (Multi-Server)",
        "watch_1": "📺 Watch (Server 1)",
        "watch_2": "📺 Watch (Server 2)",
        "watch_3": "📺 Watch (Server 3)",
        "results": "📽️ Search Results:",
        "genres_msg": "🎭 Select a Movie Category:",
        "not_found": "❌ No results found. Check spelling."
    }
}

GENRES = ["Action", "Comedy", "Horror", "Sci-Fi", "Drama", "Animation", "Romance", "Thriller"]

# --- HELPERS ---
def get_lang(context, user_id):
    return context.user_data.get(user_id, "en")

def get_yts(movie_title):
    try:
        url = f"https://yts.mx/api/v2/list_movies.json?query_term={movie_title}"
        data = requests.get(url).json()
        return data['data']['movies'][0].get('torrents', []) if data['data']['movie_count'] > 0 else []
    except: return []

# --- CORE SEARCH ENGINE ---
async def search_engine(update, context, query, search_type=None, year=None):
    lang = get_lang(context, update.effective_user.id)
    url = f"http://www.omdbapi.com/?s={query}&apikey={OMDB_API_KEY}"
    if search_type: url += f"&type={search_type}"
    if year: url += f"&y={year}"
    
    res = requests.get(url).json()
    keyboard = []
    if res.get('Response') == 'True':
        for m in res.get('Search')[:6]:
            icon = "🎬" if m['Type'] == 'movie' else "📺"
            keyboard.append([InlineKeyboardButton(f"{icon} {m['Title']} ({m['Year']})", callback_data=f"select_{m['imdbID']}")])
        await update.message.reply_text(STRINGS[lang]["results"], reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        # Fuzzy search logic using Gemini
        prompt = f"The user searched for '{query}' but no results were found. Correct the spelling or suggest the most likely real movie title only."
        ai_res = ai_model.generate_content(prompt)
        await update.message.reply_text(f"❌ Not found. Did you mean: **{ai_res.text.strip()}**?")

# --- CONTENT SENDER ---
async def send_movie(update, context, data, lang):
    s = STRINGS[lang]
    chat_id = update.effective_chat.id
    imdb_id = data.split("_")[1]
    
    m = requests.get(f"http://www.omdbapi.com/?i={imdb_id}&plot=full&apikey={OMDB_API_KEY}").json()
    title = m.get('Title', 'N/A')
    m_type = m.get('Type', 'movie')
    
    caption = (
        f"✅ **Unlocked Successfully!**\n\n"
        f"🎬 **{title} ({m.get('Year')})**\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"⭐ **Rating:** {m.get('imdbRating')}/10 | 🎭 **Genre:** {m.get('Genre')}\n"
        f"👥 **Cast:** {m.get('Actors')}\n\n"
        f"📝 **Plot:**\n_{m.get('Plot')[:350]}..._\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"⚡ *Powered by filxel AI*"
    )
    
    # Multi-Server Buttons
    keyboard = [
        [InlineKeyboardButton(s["watch_1"], url=f"https://vidsrc.me/embed/{m_type}?imdb={imdb_id}")],
        [InlineKeyboardButton(s["watch_2"], url=f"https://vidsrc.xyz/embed/{m_type}?imdb={imdb_id}")],
        [InlineKeyboardButton(s["watch_3"], url=f"https://multiembed.mov/directstream.php?video_id={imdb_id}")]
    ]
    
    if m_type == 'movie':
        for t in get_yts(title):
            keyboard.append([InlineKeyboardButton(f"📥 {t['quality']} ({t['size']})", url=t['url'])])
            
    poster = m.get('Poster') if m.get('Poster') != "N/A" else "https://via.placeholder.com/500x750"
    await context.bot.send_photo(chat_id=chat_id, photo=poster, caption=caption, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

# --- HANDLERS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton("🇱🇰 සිංහල", callback_data="setlang_si"),
                 InlineKeyboardButton("🇺🇸 English", callback_data="setlang_en")]]
    await update.message.reply_text("👋 Hello! Select language / භාෂාව තෝරන්න:", reply_markup=InlineKeyboardMarkup(keyboard))

async def series_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = " ".join(context.args)
    if not query: return await update.message.reply_text("💡 Usage: `/series Breaking Bad`")
    await search_engine(update, context, query, "series")

async def actor_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = " ".join(context.args)
    if not query: return await update.message.reply_text("💡 Usage: `/actor Vijay`")
    await search_engine(update, context, query)

async def year_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args: return await update.message.reply_text("💡 Usage: `/year 2024`")
    year = context.args[0]
    await search_engine(update, context, "movie", year=year)

async def ai_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args: return await update.message.reply_text("💡 Usage: `/ai robot movie 2024`")
    desc = " ".join(context.args)
    prompt = f"Identify movie/series name from description: {desc}. Return ONLY the movie name."
    try:
        response = ai_model.generate_content(prompt)
        movie_name = response.text.strip()
        await update.message.reply_text(f"🔍 AI Suggestion: **{movie_name}**")
        await search_engine(update, context, movie_name)
    except: await update.message.reply_text("❌ AI Error.")

async def handle_movie_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.message.text
    if query.startswith('/'): return
    await search_engine(update, context, query, "movie")

async def trending(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = f"https://api.themoviedb.org/3/trending/all/day?api_key={TMDB_API_KEY}"
    res = requests.get(url).json().get('results', [])[:8]
    keyboard = [[InlineKeyboardButton(f"🔥 {m.get('title', m.get('name'))}", callback_data=f"select_{m.get('id')}")] for m in res]
    await update.message.reply_text("🔥 **Trending Today**", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def show_genres(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = get_lang(context, update.effective_user.id)
    keyboard = []
    for i in range(0, len(GENRES), 2):
        row = [InlineKeyboardButton(GENRES[i], callback_data=f"gen_{GENRES[i]}")]
        if i+1 < len(GENRES): row.append(InlineKeyboardButton(GENRES[i+1], callback_data=f"gen_{GENRES[i+1]}"))
        keyboard.append(row)
    await update.message.reply_text(STRINGS[lang]["genres_msg"], reply_markup=InlineKeyboardMarkup(keyboard))

async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    data = query.data
    lang = get_lang(context, user_id)
    await query.answer()

    if data.startswith("setlang_"):
        l_code = data.split("_")[1]
        context.user_data[user_id] = l_code
        welcome = STRINGS[l_code]["welcome"].format(name=query.from_user.first_name)
        await query.edit_message_text(f"{welcome}\n\n{STRINGS[l_code]['ads_disclaimer']}\n\n{STRINGS[l_code]['commands']}", parse_mode='Markdown')

    elif data.startswith("select_"):
        keyboard = [[InlineKeyboardButton(STRINGS[lang]["unlock"], url=SMART_LINK)]]
        msg = await query.message.reply_text(STRINGS[lang]["ad_msg"], reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
        await asyncio.sleep(6) # Ad wait
        await msg.edit_text("⏳ Unlocking Content...")
        await asyncio.sleep(1)
        await send_movie(update, context, data, lang)
        await msg.delete()

if __name__ == '__main__':
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("ai", ai_search))
    app.add_handler(CommandHandler("series", series_cmd))
    app.add_handler(CommandHandler("actor", actor_cmd))
    app.add_handler(CommandHandler("year", year_cmd))
    app.add_handler(CommandHandler("trending", trending))
    app.add_handler(CommandHandler("genres", show_genres))
    app.add_handler(CallbackQueryHandler(button_click))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_movie_search))
    
    print("🚀 Flixel AI v50.0 Live & Stable! Millionaire Ready!")
    app.run_polling(drop_pending_updates=True)
