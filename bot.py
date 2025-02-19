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
    video_id TEXT UNIQUE,
    group_id TEXT,
    timestamp DATETIME
)
""")
cursor.execute("""
CREATE TABLE IF NOT EXISTS view_logs (
    video_id TEXT UNIQUE,
    last_view_update DATETIME
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

def increase_views(video_id, views):
    """Simulate increasing video views (replace this with real API calls if needed)."""
    print(f"✅ Increased {views} views on video {video_id}")

def process_new_videos(channel_id):
    """Automatically check for new videos, comment, and increase views."""
    videos = fetch_latest_videos(channel_id)
    
    for video in videos:
        video_id = video["id"]["videoId"]
        title = video["snippet"]["title"]
        
        # Check if video is already processed
        cursor.execute("SELECT * FROM actions WHERE video_id = ?", (video_id,))
        if cursor.fetchone():
            continue  # Skip already processed videos

        # Generate and send comment
        comment = generate_comment(title)
        print(f"💬 Commenting on {title}: {comment}")
        
        # Log the action
        log_action("commented", video_id)

        # Increase views (10 for new videos)
        increase_views(video_id, 10)
        
        # Log view update
        cursor.execute("""
        INSERT INTO view_logs (video_id, last_view_update)
        VALUES (?, datetime('now'))
        """, (video_id,))
        conn.commit()

def process_old_videos():
    """Increase views on old videos weekly."""
    cursor.execute("""
    SELECT video_id, last_view_update FROM view_logs
    WHERE last_view_update <= datetime('now', '-7 days')
    """)
    
    old_videos = cursor.fetchall()
    
    for video_id, _ in old_videos:
        increase_views(video_id, 20)
        
        # Update last view update timestamp
        cursor.execute("""
        UPDATE view_logs SET last_view_update = datetime('now')
        WHERE video_id = ?
        """, (video_id,))
        conn.commit()

def main():
    updater = Updater(TELEGRAM_BOT_TOKEN)
    dispatcher = updater.dispatcher

    # Command handlers
    dispatcher.add_handler(CommandHandler("report", send_analytics))

    # Start automated processes
    channel_id = "YOUR_CHANNEL_ID_HERE"  # Replace with your channel ID
    while True:
        process_new_videos(channel_id)
        process_old_videos()
        time.sleep(600)  # Wait 10 minutes before checking again

    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()