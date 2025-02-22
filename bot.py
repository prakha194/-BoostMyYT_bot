import logging
import requests
import sqlite3
import google.generativeai as genai
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from config import *

# Initialize Telegram Bot
bot = Bot(token=TELEGRAM_BOT_TOKEN)
dp = Dispatcher(bot)
scheduler = AsyncIOScheduler()

# Gemini AI Setup
genai.configure(api_key=GEMINI_API_KEY)

# Database Setup
conn = sqlite3.connect("youtube_comments.db")
cursor = conn.cursor()
cursor.execute("""
    CREATE TABLE IF NOT EXISTS replied_comments (
        comment_id TEXT PRIMARY KEY
    )
""")
conn.commit()

# Fetch comments from latest video
def fetch_latest_video_comments():
    url = f"https://www.googleapis.com/youtube/v3/search?part=snippet&channelId={YOUTUBE_CHANNEL_ID}&maxResults=1&order=date&type=video&key={YOUTUBE_API_KEY}"
    response = requests.get(url).json()
    
    if "items" in response:
        video_id = response["items"][0]["id"]["videoId"]
        comments_url = f"https://www.googleapis.com/youtube/v3/commentThreads?part=snippet&videoId={video_id}&key={YOUTUBE_API_KEY}&maxResults=20"
        comments_response = requests.get(comments_url).json()
        
        comments = []
        if "items" in comments_response:
            for item in comments_response["items"]:
                comment_id = item["id"]
                comment_text = item["snippet"]["topLevelComment"]["snippet"]["textDisplay"]
                comments.append((video_id, comment_id, comment_text))
        return comments
    return []

# Generate AI Response using Gemini
def generate_ai_reply(comment_text):
    model = genai.GenerativeModel("gemini-pro")
    response = model.generate_content(f"Reply to this YouTube comment: {comment_text}")
    return response.text if response.text else "Thank you for your comment! 😊"

# Send AI-generated comment to Telegram
async def send_to_telegram(video_id, comment_text, ai_reply):
    message = f"📢 **New Comment Detected**\n\n"
    message += f"🎬 **Video ID:** `{video_id}`\n"
    message += f"💬 **Comment:** {comment_text}\n"
    message += f"🤖 **AI Reply:** {ai_reply}"
    
    await bot.send_message(chat_id="@your_channel_or_group", text=message, parse_mode="Markdown")

# Auto-comment function
async def auto_comment():
    comments = fetch_latest_video_comments()
    for video_id, comment_id, text in comments:
        cursor.execute("SELECT * FROM replied_comments WHERE comment_id=?", (comment_id,))
        if not cursor.fetchone():
            ai_reply = generate_ai_reply(text)
            await send_to_telegram(video_id, text, ai_reply)
            cursor.execute("INSERT INTO replied_comments VALUES (?)", (comment_id,))
            conn.commit()
            logging.info(f"Sent AI reply to Telegram: {text}")

# Schedule auto-commenting every 30 minutes
scheduler.add_job(auto_comment, "interval", minutes=30)
scheduler.start()

# Start bot
if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)