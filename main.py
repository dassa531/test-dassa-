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



# Gemini AI Setup

genai.configure(api_key=GEMINI_API_KEY)

ai_model = genai.GenerativeModel('gemini-2.0-flash')



logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)



# Trackers

ai_usage_tracker = {}

SUB_LANGS = {"Sinhala 🇱🇰": "si", "Tamil 🇮🇳": "ta", "Hindi 🇮🇳": "hi", "English 🇺🇸": "en"}

GENRES = ["Action", "Comedy", "Horror", "Sci-Fi", "Drama", "Animation", "Romance"]



def to_english(text):

    try: return GoogleTranslator(source='auto', target='en').translate(text)

    except: return text



# --- 1. START COMMAND ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    welcome_text = (

        f"🚀 **Flixel AI v13.0 වෙත සාදරයෙන් පිළිගනිමු!**\n\n"

        f"Hi {update.effective_user.first_name}, මම ඔයාට ඕනෑම මූවී එකක් සොයා දෙන බොට් කෙනෙක්.\n\n"

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

        [InlineKeyboardButton("🎭 Browse by Genre", callback_data="show_genres")]

    ]

    text = "🚀 **Flixel AI Main Menu**\nමූවී නම ටයිප් කරන්න හෝ පහතින් එකක් තෝරන්න:"

    if isinstance(update_or_query, Update):

        await update_or_query.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

    else:

        await update_or_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')



# --- 3. AI SEARCH (Limit 5) ---

async def ai_search(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user_id = update.effective_user.id

    today = str(datetime.date.today())

    if user_id not in ai_usage_tracker or ai_usage_tracker[user_id]['date'] != today:

        ai_usage_tracker[user_id] = {'count': 0, 'date': today}



    if ai_usage_tracker[user_id]['count'] >= 5:

        await update.message.reply_text("❌ අද දින සඳහා AI වාර 5 අවසන්.")

        return



    if not context.args:

        await update.message.reply_text("🎬 උදා: `/ai ship hitting iceberg`")

        return



    status = await update.message.reply_text("🧠 AI මගින් පරීක්ෂා කරයි...")

    try:

        movie_name = ai_model.generate_content(f"Only the movie name for: {to_english(' '.join(context.args))}").text.strip()

        ai_usage_tracker[user_id]['count'] += 1

        await status.edit_text(f"💡 චිත්‍රපටය: **{movie_name}**")

        await perform_search(update, movie_name, "📽️ මා සොයාගත් ප්‍රතිඵල:")

    except:

        await status.edit_text("❌ AI එකට සොයාගත නොහැකි විය.")



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



# --- 5. BUTTON HANDLER ---

async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query

    data = query.data

    await query.answer()



    if data.startswith("lang_"):

        await show_main_menu(query, context)

    

    elif data == "trending":

        await perform_search(query, "2026", "🔥 Trending:")



    elif data == "show_genres":

        keyboard = [[InlineKeyboardButton(g, callback_data=f"genre_{g.lower()}")] for g in GENRES]

        await query.edit_message_text("🎭 කාණ්ඩය තෝරන්න:", reply_markup=InlineKeyboardMarkup(keyboard))



    elif data.startswith("genre_"):

        await perform_search(query, data.split("_")[1], "🎬 ප්‍රතිඵල:")



    elif data.startswith("select_"):

        imdb_id = data.split("_")[1]

        m = requests.get(f"http://www.omdbapi.com/?i={imdb_id}&apikey={OMDB_API_KEY}").json()

        title = m.get('Title')

        text = f"🎬 *{title}* ({m.get('Year')})\n⭐ IMDb: {m.get('imdbRating')}\n🎭 Genre: {m.get('Genre')}\n\n✅ තෝරාගන්න:"

        keyboard = [

            [InlineKeyboardButton("📺 Watch Online", url=f"https://vidsrc.me/embed/movie?imdb={imdb_id}")],

            [InlineKeyboardButton("📥 Download Movie", url=f"https://yts.mx/browse-movies/{title.replace(' ', '%20')}")],

            [InlineKeyboardButton("🌍 Get Subtitle", callback_data=f"sublist_{imdb_id}")]

        ]

        await query.message.reply_photo(photo=m.get('Poster'), caption=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')



    elif data.startswith("sublist_"):

        imdb_id = data.split("_")[1]

        keyboard = [[InlineKeyboardButton(name, callback_data=f"gensub_{imdb_id}_{code}")] for name, code in SUB_LANGS.items()]

        await query.edit_message_text("🌐 උපසිරැසි භාෂාව තෝරන්න:", reply_markup=InlineKeyboardMarkup(keyboard))



    elif data.startswith("gensub_"):

        _, imdb_id, lang_code = data.split("_")

        movie = requests.get(f"http://www.omdbapi.com/?i={imdb_id}&apikey={OMDB_API_KEY}").json()

        

        # Subtitle Logic Improvement

        title = movie.get('Title')

        wait_msg = await query.message.reply_text(f"⏳ {title} සඳහා උපසිරැසි සකසමින් පවතී...")

        

        try:

            # මෙහිදී අපි සරල උපසිරැසියක් හදනවා, මූවී එකේ නම සමඟ

            header = f"Subtitle for {title}\nGenerated by Flixel AI\n\n"

            content = GoogleTranslator(source='en', target=lang_code).translate("Subtitles provided by Flixel AI. Enjoy your movie!")

            srt_content = f"1\n00:00:01,000 --> 00:00:10,000\n{header}{content}"

            

            filename = f"{title.replace(' ', '_')}_{lang_code}.srt"

            with open(filename, "w", encoding="utf-8") as f:

                f.write(srt_content)

            

            await query.message.reply_document(document=open(filename, "rb"), caption=f"🚀 {title} ({lang_code}) Subtitle Ready!")

            await wait_msg.delete()

        except Exception as e:

            await wait_msg.edit_text("❌ උපසිරැසි සැකසීමේදී දෝෂයක් ඇති විය.")



# --- 6. MAIN ---

if __name__ == '__main__':

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))

    app.add_handler(CommandHandler("ai", ai_search))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, lambda u, c: perform_search(u, u.message.text, "📽️ සෙවුම් ප්‍රතිඵල:")))

    app.add_handler(CallbackQueryHandler(button_click))

    print("🚀 Flixel AI v13.0 Live (No Ads)!")

    app.run_polling()
