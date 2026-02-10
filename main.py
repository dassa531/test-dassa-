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
        "welcome": "👋 ආයුබෝවන් {name}!\n\n🚀 **filxel AI v70.0** වෙත සාදරයෙන් පිළිගනිමු.\nමම මූවී සොයා දෙන **filxel** නිල බොට්.",
        "ads_disclaimer": "⚠️ **දැනුම්දීමයි:** අපේ සේවාව නොමිලේ දෙන නිසා දැන්වීම් (Ads) භාවිතා කරනවා. එය අපට සහයෝගයක්. 🙏",
        "commands": "🔍 **සෙවුම් ක්‍රම:**\n• නම එවන්න - සෙවීමට\n• `/series` [නම] - ටීවී සීරීස්\n• `/actor` [නම] - නළුවා අනුව\n• `/year` [වසර] - වසර අනුව\n• `/ai` - AI සෙවුම\n• `/trending` - ජනප්‍රිය මූවීස්",
        "ad_msg": "⚠️ **Security Check!**\n\nපහත Unlock බටන් එක ක්ලික් කර ඇඩ් එක බලන්න. තත්පර 6කින් මූවී එක Automatic Release වේවි.",
        "unlock": "🔓 Unlock Content (Auto Release)",
        "watch_main": "📺 Watch Online",
        "select_server": "📽️ **Select a Streaming Server**\nසර්වර් එකක් තෝරාගන්න:",
        "select_season": "📅 **Select Season**\nසීසන් එක තෝරන්න:",
        "select_episode": "🎞️ **Select Episode**\nඑපිසෝඩ් එක තෝරන්න:",
        "results": "📽️ **Search Results:**",
        "genres_msg": "🎭 කැමති මූවී වර්ගයක් තෝරන්න:",
        "not_found": "❌ සොයාගත නොහැකි විය. කරුණාකර නිවැරදි නම එවන්න."
    },
    "en": {
        "welcome": "👋 Hello {name}!\n\nWelcome to 🚀 **filxel AI v70.0**.\nOfficial **filxel** movie bot.",
        "ads_disclaimer": "⚠️ **Note:** We use ads to keep this service free. Your support is appreciated! 🙏",
        "commands": "🔍 **Search Commands:**\n• Send name - Search\n• `/series` [name] - TV Series\n• `/actor` [name] - By Actor\n• `/year` [year] - By Year\n• `/ai` - AI Search\n• `/trending` - Trending Now",
        "ad_msg": "⚠️ **Security Check!**\n\nClick Unlock button below. Your content will be automatically released in 6 seconds.",
        "unlock": "🔓 Unlock Content (Auto Release)",
        "watch_main": "📺 Watch Online",
        "select_server": "📽️ **Select a Streaming Server:**",
        "select_season": "📅 **Select Season:**",
        "select_episode": "🎞️ **Select Episode:**",
        "results": "📽️ **Search Results:**",
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
    # Using TMDB Multi-search for precision
    url = f"https://api.themoviedb.org/3/search/multi?api_key={TMDB_API_KEY}&query={query}"
    if year: url += f"&year={year}"
    
    res = requests.get(url).json().get('results', [])
    if res:
        keyboard = []
        for m in res[:10]:
            m_type = m.get('media_type', 'movie')
            if search_type and m_type != search_type: continue
            name = m.get('title') or m.get('name')
            release = (m.get('release_date') or m.get('first_air_date', 'N/A'))[:4]
            icon = "🎬" if m_type == 'movie' else "📺"
            keyboard.append([InlineKeyboardButton(f"{icon} {name} ({release})", callback_data=f"sl_{m_type}_{m['id']}")])
        
        if keyboard:
            await update.message.reply_text(STRINGS[lang]["results"], reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            await update.message.reply_text(STRINGS[lang]["not_found"])
    else:
        # Fuzzy AI Search Suggestion
        prompt = f"Identify movie/series name from user input: '{query}'. Return ONLY the correct title."
        ai_res = ai_model.generate_content(prompt)
        await update.message.reply_text(f"❌ Not found. Did you mean: **{ai_res.text.strip()}**?")

# --- CONTENT SENDER (POSTER VIEW) ---
async def send_media_info(update, context, m_type, tmdb_id, lang, s_num=None, e_num=None):
    # Fetch details from TMDB and OMDB for best info
    tmdb_url = f"https://api.themoviedb.org/3/{m_type}/{tmdb_id}?api_key={TMDB_API_KEY}&append_to_response=external_ids"
    tmdb_data = requests.get(tmdb_url).json()
    imdb_id = tmdb_data.get('external_ids', {}).get('imdb_id')
    
    # Get high quality poster
    poster_path = tmdb_data.get('poster_path')
    poster_url = f"https://image.tmdb.org/t/p/w500{poster_path}" if poster_path else "https://via.placeholder.com/500x750"
    
    name = tmdb_data.get('title') or tmdb_data.get('name')
    rating = tmdb_data.get('vote_average', 'N/A')
    genres = ", ".join([g['name'] for g in tmdb_data.get('genres', [])])
    plot = tmdb_data.get('overview', 'No description available.')

    caption = (
        f"🎬 **{name}**\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"⭐ **Rating:** {rating}/10\n"
        f"🎭 **Genre:** {genres}\n"
    )
    if s_num: caption += f"📍 **Season {s_num} | Episode {e_num}**\n"
    caption += f"\n📝 **Plot:**\n_{plot[:350]}..._\n"
    caption += f"━━━━━━━━━━━━━━━━━━━━━\n⚡ *Powered by filxel AI*"

    # Buttons
    cb_data = f"srvlist_{m_type}_{tmdb_id}"
    if s_num: cb_data += f"_{s_num}_{e_num}"
    
    keyboard = [[InlineKeyboardButton(STRINGS[lang]["watch_main"], callback_data=cb_data)]]
    
    # Torrent Download for Movies
    if m_type == 'movie':
        for t in get_yts(name):
            keyboard.append([InlineKeyboardButton(f"📥 Download {t['quality']} ({t['size']})", url=t['url'])])

    await context.bot.send_photo(chat_id=update.effective_chat.id, photo=poster_url, caption=caption, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

# --- HANDLERS ---
async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    lang = get_lang(context, query.from_user.id)
    await query.answer()

    if data.startswith("setlang_"):
        l_code = data.split("_")[1]
        context.user_data[query.from_user.id] = l_code
        welcome = STRINGS[l_code]["welcome"].format(name=query.from_user.first_name)
        await query.edit_message_text(f"{welcome}\n\n{STRINGS[l_code]['ads_disclaimer']}\n\n{STRINGS[l_code]['commands']}", parse_mode='Markdown')

    elif data.startswith("sl_"):
        _, m_type, tmdb_id = data.split("_")
        if m_type == 'tv':
            url = f"https://api.themoviedb.org/3/tv/{tmdb_id}?api_key={TMDB_API_KEY}"
            res = requests.get(url).json()
            seasons = res.get('seasons', [])
            kb = [[InlineKeyboardButton(f"📅 Season {s['season_number']}", callback_data=f"ep_{tmdb_id}_{s['season_number']}")] for s in seasons if s['season_number'] > 0]
            await query.message.reply_text(STRINGS[lang]["select_season"], reply_markup=InlineKeyboardMarkup(kb))
        else:
            kb = [[InlineKeyboardButton(STRINGS[lang]["unlock"], url=SMART_LINK)]]
            msg = await query.message.reply_text(STRINGS[lang]["ad_msg"], reply_markup=InlineKeyboardMarkup(kb))
            await asyncio.sleep(6) # Monetization sleep
            await msg.delete()
            await send_media_info(update, context, 'movie', tmdb_id, lang)

    elif data.startswith("ep_"):
        _, tmdb_id, s_num = data.split("_")
        url = f"https://api.themoviedb.org/3/tv/{tmdb_id}/season/{s_num}?api_key={TMDB_API_KEY}"
        res = requests.get(url).json()
        episodes = res.get('episodes', [])
        keyboard, row = [], []
        for e in episodes:
            row.append(InlineKeyboardButton(f"E{e['episode_number']}", callback_data=f"unlock_tv_{tmdb_id}_{s_num}_{e['episode_number']}"))
            if len(row) == 4:
                keyboard.append(row)
                row = []
        if row: keyboard.append(row)
        await query.message.reply_text(STRINGS[lang]["select_episode"], reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("unlock_tv_"):
        _, _, tmdb_id, s, e = data.split("_")
        kb = [[InlineKeyboardButton(STRINGS[lang]["unlock"], url=SMART_LINK)]]
        msg = await query.message.reply_text(STRINGS[lang]["ad_msg"], reply_markup=InlineKeyboardMarkup(kb))
        await asyncio.sleep(6)
        await msg.delete()
        await send_media_info(update, context, 'tv', tmdb_id, lang, s, e)

    elif data.startswith("srvlist_"):
        parts = data.split("_")
        m_type, tmdb_id = parts[1], parts[2]
        url_ext = f"{m_type}?tmdb={tmdb_id}"
        if len(parts) > 3: url_ext += f"&season={parts[3]}&episode={parts[4]}"
        
        srv_kb = [
            [InlineKeyboardButton("📽️ Server 1 (vidsrc.me)", url=f"https://vidsrc.me/embed/{url_ext}")],
            [InlineKeyboardButton("📽️ Server 2 (vidsrc.xyz)", url=f"https://vidsrc.xyz/embed/{url_ext}")],
            [InlineKeyboardButton("📽️ Server 3 (MultiEmbed)", url=f"https://multiembed.mov/directstream.php?video_id={tmdb_id}&tmdb=1" + (f"&s={parts[3]}&e={parts[4]}" if len(parts)>3 else ""))]
        ]
        await query.message.reply_text(STRINGS[lang]["select_server"], reply_markup=InlineKeyboardMarkup(srv_kb))

    elif data.startswith("gen_"):
        genre = data.split("_")[1]
        await search_engine(update, context, genre)

# --- COMMANDS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = [[InlineKeyboardButton("🇱🇰 සිංහල", callback_data="setlang_si"), InlineKeyboardButton("🇺🇸 English", callback_data="setlang_en")]]
    await update.message.reply_text("👋 Select Language / භාෂාව තෝරන්න:", reply_markup=InlineKeyboardMarkup(kb))

async def ai_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args: return await update.message.reply_text("💡 Usage: `/ai robot movie 2024`")
    prompt = f"Identify movie/series name from: {' '.join(context.args)}. Return ONLY the name."
    res = ai_model.generate_content(prompt)
    await search_engine(update, context, res.text.strip())

async def trending(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = f"https://api.themoviedb.org/3/trending/all/day?api_key={TMDB_API_KEY}"
    res = requests.get(url).json().get('results', [])[:8]
    keyboard = [[InlineKeyboardButton(f"🔥 {m.get('title', m.get('name'))} ({ (m.get('release_date') or m.get('first_air_date', ''))[:4] })", callback_data=f"sl_{m.get('media_type')}_{m['id']}")] for m in res]
    await update.message.reply_text("🔥 **Trending Today**", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def show_genres(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton(GENRES[i], callback_data=f"gen_{GENRES[i]}"),
                 InlineKeyboardButton(GENRES[i+1], callback_data=f"gen_{GENRES[i+1]}")] for i in range(0, len(GENRES), 2)]
    await update.message.reply_text(STRINGS[get_lang(context, update.effective_user.id)]["genres_msg"], reply_markup=InlineKeyboardMarkup(keyboard))

if __name__ == '__main__':
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("ai", ai_search))
    app.add_handler(CommandHandler("series", lambda u, c: search_engine(u, c, " ".join(c.args), "tv")))
    app.add_handler(CommandHandler("actor", lambda u, c: search_engine(u, c, " ".join(c.args))))
    app.add_handler(CommandHandler("year", lambda u, c: search_engine(u, c, "movie", year=c.args[0] if c.args else None)))
    app.add_handler(CommandHandler("trending", trending))
    app.add_handler(CommandHandler("genres", show_genres))
    app.add_handler(CallbackQueryHandler(button_click))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, lambda u, c: search_engine(u, c, u.message.text)))
    
    print("🚀 filxel AI v70.0 Live & Stable! [The Millionaire Edition]")
    app.run_polling(drop_pending_updates=True)
