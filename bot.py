import os
import time
import sqlite3
import asyncio
import logging
from telegram import Update, Bot
from telegram.ext import Application, CommandHandler, CallbackContext
from googleapiclient.discovery import build
import google.generativeai as genai  # Google Gemini API

# Load environment variables (Render & GitHub)
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
YOUTUBE_CHANNEL_ID = os.getenv("YOUTUBE_CHANNEL_ID")

# Initialize APIs
bot = Bot(token=TELEGRAM_BOT_TOKEN)
youtube = build("youtube", "v3", developerKey=YOUTUBE_API_KEY)

# Configure Gemini API
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-pro")

# Logging setup
logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# Database setup
def get_db_connection():
    conn = sqlite3.connect("bot_actions.db")
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS actions (
        id INTEGER PRIMARY KEY,
        action TEXT,
        video_id TEXT UNIQUE,
        group_id TEXT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS view_logs (
        video_id TEXT UNIQUE,
        last_view_update DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """)
    conn.commit()
    return conn, cursor

# Fetch latest videos
def fetch_latest_videos():
    """Fetch latest videos from the YouTube channel."""
    request = youtube.search().list(part="snippet", channelId=YOUTUBE_CHANNEL_ID, maxResults=5, order="date")
    return request.execute().get("items", [])

# Generate AI comment
def generate_comment(video_title):
    """Generate an AI-powered comment for a YouTube video."""
    prompt = f"Write a friendly and engaging comment for a YouTube video titled: {video_title}"
    try:
        response = model.generate_content(prompt)
        return response.text.strip() if response and response.text else "Great video!"
    except Exception as e:
        logger.error(f"Error generating comment: {str(e)}")
        return "Great video!"

# Log bot actions
def log_action(action, video_id, group_id=None):
    """Log bot actions to the database."""
    conn, cursor = get_db_connection()
    cursor.execute("INSERT OR IGNORE INTO actions (action, video_id, group_id) VALUES (?, ?, ?)", (action, video_id, group_id))
    conn.commit()
    conn.close()

# Send analytics
async def send_analytics(update: Update, _: CallbackContext):
    """Send live analytics to the user."""
    conn, cursor = get_db_connection()
    cursor.execute("SELECT * FROM actions ORDER BY timestamp DESC")
    actions = cursor.fetchall()
    conn.close()

    report = "📊 Live Analytics:\n\n"
    for action in actions[:10]:  # Show only last 10 actions
        report += f"- {action[1]} on video {action[2]}\n"

    await update.message.reply_text(report)

# Increase views (placeholder)
def increase_views(video_id, views):
    """Simulate increasing video views."""
    print(f"✅ Increased {views} views on video {video_id}")

# Process new videos
def process_new_videos():
    """Check for new videos and automate engagement."""
    videos = fetch_latest_videos()
    conn, cursor = get_db_connection()

    for video in videos:
        video_id = video["id"].get("videoId")
        if not video_id:
            continue

        title = video["snippet"]["title"]

        # Check if already processed
        cursor.execute("SELECT * FROM actions WHERE video_id = ?", (video_id,))
        if cursor.fetchone():
            continue

        # Generate and send comment
        comment = generate_comment(title)
        print(f"💬 Commenting on {title}: {comment}")

        # Log actions
        log_action("commented", video_id)

        # Increase views
        increase_views(video_id, 10)

        # Log view update
        cursor.execute("INSERT OR REPLACE INTO view_logs (video_id, last_view_update) VALUES (?, datetime('now'))", (video_id,))
        conn.commit()

    conn.close()

# Process old videos (increase views weekly)
def process_old_videos():
    """Increase views on old videos every 7 days."""
    conn, cursor = get_db_connection()
    cursor.execute("SELECT video_id FROM view_logs WHERE last_view_update <= datetime('now', '-7 days')")
    
    old_videos = cursor.fetchall()
    for video_id in old_videos:
        increase_views(video_id[0], 20)
        cursor.execute("UPDATE view_logs SET last_view_update = datetime('now') WHERE video_id = ?", (video_id[0],))
        conn.commit()

    conn.close()

# Background task for processing
async def background_task():
    """Run automated tasks in the background."""
    while True:
        process_new_videos()
        process_old_videos()
        await asyncio.sleep(600)  # Wait 10 minutes before checking again

# Handle errors
async def error_handler(update: Update, context: CallbackContext):
    """Handles bot errors."""
    logger.error(f"Exception: {context.error}")

# Main function
def main():
    global application
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Command handlers
    application.add_handler(CommandHandler("report", send_analytics))

    # Error handling
    application.add_error_handler(error_handler)

    # Start polling
    import asyncio

async def main():
    asyncio.create_task(background_task())

asyncio.run(main())
if __name__ == "__main__":
    main()
