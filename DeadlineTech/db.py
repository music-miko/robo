from pymongo import MongoClient
from config import MONGO_URI

client = MongoClient(MONGO_URI)
db = client["music"]
collection = db["song"]

def is_song_sent(video_id: str) -> bool:
    return collection.find_one({"video_id": video_id}) is not None

def mark_song_as_sent(video_id: str):
    collection.insert_one({"video_id": video_id})
