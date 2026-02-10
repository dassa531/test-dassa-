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

# Monetag Smart Link එක මෙතනට දාන්න
SMART_LINK = "https://your-monetag-smartlink-url.com" 

genai.configure(api_key=GEMINI_API_KEY)
ai_model = genai.GenerativeModel('gemini-2.0-flash')

logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)

STRINGS = {
    "si": {
        "welcome": "🚀 **Flixel AI v37.0**\n\nමම මූවී සොයා දෙන **filxel** නිල බොට්.\n\n🔍 **විධානයන්:**\n• නම එවන්න (සෙවීමට)\n• AI සෙවුම: `/ai [විස්තරය]`\n• Trending: `🔥 Trending` ඔබන්න",
        "ad_msg": "⚠️ **Security Check!**\n\nපහත බටන් එක ක්ලික් කර ඇඩ් එක බලන අතරතුර අපි ඔබේ මූවී එක සූදානම් කරනවා. තත්පර 5කින් මෙය ස්වයංක්‍රීයව Unlock වේවි.",
        "unlock": "🔓 Unlock Content (Auto)",
        "unlocking": "⏳ Unlocking your content... Please wait...",
        "watch": "📺 ඔන්ලයින් බලන්න",
        "results": "📽️ සෙවුම් ප්‍රතිඵල:",
        "not_found": "❌ කිසිවක් සොයාගත නොහැකි විය.",
        "seasons": "📅 Seasons තෝරන්න",
        "episodes": "📂 Episodes තෝරන්න"
    },
    "en": {
        "welcome": "🚀 **Flixel AI v37.0**\n\nI am the official **filxel** movie bot.\n\n🔍 **Commands:**\n• Send Name (Search)\n• AI Search: `/ai [description]`\n• Trends: Press `🔥 Trending`",
        "ad_msg": "⚠️ **Security Check!**\n\nClick below to unlock. Your movie will be automatically displayed in 5 seconds.",
        "unlock": "🔓 Unlock Content (Auto)",
        "unlocking": "⏳ Unlocking your content... Please wait...",
        "watch": "📺 Watch Online",
        "results": "📽️ Search Results:",
        "not_found": "❌ No results found.",
        "seasons": "📅 Select Seasons",
        "episodes": "📂 Select Episodes"
    }
}

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

# --- BEAUTIFUL CONTENT SENDER (THE UNLOCKER) ---
async def send_unlocked_content(update, context, data, lang):
    s = STRINGS[lang]
    chat_id = update.effective_chat.id

    if data.startswith("select_"): # OMDB Data
        imdb_id = data.split("_")[1]
        m = requests.get(f"http://www.omdbapi.com/?i={imdb_id}&plot=full&apikey={OMDB_API_KEY}").json()
        
        title = m.get('Title', 'N/A')
        year = m.get('Year', 'N/A')
        rating = m.get('imdbRating', 'N/A')
        genre = m.get('Genre', 'N/A')
        runtime = m.get('Runtime', 'N/A')
        actors = m.get('Actors', 'N/A')
        plot = m.get('Plot', 'No plot available.')

        caption = (
            f"✅ **Unlocked Successfully!**\n\n"
            f"🎬 **{title} ({year})**\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"⭐ **Rating:** {rating}/10\n"
            f"🎭 **Genre:** {genre}\n"
            f"⏳ **Runtime:** {runtime}\n"
            f"👥 **Cast:** {actors}\n\n"
            f"📝 **Plot:**\n_{plot[:400]}..._\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"⚡ *Powered by filxel AI*"
        )

        keyboard = [[InlineKeyboardButton(s["watch"], url=f"https://vidsrc.me/embed/movie?imdb={imdb_id}")]]
        yts = get_yts_links(title)
        for t in yts:
            keyboard.append([InlineKeyboardButton(f"📥 {t['quality']} ({t['size']})", url=t['url'])])
        
        poster = m.get('Poster') if m.get('Poster') != "N/A" else "https://via.placeholder.com/500x750"
        await context.bot.send_photo(chat_id=chat_id, photo=poster, caption=caption, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

    elif data.startswith("tmdb_movie_") or data.startswith("tv_"): # TMDB Data
        prefix, *parts = data.split("_")
        tmdb_id = parts[-1]
        
        if prefix == "tv":
            m = requests.get(f"https://api.themoviedb.org/3/tv/{tmdb_id}?api_key={TMDB_API_KEY}").json()
            title = m.get('name', 'N/A')
            year = m.get('first_air_date', '0000')[:4]
            desc = f"📅 **Seasons:** {m.get('number_of_seasons')}\n📂 **Episodes:** {m.get('number_of_episodes')}"
            keyboard = [[InlineKeyboardButton(f"📅 Season {i}", callback_data=f"season_{tmdb_id}_{i}")] for i in range(1, m.get('number_of_seasons', 0)+1)]
        else:
            m = requests.get(f"https://api.themoviedb.org/3/movie/{tmdb_id}?api_key={TMDB_API_KEY}").json()
            title = m.get('title', 'N/A')
            year = m.get('release_date', '0000')[:4]
            desc = f"⭐ **Popularity:** {m.get('popularity')}"
            keyboard = [[InlineKeyboardButton(s["watch"], url=f"https://vidsrc.me/embed/movie?tmdb={tmdb_id}")]]

        caption = (
            f"✅ **Unlocked Successfully!**\n\n"
            f"🎬 **{title} ({year})**\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"{desc}\n\n"
            f"📝 **Plot:**\n_{m.get('overview', 'No plot available.')[:450]}..._\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"⚡ *Powered by filxel AI*"
        )

        poster = f"https://image.tmdb.org/t/p/w500{m['poster_path']}" if m.get('poster_path') else "https://via.placeholder.com/500x750"
        await context.bot.send_photo(chat_id=chat_id, photo=poster, caption=caption, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

# --- HANDLERS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton("🇱🇰 සිංහල", callback_data="setlang_si"),
                 InlineKeyboardButton("🇺🇸 English", callback_data="setlang_en")]]
    await update.message.reply_text("👋 Hello! Select language / භාෂාව තෝරන්න:", reply_markup=InlineKeyboardMarkup(keyboard))

async def ai_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = get_lang(context, update.effective_user.id)
    if not context.args:
        await update.message.reply_text("💡 විස්තරය ඇතුළත් කරන්න. (උදා: /ai space movie with robots)")
        return
    desc = " ".join(context.args)
    prompt = f"Identify the movie/series name from this description: {desc}. Return ONLY the name."
    try:
        response = ai_model.generate_content(prompt)
        movie_name = response.text.strip()
        await update.message.reply_text(f"🔍 AI Suggestion: **{movie_name}**")
        update.message.text = movie_name
        await handle_search(update, context)
    except: await update.message.reply_text("❌ AI Error.")

async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    data = query.data
    lang = get_lang(context, user_id)
    s = STRINGS[lang]
    await query.answer()

    if data.startswith("setlang_"):
        lang_code = data.split("_")[1]
        context.user_data[user_id] = lang_code
        keyboard = [[InlineKeyboardButton("🔥 Trending", callback_data="trending")]]
        await query.edit_message_text(STRINGS[lang_code]["welcome"], reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

    elif data.startswith(("select_", "tmdb_movie_", "tv_")):
        keyboard = [[InlineKeyboardButton(s["unlock"], url=SMART_LINK)]]
        msg = await query.message.reply_text(s["ad_msg"], reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
        
        await asyncio.sleep(5) # ඇඩ් එක බලන කාලය
        await msg.edit_text(s["unlocking"])
        await asyncio.sleep(2)
        
        await send_unlocked_content(update, context, data, lang)
        await msg.delete()

    elif data == "trending":
        url = f"https://api.themoviedb.org/3/trending/movie/day?api_key={TMDB_API_KEY}"
        res = requests.get(url).json().get('results', [])[:8]
        keyboard = [[InlineKeyboardButton(f"🔥 {m['title']} ({m.get('release_date','0000')[:4]})", callback_data=f"tmdb_movie_{m['id']}")] for m in res]
        await query.message.reply_text("🔥 **Trending Today**", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

    elif data.startswith("season_"):
        _, tv_id, s_num = data.split("_")
        m = requests.get(f"https://api.themoviedb.org/3/tv/{tv_id}/season/{s_num}?api_key={TMDB_API_KEY}").json()
        keyboard = []
        for ep in m.get('episodes', [])[:20]:
            watch_url = f"https://vidsrc.me/embed/tv?tmdb={tv_id}&sea={s_num}&epi={ep['episode_number']}"
            keyboard.append([InlineKeyboardButton(f"E{ep['episode_number']} - {ep['name']}", url=watch_url)])
        await query.message.reply_text(f"📂 *S{s_num} Episodes*", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def handle_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = get_lang(context, update.effective_user.id)
    query = update.message.text
    
    m_res = requests.get(f"http://www.omdbapi.com/?s={query}&apikey={OMDB_API_KEY}").json()
    tv_res = requests.get(f"https://api.themoviedb.org/3/search/tv?api_key={TMDB_API_KEY}&query={query}").json().get('results', [])
    
    keyboard = []
    if m_res.get('Response') == 'True':
        for m in m_res.get('Search')[:5]:
            # නම සමඟ වසර පෙන්වීම
            keyboard.append([InlineKeyboardButton(f"🎬 {m['Title']} ({m['Year']})", callback_data=f"select_{m['imdbID']}")])
    
    for tv in tv_res[:3]:
        year = tv.get('first_air_date', '0000')[:4]
        keyboard.append([InlineKeyboardButton(f"📺 {tv['name']} ({year})", callback_data=f"tv_{tv['id']}")])
    
    if keyboard: await update.message.reply_text(STRINGS[lang]["results"], reply_markup=InlineKeyboardMarkup(keyboard))
    else: await update.message.reply_text(STRINGS[lang]["not_found"])

if __name__ == '__main__':
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("ai", ai_search))
    app.add_handler(CallbackQueryHandler(button_click))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_search))
    print("🚀 Flixel AI v37.0 Live - Professional Filxel Experience!")
    app.run_polling()
