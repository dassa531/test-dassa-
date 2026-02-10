import os
import logging
import requests
import google.generativeai as genai
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
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
        "welcome": "🚀 **Flixel AI v34.0**\n\nමම ඔයාට ඕනෑම මූවී එකක් හෝ TV Series එකක් සොයා දෙන බොට් කෙනෙක්.\n\n🔍 **විධානයන්:**\n• නම එවන්න (සෙවීමට)\n• නළුවා: `/actor [නම]`\n• වසර: `/year [වසර]`\n• AI සෙවුම: `/ai [විස්තරය]`\n• Trending: `🔥 Trending` ඔබන්න",
        "ad_msg": "⚠️ **Security Check!**\n\nලින්ක් එක ලබා ගැනීමට පහත 'Unlock' බටන් එක ක්ලික් කර තත්පර 5ක් රැඳී සිටින්න. ඉන්පසු ස්වයංක්‍රීයව මූවී එක ලැබෙනු ඇත.",
        "unlock": "🔓 Unlock Content (Auto-Release)",
        "watch": "📺 ඔන්ලයින් බලන්න",
        "results": "📽️ සෙවුම් ප්‍රතිඵල:",
        "not_found": "❌ කිසිවක් සොයාගත නොහැකි විය.",
        "seasons": "📅 Seasons තෝරන්න",
        "episodes": "📂 Episodes තෝරන්න"
    },
    "en": {
        "welcome": "🚀 **Flixel AI v34.0**\n\nI can help you find any Movie or TV Series.\n\n🔍 **Commands:**\n• Send Name (Search)\n• Actor: `/actor [name]`\n• Year: `/year [year]`\n• AI Search: `/ai [description]`\n• Trends: Press `🔥 Trending`",
        "ad_msg": "⚠️ **Security Check!**\n\nTo get the link, click 'Unlock' below and wait for 5 seconds. The content will be automatically released.",
        "unlock": "🔓 Unlock Content (Auto-Release)",
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

# --- AUTO RELEASE LOGIC ---
async def release_content(context: ContextTypes.DEFAULT_TYPE):
    job = context.job
    chat_id = job.chat_id
    data = job.data['data']
    lang = job.data['lang']
    s = STRINGS[lang]

    if data.startswith("select_"): # OMDB
        imdb_id = data.split("_")[1]
        m = requests.get(f"http://www.omdbapi.com/?i={imdb_id}&plot=full&apikey={OMDB_API_KEY}").json()
        keyboard = [[InlineKeyboardButton(s["watch"], url=f"https://vidsrc.me/embed/movie?imdb={imdb_id}")]]
        yts = get_yts_links(m.get('Title'))
        for t in yts: keyboard.append([InlineKeyboardButton(f"📥 {t['quality']} ({t['size']})", url=t['url'])])
        poster = m.get('Poster') if m.get('Poster') != "N/A" else "https://via.placeholder.com/500x750"
        await context.bot.send_photo(chat_id=chat_id, photo=poster, caption=f"✅ **Unlocked!**\n🎬 *{m.get('Title')}*\n⭐ IMDb: {m.get('imdbRating')}\n\n{m.get('Plot')[:500]}...", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

    elif data.startswith("tmdb_movie_"): # TMDB Movie
        tmdb_id = data.split("_")[2]
        m = requests.get(f"https://api.themoviedb.org/3/movie/{tmdb_id}?api_key={TMDB_API_KEY}").json()
        keyboard = [[InlineKeyboardButton(s["watch"], url=f"https://vidsrc.me/embed/movie?tmdb={tmdb_id}")]]
        poster = f"https://image.tmdb.org/t/p/w500{m['poster_path']}" if m.get('poster_path') else "https://via.placeholder.com/500x750"
        await context.bot.send_photo(chat_id=chat_id, photo=poster, caption=f"✅ **Unlocked!**\n🎬 *{m['title']}*\n\n{m['overview'][:500]}...", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

    elif data.startswith("tv_"): # TV Show
        tv_id = data.split("_")[1]
        m = requests.get(f"https://api.themoviedb.org/3/tv/{tv_id}?api_key={TMDB_API_KEY}").json()
        keyboard = [[InlineKeyboardButton(f"📅 Season {i}", callback_data=f"season_{tv_id}_{i}")] for i in range(1, m['number_of_seasons']+1)]
        poster = f"https://image.tmdb.org/t/p/w500{m['poster_path']}" if m.get('poster_path') else "https://via.placeholder.com/500x750"
        await context.bot.send_photo(chat_id=chat_id, photo=poster, caption=f"✅ **Unlocked!**\n📺 *{m['name']}*\n\n{s['seasons']}", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

# --- HANDLERS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton("🇱🇰 සිංහල", callback_data="setlang_si"),
                 InlineKeyboardButton("🇺🇸 English", callback_data="setlang_en")]]
    await update.message.reply_text("👋 Hello! Select language / භාෂාව තෝරන්න:", reply_markup=InlineKeyboardMarkup(keyboard))

async def ai_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = get_lang(context, update.effective_user.id)
    if not context.args:
        await update.message.reply_text("💡 විස්තරය ඇතුළත් කරන්න. (උදා: /ai පාවෙන නැවක් තියෙන මූවී එක)")
        return
    desc = " ".join(context.args)
    prompt = f"Identify the movie name from this description: {desc}. Return ONLY the name."
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
        await query.edit_message_text(STRINGS[lang_code]["welcome"], parse_mode='Markdown')

    elif data.startswith(("select_", "tmdb_movie_", "tv_")):
        # Unlock Button with Smart Link
        keyboard = [[InlineKeyboardButton(s["unlock"], url=SMART_LINK)]]
        await query.message.reply_text(s["ad_msg"], reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
        
        # ස්වයංක්‍රීයව රිලීස් කරන Job එකක් පටන් ගන්නවා (තත්පර 6කින්)
        context.job_queue.run_once(release_content, 6, data={'data': data, 'lang': lang}, chat_id=query.message.chat_id)

    elif data == "trending":
        url = f"https://api.themoviedb.org/3/trending/movie/day?api_key={TMDB_API_KEY}"
        res = requests.get(url).json().get('results', [])[:8]
        keyboard = [[InlineKeyboardButton(f"🔥 {m['title']}", callback_data=f"tmdb_movie_{m['id']}")] for m in res]
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
        for m in m_res.get('Search')[:4]: keyboard.append([InlineKeyboardButton(f"🎬 {m['Title']}", callback_data=f"select_{m['imdbID']}")])
    for tv in tv_res[:4]: keyboard.append([InlineKeyboardButton(f"📺 {tv['name']}", callback_data=f"tv_{tv['id']}")])
    
    if keyboard: await update.message.reply_text(STRINGS[lang]["results"], reply_markup=InlineKeyboardMarkup(keyboard))
    else: await update.message.reply_text(STRINGS[lang]["not_found"])

if __name__ == '__main__':
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("ai", ai_search))
    app.add_handler(CallbackQueryHandler(button_click))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_search))
    print("🚀 Flixel AI v34.0 Live - Professional Auto-Unlock!")
    app.run_polling()
