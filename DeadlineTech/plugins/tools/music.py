import os
import re
import asyncio
import requests
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram.enums import ChatAction
from youtubesearchpython.__future__ import VideosSearch

from DeadlineTech import app
from config import API_KEY, API_BASE_URL, SAVE_CHANNEL_ID

# Constants
MIN_FILE_SIZE = 51200
DOWNLOADS_DIR = "downloads"

# Extract YouTube video ID from URLs or return None
def extract_video_id(link: str) -> str | None:
    patterns = [
        r'youtube\.com\/(?:embed\/|v\/|watch\?v=|watch\?.+&v=)([0-9A-Za-z_-]{11})',
        r'youtu\.be\/([0-9A-Za-z_-]{11})',
        r'youtube\.com\/(?:playlist\?list=[^&]+&v=|v\/)([0-9A-Za-z_-]{11})',
        r'youtube\.com\/(?:.*\?v=|.*/)([0-9A-Za-z_-]{11})'
    ]
    for pattern in patterns:
        match = re.search(pattern, link)
        if match:
            return match.group(1)
    return None

# Download audio using external API
def api_dl(video_id: str) -> str | None:
    api_url = f"{API_BASE_URL}/download/song/{video_id}?key={API_KEY}"
    os.makedirs(DOWNLOADS_DIR, exist_ok=True)
    file_path = os.path.join(DOWNLOADS_DIR, f"{video_id}.mp3")

    if os.path.exists(file_path):
        return file_path

    try:
        response = requests.get(api_url, stream=True, timeout=15)
        if response.status_code == 200:
            with open(file_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            if os.path.getsize(file_path) < MIN_FILE_SIZE:
                os.remove(file_path)
                return None
            return file_path
        return None
    except Exception as e:
        print(f"API Download error: {e}")
        return None

# Delete downloaded file after delay
async def remove_file_later(path: str, delay: int = 600):
    await asyncio.sleep(delay)
    try:
        if os.path.exists(path):
            os.remove(path)
            print(f"🗑️ Deleted file after delay: {path}")
    except Exception as e:
        print(f"❌ Error deleting file {path}: {e}")

# Convert duration string to seconds
def parse_duration(duration: str) -> int:
    parts = list(map(int, duration.split(":")))
    if len(parts) == 3:
        h, m, s = parts
    elif len(parts) == 2:
        h, m = 0, parts[0]
        s = parts[1]
    else:
        return int(parts[0])
    return h * 3600 + m * 60 + s

# /song command handler
@app.on_message(filters.command(["song", "music"]))
async def song_command(client: Client, message: Message):
    if len(message.command) < 2:
        return await message.reply_text(
            "🎧 <b>How to Use:</b> <code>/song &lt;YouTube URL or Song Name&gt;</code>\nExample: <code>/song Shape of You</code>",
            parse_mode="html"
        )

    query = message.text.split(None, 1)[1].strip()
    video_id = extract_video_id(query)

    if video_id:
        await message.reply_text("🎼 Fetching your song, please wait...")
        await send_audio_by_video_id(client, message, video_id)
    else:
        await message.reply_text("🔍 Searching for your song...")
        try:
            videos_search = VideosSearch(query, limit=5)
            search_result = await videos_search.next()
            results = search_result.get('result', [])

            if not results:
                return await message.reply_text("❌ No results found.")

            buttons = [
                [InlineKeyboardButton(
                    text=(video['title'][:30] + '...') if len(video['title']) > 30 else video['title'],
                    callback_data=f"dl_{video['id']}")]
                for video in results
            ]

            await message.reply_text(
                "🎶 <b>Select the song you want:</b>",
                reply_markup=InlineKeyboardMarkup(buttons),
                parse_mode="html"
            )

        except Exception as e:
            await message.reply_text(f"❌ Search failed: {e}")

# Callback query handler for song selection
@app.on_callback_query(filters.regex(r"^dl_(.+)$"))
async def download_callback(client: Client, callback_query: CallbackQuery):
    video_id = callback_query.data.split("_", 1)[1]
    await callback_query.answer("🎧 Downloading your track...", show_alert=False)
    await client.send_chat_action(callback_query.message.chat.id, ChatAction.UPLOAD_AUDIO)
    await callback_query.message.edit("🎶 Preparing your song...")
    await send_audio_by_video_id(client, callback_query.message, video_id)
    await callback_query.message.edit("✅ Song sent! Use /song to download more music.")

# Send audio file to user and forward to channel
async def send_audio_by_video_id(client: Client, message: Message, video_id: str):
    try:
        videos_search = VideosSearch(video_id, limit=1)
        search_result = await videos_search.next()
        video_info = search_result['result'][0] if search_result['result'] else None
        title = video_info['title'] if video_info else "Unknown Title"
        duration_str = video_info.get('duration', '0:00')
        duration = parse_duration(duration_str)
        video_url = video_info.get('link', None)
    except Exception:
        title = "Unknown Title"
        duration_str = "0:00"
        duration = 0
        video_url = None

    file_path = await asyncio.to_thread(api_dl, video_id)

    if file_path:
        caption = f"🎧 <b>{title}</b>\n🕒 Duration: {duration_str}"
        if video_url:
            caption += f"\n🔗 <a href=\"{video_url}\">Watch on YouTube</a>"
        caption += "\n\n🎵 Powered by <a href=\"https://t.me/DeadlineTechTeam\">Team DeadlineTech</a>"

        audio_msg = await message.reply_audio(
            audio=file_path,
            title=title,
            performer="DeadlineTech Bot",
            duration=duration,
            caption=caption,
            parse_mode="html"
        )

        # Forward to save channel
        if SAVE_CHANNEL_ID:
            try:
                await client.send_audio(
                    chat_id=SAVE_CHANNEL_ID,
                    audio=file_path,
                    title=title,
                    performer="DeadlineTech Bot",
                    duration=duration,
                    caption=caption,
                    parse_mode="html"
                )
            except Exception as e:
                print(f"❌ Error saving to channel: {e}")

        asyncio.create_task(remove_file_later(file_path, delay=600))
    else:
        await message.reply_text("❌ Failed to download the song. Please try again later.")
