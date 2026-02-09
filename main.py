import os
import logging
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# API Keys (Railway Variables වලින් ලබා ගනී)
TOKEN = os.getenv('TOKEN')
OMDB_API_KEY = os.getenv('OMDB_API_KEY')

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

async def get_movie_info(movie_name):
    url = f"http://www.omdbapi.com/?t={movie_name}&apikey={OMDB_API_KEY}"
    try:
        response = requests.get(url, timeout=10).json()
        if response.get('Response') == 'True':
            return response
    except Exception as e:
        logging.error(f"Error: {e}")
    return None

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"ආයුබෝවන් {update.effective_user.first_name}! 🎬\n"
        "මම Flixel AI. ඕනෑම ඉංග්‍රීසි මූවී එකක නම එවන්න. මම ඒකේ විස්තර සහ Download Links හොයලා දෙන්නම්."
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.message.text
    if len(query) < 3:
        await update.message.reply_text("❌ මූවී එකේ නම අකුරු 3කට වඩා වැඩි වෙන්න ඕනේ.")
        return

    msg = await update.message.reply_text("🎬 විස්තර සොයමින් පවතී...")
    movie = await get_movie_info(query)

    if movie:
        title = movie.get('Title')
        year = movie.get('Year')
        poster = movie.get('Poster')
        
        # Download links
        yts_lnk = f"https://yts.mx/browse-movies/{title.replace(' ', '%20')}/all/all/0/latest/0/all"
        google_dl = f"https://www.google.com/search?q={title.replace(' ', '+')}+{year}+direct+download+link"

        text = (
            f"🎥 *Title:* {title} ({year})\n"
            f"⭐ *IMDb:* {movie.get('imdbRating')}\n\n"
            f"📝 *Plot:* {movie.get('Plot')[:300]}..."
        )

        keyboard = [
            [InlineKeyboardButton("🌐 Search on YTS", url=yts_lnk)],
            [InlineKeyboardButton("🚀 Direct Google Search", url=google_dl)]
        ]
        
        if poster and poster != "N/A":
            await update.message.reply_photo(photo=poster, caption=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
        else:
            await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
        await msg.delete()
    else:
        await msg.edit_text("❌ කණගාටුයි, ඒ නමින් මූවී එකක් හමු වුණේ නැහැ.")

if __name__ == '__main__':
    if not TOKEN:
        print("❌ Error: TOKEN not found!")
    else:
        app = Application.builder().token(TOKEN).build()
        app.add_handler(CommandHandler("start", start))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        print("✅ Flixel Bot is Online on Railway!")
        app.run_polling()
