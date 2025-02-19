import os
import sqlite3
import time
import schedule
from telegram import Bot
from telegram.ext import CommandHandler, Updater
from googleapiclient.discovery import build
import google.generativeai as genai

# Load environment variables
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
TELEGRAM_GROUP_ID = os.getenv("TELEGRAM_GROUP_ID")
YOUTUBE_CHANNEL_ID = os.getenv("YOUTUBE_CHANNEL_ID")

# Initialize APIs
bot = Bot(token=TELEGRAM_BOT_TOKEN)
youtube = build("youtube", "v3", developerKey=YOUTUBE_API_KEY)
genai.configure(api_key=GEMINI_API_KEY)

# Database for logging actions
conn = sqlite3.connect("bot_actions.db", check_same_thread=False)
cursor = conn.cursor()
cursor.execute("""
CREATE TABLE IF NOT EXISTS actions (
    id INTEGER PRIMARY KEY,
    action TEXT,
    video_id TEXT,
    views_added INTEGER,
    timestamp DATETIME
)
""")
conn.commit()

def fetch_latest_videos():
    """Fetch latest videos from your YouTube channel."""
    request = youtube.search().list(
        part="snippet",
        channelId=YOUTUBE_CHANNEL_ID,
        maxResults=10,
        order="date"
    )
    return request.execute().get("items", [])

def generate_comment(video_title):
    """Generate a context-aware comment using Gemini."""
    model = genai.GenerativeModel('gemini-pro')
    response = model.generate_content(f"Generate a friendly comment for a YouTube video titled: {video_title}")
    return response.text

def boost_views(video_id, views):
    """Simulate adding views to a video."""
    # Replace this with your actual views-boosting logic (e.g., using a views service API).
    print(f"Added {views} views to video: {video_id}")
    log_action(f"Added {views} views", video_id, views)

def log_action(action, video_id, views_added=0):
    """Log bot actions to the database."""
    cursor.execute("""
    INSERT INTO actions (action, video_id, views_added, timestamp)
    VALUES (?, ?, ?, datetime('now'))
    """, (action, video_id, views_added))
    conn.commit()

def share_video(video):
    """Share a video in the Telegram group."""
    video_id = video["id"]["videoId"]
    video_title = video["snippet"]["title"]
    video_url = f"https://youtube.com/watch?v={video_id}"
    bot.send_message(chat_id=TELEGRAM_GROUP_ID, text=f"🎥 New video: {video_title}\n{video_url}")
    log_action("Shared video", video_id)

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
    cursor.execute("SELECT * FROM actions ORDER BY timestamp DESC")
    actions = cursor.fetchall()

    report = "📊 Bot Analytics:\n\n"
    for action in actions:
        report += f"- {action[1]} on video {action[2]} (Views added: {action[3]})\n"

    update.message.reply_text(report)

def start(update: Update, context):
    """Start command handler."""
    update.message.reply_text("Welcome to BoostMyYT_bot! Use /report to get analytics.")

def main():
    """Start the bot."""
    updater = Updater(TELEGRAM_BOT_TOKEN)
    dispatcher = updater.dispatcher

    # Command handlers
    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CommandHandler("report", send_analytics))

    # Schedule weekly views boosting
    schedule.every().week.do(weekly_views_boosting)

    updater.start_polling()

    # Keep the bot running
    while True:
        schedule.run_pending()
        time.sleep(1)

if __name__ == "__main__":
    main()