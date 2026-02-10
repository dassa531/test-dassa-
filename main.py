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
        "welcome": "👋 ආයුබෝවන් {name}!\n\n🚀 **Flixel AI v60.0** වෙත සාදරයෙන් පිළිගනිමු.\nමම මූවී සොයා දෙන **filxel** [2026-02-10] නිල බොට්.",
        "ads_disclaimer": "⚠️ **දැනුම්දීමයි:** අපේ සේවාව නොමිලේ දෙන නිසා දැන්වීම් (Ads) භාවිතා කරනවා. 🙏",
        "commands": "🔍 **සෙවුම් ක්‍රම:**\n• නම එවන්න - සෙවීමට\n• `/ai` | `/series` | `/actor` | `/year` | `/trending`",
        "ad_msg": "⚠️ **Security Check!**\n\nපහත Unlock බටන් එක ක්ලික් කරන්න. තත්පර 6කින් අන්තර්ගතය විවෘත වේවි.",
        "unlock": "🔓 Unlock Content (Auto Release)",
        "watch_main": "📺 Watch Online (Streaming)",
        "select_server": "📽️ කැමති සර්වර් එකක් තෝරාගන්න:",
        "select_season": "📅 Season එක තෝරන්න:",
        "select_episode": "🎞️ Episode එක තෝරන්න:",
        "results": "📽️ සෙවුම් ප්‍රතිඵල:",
        "genres_msg": "🎭 කැමති මූවී වර්ගයක් තෝරන්න:",
        "not_found": "❌ සොයාගත නොහැකි විය. කරුණාකර නිවැරදි නම එවන්න."
    },
    "en": {
        "welcome": "👋 Hello {name}!\n\nWelcome to 🚀 **Flixel AI v60.0**.\nOfficial **filxel** [2026-02-10] movie bot.",
        "ads_disclaimer": "⚠️ **Note:** We use ads to keep this service free. 🙏",
        "commands": "🔍 **Search Commands:**\n• Send name - Search\n• `/ai` | `/series` | `/actor` | `/year` | `/trending`",
        "ad_msg": "⚠️ **Security Check!**\n\nClick Unlock. Content will be open in 6 seconds.",
        "unlock": "🔓 Unlock Content (Auto Release)",
        "watch_main": "📺 Watch Online (Streaming)",
        "select_server": "📽️ Select a Streaming Server:",
        "select_season": "📅 Select Season:",
        "select_episode": "🎞️ Select Episode:",
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
    # Using TMDB for better multi-search (Movie & TV)
    url = f"https://api.themoviedb.org/3/search/multi?api_key={TMDB_API_KEY}&query={query}"
    if year: url += f"&year={year}"
    
    res = requests.get(url).json().get('results', [])
    if res:
        keyboard = []
        for m in res[:8]:
            m_type = m.get('media_type', 'movie')
            if search_type and m_type != search_type: continue
            name = m.get('title') or m.get('name')
            release = m.get('release_date') or m.get('first_air_date', 'N/A')
            icon = "🎬" if m_type == 'movie' else "📺"
            keyboard.append([InlineKeyboardButton(f"{icon} {name} ({release[:4]})", callback_data=f"sl_{m_type}_{m['id']}")])
        await update.message.reply_text(STRINGS[lang]["results"], reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        # Fuzzy AI Search
        prompt = f"Identify movie name from: {query}. Return ONLY the correct title."
        ai_res = ai_model.generate_content(prompt)
        await update.message.reply_text(f"❌ Not found. Did you mean: **{ai_res.text.strip()}**?")

# --- TV SERIES HANDLERS ---
async def show_seasons(query, tmdb_id, lang):
    url = f"https://api.themoviedb.org/3/tv/{tmdb_id}?api_key={TMDB_API_KEY}"
    res = requests.get(url).json()
    seasons = res.get('seasons', [])
    keyboard = []
    for s in seasons:
        if s['season_number'] > 0:
            keyboard.append([InlineKeyboardButton(f"📅 Season {s['season_number']}", callback_data=f"ep_{tmdb_id}_{s['season_number']}")])
    await query.message.reply_text(STRINGS[lang]["select_season"], reply_markup=InlineKeyboardMarkup(keyboard))

async def show_episodes(query, tmdb_id, season_num, lang):
    url = f"https://api.themoviedb.org/3/tv/{tmdb_id}/season/{season_num}?api_key={TMDB_API_KEY}"
    res = requests.get(url).json()
    episodes = res.get('episodes', [])
    keyboard = []
    row = []
    for e in episodes:
        row.append(InlineKeyboardButton(f"E{e['episode_number']}", callback_data=f"stream_tv_{tmdb_id}_{season_num}_{e['episode_number']}"))
        if len(row) == 4:
            keyboard.append(row)
            row = []
    if row: keyboard.append(row)
    await query.message.reply_text(STRINGS[lang]["select_episode"], reply_markup=InlineKeyboardMarkup(keyboard))

# --- CONTENT SENDER ---
async def send_media_info(update, context, m_type, tmdb_id, lang, s_num=None, e_num=None):
    # Get detailed info from TMDB
    url = f"https://api.themoviedb.org/3/{m_type}/{tmdb_id}?api_key={TMDB_API_KEY}"
    m = requests.get(url).json()
    name = m.get('title') or m.get('name')
    
    # Get IMDb ID for OMDB Plot/Rating (if needed) or just use TMDB
    imdb_id = m.get('external_ids', {}).get('imdb_id') or m.get('imdb_id')
    
    caption = (
        f"✅ **Unlocked Successfully!**\n\n"
        f"🎬 **{name}**\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"⭐ **Rating:** {m.get('vote_average')}/10\n"
        f"🎭 **Genre:** {m.get('genres')[0]['name'] if m.get('genres') else 'N/A'}\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"⚡ *Powered by filxel AI*"
    )
    if s_num: caption += f"\n📍 **Season {s_num} | Episode {e_num}**"

    # Watch Button
    cb_data = f"srvlist_{m_type}_{tmdb_id}"
    if s_num: cb_data += f"_{s_num}_{e_num}"
    
    keyboard = [[InlineKeyboardButton(STRINGS[lang]["watch_main"], callback_data=cb_data)]]
    
    # Download for Movies
    if m_type == 'movie':
        for t in get_yts(name):
            keyboard.append([InlineKeyboardButton(f"📥 Download {t['quality']} ({t['size']})", url=t['url'])])

    poster = f"https://image.tmdb.org/t/p/w500{m.get('poster_path')}" if m.get('poster_path') else "https://via.placeholder.com/500x750"
    await context.bot.send_photo(chat_id=update.effective_chat.id, photo=poster, caption=caption, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

# --- BUTTON CLICK HANDLER ---
async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    lang = get_lang(context, query.from_user.id)
    await query.answer()

    if data.startswith("setlang_"):
        context.user_data[query.from_user.id] = data.split("_")[1]
        welcome = STRINGS[context.user_data[query.from_user.id]]["welcome"].format(name=query.from_user.first_name)
        await query.edit_message_text(f"{welcome}\n\n{STRINGS[lang]['commands']}", parse_mode='Markdown')

    elif data.startswith("sl_"):
        _, m_type, tmdb_id = data.split("_")
        if m_type == 'tv':
            await show_seasons(query, tmdb_id, lang)
        else:
            # Monetization
            kb = [[InlineKeyboardButton(STRINGS[lang]["unlock"], url=SMART_LINK)]]
            msg = await query.message.reply_text(STRINGS[lang]["ad_msg"], reply_markup=InlineKeyboardMarkup(kb))
            await asyncio.sleep(6)
            await msg.delete()
            await send_media_info(update, context, 'movie', tmdb_id, lang)

    elif data.startswith("ep_"):
        _, tmdb_id, s_num = data.split("_")
        await show_episodes(query, tmdb_id, s_num, lang)

    elif data.startswith("stream_tv_"):
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
            [InlineKeyboardButton("📺 Server 1 (vidsrc.me)", url=f"https://vidsrc.me/embed/{url_ext}")],
            [InlineKeyboardButton("📺 Server 2 (vidsrc.xyz)", url=f"https://vidsrc.xyz/embed/{url_ext}")],
            [InlineKeyboardButton("📺 Server 3 (MultiEmbed)", url=f"https://multiembed.mov/directstream.php?video_id={tmdb_id}&tmdb=1" + (f"&s={parts[3]}&e={parts[4]}" if len(parts)>3 else ""))]
        ]
        await query.message.reply_text(STRINGS[lang]["select_server"], reply_markup=InlineKeyboardMarkup(srv_kb))

# --- COMMANDS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = [[InlineKeyboardButton("🇱🇰 සිංහල", callback_data="setlang_si"), InlineKeyboardButton("🇺🇸 English", callback_data="setlang_en")]]
    await update.message.reply_text("👋 Select Language:", reply_markup=InlineKeyboardMarkup(kb))

async def ai_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args: return
    query = " ".join(context.args)
    prompt = f"Identify movie/series name from: {query}. Return ONLY the name."
    res = ai_model.generate_content(prompt)
    await search_engine(update, context, res.text.strip())

async def trending(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = f"https://api.themoviedb.org/3/trending/all/day?api_key={TMDB_API_KEY}"
    res = requests.get(url).json().get('results', [])[:8]
    keyboard = [[InlineKeyboardButton(f"🔥 {m.get('title', m.get('name'))}", callback_data=f"sl_{m.get('media_type')}_{m['id']}")] for m in res]
    await update.message.reply_text("🔥 **Trending Today**", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

if __name__ == '__main__':
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("ai", ai_search))
    app.add_handler(CommandHandler("trending", trending))
    app.add_handler(CommandHandler("series", lambda u, c: search_engine(u, c, " ".join(c.args), "tv")))
    app.add_handler(CommandHandler("actor", lambda u, c: search_engine(u, c, " ".join(c.args))))
    app.add_handler(CommandHandler("year", lambda u, c: search_engine(u, c, "movie", year=c.args[0] if c.args else None)))
    app.add_handler(CallbackQueryHandler(button_click))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, lambda u, c: search_engine(u, c, u.message.text)))
    
    print("🚀 Flixel AI v60.0 Live & Stable!")
    app.run_polling(drop_pending_updates=True)
