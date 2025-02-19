import os
import time
import sqlite3
from telegram import Bot, Update
from telegram.ext import CommandHandler, Updater
from googleapiclient.discovery import build
from openai import OpenAI  # For advanced commenting

# Load environment variables
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")

# Initialize APIs
bot = Bot(token=TELEGRAM_BOT_TOKEN)
youtube = build("youtube", "v3", developerKey=YOUTUBE_API_KEY)
openai = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Database for logging actions
conn = sqlite3.connect("bot_actions.db")
cursor = conn.cursor()
cursor.execute("""
CREATE TABLE IF NOT EXISTS actions (
    id INTEGER PRIMARY KEY,
    action TEXT,
    video_id TEXT,
    group_id TEXT,
    timestamp DATETIME
)
""")
conn.commit()

def fetch_latest_videos(channel_id):
    """Fetch latest videos from a YouTube channel."""
    request = youtube.search().list(
        part="snippet",
        channelId=channel_id,
        maxResults=5,
        order="date"
    )
    return request.execute().get("items", [])

def generate_comment(video_title):
    """Generate a context-aware comment using AI."""
    response = openai.Completion.create(
        model="text-davinci-003",
        prompt=f"Generate a friendly comment for a YouTube video titled: {video_title}",
        max_tokens=50
    )
    return response.choices[0].text.strip()

def log_action(action, video_id, group_id=None):
    """Log bot actions to the database."""
    cursor.execute("""
    INSERT INTO actions (action, video_id, group_id, timestamp)
    VALUES (?, ?, ?, datetime('now'))
    """, (action, video_id, group_id))
    conn.commit()

def send_analytics(update: Update):
    """Send live analytics to the user."""
    cursor.execute("SELECT * FROM actions ORDER BY timestamp DESC")
    actions = cursor.fetchall()

    report = "📊 Live Analytics:\n\n"
    for action in actions:
        report += f"- {action[1]} on video {action[2]}\n"

    update.message.reply_text(report)

def main():
    updater = Updater(TELEGRAM_BOT_TOKEN)
    dispatcher = updater.dispatcher

    # Command handlers
    dispatcher.add_handler(CommandHandler("report", send_analytics))

    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
