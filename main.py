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
SMART_LINK = "https://otieu.com/4/10513841" # Monetag Link

# Gemini Setup
genai.configure(api_key=GEMINI_API_KEY)
ai_model = genai.GenerativeModel('gemini-2.0-flash')

logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)

STRINGS = {
    "si": {
        "welcome": "👋 ආයුබෝවන් {name}!\n\n🚀 **filxel AI v75.0** වෙත සාදරයෙන් පිළිගනිමු.\nමම මූවී සහ සීරීස් සොයා දෙන **filxel** නිල බොට්.",
        "ads_disclaimer": "⚠️ **දැනුම්දීමයි:** අපේ සේවාව නොමිලේ දෙන නිසා දැන්වීම් (Ads) භාවිතා කරනවා. 🙏",
        "commands": "🔍 **සෙවුම් ක්‍රම:**\n• නම එවන්න - ඕනෑම එකක් සෙවීමට\n• `/series` [නම] - **TV Series විතරක්ම** සෙවීමට\n• `/actor` [නම] - නළුවා අනුව\n• `/year` [වසර] - වසර අනුව\n• `/ai` - AI සෙවුම",
        "ad_msg": "⚠️ **Security Check!**\n\nපහත Unlock බටන් එක ක්ලික් කරන්න. තත්පර 6කින් අන්තර්ගතය විවෘත වේවි.",
        "unlock": "🔓 Unlock Content (Auto Release)",
        "watch_main": "📺 Watch Online",
        "select_server": "📽️ **Select a Streaming Server**\nසර්වර් එකක් තෝරාගන්න:",
        "select_season": "📅 **Select Season**\nසීසන් එක තෝරන්න:",
        "select_episode": "🎞️ **Select Episode**\nඑපිසෝඩ් එක තෝරන්න:",
        "results": "📽️ **සෙවුම් ප්‍රතිඵල:**",
        "not_found": "❌ සොයාගත නොහැකි විය. කරුණාකර නිවැරදි නම එවන්න."
    },
    "en": {
        "welcome": "👋 Hello {name}!\n\nWelcome to 🚀 **filxel AI v75.0**.\nOfficial **filxel** movie & series bot.",
        "ads_disclaimer": "⚠️ **Note:** We use ads to keep this service free. 🙏",
        "commands": "🔍 **Search Commands:**\n• Send name - Search all\n• `/series` [name] - **TV Series Only**\n• `/actor` [name] - By Actor\n• `/year` [year] - By Year\n• `/ai` - AI Search",
        "ad_msg": "⚠️ **Security Check!**\n\nClick Unlock button below. Releases in 6 seconds.",
        "unlock": "🔓 Unlock Content (Auto Release)",
        "watch_main": "📺 Watch Online",
        "select_server": "📽️ **Select a Streaming Server:**",
        "select_season": "📅 **Select Season:**",
        "select_episode": "🎞️ **Select Episode:**",
        "results": "📽️ **Search Results:**",
        "not_found": "❌ No results found. Check spelling."
    }
}

# --- HELPERS ---
def get_lang(context, user_id):
    return context.user_data.get(user_id, "en")

# --- CORE SEARCH ENGINE (Strict Filtering) ---
async def search_engine(update, context, query, search_type=None, year=None):
    lang = get_lang(context, update.effective_user.id)
    # Using TMDB Search (Multi or TV specific)
    base_url = "https://api.themoviedb.org/3/search/"
    endpoint = "tv" if search_type == "tv" else "multi"
    url = f"{base_url}{endpoint}?api_key={TMDB_API_KEY}&query={query}"
    
    if year: url += f"&first_air_date_year={year}" if search_type == "tv" else f"&year={year}"
    
    res = requests.get(url).json().get('results', [])
    if res:
        keyboard = []
        for m in res[:12]:
            m_type = m.get('media_type', 'tv' if search_type == "tv" else 'movie')
            
            # Additional check to ensure ONLY TV series if search_type is 'tv'
            if search_type == "tv" and m_type != "tv": continue
            if m_type == "person": continue # Skip actor results in list
            
            full_name = m.get('title') or m.get('name')
            release_date = m.get('release_date') or m.get('first_air_date', 'N/A')
            year_val = release_date[:4] if release_date != 'N/A' else "N/A"
            
            icon = "📺" if m_type == "tv" else "🎬"
            keyboard.append([InlineKeyboardButton(f"{icon} {full_name} ({year_val})", callback_data=f"sl_{m_type}_{m['id']}")])
        
        if keyboard:
            await update.message.reply_text(STRINGS[lang]["results"], reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            await update.message.reply_text(STRINGS[lang]["not_found"])
    else:
        await update.message.reply_text(STRINGS[lang]["not_found"])

# --- CONTENT SENDER (POSTER VIEW) ---
async def send_media_info(update, context, m_type, tmdb_id, lang, s_num=None, e_num=None):
    tmdb_url = f"https://api.themoviedb.org/3/{m_type}/{tmdb_id}?api_key={TMDB_API_KEY}"
    tmdb_data = requests.get(tmdb_url).json()
    
    poster_path = tmdb_data.get('poster_path')
    poster_url = f"https://image.tmdb.org/t/p/w500{poster_path}" if poster_path else "https://via.placeholder.com/500x750"
    
    name = tmdb_data.get('title') or tmdb_data.get('name')
    rating = round(tmdb_data.get('vote_average', 0), 1)
    plot = tmdb_data.get('overview', 'No description available.')

    caption = (
        f"{'🎬' if m_type == 'movie' else '📺'} **{name}**\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"⭐ **Rating:** {rating}/10\n"
        f"🎭 **Genre:** {tmdb_data.get('genres')[0]['name'] if tmdb_data.get('genres') else 'N/A'}\n"
    )
    if s_num: caption += f"📍 **Season {s_num} | Episode {e_num}**\n"
    caption += f"\n📝 **Plot:**\n_{plot[:350]}..._\n"
    caption += f"━━━━━━━━━━━━━━━━━━━━━\n⚡ *Powered by filxel AI*"

    cb_data = f"srvlist_{m_type}_{tmdb_id}"
    if s_num: cb_data += f"_{s_num}_{e_num}"
    
    keyboard = [[InlineKeyboardButton(STRINGS[lang]["watch_main"], callback_data=cb_data)]]
    await context.bot.send_photo(chat_id=update.effective_chat.id, photo=poster_url, caption=caption, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

# --- CALLBACKS ---
async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    lang = get_lang(context, query.from_user.id)
    await query.answer()

    if data.startswith("setlang_"):
        l_code = data.split("_")[1]
        context.user_data[query.from_user.id] = l_code
        await query.edit_message_text(STRINGS[l_code]["welcome"].format(name=query.from_user.first_name) + "\n\n" + STRINGS[l_code]["commands"], parse_mode='Markdown')

    elif data.startswith("sl_"):
        _, m_type, tmdb_id = data.split("_")
        if m_type == 'tv':
            res = requests.get(f"https://api.themoviedb.org/3/tv/{tmdb_id}?api_key={TMDB_API_KEY}").json()
            seasons = res.get('seasons', [])
            kb = [[InlineKeyboardButton(f"📅 Season {s['season_number']}", callback_data=f"ep_{tmdb_id}_{s['season_number']}")] for s in seasons if s['season_number'] > 0]
            await query.message.reply_text(STRINGS[lang]["select_season"], reply_markup=InlineKeyboardMarkup(kb))
        else:
            kb = [[InlineKeyboardButton(STRINGS[lang]["unlock"], url=SMART_LINK)]]
            msg = await query.message.reply_text(STRINGS[lang]["ad_msg"], reply_markup=InlineKeyboardMarkup(kb))
            await asyncio.sleep(6)
            await msg.delete()
            await send_media_info(update, context, 'movie', tmdb_id, lang)

    elif data.startswith("ep_"):
        _, tmdb_id, s_num = data.split("_")
        res = requests.get(f"https://api.themoviedb.org/3/tv/{tmdb_id}/season/{s_num}?api_key={TMDB_API_KEY}").json()
        episodes = res.get('episodes', [])
        keyboard, row = [], []
        for e in episodes:
            row.append(InlineKeyboardButton(f"E{e['episode_number']}", callback_data=f"unlock_tv_{tmdb_id}_{s_num}_{e['episode_number']}"))
            if len(row) == 4: keyboard.append(row); row = []
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
            [InlineKeyboardButton("📽️ Server 1", url=f"https://vidsrc.me/embed/{url_ext}")],
            [InlineKeyboardButton("📽️ Server 2", url=f"https://vidsrc.xyz/embed/{url_ext}")],
            [InlineKeyboardButton("📽️ Server 3 (MultiEmbed)", url=f"https://multiembed.mov/directstream.php?video_id={tmdb_id}&tmdb=1" + (f"&s={parts[3]}&e={parts[4]}" if len(parts)>3 else ""))]
        ]
        await query.message.reply_text(STRINGS[lang]["select_server"], reply_markup=InlineKeyboardMarkup(srv_kb))

# --- COMMANDS ---
async def start(update, context):
    kb = [[InlineKeyboardButton("🇱🇰 සිංහල", callback_data="setlang_si"), InlineKeyboardButton("🇺🇸 English", callback_data="setlang_en")]]
    await update.message.reply_text("👋 Select Language / භාෂාව තෝරන්න:", reply_markup=InlineKeyboardMarkup(kb))

async def series_cmd(update, context):
    if not context.args: return await update.message.reply_text("💡 Usage: `/series Money Heist`")
    await search_engine(update, context, " ".join(context.args), search_type="tv")

if __name__ == '__main__':
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("series", series_cmd))
    app.add_handler(CommandHandler("ai", lambda u, c: search_engine(u, c, " ".join(c.args)) if c.args else None))
    app.add_handler(CommandHandler("actor", lambda u, c: search_engine(u, c, " ".join(c.args))))
    app.add_handler(CommandHandler("year", lambda u, c: search_engine(u, c, "movie", year=c.args[0] if c.args else None)))
    app.add_handler(CallbackQueryHandler(button_click))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, lambda u, c: search_engine(u, c, u.message.text)))
    
    print("🚀 filxel AI v75.0 Live - TV Series Exclusive Mode!")
    app.run_polling(drop_pending_updates=True)
