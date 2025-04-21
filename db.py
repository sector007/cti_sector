from pymongo import MongoClient
from config import mongo_uri, mongo_db, mongo_collection

client = MongoClient(mongo_uri)
db = client[mongo_db]
collection = db[mongo_collection]

def save_credentials(entries, meta=None):
    for entry in entries:
        doc = {**entry}
        if meta:
            doc.update(meta)
        collection.insert_one(doc)
