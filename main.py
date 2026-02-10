import os
import logging
import requests
import datetime
import google.generativeai as genai
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from deep_translator import GoogleTranslator

# --- CONFIGURATION ---
TOKEN = os.getenv('TOKEN')
OMDB_API_KEY = os.getenv('OMDB_API_KEY')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')

# Monetad Direct Link (ඔයාගේ ලින්ක් එක මෙතනට දාන්න)
AD_LINK = "https://your-monetad-link.com" 

# Gemini AI Setup
genai.configure(api_key=GEMINI_API_KEY)
ai_model = genai.GenerativeModel('gemini-pro')

logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)

# Global Trackers
ai_usage_tracker = {}
# සබ්ටයිටල් සහ කැටගරි
SUB_LANGS = {"Sinhala 🇱🇰": "si", "Tamil 🇮🇳": "ta", "Hindi 🇮🇳": "hi", "English 🇺🇸": "en"}
GENRES = ["Action", "Comedy", "Horror", "Sci-Fi", "Drama", "Animation", "Romance"]

# --- HELPER: AUTO TRANSLATE ---
def to_english(text):
    try:
        return GoogleTranslator(source='auto', target='en').translate(text)
    except:
        return text

# --- 1. START COMMAND ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_text = (
        f"🚀 **Flixel AI v12.0 වෙත සාදරයෙන් පිළිගනිමු!**\n\n"
        f"Hi {update.effective_user.first_name}, ඔබ දැනට භාවිතා කරන්නේ අපගේ **Free Plan** එකයි. "
        f"එම නිසා බාගත කිරීම් වලදී (Watch/Download/SRT) පළමු වරට දැන්වීමක් (Ad) දර්ශනය වේ. "
        f"එය ඔබගේ මූවී නැරඹීමට බාධාවක් නොවන අතර දෙවන වර ක්ලික් කිරීමේදී ඔබට අදාළ ගොනුව ලැබෙනු ඇත.\n\n"
        f"🔍 **සෙවීමට:** මූවී නම ටයිප් කර එවන්න.\n"
        f"🧠 **AI සෙවුම:** `/ai [විස්තරය]` (දිනකට 5 වතාවකි)\n\n"
        f"📢 **පළමුව භාෂාව තෝරාගන්න:**"
    )
    keyboard = [[InlineKeyboardButton("🇱🇰 Sinhala", callback_data="lang_si"),
                 InlineKeyboardButton("🇺🇸 English", callback_data="lang_en")]]
    await update.message.reply_text(welcome_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

# --- 2. MAIN MENU ---
async def show_main_menu(update_or_query, context):
    keyboard = [
        [InlineKeyboardButton("🔥 Trending Movies", callback_data="trending")],
        [InlineKeyboardButton("🎭 Browse by Genre", callback_data="show_genres")],
        [InlineKeyboardButton("🔍 Search Help", callback_data="ai_info")]
    ]
    text = "🚀 **Flixel AI Main Menu**\nමූවී නම ටයිප් කරන්න හෝ පහතින් එකක් තෝරන්න:"
    if isinstance(update_or_query, Update):
        await update_or_query.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    else:
        await update_or_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

# --- 3. AI SCENE SEARCH (Limit 5) ---
async def ai_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    today = str(datetime.date.today())
    
    if user_id not in ai_usage_tracker or ai_usage_tracker[user_id]['date'] != today:
        ai_usage_tracker[user_id] = {'count': 0, 'date': today}

    if ai_usage_tracker[user_id]['count'] >= 5:
        await update.message.reply_text("❌ ඔබට අද දින සඳහා ලබා දී ඇති AI සෙවුම් වාර 5 අවසන්. හෙට නැවත උත්සාහ කරන්න.")
        return

    if not context.args:
        await update.message.reply_text("🎬 දර්ශනය විස්තර කරන්න. උදා: `/ai ship hitting an iceberg`")
        return

    status = await update.message.reply_text("🧠 AI මගින් හඳුනාගනිමින් පවතී...")
    try:
        movie_name = ai_model.generate_content(f"Movie name for: {to_english(' '.join(context.args))}. Only name.").text.strip()
        ai_usage_tracker[user_id]['count'] += 1
        rem = 5 - ai_usage_tracker[user_id]['count']
        await status.edit_text(f"💡 මම හිතන්නේ මේ: **{movie_name}**\n(ඔබට තව වාර {rem} ක් ඉතිරිව ඇත)")
        await perform_search(update, movie_name, "📽️ මා සොයාගත් ප්‍රතිඵල:")
    except:
        await status.edit_text("❌ AI එකට මූවී එක අඳුරගන්න බැරි වුණා.")

# --- 4. SEARCH LOGIC ---
async def perform_search(update_or_query, query, success_text):
    search_term = to_english(query)
    url = f"http://www.omdbapi.com/?s={search_term.replace(' ', '+')}&apikey={OMDB_API_KEY}"
    res = requests.get(url).json()

    if res.get('Response') == 'True':
        movies = res.get('Search')[:8]
        keyboard = [[InlineKeyboardButton(f"🎬 {m['Title']} ({m['Year']})", callback_data=f"select_{m['imdbID']}")] for m in movies]
        if isinstance(update_or_query, Update):
            await update_or_query.message.reply_text(success_text, reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            await update_or_query.message.reply_text(success_text, reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        msg = "❌ චිත්‍රපටය සොයාගත නොහැකි විය."
        if isinstance(update_or_query, Update): await update_or_query.message.reply_text(msg)
        else: await update_or_query.message.reply_text(msg)

# --- 5. BUTTON CLICK HANDLER (Smart Ad Engine) ---
async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    user_id = update.effective_user.id
    await query.answer()

    if 'clicks' not in context.user_data:
        context.user_data['clicks'] = {}

    if data.startswith("lang_"):
        await show_main_menu(query, context)
    
    elif data == "trending":
        await perform_search(query, "2026", "🔥 Trending Movies:")

    elif data == "show_genres":
        keyboard = [[InlineKeyboardButton(g, callback_data=f"genre_{g.lower()}")] for g in GENRES]
        keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="back_to_menu")])
        await query.edit_message_text("🎭 කාණ්ඩය තෝරන්න:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data == "back_to_menu":
        await show_main_menu(query, context)

    elif data == "ai_info":
        await query.edit_message_text("🔍 සෘජුව මූවී නම එවන්න හෝ `/ai [scene]` ලෙස පාවිච්චි කරන්න.")

    elif data.startswith("genre_"):
        await perform_search(query, data.split("_")[1], "🎬 ප්‍රතිඵල:")

    elif data.startswith("select_"):
        imdb_id = data.split("_")[1]
        m = requests.get(f"http://www.omdbapi.com/?i={imdb_id}&apikey={OMDB_API_KEY}").json()
        title = m.get('Title')
        text = f"🎬 *{title}* ({m.get('Year')})\n⭐ IMDb: {m.get('imdbRating')}\n\n✅ **පහත බොත්තම් පළමු වර එබූ විට දැන්වීමක් පෙන්වනු ඇත:**"
        keyboard = [
            [InlineKeyboardButton("📺 Watch Movie (Ads)", callback_data=f"watch_{imdb_id}")],
            [InlineKeyboardButton("📥 Download Movie (Ads)", callback_data=f"down_{imdb_id}")],
            [InlineKeyboardButton("🌍 Get AI Subtitle (Ads)", callback_data=f"srt_{imdb_id}")]
        ]
        await query.message.reply_photo(photo=m.get('Poster'), caption=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

    # --- SMART AD LOGIC (Click 1: Ad, Click 2: File) ---
    elif any(data.startswith(x) for x in ["watch_", "down_", "srt_"]):
        btn_type, imdb_id = data.split("_")
        
        if data not in context.user_data['clicks']:
            context.user_data['clicks'][data] = True
            keyboard = [[InlineKeyboardButton("👉 Click here to Continue (Ad Link)", url=AD_LINK)],
                        [InlineKeyboardButton("✅ I have clicked, Next", callback_data=data)]]
            await query.message.reply_text(f"⚠️ ඔබ Free Plan එක භාවිතා කරන නිසා, පළමු වරට මෙම දැන්වීම ක්ලික් කර නැවත එම බොත්තමම (හෝ Next) ඔබන්න.", reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            m = requests.get(f"http://www.omdbapi.com/?i={imdb_id}&apikey={OMDB_API_KEY}").json()
            title = m.get('Title')
            if btn_type == "watch":
                await query.message.reply_text(f"✅ **{title}** නරඹන්න:\nhttps://vidsrc.me/embed/movie?imdb={imdb_id}")
            elif btn_type == "down":
                await query.message.reply_text(f"✅ **{title}** බාගත කරන්න:\nhttps://yts.mx/browse-movies/{title.replace(' ', '%20')}")
            elif btn_type == "srt":
                keyboard = [[InlineKeyboardButton(name, callback_data=f"gensub_{imdb_id}_{code}")] for name, code in SUB_LANGS.items()]
                await query.message.reply_text("🌐 උපසිරැසි භාෂාව තෝරන්න:", reply_markup=InlineKeyboardMarkup(keyboard))
            del context.user_data['clicks'][data] # Reset for next time

    elif data.startswith("gensub_"):
        _, imdb_id, lang_code = data.split("_")
        movie = requests.get(f"http://www.omdbapi.com/?i={imdb_id}&apikey={OMDB_API_KEY}").json()
        translated = GoogleTranslator(source='en', target=lang_code).translate(f"Generated by Flixel AI for {movie.get('Title')}")
        srt = f"1\n00:00:01,000 --> 00:00:10,000\n{translated}"
        filename = f"{movie.get('Title')}_{lang_code}.srt"
        with open(filename, "w", encoding="utf-8") as f: f.write(srt)
        await query.message.reply_document(document=open(filename, "rb"), caption=f"🚀 Subtitle Ready!")

# --- 7. MAIN ---
if __name__ == '__main__':
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("ai", ai_search))
    app.add_handler(CommandHandler("actor", lambda u, c: perform_search(u, " ".join(c.args), "⭐ ප්‍රතිඵල:") if c.args else None))
    app.add_handler(CommandHandler("year", lambda u, c: perform_search(u, f"movie&y={c.args[0]}", "📅 ප්‍රතිඵල:") if c.args else None))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, lambda u, c: perform_search(u, u.message.text, "📽️ සෙවුම් ප්‍රතිඵල:")))
    app.add_handler(CallbackQueryHandler(button_click))
    print("🚀 Flixel AI v12.0 Live!")
    app.run_polling()
