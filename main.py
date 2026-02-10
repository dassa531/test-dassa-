import os
import logging
import requests
import google.generativeai as genai
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

# --- CONFIGURATION ---
TOKEN = os.getenv('TOKEN')
OMDB_API_KEY = os.getenv('OMDB_API_KEY')
TMDB_API_KEY = os.getenv('TMDB_API_KEY')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')

# --- MONETIZATION CONFIG ---
# Monetag එකෙන් ගන්නා Smart Link එක මෙතනට දාන්න
SMART_LINK = "https://your-monetag-smartlink-url.com" 

genai.configure(api_key=GEMINI_API_KEY)
ai_model = genai.GenerativeModel('gemini-2.0-flash')

logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)

# භාෂාව අනුව මැසේජ් පද්ධතිය
STRINGS = {
    "si": {
        "welcome": "🚀 **Flixel AI v32.0**\n\nමම ඔයාට ඕනෑම මූවී එකක් හෝ TV Series එකක් සොයා දෙන බොට් කෙනෙක්.\n\n🔍 **විධානයන්:**\n• නම එවන්න (Search)\n• නළුවා අනුව: `/actor [නම]`\n• වසර අනුව: `/year [වසර]`\n• AI සෙවුම: `/ai [විස්තරය]`\n• Trending: `🔥 Trending` ඔබන්න",
        "desc_title": "📝 **විස්තරය:**",
        "watch": "📺 ඔන්ලයින් බලන්න",
        "download": "📥 ඩවුන්ලෝඩ්",
        "ad_msg": "⚠️ **Security Check!**\n\nලින්ක් එක ලබා ගැනීමට පහත 'Unlock' බටන් එක ක්ලික් කර තත්පර 5ක් රැඳී සිට නැවත මූවී එක තෝරන්න.",
        "unlock": "🔓 Unlock Content",
        "results": "📽️ සෙවුම් ප්‍රතිඵල:",
        "not_found": "❌ කිසිවක් සොයාගත නොහැකි විය.",
        "seasons": "📅 Seasons තෝරන්න",
        "episodes": "📂 Episodes තෝරන්න"
    },
    "en": {
        "welcome": "🚀 **Flixel AI v32.0**\n\nI can help you find any Movie or TV Series.\n\n🔍 **Commands:**\n• Send Name (Search)\n• Actor: `/actor [name]`\n• Year: `/year [year]`\n• AI Search: `/ai [description]`\n• Trends: Press `🔥 Trending`",
        "desc_title": "📝 **Description:**",
        "watch": "📺 Watch Online",
        "download": "📥 Download",
        "ad_msg": "⚠️ **Security Check!**\n\nTo get the link, click 'Unlock' below, wait 5 seconds, and then select the movie again.",
        "unlock": "🔓 Unlock Content",
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

# --- AI SEARCH HANDLER ---
async def ai_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = get_lang(context, update.effective_user.id)
    if not context.args:
        await update.message.reply_text("💡 Please describe the movie after /ai (e.g., /ai movie about space and robots)")
        return
    
    description = " ".join(context.args)
    prompt = f"Identify the movie/series name from this description: {description}. Return ONLY the name."
    
    try:
        response = ai_model.generate_content(prompt)
        movie_name = response.text.strip()
        await update.message.reply_text(f"🔍 AI Suggestion: **{movie_name}**\nSearching...")
        update.message.text = movie_name
        await handle_search(update, context)
    except Exception as e:
        await update.message.reply_text("❌ AI Error. Please try again.")

# --- CORE HANDLERS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton("🇱🇰 සිංහල", callback_data="setlang_si"),
                 InlineKeyboardButton("🇺🇸 English", callback_data="setlang_en")]]
    await update.message.reply_text("👋 Hello! Please select your language / භාෂාව තෝරන්න:", 
                                  reply_markup=InlineKeyboardMarkup(keyboard))

async def actor_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = get_lang(context, update.effective_user.id)
    if not context.args:
        await update.message.reply_text("❌ Please provide an actor name!")
        return
    name = " ".join(context.args)
    res = requests.get(f"https://api.themoviedb.org/3/search/person?api_key={TMDB_API_KEY}&query={name}").json()
    if res.get('results'):
        p_id = res['results'][0]['id']
        movies = requests.get(f"https://api.themoviedb.org/3/person/{p_id}/movie_credits?api_key={TMDB_API_KEY}").json()
        cast = sorted(movies.get('cast', []), key=lambda x: x.get('popularity', 0), reverse=True)[:8]
        keyboard = [[InlineKeyboardButton(f"🎬 {m['title']} ({m.get('release_date','0000')[:4]})", callback_data=f"tmdb_movie_{m['id']}")] for m in cast]
        await update.message.reply_text(f"🎭 **Movies of {name}:**", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    else:
        await update.message.reply_text(STRINGS[lang]["not_found"])

async def year_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = get_lang(context, update.effective_user.id)
    if not context.args:
        await update.message.reply_text("❌ Please provide a year!")
        return
    year = context.args[0]
    url = f"https://api.themoviedb.org/3/discover/movie?api_key={TMDB_API_KEY}&primary_release_year={year}&sort_by=popularity.desc"
    res = requests.get(url).json().get('results', [])[:8]
    if res:
        keyboard = [[InlineKeyboardButton(f"🎬 {m['title']}", callback_data=f"tmdb_movie_{m['id']}")] for m in res]
        await update.message.reply_text(f"📅 **Best Movies of {year}:**", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    else:
        await update.message.reply_text(STRINGS[lang]["not_found"])

async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    data = query.data
    lang = get_lang(context, user_id)
    s = STRINGS[lang]
    await query.answer()

    # --- 1st CLICK AD LOGIC ---
    if data.startswith(("select_", "tmdb_movie_", "tv_")):
        # යූසර් මීට කලින් මේ මූවී එකට ඇඩ් එක බැලුවද බලනවා
        if not context.user_data.get(f"ad_done_{user_id}_{data}"):
            context.user_data[f"ad_done_{user_id}_{data}"] = True # දැන් ඇඩ් එක පෙන්නුවා කියලා සටහන් කරනවා
            keyboard = [[InlineKeyboardButton(s["unlock"], url=SMART_LINK)]]
            await query.message.reply_text(s["ad_msg"], reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
            return # මෙතනින් නවතිනවා, යූසර් ආයෙත් ඇවිත් ක්ලික් කරන්න ඕනේ

    # --- 2nd CLICK CONTENT LOGIC ---
    if data.startswith("setlang_"):
        lang_code = data.split("_")[1]
        context.user_data[user_id] = lang_code
        keyboard = [[InlineKeyboardButton("🔥 Trending", callback_data="trending")]]
        await query.edit_message_text(STRINGS[lang_code]["welcome"], reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

    elif data == "trending":
        url = f"https://api.themoviedb.org/3/trending/movie/day?api_key={TMDB_API_KEY}"
        res = requests.get(url).json().get('results', [])[:10]
        keyboard = [[InlineKeyboardButton(f"🔥 {m['title']}", callback_data=f"tmdb_movie_{m['id']}")] for m in res]
        await query.edit_message_text("🔥 **Trending Movies**", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

    elif data.startswith("select_"): # OMDB
        imdb_id = data.split("_")[1]
        m = requests.get(f"http://www.omdbapi.com/?i={imdb_id}&plot=full&apikey={OMDB_API_KEY}").json()
        title = m.get('Title')
        keyboard = [[InlineKeyboardButton(s["watch"], url=f"https://vidsrc.me/embed/movie?imdb={imdb_id}")]]
        yts = get_yts_links(title)
        for t in yts: keyboard.append([InlineKeyboardButton(f"📥 {t['quality']} ({t['size']})", url=t['url'])])
        poster = m.get('Poster') if m.get('Poster') != "N/A" else "https://via.placeholder.com/500x750"
        await query.message.reply_photo(photo=poster, caption=f"🎬 *{title}*\n⭐ Rating: {m.get('imdbRating')}\n\n{m.get('Plot')[:500]}...", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

    elif data.startswith("tmdb_movie_"): # TMDB
        tmdb_id = data.split("_")[2]
        m = requests.get(f"https://api.themoviedb.org/3/movie/{tmdb_id}?api_key={TMDB_API_KEY}").json()
        watch_url = f"https://vidsrc.me/embed/movie?tmdb={tmdb_id}"
        keyboard = [[InlineKeyboardButton(s["watch"], url=watch_url)]]
        poster = f"https://image.tmdb.org/t/p/w500{m['poster_path']}" if m.get('poster_path') else "https://via.placeholder.com/500x750"
        await query.message.reply_photo(photo=poster, caption=f"🎬 *{m['title']}*\n\n{m['overview'][:500]}...", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

    elif data.startswith("tv_"): # TV Shows
        tv_id = data.split("_")[1]
        m = requests.get(f"https://api.themoviedb.org/3/tv/{tv_id}?api_key={TMDB_API_KEY}").json()
        keyboard = [[InlineKeyboardButton(f"📅 Season {i}", callback_data=f"season_{tv_id}_{i}")] for i in range(1, m['number_of_seasons']+1)]
        poster = f"https://image.tmdb.org/t/p/w500{m['poster_path']}" if m.get('poster_path') else "https://via.placeholder.com/500x750"
        await query.message.reply_photo(photo=poster, caption=f"📺 *{m['name']}*\n\n{s['seasons']}", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

    elif data.startswith("season_"):
        _, tv_id, s_num = data.split("_")
        m = requests.get(f"https://api.themoviedb.org/3/tv/{tv_id}/season/{s_num}?api_key={TMDB_API_KEY}").json()
        keyboard = []
        for ep in m.get('episodes', [])[:20]:
            watch_url = f"https://vidsrc.me/embed/tv?tmdb={tv_id}&sea={s_num}&epi={ep['episode_number']}"
            keyboard.append([InlineKeyboardButton(f"E{ep['episode_number']} - {ep['name']}", url=watch_url)])
        await query.message.reply_text(f"📂 *{s['episodes']} (S{s_num})*", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def handle_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = get_lang(context, update.effective_user.id)
    query = update.message.text
    m_res = requests.get(f"http://www.omdbapi.com/?s={query}&apikey={OMDB_API_KEY}").json()
    tv_res = requests.get(f"https://api.themoviedb.org/3/search/tv?api_key={TMDB_API_KEY}&query={query}").json().get('results', [])
    keyboard = []
    if m_res.get('Response') == 'True':
        for m in m_res.get('Search')[:4]: keyboard.append([InlineKeyboardButton(f"🎬 {m['Title']} ({m['Year']})", callback_data=f"select_{m['imdbID']}")])
    for tv in tv_res[:4]: keyboard.append([InlineKeyboardButton(f"📺 {tv['name']}", callback_data=f"tv_{tv['id']}")])
    if keyboard: await update.message.reply_text(STRINGS[lang]["results"], reply_markup=InlineKeyboardMarkup(keyboard))
    else: await update.message.reply_text(STRINGS[lang]["not_found"])

if __name__ == '__main__':
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("actor", actor_search))
    app.add_handler(CommandHandler("ai", ai_search))
    app.add_handler(CallbackQueryHandler(button_click))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_search))
    print("🚀 Flixel AI v32.0 Live - Millionaire Plan Active!")
    app.run_polling()
