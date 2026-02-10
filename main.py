import os
import logging
import asyncio
import requests
import google.generativeai as genai
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

# --- CONFIGURATION ---
TOKEN = os.getenv('TOKEN')
TMDB_API_KEY = os.getenv('TMDB_API_KEY')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
SMART_LINK = "https://otieu.com/4/10513841" # Monetag Smart Link

# Gemini AI Setup
genai.configure(api_key=GEMINI_API_KEY)
ai_model = genai.GenerativeModel('gemini-2.0-flash')

logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)

STRINGS = {
    "si": {
        "welcome": "👋 ආයුබෝවන් {name}!\n\n🚀 **filxel AI v10.0**\nමම මූවී සොයා දෙන **FLIXEL** නිල බොට්.",
        "ads_disclaimer": "⚠️ **දැනුම්දීමයි:** අපේ සේවාව නොමිලේ දෙන නිසා දැන්වීම් (Ads) භාවිතා කරනවා. 🙏",
        "commands": "🔍 **සෙවුම් ක්‍රම:**\n• මූවී එකේ නම එවන්න \n• `/series` [නම] - TV Series විතරක්\n• `/actor` [නම] - නළුවා අනුව\n• `/year` [වසර] - වසර අනුව\n• `/find` [නම] [වසර] - නළුවා + වසර\n• `/trending` - අද ජනප්‍රිය",
        "ad_msg": "⚠️ **Security Check!**\n\nපහත Unlock බටන් එක ක්ලික් කරන්න. තත්පර 6කින් මූවී එක ලැබෙනු ඇත.",
        "unlock": "🔓 Unlock Content",
        "results": "📽️ **සෙවුම් ප්‍රතිඵල (Movies):**",
        "not_found": "❌ සොයාගත නොහැකි විය. නිවැරදි නම එවන්න."
    },
    "en": {
        "welcome": "👋 Hello {name}!\n\nWelcome to 🚀 **filxel AI v10.0**.\nOfficial **FLIXEL** movie bot.",
        "ads_disclaimer": "⚠️ **Note:** We use ads to keep this service free. 🙏",
        "commands": "🔍 **Commands:**\n• Send Movie Name \n• `/series` - TV Series Only\n• `/actor` - Actor Search\n• `/year` - Year Search\n• `/find` - Actor + Year\n• `/trending` - Trending Today",
        "ad_msg": "⚠️ **Security Check!**\n\nClick Unlock button. Ready in 6 seconds.",
        "unlock": "🔓 Unlock Content",
        "results": "📽️ **Search Results (Movies):**",
        "not_found": "❌ No results found."
    }
}

# --- SEARCH ENGINE CORE ---
async def search_engine(update, context, query, search_type=None, year=None, actor_name=None, limit=8):
    lang = context.user_data.get(update.effective_user.id, "en")
    
    # 1. Actor Search Logic (Limit 10 as requested)
    if actor_name:
        act_url = f"https://api.themoviedb.org/3/search/person?api_key={TMDB_API_KEY}&query={actor_name}"
        act_data = requests.get(act_url).json().get('results')
        if not act_data: return await update.message.reply_text(STRINGS[lang]["not_found"])
        act_id = act_data[0]['id']
        url = f"https://api.themoviedb.org/3/discover/movie?api_key={TMDB_API_KEY}&with_cast={act_id}&sort_by=popularity.desc"
        if year: url += f"&primary_release_year={year}"
        limit = 10
    
    # 2. Year Only Logic (Limit 10 as requested)
    elif search_type == "year_only":
        url = f"https://api.themoviedb.org/3/discover/movie?api_key={TMDB_API_KEY}&primary_release_year={year}&sort_by=popularity.desc"
        limit = 10
    
    # 3. TV Series Search (Strictly for /series command)
    elif search_type == "tv":
        url = f"https://api.themoviedb.org/3/search/tv?api_key={TMDB_API_KEY}&query={query}"
    
    # 4. MAIN FEATURE: Default Movie Search (Strictly Movies, Limit 8)
    else:
        url = f"https://api.themoviedb.org/3/search/movie?api_key={TMDB_API_KEY}&query={query}"

    try:
        data = requests.get(url).json().get('results', [])
        if data:
            keyboard = []
            for m in data[:limit]:
                m_type = "tv" if search_type == "tv" else "movie"
                full_name = m.get('title') or m.get('name')
                release_date = m.get('release_date') or m.get('first_air_date', 'N/A')
                year_val = release_date[:4] if release_date != 'N/A' else "N/A"
                
                icon = "🎬" if m_type == "movie" else "📺"
                keyboard.append([InlineKeyboardButton(f"{icon} {full_name} ({year_val})", callback_data=f"sl_{m_type}_{m['id']}")])
            
            if keyboard:
                msg_text = STRINGS[lang]["results"] if search_type != "tv" else "📽️ **TV Series Results:**"
                await update.message.reply_text(msg_text, reply_markup=InlineKeyboardMarkup(keyboard))
            else:
                await update.message.reply_text(STRINGS[lang]["not_found"])
        else:
            # AI Fuzzy Search Logic
            prompt = f"Extract only the correct movie title from this text: '{query}'. Return only the name."
            ai_res = ai_model.generate_content(prompt)
            await update.message.reply_text(f"❌ Not found. Did you mean: **{ai_res.text.strip()}**?")
    except:
        await update.message.reply_text("⚠️ API Error. Try again later.")

# --- CONTENT DISPLAY (POSTER VIEW) ---
async def send_media_info(update, context, m_type, tmdb_id, lang, s=None, e=None):
    res = requests.get(f"https://api.themoviedb.org/3/{m_type}/{tmdb_id}?api_key={TMDB_API_KEY}").json()
    poster = f"https://image.tmdb.org/t/p/w500{res.get('poster_path')}" if res.get('poster_path') else "https://via.placeholder.com/500x750"
    
    caption = (
        f"{'🎬' if m_type == 'movie' else '📺'} **{res.get('title') or res.get('name')}**\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"⭐ Rating: {res.get('vote_average')}/10\n"
        f"🎭 Genre: {res.get('genres')[0]['name'] if res.get('genres') else 'N/A'}\n"
    )
    if s: caption += f"📍 Season {s} | Episode {e}\n"
    caption += f"\n📝 Plot: _{res.get('overview')[:300]}..._\n"
    caption += f"━━━━━━━━━━━━━━━━━━━━━\n⚡ *Powered by filxel AI*"

    cb = f"srv_{m_type}_{tmdb_id}"
    if s: cb += f"_{s}_{e}"
    kb = [[InlineKeyboardButton("📺 Watch Online", callback_data=cb)]]
    await context.bot.send_photo(update.effective_chat.id, poster, caption=caption, reply_markup=InlineKeyboardMarkup(kb), parse_mode='Markdown')

# --- BUTTON HANDLER ---
async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    lang = context.user_data.get(query.from_user.id, "en")
    await query.answer()

    if data.startswith("setlang_"):
        l = data.split("_")[1]
        context.user_data[query.from_user.id] = l
        await query.edit_message_text(STRINGS[l]["welcome"].format(name=query.from_user.first_name) + "\n\n" + STRINGS[l]["commands"])

    elif data.startswith("sl_"):
        _, mt, tid = data.split("_")
        if mt == 'tv':
            res = requests.get(f"https://api.themoviedb.org/3/tv/{tid}?api_key={TMDB_API_KEY}").json()
            kb = [[InlineKeyboardButton(f"📅 Season {s['season_number']}", callback_data=f"ep_{tid}_{s['season_number']}")] for s in res.get('seasons', []) if s['season_number'] > 0]
            await query.message.reply_text("📅 Select Season:", reply_markup=InlineKeyboardMarkup(kb))
        else:
            msg = await query.message.reply_text(STRINGS[lang]["ad_msg"], reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(STRINGS[lang]["unlock"], url=SMART_LINK)]]))
            await asyncio.sleep(6); await msg.delete()
            await send_media_info(update, context, 'movie', tid, lang)

    elif data.startswith("ep_"):
        _, tid, s = data.split("_")
        res = requests.get(f"https://api.themoviedb.org/3/tv/{tid}/season/{s}?api_key={TMDB_API_KEY}").json()
        kb, row = [], []
        for e in res.get('episodes', []):
            row.append(InlineKeyboardButton(f"E{e['episode_number']}", callback_data=f"unl_{tid}_{s}_{e['episode_number']}"))
            if len(row) == 4: kb.append(row); row = []
        if row: kb.append(row)
        await query.message.reply_text("🎞️ Select Episode:", reply_markup=InlineKeyboardMarkup(kb))

    elif data.startswith("unl_"):
        _, tid, s, e = data.split("_")
        msg = await query.message.reply_text(STRINGS[lang]["ad_msg"], reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(STRINGS[lang]["unlock"], url=SMART_LINK)]]))
        await asyncio.sleep(6); await msg.delete()
        await send_media_info(update, context, 'tv', tid, lang, s, e)

    elif data.startswith("srv_"):
        p = data.split("_")
        ext = f"{p[1]}?tmdb={p[2]}"
        if len(p) > 3: ext += f"&season={p[3]}&episode={p[4]}"
        srvs = [
            [InlineKeyboardButton("📽️ Server 1", url=f"https://vidsrc.me/embed/{ext}")],
            [InlineKeyboardButton("📽️ Server 2", url=f"https://vidsrc.xyz/embed/{ext}")],
            [InlineKeyboardButton("📽️ Server 3 (Multi)", url=f"https://multiembed.mov/directstream.php?video_id={p[2]}&tmdb=1" + (f"&s={p[3]}&e={p[4]}" if len(p)>3 else ""))]
        ]
        await query.message.reply_text("📽️ Select Server:", reply_markup=InlineKeyboardMarkup(srvs))

# --- COMMAND HANDLERS ---
async def trending(update, context):
    url = f"https://api.themoviedb.org/3/trending/movie/day?api_key={TMDB_API_KEY}"
    res = requests.get(url).json().get('results', [])[:8]
    kb = [[InlineKeyboardButton(f"🔥 {m.get('title')} ({m.get('release_date')[:4]})", callback_data=f"sl_movie_{m['id']}")] for m in res]
    await update.message.reply_text("🔥 **Trending Movies Today**", reply_markup=InlineKeyboardMarkup(kb), parse_mode='Markdown')

if __name__ == '__main__':
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", lambda u, c: u.message.reply_text("Select Language:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🇱🇰 සිංහල", callback_data="setlang_si"), InlineKeyboardButton("🇺🇸 English", callback_data="setlang_en")]]))))
    app.add_handler(CommandHandler("series", lambda u, c: search_engine(u, c, " ".join(c.args), "tv") if c.args else None))
    app.add_handler(CommandHandler("actor", lambda u, c: search_engine(u, c, None, actor_name=" ".join(c.args), limit=10) if c.args else None))
    app.add_handler(CommandHandler("year", lambda u, c: search_engine(u, c, None, search_type="year_only", year=c.args[0], limit=10) if c.args else None))
    app.add_handler(CommandHandler("find", lambda u, c: search_engine(u, c, None, year=c.args[-1], actor_name=" ".join(c.args[:-1]), limit=10) if len(c.args) >= 2 else None))
    app.add_handler(CommandHandler("trending", trending))
    app.add_handler(CommandHandler("ai", lambda u, c: search_engine(u, c, ai_model.generate_content(f"Extract only movie name from: {' '.join(c.args)}").text.strip()) if c.args else None))
    app.add_handler(CallbackQueryHandler(button_click))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, lambda u, c: search_engine(u, c, u.message.text, limit=8)))
    
    print("🚀 filxel AI v10.0 - Movies Priority Edition Live!")
    app.run_polling()
