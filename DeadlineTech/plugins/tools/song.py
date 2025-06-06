import os
import re
import asyncio
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram.enums import ChatAction
from youtubesearchpython.__future__ import VideosSearch
from DeadlineTech import app
from config import API_KEY, API_BASE_URL

MIN_FILE_SIZE = 51200
DOWNLOADS_DIR = "downloads"

def extract_video_id(link: str) -> str:
    patterns = [
        r'youtube\.com\/(?:embed\/|v\/|watch\?v=|watch\?.+&v=)([0-9A-Za-z_-]{11})',
        r'youtu\.be\/([0-9A-Za-z_-]{11})',
        r'youtube\.com\/(?:playlist\?list=[^&]+&v=|v\/)([0-9A-Za-z_-]{11})',
        r'youtube\.com\/(?:.*\?v=|.*\/)([0-9A-Za-z_-]{11})'
    ]
    for pattern in patterns:
        match = re.search(pattern, link)
        if match:
            return match.group(1)
    return None

def api_dl(video_id: str) -> str | None:
    api_url = f"{API_BASE_URL}/download/song/{video_id}?key={API_KEY}"
    os.makedirs(DOWNLOADS_DIR, exist_ok=True)
    file_path = os.path.join(DOWNLOADS_DIR, f"{video_id}.mp3")

    if os.path.exists(file_path):
        return file_path

    try:
        import requests
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
        else:
            return None
    except Exception as e:
        print(f"API Download error: {e}")
        return None

async def remove_file_later(path: str, delay: int = 300):
    await asyncio.sleep(delay)
    try:
        if os.path.exists(path):
            os.remove(path)
            print(f"Deleted file after delay: {path}")
    except Exception as e:
        print(f"Error deleting file {path}: {e}")

@app.on_message(filters.command("song"))
async def song_command(client: Client, message: Message):
    if len(message.command) < 2:
        return await message.reply_text(
            "<b>Usage:</b>\n"
            "<code>/song <YouTube URL or song name></code>\n\n"
            "Example:\n<code>/song https://youtu.be/dQw4w9WgXcQ</code>\n"
            "or\n<code>/song Despacito</code>"
        )

    query = message.text.split(None, 1)[1].strip()
    video_id = extract_video_id(query)

    if video_id:
        # Direct URL, download immediately
        await message.reply_text("⬇️ Downloading your song... Please wait.")
        await send_audio_by_video_id(client, message, video_id)
    else:
        # Search and show inline buttons for top 5 results
        await message.reply_text("🔎 Searching for your song...")

        try:
            videos_search = VideosSearch(query, limit=5)
            search_result = await videos_search.next()
            results = search_result.get('result', [])

            if not results:
                return await message.reply_text("❌ No results found for your query.")

            buttons = []
            for video in results:
                title = video['title']
                vid = video['id']
                # Keep title short for button
                short_title = title if len(title) <= 30 else title[:27] + "..."
                buttons.append(
                    [InlineKeyboardButton(short_title, callback_data=f"dl_{vid}")]
                )

            await message.reply_text(
                "🎵 Select the song you want to download:",
                reply_markup=InlineKeyboardMarkup(buttons)
            )

        except Exception as e:
            await message.reply_text(f"❌ Search failed: {e}")

@app.on_callback_query(filters.regex(r"^dl_(.+)$"))
async def download_callback(client: Client, callback_query: CallbackQuery):
    video_id = callback_query.data.split("_", 1)[1]

    await callback_query.answer("⬇️ Downloading... Please wait.", show_alert=False)
    await client.send_chat_action(callback_query.message.chat.id, ChatAction.UPLOAD_AUDIO)

    # Edit message to indicate downloading
    await callback_query.message.edit("⬇️ Downloading your selected song...")

    await send_audio_by_video_id(client, callback_query.message, video_id)

    # Optionally, delete buttons or edit message to finished
    await callback_query.message.edit("✅ Song sent! Use /song to download another.")

async def send_audio_by_video_id(client: Client, message: Message, video_id: str):
    # Try to get video info for title and duration
    try:
        videos_search = VideosSearch(video_id, limit=1)
        search_result = await videos_search.next()
        video_info = search_result['result'][0] if search_result['result'] else None
        title = video_info['title'] if video_info else "Unknown Title"
        duration = video_info.get('duration', 'N/A') if video_info else 'N/A'
    except Exception:
        title = "Unknown Title"
        duration = "N/A"

    # Download song using your API (run in thread to avoid blocking)
    file_path = await asyncio.to_thread(api_dl, video_id)

    if file_path:
        await message.reply_audio(
            audio=file_path,
            title=title,
            performer="DeadlineTech Bot",
            duration=0,  # Optionally parse duration into seconds
            caption=f"🎵 <b>{title}</b>\n🕒 Duration: {duration}\n\nPowered by <a href="https://t.me/DeadlineTechTeam">Team DeadlineTech</a>"
        )
        # Schedule file deletion after 5 mins
        asyncio.create_task(remove_file_later(file_path, delay=300))
    else:
        await message.reply_text("❌ Failed to download the song. Please try again later.")
