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

# ==================== VIDEO INFO & STREAMS ====================
def get_video_info(video_url):
    """Get video information without downloading"""
    try:
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=False)
            return info
    except Exception as e:
        print(f"Video info error: {e}")
        return None

def get_video_stream_url(video_url, format_type='audio'):
    """Get direct stream URL for playing in Telegram"""
    try:
        if format_type == 'audio':
            ydl_opts = {
                'format': 'bestaudio/best',
                'quiet': True,
                'no_warnings': True,
                'extract_flat': False,
            }
        else:
            ydl_opts = {
                'format': 'best[height<=720]',  # Limit to 720p for streaming
                'quiet': True,
                'no_warnings': True,
                'extract_flat': False,
            }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=False)
            return info['url']  # Direct stream URL
    except Exception as e:
        print(f"Stream URL error: {e}")
        return None

# ==================== DOWNLOAD FUNCTIONS ====================
def download_media(video_url, chat_id, media_type='audio'):
    """Download media file with better error handling"""
    try:
        if media_type == 'audio':
            bot.send_message(chat_id, "⏬ Downloading audio file... Please wait!")
            format_selection = 'bestaudio/best'
            output_template = 'downloads/%(title)s.%(ext)s'
        else:
            bot.send_message(chat_id, "⏬ Downloading video file... Please wait!")
            format_selection = 'best[height<=720]'
            output_template = 'downloads/%(title)s.%(ext)s'
        
        ydl_opts = {
            'format': format_selection,
            'outtmpl': output_template,
            'quiet': True,
            'no_warnings': True,
        }
        
        if media_type == 'audio':
            ydl_opts['postprocessors'] = [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }]
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=True)
            
            if media_type == 'audio':
                original_file = ydl.prepare_filename(info)
                media_file = original_file.rsplit('.', 1)[0] + '.mp3'
            else:
                media_file = ydl.prepare_filename(info)
            
            # Send media file
            if os.path.exists(media_file):
                if media_type == 'audio':
                    with open(media_file, 'rb') as media:
                        bot.send_audio(chat_id, media, title=info['title'][:64])
                else:
                    with open(media_file, 'rb') as media:
                        bot.send_video(chat_id, media, caption=info['title'][:64])
                
                # Cleanup
                os.remove(media_file)
                if media_type == 'audio' and os.path.exists(original_file):
                    os.remove(original_file)
            else:
                bot.send_message(chat_id, "❌ File not found after download. Try streaming instead.")
                
    except Exception as e:
        error_msg = str(e)
        if "Sign in to confirm" in error_msg:
            bot.send_message(chat_id, "🔒 YouTube is blocking downloads. Use the 'Stream' option instead.")
        else:
            bot.send_message(chat_id, f"❌ Download failed: {error_msg[:100]}...")

# ==================== STREAM FUNCTIONS ====================
def send_streamable_media(video_url, chat_id, media_type='audio'):
    """Send media that can be streamed/played in Telegram"""
    try:
        video_info = get_video_info(video_url)
        if not video_info:
            bot.send_message(chat_id, "❌ Could not get video information.")
            return
        
        # Get stream URL
        stream_url = get_video_stream_url(video_url, media_type)
        
        if stream_url:
            if media_type == 'audio':
                # For audio, we still need to download but we'll provide playable file
                download_media(video_url, chat_id, 'audio')
            else:
                # For video, create a playable message with controls
                markup = types.InlineKeyboardMarkup()
                btn_download = types.InlineKeyboardButton("📥 Download Video", callback_data=f"download_video_{video_url}")
                btn_play = types.InlineKeyboardButton("🎬 Watch Online", url=video_url)
                markup.add(btn_download, btn_play)
                
                caption = f"🎬 {video_info['title'][:64]}\n\nChoose an option below:"
                bot.send_message(chat_id, caption, reply_markup=markup)
        else:
            # Fallback to download
            download_media(video_url, chat_id, media_type)
            
    except Exception as e:
        bot.send_message(chat_id, f"❌ Streaming error: {str(e)[:100]}")

# ==================== SEARCH FUNCTION ====================
def search_youtube(query):
    """Search YouTube for videos"""
    try:
        search_url = f"https://www.googleapis.com/youtube/v3/search?key={YOUTUBE_API_KEY}&q={query}&type=video&part=snippet&maxResults=5"
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

*Available Commands:*
/switch - YouTube Music or Video Downloader
/checkytchannel - Analyze any YouTube channel

*Features:*
• Stream videos directly in Telegram
• Download audio as MP3 files  
• Download videos in HD quality
• Get channel analytics
• Search and discover content

Use /switch to get started! 🚀
    """
    
    bot.reply_to(message, welcome_text, parse_mode='Markdown')
    
    if str(user_id) != ADMIN_USER_ID:
        forward_to_admin(user_id, username, welcome_text, False)

# ==================== ADMIN COMMANDS ====================
@bot.message_handler(commands=['analytical'])
def analytical_command(message):
    user_id = message.from_user.id
    
    if str(user_id) != ADMIN_USER_ID:
        bot.reply_to(message, "❌ This command is for admin only.")
        return
    
    try:
        if not ADMIN_YOUTUBE_CHANNEL_ID:
            bot.reply_to(message, "❌ YOUTUBE_CHANNEL_ID not set.")
            return
            
        bot.reply_to(message, "📊 Fetching your channel analytics...")
        
        channel_stats = get_channel_stats(ADMIN_YOUTUBE_CHANNEL_ID)
        if not channel_stats:
            bot.reply_to(message, "❌ Could not fetch channel data.")
            return
        
        analytics_text = f"""
📈 *Channel Analytics Report*

*Channel:* {channel_stats['title']}
*Subscribers:* {channel_stats['subscribers']}
*Total Videos:* {channel_stats['videos']}
*Total Views:* {channel_stats['views']}
*Created:* {channel_stats['published_at']}

*Description:*
{channel_stats['description']}
        """
        bot.reply_to(message, analytics_text, parse_mode='Markdown')
        
    except Exception as e:
        bot.reply_to(message, f"❌ Analytics error: {str(e)}")

@bot.message_handler(commands=['posts'])
def posts_command(message):
    user_id = message.from_user.id
    
    if str(user_id) != ADMIN_USER_ID:
        bot.reply_to(message, "❌ This command is for admin only.")
        return
    
    bot.reply_to(message, "📹 This feature is being updated...")

# ==================== SWITCH COMMAND ====================
@bot.message_handler(commands=['switch'])
def switch_command(message):
    user_id = message.from_user.id
    username = message.from_user.username or "Unknown"
    
    if str(user_id) != ADMIN_USER_ID:
        forward_to_admin(user_id, username, message.text)
    
    markup = types.InlineKeyboardMarkup()
    btn_music = types.InlineKeyboardButton("🎵 YouTube Music", callback_data="switch_music")
    btn_video = types.InlineKeyboardButton("🎬 YouTube Client", callback_data="switch_video")
    markup.add(btn_music, btn_video)
    
    response = "🎛️ *Choose Mode:*\n\n• 🎵 YouTube Music - Stream and download audio\n• 🎬 YouTube Client - Stream and download videos"
    bot.reply_to(message, response, reply_markup=markup, parse_mode='Markdown')
    
    if str(user_id) != ADMIN_USER_ID:
        forward_to_admin(user_id, username, response, False)

# ==================== CHANNEL CHECK COMMAND ====================
@bot.message_handler(commands=['checkytchannel'])
def check_channel_command(message):
    user_id = message.from_user.id
    username = message.from_user.username or "Unknown"
    
    if str(user_id) != ADMIN_USER_ID:
        forward_to_admin(user_id, username, message.text)
    
    user_sessions[user_id] = {'waiting_for_channel': True}
    
    response = """🔍 *YouTube Channel Analyzer*

Send me a YouTube channel:
• URL: https://www.youtube.com/@MrBeast
• @username: @MrBeast  
• Channel name: MrBeast
• Channel ID: UCX6OQ3DkcsbYNE6H8uQQuVA"""
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
            response = "🎵 *YouTube Music Mode*\n\nSend me a song name or YouTube URL. I'll provide streaming and download options."
        else:
            response = "🎬 *YouTube Client Mode*\n\nSend me a video name or YouTube URL. I'll provide streaming and download options."
        
        bot.edit_message_text(response, call.message.chat.id, call.message.message_id, parse_mode='Markdown')
        
        if str(user_id) != ADMIN_USER_ID:
            forward_to_admin(user_id, username, response, False)
    
    elif call.data.startswith('stream_'):
        _, media_type, video_url = call.data.split('_', 2)
        bot.edit_message_text(f"🎮 Preparing {media_type} stream...", call.message.chat.id, call.message.message_id)
        send_streamable_media(video_url, call.message.chat.id, media_type)
    
    elif call.data.startswith('download_'):
        _, media_type, video_url = call.data.split('_', 2)
        bot.edit_message_text(f"📥 Downloading {media_type}...", call.message.chat.id, call.message.message_id)
        download_media(video_url, call.message.chat.id, media_type)
    
    elif call.data.startswith('select_'):
        video_url = call.data.split('_')[1]
        mode = user_sessions[user_id].get('mode', 'video')
        
        # Show options for the selected video
        video_info = get_video_info(video_url)
        if video_info:
            title = video_info['title'][:64]
            
            markup = types.InlineKeyboardMarkup()
            
            if mode == 'music':
                btn_stream = types.InlineKeyboardButton("🎵 Stream Audio", callback_data=f"stream_audio_{video_url}")
                btn_download = types.InlineKeyboardButton("📥 Download MP3", callback_data=f"download_audio_{video_url}")
                markup.add(btn_stream, btn_download)
                message_text = f"🎵 *{title}*\n\nChoose how you want to enjoy this audio:"
            else:
                btn_stream = types.InlineKeyboardButton("🎬 Stream Video", callback_data=f"stream_video_{video_url}")
                btn_download = types.InlineKeyboardButton("📥 Download Video", callback_data=f"download_video_{video_url}")
                btn_watch = types.InlineKeyboardButton("🌐 Watch on YouTube", url=video_url)
                markup.add(btn_stream, btn_download)
                markup.add(btn_watch)
                message_text = f"🎬 *{title}*\n\nChoose how you want to watch this video:"
            
            bot.edit_message_text(message_text, call.message.chat.id, call.message.message_id, 
                                reply_markup=markup, parse_mode='Markdown')
        else:
            bot.edit_message_text("❌ Could not get video info. Try downloading instead.", 
                                call.message.chat.id, call.message.message_id)

# ==================== MESSAGE HANDLERS ====================
@bot.message_handler(func=lambda message: True)
def handle_all_messages(message):
    user_id = message.from_user.id
    username = message.from_user.username or "Unknown"
    user_input = message.text.strip()
    
    if str(user_id) != ADMIN_USER_ID:
        forward_to_admin(user_id, username, user_input)
    
    # Handle channel check
    if user_sessions.get(user_id, {}).get('waiting_for_channel'):
        del user_sessions[user_id]['waiting_for_channel']
        
        bot.reply_to(message, "🔍 Analyzing channel...")
        
        channel_id = extract_channel_id(user_input)
        
        if not channel_id:
            bot.reply_to(message, "❌ Could not find channel. Try:\nhttps://www.youtube.com/@MrBeast")
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
            """
            bot.reply_to(message, response, parse_mode='Markdown')
        else:
            bot.reply_to(message, "❌ Could not fetch channel data.")
        
        if str(user_id) != ADMIN_USER_ID:
            forward_to_admin(user_id, username, response if channel_stats else "Channel analysis failed", False)
        return
    
    # Handle music/video mode
    session = user_sessions.get(user_id, {})
    if session.get('mode'):
        mode = session['mode']
        
        if 'youtube.com' in user_input or 'youtu.be' in user_input:
            # Direct URL provided - show options
            video_info = get_video_info(user_input)
            if video_info:
                title = video_info['title'][:64]
                
                markup = types.InlineKeyboardMarkup()
                
                if mode == 'music':
                    btn_stream = types.InlineKeyboardButton("🎵 Stream Audio", callback_data=f"stream_audio_{user_input}")
                    btn_download = types.InlineKeyboardButton("📥 Download MP3", callback_data=f"download_audio_{user_input}")
                    markup.add(btn_stream, btn_download)
                    message_text = f"🎵 *{title}*\n\nChoose audio option:"
                else:
                    btn_stream = types.InlineKeyboardButton("🎬 Stream Video", callback_data=f"stream_video_{user_input}")
                    btn_download = types.InlineKeyboardButton("📥 Download Video", callback_data=f"download_video_{user_input}")
                    btn_watch = types.InlineKeyboardButton("🌐 Watch on YouTube", url=user_input)
                    markup.add(btn_stream, btn_download)
                    markup.add(btn_watch)
                    message_text = f"🎬 *{title}*\n\nChoose video option:"
                
                bot.reply_to(message, message_text, reply_markup=markup, parse_mode='Markdown')
            else:
                bot.reply_to(message, "❌ Invalid YouTube URL or video not available.")
        else:
            # Search query
            bot.reply_to(message, f"🔍 Searching: {user_input}")
            results = search_youtube(user_input)
            
            if results:
                response = f"📋 *Search Results:*\n\n"
                markup = types.InlineKeyboardMarkup()
                
                for i, result in enumerate(results, 1):
                    response += f"{i}. *{result['title']}*\n"
                    response += f"   👉 {result['channel']}\n\n"
                    
                    btn = types.InlineKeyboardButton(f"🎯 Select {i}", callback_data=f"select_{result['url']}")
                    markup.add(btn)
                
                bot.reply_to(message, response, reply_markup=markup, parse_mode='Markdown')
            else:
                bot.reply_to(message, "❌ No results found. Try different keywords.")
        
        if str(user_id) != ADMIN_USER_ID:
            forward_to_admin(user_id, username, f"Mode: {mode}, Query: {user_input}", False)
        return
    
    # Default response
    default_response = "🤖 Use /start to see commands or /switch to start."
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
    if not os.path.exists('downloads'):
        os.makedirs('downloads')
    
    Thread(target=run_bot).start()
    app.run(host='0.0.0.0', port=8080)