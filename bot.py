import logging
from telegram import Update, ChatMember, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
    CallbackContext,
    CallbackQueryHandler,
)
import openai  # For ChatGPT API
import google.generativeai as genai  # For Gemini API
import os  # For environment variables

# Load environment variables
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
CHANNEL_USERNAME = "@premiumlinkers"  # Your channel username

# Initialize APIs
openai.api_key = OPENAI_API_KEY
genai.configure(api_key=GEMINI_API_KEY)  # Initialize Gemini API

# Logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)

# Store user preferences and membership status
user_data = {}

# Check if user is a member of the channel
async def is_member(user_id: int, context: CallbackContext) -> bool:
    try:
        member = await context.bot.get_chat_member(chat_id=CHANNEL_USERNAME, user_id=user_id)
        return member.status in [ChatMember.MEMBER, ChatMember.ADMINISTRATOR, ChatMember.OWNER]
    except Exception as e:
        logging.error(f"Error checking membership: {e}")
        return False

# Start command
async def start(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id
    if await is_member(user_id, context):
        await update.message.reply_text("Welcome! You can start using the bot.")
    else:
        await update.message.reply_text(f"Please join {CHANNEL_USERNAME} to use this bot.")

# Choose AI command
async def choose_ai(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id
    if not await is_member(user_id, context):
        await update.message.reply_text(f"Please join {CHANNEL_USERNAME} to use this bot.")
        return

    keyboard = [
        [InlineKeyboardButton("ChatGPT", callback_data="chatgpt")],
        [InlineKeyboardButton("Gemini", callback_data="gemini")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Choose an AI:", reply_markup=reply_markup)

# Handle AI selection
async def handle_ai_selection(update: Update, context: CallbackContext):
    query = update.callback_query
    user_id = query.from_user.id
    ai_choice = query.data

    user_data[user_id] = {"ai": ai_choice}
    await query.edit_message_text(f"You have selected {ai_choice.capitalize()}.")

# Handle messages
async def handle_message(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id

    # Check channel membership
    if not await is_member(user_id, context):
        await update.message.reply_text(f"Please join {CHANNEL_USERNAME} to use this bot.")
        return

    # Check if AI is selected
    if user_id not in user_data or "ai" not in user_data[user_id]:
        await update.message.reply_text("Please choose an AI using /chooseai.")
        return

    user_input = update.message.text
    ai_choice = user_data[user_id]["ai"]

    if ai_choice == "chatgpt":
        # Call ChatGPT API
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": user_input}]
        )
        reply = response['choices'][0]['message']['content']
    elif ai_choice == "gemini":
        # Call Gemini API
        try:
            model = genai.GenerativeModel('gemini-pro')
            response = model.generate_content(user_input)
            reply = response.text
        except Exception as e:
            logging.error(f"Gemini API error: {e}")
            reply = "Sorry, I couldn't generate a response. Please try again."

    await update.message.reply_text(reply)

# Set group command
async def set_group(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id
    group_name = " ".join(context.args)

    if not group_name:
        await update.message.reply_text("Please provide a group name. Usage: /setgroup <group_name>")
        return

    # Add logic to make the bot an admin in the group
    await update.message.reply_text(f"Group '{group_name}' set. Please make the bot an admin in the group.")

# Main function
if __name__ == "__main__":
    application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    # Handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("chooseai", choose_ai))
    application.add_handler(CallbackQueryHandler(handle_ai_selection))
    application.add_handler(CommandHandler("setgroup", set_group))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Run the bot
    application.run_polling()
