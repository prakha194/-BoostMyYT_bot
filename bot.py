import logging
import requests
import sqlite3
import asyncio
import google.generativeai as genai
from aiogram import Bot, Dispatcher, types
from aiogram.types import Message
from aiogram import executor
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import os
import random
from fastapi import FastAPI
import uvicorn

# Load API keys
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
YOUTUBE_CHANNEL_ID = os.getenv("YOUTUBE_CHANNEL_ID")
TELEGRAM_GROUP_ID = int(os.getenv("TELEGRAM_GROUP_ID"))
TELEGRAM_ADMIN_ID = int(os.getenv("TELEGRAM_ADMIN_ID"))

# Initialize FastAPI App
app = FastAPI()

# Initialize Telegram Bot
bot = Bot(token=TELEGRAM_BOT_TOKEN)
dp = Dispatcher(bot)

# Gemini AI Setup
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

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

# Function to fetch old videos
def fetch_old_videos():
    url = f"https://www.googleapis.com/youtube/v3/search?part=snippet&channelId={YOUTUBE_CHANNEL_ID}&maxResults=10&order=viewCount&type=video&key={YOUTUBE_API_KEY}"
    response = requests.get(url).json()
    return [(item["id"]["videoId"], item["snippet"]["title"]) for item in response.get("items", [])]

# Function to send new videos to group
async def send_new_videos():
    videos = fetch_latest_videos()
    for video_id, title in videos:
        message = f"📢 **New Video Uploaded!**\n🎬 *{title}*\n🔗 https://www.youtube.com/watch?v={video_id}"
        await bot.send_message(chat_id=TELEGRAM_GROUP_ID, text=message, parse_mode="Markdown")

# Function to distribute 20 views per week
async def distribute_views():
    new_videos = fetch_latest_videos()
    old_videos = fetch_old_videos()

    if new_videos:
        selected_new = random.sample(new_videos, min(10, len(new_videos)))
        selected_old = random.sample(old_videos, min(10, len(old_videos)))
    else:
        selected_new = []
        selected_old = random.sample(old_videos, min(20, len(old_videos)))

    all_selected = selected_new + selected_old

    for video_id, title in all_selected:
        message = f"👀 Boosting Views: {title}\n🔗 https://www.youtube.com/watch?v={video_id}"
        await bot.send_message(chat_id=TELEGRAM_GROUP_ID, text=message, parse_mode="Markdown")

# Function to send weekly stats to admin
async def send_weekly_stats():
    videos = fetch_latest_videos()
    if not videos:
        return

    stats_message = "📊 **Weekly YouTube Stats**\n\n"
    for video_id, title in videos:
        stats_message += f"🎬 *{title}*\n🔗 [Watch Now](https://www.youtube.com/watch?v={video_id})\n\n"

    await bot.send_message(chat_id=TELEGRAM_ADMIN_ID, text=stats_message, parse_mode="Markdown")

# Report command to send stats to admin anytime
@dp.message_handler(commands=["report"])
async def report_command(message: Message):
    if message.from_user.id == TELEGRAM_ADMIN_ID:
        await send_weekly_stats()
        await message.reply("📊 Weekly stats sent to your DM!")

# Schedule tasks
scheduler = AsyncIOScheduler()
scheduler.add_job(send_new_videos, "interval", hours=1)
scheduler.add_job(distribute_views, "cron", day_of_week="mon", hour=12)  # Weekly view boost
scheduler.add_job(send_weekly_stats, "cron", day_of_week="sun", hour=1)

# API Route for Health Check (fixes 405 error)
@app.get("/")
async def root():
    return {"message": "Telegram Bot is Running!"}

# Function to start bot properly
async def start_bot():
    scheduler.start()
    await dp.start_polling()

# Run FastAPI Server and Telegram Bot
if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.create_task(start_bot())
    uvicorn.run(app, host="0.0.0.0", port=8000)
