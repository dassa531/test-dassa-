import os
import logging
import requests
import datetime
import google.generativeai as genai
from bs4 import BeautifulSoup
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

# --- CONFIG ---
TOKEN = os.getenv('TOKEN')
OMDB_API_KEY = os.getenv('OMDB_API_KEY')
TMDB_API_KEY = os.getenv('TMDB_API_KEY')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')

# AI Configuration
genai.configure(api_key=GEMINI_API_KEY)
ai_model = genai.GenerativeModel('gemini-1.5-flash')

# Logging
logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)

# User AI Usage Tracking (Memory based)
user_ai_usage = {}

# --- HELPER FUNCTIONS ---

def get_sinhala_links(title):
    headers = {'User-Agent': 'Mozilla/5.0'}
    sub_buttons = []
    try:
        res = requests.get(f"https://cinesubz.co/?s={title.replace(' ', '+')}", headers=headers, timeout=5)
        soup = BeautifulSoup(res.text, 'html.parser')
        res_tag = soup.find('h2') or soup.find('h3')
        if res_tag and res_tag.find('a'):
            sub_buttons.append(InlineKeyboardButton("🇱🇰 Cinesubz (Sinhala)", url=res_tag.find('a')['href']))
    except: pass
    try:
        res = requests.get(f"https://www.baiscope.lk/?s={title.replace(' ', '+')}", headers=headers, timeout=5)
        soup = BeautifulSoup(res.text, 'html.parser')
        res_tag = soup.find('h2', class_='entry-title')
        if res_tag and res_tag.find('a'):
            sub_buttons.append(InlineKeyboardButton("🇱🇰 Baiscope (Sinhala)", url=res_tag.find('a')['href']))
    except: pass
    return sub_buttons

def fetch_tmdb(endpoint, params={}):
    params['api_key'] = TMDB_API_KEY
    url = f"https://api.themoviedb.org/3/{endpoint}"
    return requests.get(url, params=params).json()

def identify_movie_with_ai(description):
    prompt = f"Identify the movie name based on this description: '{description}'. Reply ONLY with the movie title. If you can't identify it, reply 'Unknown'."
    try:
        response = ai_model.generate_content(prompt)
        return response.text.strip()
    except: return "Unknown"

# --- BOT HANDLERS ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🔥 Trending Movies", callback_data="trending")],
        [InlineKeyboardButton("🎭 Genres (කාණ්ඩ)", callback_data="genres_menu")]
    ]
    text = (
        f"🎬 **Welcome to Flixel AI v8.0**\n\n"
        f"Hi {update.effective_user.first_name}, මම ඔබේ දියුණු කළ මූවී සහායකයා.\n\n"
        f"🔍 නම මතක නම් නම ටයිප් කර එවන්න.\n"
        f"🤖 නම මතක නැතිනම් සීන් එක විස්තර කරන්න: `/ai [scene info]`\n"
        f"(AI සෙවුම් වාර 5ක් දිනකට හිමිවේ)"
    )
    if update.message:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    else:
        await update.callback_query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def ai_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    today = datetime.date.today().isoformat()
    
    # Check/Reset Limit
    if user_id not in user_ai_usage or user_ai_usage[user_id]['date'] != today:
        user_ai_usage[user_id] = {'count': 0, 'date': today}
    
    if user_ai_usage[user_id]['count'] >= 5:
        await update.message.reply_text("🚫 ඔබේ දෛනික AI සෙවුම් වාර 5 අවසන්. හෙට නැවත උත්සාහ කරන්න.")
        return

    description = " ".join(context.args)
    if not description:
        await update.message.reply_text("💡 කරුණාකර මූවී එකේ සීන් එකක් විස්තර කරන්න.\nඋදා: `/ai movie about a sinking ship`")
        return

    status_msg = await update.message.reply_text("🤖 AI මගින් මූවී එක හඳුනාගනිමින් පවතී...")
    
    movie_name = identify_movie_with_ai(description)
    
    if movie_name == "Unknown":
        await status_msg.edit_text("❌ කණගාටුයි, එම විස්තරයෙන් මූවී එක හඳුනා ගැනීමට AI අපොහොසත් විය.")
        return

    # Update Usage
    user_ai_usage[user_id]['count'] += 1
    
    # Search with Identified Name
    res = requests.get(f"http://www.omdbapi.com/?s={movie_name}&apikey={OMDB_API_KEY}").json()
    if res.get('Response') == 'True':
        movies = res.get('Search')[:5]
        keyboard = [[InlineKeyboardButton(f"🎬 {m['Title']} ({m['Year']})", callback_data=f"show_{m['imdbID']}")] for m in movies]
        await status_msg.edit_text(
            f"✅ AI සොයාගත්තේ: **{movie_name}**\n(අද දින ඉතිරි AI වාර ගණන: {5 - user_ai_usage[user_id]['count']})",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    else:
        await status_msg.edit_text(f"💡 AI පවසන්නේ මෙය '{movie_name}' විය හැකි බවයි, නමුත් ලින්ක් සොයාගත නොහැකි විය.")

async def handle_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.message.text
    res = requests.get(f"http://www.omdbapi.com/?s={query}&apikey={OMDB_API_KEY}").json()
    if res.get('Response') == 'True':
        movies = res.get('Search')[:8]
        keyboard = [[InlineKeyboardButton(f"🎬 {m['Title']} ({m['Year']})", callback_data=f"show_{m['imdbID']}")] for m in movies]
        await update.message.reply_text("📽️ මා සොයාගත් ප්‍රතිඵල මෙන්න:", reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await update.message.reply_text("❌ මූවී එක හමු වුණේ නැහැ. නම නිවැරදිද? නැත්නම් `/ai` විධානය භාවිතා කරන්න.")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    await query.answer()

    if data == "trending":
        res = fetch_tmdb("trending/movie/week")
        movies = res.get('results', [])[:10]
        keyboard = [[InlineKeyboardButton(f"🎬 {m['title']}", callback_data=f"tmdb_{m['id']}")] for m in movies]
        keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data="back_home")])
        await query.message.edit_text("🔥 අද දින ලොව වැඩිපුරම නරඹන මූවීස්:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data == "genres_menu":
        genres = [("🎬 Action", 28), ("👻 Horror", 27), ("💖 Romance", 10749), ("🤖 Sci-Fi", 878)]
        keyboard = [[InlineKeyboardButton(g[0], callback_data=f"gen_{g[1]}")] for g in genres]
        keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data="back_home")])
        await query.message.edit_text("🎭 ඔබට අවශ්‍ය කාණ්ඩය තෝරන්න:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("gen_"):
        gid = data.split("_")[1]
        res = fetch_tmdb("discover/movie", {"with_genres": gid})
        movies = res.get('results', [])[:10]
        keyboard = [[InlineKeyboardButton(f"🎬 {m['title']}", callback_data=f"tmdb_{m['id']}")] for m in movies]
        keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data="genres_menu")])
        await query.message.edit_text("✅ ඔබ තේරූ කාණ්ඩයේ මූවීස් මෙන්න:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("tmdb_"):
        tid = data.split("_")[1]
        m = fetch_tmdb(f"movie/{tid}")
        await show_movie_info(query, m.get('title'))

    elif data == "back_home":
        await start(update, context)

async def show_movie_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    imdb_id = query.data.split("_")[1]
    movie_data = requests.get(f"http://www.omdbapi.com/?i={imdb_id}&apikey={OMDB_API_KEY}").json()
    await show_movie_info(query, movie_data.get('Title'), movie_data)

async def show_movie_info(query, title, movie=None):
    if not movie:
        movie = requests.get(f"http://www.omdbapi.com/?t={title}&apikey={OMDB_API_KEY}").json()
    if movie.get('Response') == 'True':
        imdb_id = movie.get('imdbID')
        keyboard = [[InlineKeyboardButton("📺 Watch Online (English)", url=f"https://vidsrc.me/embed/movie?imdb={imdb_id}")]]
        subs = get_sinhala_links(title)
        for b in subs: keyboard.append([b])
        keyboard.append([InlineKeyboardButton("📥 Torrent (YTS)", url=f"https://yts.mx/browse-movies/{title.replace(' ', '%20')}/all/all/0/latest/0/all")])

        poster = movie.get('Poster')
        if poster == "N/A": poster = "https://via.placeholder.com/500x750?text=No+Poster"
        
        await query.message.reply_photo(
            photo=poster,
            caption=f"🎬 *{movie.get('Title')}*\n⭐ IMDb: {movie.get('imdbRating')}\n\n{movie.get('Plot')[:350]}...",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )

# --- MAIN ---
if __name__ == '__main__':
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("ai", ai_search))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_search))
    app.add_handler(CallbackQueryHandler(button_handler, pattern="^(trending|genres_menu|gen_|tmdb_|back_home)"))
    app.add_handler(CallbackQueryHandler(show_movie_callback, pattern="^show_"))
    
    print("✅ Flixel v8.0 AI Hub is Live!")
    app.run_polling()
