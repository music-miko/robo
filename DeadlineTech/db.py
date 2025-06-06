from pymongo import MongoClient
from config import MONGO_URI, MONGO_DB, MONGO_COLLECTION

client = MongoClient(MONGO_URI)
db = client[MONGO_DB]
collection = db[MONGO_COLLECTION]

def is_song_sent(video_id: str) -> bool:
    return collection.find_one({"video_id": video_id}) is not None

def mark_song_as_sent(video_id: str):
    collection.insert_one({"video_id": video_id})
