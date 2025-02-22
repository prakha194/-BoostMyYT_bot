import logging
import requests
import sqlite3
import asyncio
import random
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import os

# Load API keys from environment variables
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
YOUTUBE_CHANNEL_ID = os.getenv("YOUTUBE_CHANNEL_ID")
TELEGRAM_GROUP_ID = os.getenv("TELEGRAM_GROUP_ID")
TELEGRAM_ADMIN_ID = os.getenv("TELEGRAM_ADMIN_ID")

# Initialize Telegram Bot & Dispatcher
bot = Bot(token=TELEGRAM_BOT_TOKEN)
dp = Dispatcher(bot)
scheduler = AsyncIOScheduler()

# Database Setup
conn = sqlite3.connect("youtube_data.db")
cursor = conn.cursor()
cursor.execute("""
    CREATE TABLE IF NOT EXISTS replied_comments (
        comment_id TEXT PRIMARY KEY
    )
""")
conn.commit()

# Function to fetch latest videos
def fetch_latest_videos():
    url = f"https://www.googleapis.com/youtube/v3/search?part=snippet&channelId={YOUTUBE_CHANNEL_ID}&maxResults=5&order=date&type=video&key={YOUTUBE_API_KEY}"
    response = requests.get(url).json()
    return [(item["id"]["videoId"], item["snippet"]["title"]) for item in response.get("items", [])]

# Function to send new videos to group
async def send_new_videos():
    videos = fetch_latest_videos()
    for video_id, title in videos:
        message = f"📢 **New Video Uploaded!**\n🎬 *{title}*\n🔗 https://www.youtube.com/watch?v={video_id}"
        await bot.send_message(chat_id=TELEGRAM_GROUP_ID, text=message, parse_mode="Markdown")

# Function to send weekly stats
async def send_weekly_stats():
    videos = fetch_latest_videos()
    if not videos:
        return

    stats_message = "📊 **Weekly YouTube Stats**\n\n"
    for video_id, title in videos:
        stats_message += f"🎬 *{title}*\n🔗 [Watch Now](https://www.youtube.com/watch?v={video_id})\n\n"

    await bot.send_message(chat_id=TELEGRAM_ADMIN_ID, text=stats_message, parse_mode="Markdown")

# Schedule tasks
scheduler.add_job(lambda: asyncio.create_task(send_new_videos()), "interval", hours=1)
scheduler.add_job(lambda: asyncio.create_task(send_weekly_stats()), "cron", day_of_week="sun", hour=1)

# Start Bot & Scheduler
async def on_startup(_):
    scheduler.start()
    print("Bot & Scheduler Started")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    executor.start_polling(dp, skip_updates=True, on_startup=on_startup)
