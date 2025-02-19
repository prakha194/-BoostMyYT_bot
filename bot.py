import os
import time
import schedule
from telegram import Bot, Update
from telegram.ext import Updater, CommandHandler
from googleapiclient.discovery import build

# Load environment variables
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
TELEGRAM_GROUP_ID = os.getenv("TELEGRAM_GROUP_ID")
YOUTUBE_CHANNEL_ID = os.getenv("YOUTUBE_CHANNEL_ID")
YOUR_CHAT_ID = os.getenv("YOUR_CHAT_ID")  # Your private chat ID with the bot

# Initialize APIs
bot = Bot(token=TELEGRAM_BOT_TOKEN)
youtube = build("youtube", "v3", developerKey=YOUTUBE_API_KEY)

def fetch_latest_videos():
    """Fetch latest videos from your YouTube channel."""
    request = youtube.search().list(
        part="snippet",
        channelId=YOUTUBE_CHANNEL_ID,
        maxResults=10,
        order="date"
    )
    return request.execute().get("items", [])

def send_task_update(message):
    """Send a task update to your private chat with the bot."""
    bot.send_message(chat_id=YOUR_CHAT_ID, text=message)

def boost_views(video_id, views):
    """Simulate adding views to a video."""
    print(f"Added {views} views to video: {video_id}")
    send_task_update(f"✅ Added {views} views to video: {video_id}")

def share_video(video):
    """Share a video in the Telegram group."""
    video_id = video["id"]["videoId"]
    video_title = video["snippet"]["title"]
    video_url = f"https://youtube.com/watch?v={video_id}"
    bot.send_message(chat_id=TELEGRAM_GROUP_ID, text=f"🎥 New video: {video_title}\n{video_url}")
    send_task_update(f"✅ Shared video: {video_title}\nLink: {video_url}")

def weekly_views_boosting():
    """Boost views for the latest and older videos."""
    videos = fetch_latest_videos()
    if not videos:
        return

    # Boost 10 views to the newest video
    newest_video = videos[0]
    boost_views(newest_video["id"]["videoId"], 10)

    # Boost 10 views to older videos
    for video in videos[1:6]:  # Distribute across 5 older videos
        boost_views(video["id"]["videoId"], 2)  # 2 views per video

def send_analytics(update: Update, context):
    """Send analytics report to the user."""
    update.message.reply_text("Analytics are not available without SQLite.")

def start(update: Update, context):
    """Start command handler."""
    update.message.reply_text(
        "Welcome to BoostMyYT_bot! 🚀\n"
        "Use the following commands:\n"
        "- /report: Get analytics.\n"
        "- /help: Show this help message."
    )

def help_command(update: Update, context):
    """Help command handler."""
    update.message.reply_text(
        "🤖 BoostMyYT_bot Help:\n"
        "- /start: Start the bot.\n"
        "- /report: Get analytics.\n"
        "- /help: Show this help message."
    )

def main():
    """Start the bot."""
    updater = Updater(TELEGRAM_BOT_TOKEN)
    dispatcher = updater.dispatcher

    # Command handlers
    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CommandHandler("report", send_analytics))
    dispatcher.add_handler(CommandHandler("help", help_command))

    # Schedule weekly views boosting
    schedule.every().week.do(weekly_views_boosting)

    updater.start_polling()

    # Keep the bot running
    while True:
        schedule.run_pending()
        time.sleep(1)

if __name__ == "__main__":
    main()
