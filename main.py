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
SMART_LINK = "https://otieu.com/4/10513841" # Your Monetag Link

# Gemini Setup
genai.configure(api_key=GEMINI_API_KEY)
ai_model = genai.GenerativeModel('gemini-2.0-flash')

logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)

STRINGS = {
    "si": {
        "welcome": "👋 ආයුබෝවන් {name}!\n\n🚀 **Flixel AI v52.0** වෙත සාදරයෙන් පිළිගනිමු.\nමම මූවී සොයා දෙන **filxel** නිල බොට්.",
        "ads_disclaimer": "⚠️ **දැනුම්දීමයි:** අපේ සේවාව නොමිලේ දෙන නිසා දැන්වීම් (Ads) භාවිතා කරනවා. 🙏",
        "commands": "🔍 **සෙවුම් ක්‍රම:**\n• නම එවන්න - සෙවීමට\n• `/ai` - AI සෙවුම\n• `/series` - ටීවී සීරීස්\n• `/actor` - නළුවා අනුව\n• `/year` - වසර අනුව\n• `/trending` - අද දවසේ ජනප්‍රිය",
        "ad_msg": "⚠️ **Security Check!**\n\nපහත Unlock බටන් එක ක්ලික් කරන්න. තත්පර 6කින් සියලුම සර්වර්ස් විවෘත වේවි.",
        "unlock": "🔓 Unlock Content (Auto Release)",
        "watch_main": "📺 Watch Online (Streaming)",
        "select_server": "📽️ කැමති සර්වර් එකක් තෝරාගන්න:",
        "results": "📽️ සෙවුම් ප්‍රතිඵල:",
        "genres_msg": "🎭 කැමති මූවී වර්ගයක් තෝරන්න:",
        "not_found": "❌ සොයාගත නොහැකි විය. කරුණාකර නිවැරදි නම එවන්න."
    },
    "en": {
        "welcome": "👋 Hello {name}!\n\nWelcome to 🚀 **Flixel AI v52.0**.\nOfficial **filxel** movie bot.",
        "ads_disclaimer": "⚠️ **Note:** We use ads to keep this service free. 🙏",
        "commands": "🔍 **Search Commands:**\n• Send name - Search\n• `/ai` | `/series` | `/actor` | `/year` | `/trending`",
        "ad_msg": "⚠️ **Security Check!**\n\nClick Unlock. All servers will be open in 6 seconds.",
        "unlock": "🔓 Unlock Content (Auto Release)",
        "watch_main": "📺 Watch Online (Streaming)",
        "select_server": "📽️ Select a Streaming Server:",
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
    if res.get('Response') == 'True':
        keyboard = [[InlineKeyboardButton(f"🎬 {m['Title']} ({m['Year']})", callback_data=f"select_{m['imdbID']}")] for m in res.get('Search')[:6]]
        await update.message.reply_text(STRINGS[lang]["results"], reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        # Fuzzy AI Search
        prompt = f"The user searched for '{query}' but no results. Suggest the most likely real movie title only."
        ai_res = ai_model.generate_content(prompt)
        await update.message.reply_text(f"❌ Not found. Did you mean: **{ai_res.text.strip()}**?")

# --- CONTENT SENDER ---
async def send_movie_info(update, context, imdb_id, lang):
    m = requests.get(f"http://www.omdbapi.com/?i={imdb_id}&plot=full&apikey={OMDB_API_KEY}").json()
    title = m.get('Title', 'N/A')
    
    caption = (
        f"✅ **Unlocked Successfully!**\n\n"
        f"🎬 **{title} ({m.get('Year')})**\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"⭐ **Rating:** {m.get('imdbRating')}/10\n"
        f"🎭 **Genre:** {m.get('Genre')}\n"
        f"👥 **Cast:** {m.get('Actors')}\n\n"
        f"📝 **Plot:**\n_{m.get('Plot')[:350]}..._\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"⚡ *Powered by filxel AI*"
    )
    
    # Cleaner Interface: Only "Watch Online" and "Download" buttons
    keyboard = [[InlineKeyboardButton(STRINGS[lang]["watch_main"], callback_data=f"srvlist_{imdb_id}_{m['Type']}")]]
    
    if m['Type'] == 'movie':
        for t in get_yts(title):
            keyboard.append([InlineKeyboardButton(f"📥 Download {t['quality']} ({t['size']})", url=t['url'])])
            
    poster = m.get('Poster') if m.get('Poster') != "N/A" else "https://via.placeholder.com/500x750"
    await context.bot.send_photo(chat_id=update.effective_chat.id, photo=poster, caption=caption, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

# --- CALLBACK HANDLER ---
async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    data = query.data
    lang = get_lang(context, user_id)
    await query.answer()

    if data.startswith("setlang_"):
        context.user_data[user_id] = data.split("_")[1]
        welcome = STRINGS[context.user_data[user_id]]["welcome"].format(name=query.from_user.first_name)
        await query.edit_message_text(f"{welcome}\n\n{STRINGS[lang]['ads_disclaimer']}\n\n{STRINGS[lang]['commands']}", parse_mode='Markdown')

    elif data.startswith("select_"):
        imdb_id = data.split("_")[1]
        kb = [[InlineKeyboardButton(STRINGS[lang]["unlock"], url=SMART_LINK)]]
        msg = await query.message.reply_text(STRINGS[lang]["ad_msg"], reply_markup=InlineKeyboardMarkup(kb), parse_mode='Markdown')
        
        await asyncio.sleep(6) # Ad wait time
        await msg.edit_text("⏳ Processing Links...")
        await send_movie_info(update, context, imdb_id, lang)
        await msg.delete()

    elif data.startswith("srvlist_"):
        _, imdb_id, m_type = data.split("_")
        srv_kb = [
            [InlineKeyboardButton("📺 Server 1 (vidsrc.me)", url=f"https://vidsrc.me/embed/{m_type}?imdb={imdb_id}")],
            [InlineKeyboardButton("📺 Server 2 (vidsrc.xyz)", url=f"https://vidsrc.xyz/embed/{m_type}?imdb={imdb_id}")],
            [InlineKeyboardButton("📺 Server 3 (MultiEmbed)", url=f"https://multiembed.mov/directstream.php?video_id={imdb_id}")]
        ]
        await query.message.reply_text(STRINGS[lang]["select_server"], reply_markup=InlineKeyboardMarkup(srv_kb))

    elif data.startswith("gen_"):
        genre = data.split("_")[1]
        await search_engine(update, context, genre)

# --- COMMAND HANDLERS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton("🇱🇰 සිංහල", callback_data="setlang_si"),
                 InlineKeyboardButton("🇺🇸 English", callback_data="setlang_en")]]
    await update.message.reply_text("👋 Hello! Select language / භාෂාව තෝරන්න:", reply_markup=InlineKeyboardMarkup(keyboard))

async def ai_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args: return await update.message.reply_text("💡 Usage: `/ai robot movie 2024`")
    prompt = f"Identify movie/series name from: {' '.join(context.args)}. Return ONLY the name."
    res = ai_model.generate_content(prompt)
    await search_engine(update, context, res.text.strip())

async def trending(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = f"https://api.themoviedb.org/3/trending/all/day?api_key={TMDB_API_KEY}"
    res = requests.get(url).json().get('results', [])[:8]
    keyboard = [[InlineKeyboardButton(f"🔥 {m.get('title', m.get('name'))}", callback_data=f"select_{m.get('id')}")] for m in res]
    await update.message.reply_text("🔥 **Trending Movies Today**", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def show_genres(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton(GENRES[i], callback_data=f"gen_{GENRES[i]}"),
                 InlineKeyboardButton(GENRES[i+1], callback_data=f"gen_{GENRES[i+1]}")] for i in range(0, len(GENRES), 2)]
    await update.message.reply_text(STRINGS[get_lang(context, update.effective_user.id)]["genres_msg"], reply_markup=InlineKeyboardMarkup(keyboard))

if __name__ == '__main__':
    app = Application.builder().token(TOKEN).build()
    
    # Handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("ai", ai_search))
    app.add_handler(CommandHandler("series", lambda u, c: search_engine(u, c, " ".join(c.args), "series")))
    app.add_handler(CommandHandler("actor", lambda u, c: search_engine(u, c, " ".join(c.args))))
    app.add_handler(CommandHandler("year", lambda u, c: search_engine(u, c, "movie", year=c.args[0] if c.args else None)))
    app.add_handler(CommandHandler("trending", trending))
    app.add_handler(CommandHandler("genres", show_genres))
    app.add_handler(CallbackQueryHandler(button_click))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, lambda u, c: search_engine(u, c, u.message.text, "movie")))
    
    print("🚀 Flixel AI v52.0 Live - The Ultimate Millionaire Edition!")
    app.run_polling(drop_pending_updates=True)
