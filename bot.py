import os
import time
import sqlite3
import asyncio
from telegram import Bot, Update
from telegram.ext import Application, CommandHandler
from googleapiclient.discovery import build
import google.generativeai as genai  # Replacing OpenAI with Gemini API

# Load environment variables
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")  # Replacing OpenAI key with Gemini
YOUTUBE_CHANNEL_ID = os.getenv("YOUTUBE_CHANNEL_ID")

# Initialize APIs
bot = Bot(token=TELEGRAM_BOT_TOKEN)
youtube = build("youtube", "v3", developerKey=YOUTUBE_API_KEY)

# Configure Gemini API
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-pro")

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
def fetch_latest_videos(channel_id):
    """Fetch latest videos from a YouTube channel."""
    request = youtube.search().list(
        part="snippet",
        channelId=channel_id,
        maxResults=5,
        order="date"
    )
    return request.execute().get("items", [])

# Generate AI comment using Google Gemini
def generate_comment(video_title):
    """Generate an AI-powered comment for a YouTube video."""
    prompt = f"Write a friendly and engaging comment for a YouTube video titled: {video_title}"

    try:
        response = model.generate_content(prompt)
        return response.text.strip() if response and response.text else "Great video!"
    
    except Exception as e:
        return f"Error generating comment: {str(e)}"

# Log bot actions
def log_action(action, video_id, group_id=None):
    """Log bot actions to the database."""
    conn, cursor = get_db_connection()
    cursor.execute("""
    INSERT OR IGNORE INTO actions (action, video_id, group_id)
    VALUES (?, ?, ?)
    """, (action, video_id, group_id))
    conn.commit()
    conn.close()

# Send analytics
async def send_analytics(update: Update, _):
    """Send live analytics to the user."""
    conn, cursor = get_db_connection()
    cursor.execute("SELECT * FROM actions ORDER BY timestamp DESC")
    actions = cursor.fetchall()
    conn.close()

    report = "📊 Live Analytics:\n\n"
    for action in actions[:10]:  # Show only last 10 actions
        report += f"- {action[1]} on video {action[2]}\n"

    await update.message.reply_text(report)

# Increase views (placeholder function)
def increase_views(video_id, views):
    """Simulate increasing video views."""
    print(f"✅ Increased {views} views on video {video_id}")

# Process new videos
def process_new_videos():
    """Check for new videos and automate engagement."""
    videos = fetch_latest_videos(YOUTUBE_CHANNEL_ID)
    conn, cursor = get_db_connection()

    for video in videos:
        video_id = video["id"].get("videoId")
        if not video_id:
            continue  # Skip if not a video

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
        cursor.execute("""
        INSERT OR REPLACE INTO view_logs (video_id, last_view_update)
        VALUES (?, datetime('now'))
        """, (video_id,))
        conn.commit()

    conn.close()

# Process old videos (increase views weekly)
def process_old_videos():
    """Increase views on old videos every 7 days."""
    conn, cursor = get_db_connection()
    cursor.execute("""
    SELECT video_id FROM view_logs
    WHERE last_view_update <= datetime('now', '-7 days')
    """)
    
    old_videos = cursor.fetchall()
    for video_id in old_videos:
        increase_views(video_id[0], 20)
        cursor.execute("""
        UPDATE view_logs SET last_view_update = datetime('now')
        WHERE video_id = ?
        """, (video_id[0],))
        conn.commit()

    conn.close()

# Scheduled background task
async def background_task():
    """Run automated tasks in the background."""
    while True:
        process_new_videos()
        process_old_videos()
        await asyncio.sleep(600)  # Wait 10 minutes before checking again

# Main function
def main():
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Command handlers
    application.add_handler(CommandHandler("report", send_analytics))

    # Start polling
    application.run_polling()

    # Start background tasks
    asyncio.create_task(background_task())

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())