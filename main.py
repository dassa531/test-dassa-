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
SMART_LINK = "https://otieu.com/4/10513841" 

genai.configure(api_key=GEMINI_API_KEY)
ai_model = genai.GenerativeModel('gemini-2.0-flash')

logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)

STRINGS = {
    "si": {
        "welcome_name": "👋 ආයුබෝවන් {name}!\n\n🚀 **Flixel AI v38.0** වෙත සාදරයෙන් පිළිගනිමු.\nමම මූවී සොයා දෙන **filxel** නිල බොට්.",
        "lang_confirm": "✅ භාෂාව 'සිංහල' ලෙස තෝරාගත්තා.\n\n⚠️ **විශේෂ දැනුම්දීමයි:**\nමෙම බොට් එක නොමිලේ ලබාදෙන සේවාවක් බැවින් අපගේ වියදම් පියවා ගැනීමට දැන්වීම් (Ads) භාවිතා කරමු. මූවී එක ලබා ගැනීමට පෙර දැන්වීම් දර්ශනය වන බව කරුණාවෙන් සලකන්න. 🙏",
        "commands": "🔍 **ප්‍රධාන විධානයන්:**\n• නම එවන්න (සෙවීමට)\n• `/trending` - අද ජනප්‍රිය මූවීස්\n• `/genres` - වර්ගීකරණයන්\n• `/ai` - AI හරහා සෙවීමට",
        "ad_msg": "⚠️ **Security Check & Ads!**\n\nලින්ක් එක ලබා ගැනීමට පහත 'Unlock' බටන් එක ක්ලික් කර ඇඩ් එක බලන අතරතුර තත්පර 6ක් රැඳී සිටින්න.",
        "unlock": "🔓 Unlock Content (Support Us)",
        "unlocking": "⏳ Unlocking your content... Please wait...",
        "watch": "📺 ඔන්ලයින් බලන්න",
        "download": "📥 Download (Torrent)",
        "results": "📽️ සෙවුම් ප්‍රතිඵල (වඩාත්ම ගැලපෙන):",
        "not_found": "❌ කිසිවක් සොයාගත නොහැකි විය. කරුණාකර නිවැරදි නම එවන්න.",
        "genres_msg": "🎭 කැමති මූවී වර්ගයක් (Genre) තෝරාගන්න:",
        "seasons": "📅 Seasons තෝරන්න"
    },
    "en": {
        "welcome_name": "👋 Hello {name}!\n\nWelcome to 🚀 **Flixel AI v38.0**.\nI am the official **filxel** movie bot.",
        "lang_confirm": "✅ Language set to 'English'.\n\n⚠️ **Please Note:**\nThis is a free service, so we use ads to keep it running. Ads will be displayed before providing the content. Thank you for your support! 🙏",
        "commands": "🔍 **Main Commands:**\n• Send Name (Search)\n• `/trending` - Daily Trends\n• `/genres` - Categories\n• `/ai` - AI Search",
        "ad_msg": "⚠️ **Security Check & Ads!**\n\nTo get the link, click 'Unlock' below and wait for 6 seconds while the ad plays.",
        "unlock": "🔓 Unlock Content (Support Us)",
        "unlocking": "⏳ Unlocking your content... Please wait...",
        "watch": "📺 Watch Online",
        "download": "📥 Download (Torrent)",
        "results": "📽️ Search Results (Fuzzy Match):",
        "not_found": "❌ No results found. Please try a different name.",
        "genres_msg": "🎭 Select a Movie Category:",
        "seasons": "📅 Select Seasons"
    }
}

GENRE_LIST = ["Action", "Comedy", "Horror", "Sci-Fi", "Drama", "Animation", "Romance", "Thriller"]

# --- HELPER FUNCTIONS ---
def get_lang(context, user_id):
    return context.user_data.get(user_id, "en")

def get_yts_links(movie_title):
    try:
        yts_url = f"https://yts.mx/api/v2/list_movies.json?query_term={movie_title}"
        data = requests.get(yts_url).json()
        if data['data']['movie_count'] > 0:
            return data['data']['movies'][0].get('torrents', [])
        return []
    except: return []

# --- CONTENT SENDER ---
async def send_unlocked_content(update, context, data, lang):
    s = STRINGS[lang]
    chat_id = update.effective_chat.id

    if data.startswith("select_"):
        imdb_id = data.split("_")[1]
        m = requests.get(f"http://www.omdbapi.com/?i={imdb_id}&plot=full&apikey={OMDB_API_KEY}").json()
        title = m.get('Title', 'N/A')
        
        caption = (
            f"✅ **Unlocked Successfully!**\n\n"
            f"🎬 **{title} ({m.get('Year')})**\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"⭐ **Rating:** {m.get('imdbRating')}/10\n"
            f"🎭 **Genre:** {m.get('Genre')}\n"
            f"👥 **Cast:** {m.get('Actors')}\n\n"
            f"📝 **Plot:**\n_{m.get('Plot')[:400]}..._\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"⚡ *Powered by filxel AI*"
        )

        keyboard = [[InlineKeyboardButton(s["watch"], url=f"https://vidsrc.me/embed/movie?imdb={imdb_id}")]]
        yts = get_yts_links(title)
        for t in yts:
            keyboard.append([InlineKeyboardButton(f"📥 {t['quality']} ({t['size']})", url=t['url'])])
        
        poster = m.get('Poster') if m.get('Poster') != "N/A" else "https://via.placeholder.com/500x750"
        await context.bot.send_photo(chat_id=chat_id, photo=poster, caption=caption, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

    elif data.startswith("tmdb_movie_") or data.startswith("tv_"):
        prefix, *parts = data.split("_")
        tmdb_id = parts[-1]
        if prefix == "tv":
            m = requests.get(f"https://api.themoviedb.org/3/tv/{tmdb_id}?api_key={TMDB_API_KEY}").json()
            title = m.get('name')
            keyboard = [[InlineKeyboardButton(f"📅 Season {i}", callback_data=f"season_{tmdb_id}_{i}")] for i in range(1, m.get('number_of_seasons', 0)+1)]
        else:
            m = requests.get(f"https://api.themoviedb.org/3/movie/{tmdb_id}?api_key={TMDB_API_KEY}").json()
            title = m.get('title')
            keyboard = [[InlineKeyboardButton(s["watch"], url=f"https://vidsrc.me/embed/movie?tmdb={tmdb_id}")]]

        caption = f"✅ **Unlocked!**\n🎬 **{title}**\n\n{m.get('overview')[:450]}...\n\n⚡ *Powered by filxel AI*"
        poster = f"https://image.tmdb.org/t/p/w500{m['poster_path']}" if m.get('poster_path') else "https://via.placeholder.com/500x750"
        await context.bot.send_photo(chat_id=chat_id, photo=poster, caption=caption, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

# --- HANDLERS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.effective_user.first_name
    keyboard = [[InlineKeyboardButton("🇱🇰 සිංහල", callback_data="setlang_si"),
                 InlineKeyboardButton("🇺🇸 English", callback_data="setlang_en")]]
    await update.message.reply_text(f"👋 Hello {name}! Select language / භාෂාව තෝරන්න:", reply_markup=InlineKeyboardMarkup(keyboard))

async def show_genres(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = get_lang(context, update.effective_user.id)
    keyboard = []
    for i in range(0, len(GENRE_LIST), 2):
        row = [InlineKeyboardButton(GENRE_LIST[i], callback_data=f"gen_{GENRE_LIST[i]}")]
        if i+1 < len(GENRE_LIST): row.append(InlineKeyboardButton(GENRE_LIST[i+1], callback_data=f"gen_{GENRE_LIST[i+1]}"))
        keyboard.append(row)
    await update.message.reply_text(STRINGS[lang]["genres_msg"], reply_markup=InlineKeyboardMarkup(keyboard))

async def trending(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = f"https://api.themoviedb.org/3/trending/movie/day?api_key={TMDB_API_KEY}"
    res = requests.get(url).json().get('results', [])[:8]
    keyboard = [[InlineKeyboardButton(f"🔥 {m['title']} ({m.get('release_date','0000')[:4]})", callback_data=f"tmdb_movie_{m['id']}")] for m in res]
    await update.message.reply_text("🔥 **Trending Today**", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    name = query.from_user.first_name
    data = query.data
    lang = get_lang(context, user_id)
    s = STRINGS[lang]
    await query.answer()

    if data.startswith("setlang_"):
        l_code = data.split("_")[1]
        context.user_data[user_id] = l_code
        welcome = s["welcome_name"].format(name=name)
        await query.edit_message_text(f"{welcome}\n\n{s['lang_confirm']}\n\n{s['commands']}", parse_mode='Markdown')

    elif data.startswith(("select_", "tmdb_movie_", "tv_")):
        keyboard = [[InlineKeyboardButton(s["unlock"], url=SMART_LINK)]]
        msg = await query.message.reply_text(s["ad_msg"], reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
        await asyncio.sleep(6)
        await msg.edit_text(s["unlocking"])
        await asyncio.sleep(2)
        await send_unlocked_content(update, context, data, lang)
        await msg.delete()

    elif data.startswith("gen_"):
        genre = data.split("_")[1]
        await query.message.reply_text(f"🔍 Searching for **{genre}** movies...")
        update.message = query.message # Dummy update
        update.message.text = genre
        await handle_search(update, context)

async def handle_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = get_lang(context, update.effective_user.id)
    query = update.message.text
    # OMDB fuzzy search (s parameter handles close matches)
    m_res = requests.get(f"http://www.omdbapi.com/?s={query}&apikey={OMDB_API_KEY}").json()
    tv_res = requests.get(f"https://api.themoviedb.org/3/search/tv?api_key={TMDB_API_KEY}&query={query}").json().get('results', [])
    
    keyboard = []
    if m_res.get('Response') == 'True':
        for m in m_res.get('Search')[:5]:
            keyboard.append([InlineKeyboardButton(f"🎬 {m['Title']} ({m['Year']})", callback_data=f"select_{m['imdbID']}")])
    
    for tv in tv_res[:3]:
        year = tv.get('first_air_date', '0000')[:4]
        keyboard.append([InlineKeyboardButton(f"📺 {tv['name']} ({year})", callback_data=f"tv_{tv['id']}")])
    
    if keyboard:
        await update.message.reply_text(STRINGS[lang]["results"], reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        # Spelling correction via AI
        prompt = f"The user searched for '{query}' but no exact movie found. Suggest the closest real movie or TV show name only."
        try:
            res = ai_model.generate_content(prompt)
            suggest = res.text.strip()
            await update.message.reply_text(f"❌ Not found. Did you mean: **{suggest}**?\n(Try searching with that name)")
        except:
            await update.message.reply_text(STRINGS[lang]["not_found"])

if __name__ == '__main__':
    # මෙතන builder() එකට පස්සේ build() එක තියෙනවා නේද කියලා බලන්න
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("trending", trending))
    app.add_handler(CommandHandler("genres", show_genres))
    app.add_handler(CommandHandler("ai", ai_search))
    app.add_handler(CallbackQueryHandler(button_click))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_search))
    print("🚀 Flixel AI v38.0 Live - Professional Experience!")
    app.run_polling()
