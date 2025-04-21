from telethon import TelegramClient, events
from telethon.tl.types import PeerChannel
from telethon.tl.functions.messages import ImportChatInviteRequest
from telethon.errors.rpcerrorlist import UserAlreadyParticipantError
from pymongo import MongoClient
from config import api_id, api_hash, mongo_uri, mongo_db, mongo_collection
from parser import extract_credentials
from db import save_credentials
import sys
import io
import os

client = TelegramClient('session_cti', api_id, api_hash)

# Koneksi ke MongoDB
try:
    client_mongo = MongoClient(mongo_uri)
    db = client_mongo[mongo_db]
    credentials_collection = db[mongo_collection]
    print("[*] Connected to MongoDB successfully!")
except Exception as e:
    print(f"[ERROR] Failed to connect to MongoDB: {e}")
    sys.exit(1)

# Load source.txt
source_file = os.path.join(os.path.dirname(__file__), 'source/source.txt')
with open(source_file, 'r') as f:
    allowed_sources = set(line.strip() for line in f if line.strip())

async def get_entity_safely(source):
    try:
        if source.startswith('https://t.me/joinchat/') or source.startswith('https://t.me/+'):
            hash = source.split('/')[-1].replace('+', '')
            await client(ImportChatInviteRequest(hash))
            entity = await client.get_entity(source)
        elif source.startswith('https://t.me/'):
            username = source.split('/')[-1]
            entity = await client.get_entity(username)
        elif source.startswith('https://web.telegram.org/k/#'):
            chat_id = int(source.split('#')[-1])
            entity = await client.get_entity(chat_id)
        elif source.lstrip('-').isdigit():
            channel_id = int(source)
            entity = await client.get_entity(PeerChannel(channel_id))
        else:
            try:
                await client.join_chat(source)
            except UserAlreadyParticipantError:
                pass
            except Exception:
                pass
            entity = await client.get_entity(source)
        return entity
    except Exception as e:
        print(f"[ERROR] Gagal mendapatkan entitas untuk {source}: {e}")
        return None

def simple_progress(current, total):
    percent = int(current * 100 / total)
    sys.stdout.write(f"\r[+] Downloading... {percent}%")
    sys.stdout.flush()

async def download_initial_files():
    for chat_name in allowed_sources:
        try:
            print(f"[*] Checking source: {chat_name}")
            chat = await get_entity_safely(chat_name)
            if not chat:
                print(f"[!] Skip: Entity not found for {chat_name}")
                continue

            messages = await client.get_messages(chat, limit=1)
            for message in messages:
                if message.file and message.file.name.endswith('.txt'):
                    print(f"[+] Found file: {message.file.name} from {chat_name}")
                    file_bytes = await message.download_media(file=bytes, progress_callback=simple_progress)
                    print("\n[*] File downloaded, starting to decode...")

                    try:
                        text = io.BytesIO(file_bytes).read().decode('utf-8', errors='ignore')
                        print("[*] File decoded successfully, extracting credentials...")
                    except Exception as e:
                        print(f"[ERROR] Failed to decode file: {e}")
                        continue

                    creds = extract_credentials(text)
                    print(f"[*] Credentials extracted: {len(creds)} entries found.")

                    if creds:
                        for cred in creds:
                            print(f"Uploading to MongoDB: {cred}")
                        save_credentials(creds, {
                            "chat_id": message.chat_id,
                            "chat_name": chat_name,
                            "file_name": message.file.name,
                            "timestamp": message.date.isoformat()
                        })
                        print(f"[+] Initial file from {chat_name} saved with {len(creds)} credentials")
                    else:
                        print("[*] No credentials found in this file.")
        except Exception as e:
            print(f"[-] Error downloading from {chat_name}: {str(e)}")

@client.on(events.NewMessage(incoming=True))
async def handler(event):
    chat = await event.get_chat()
    chat_name = getattr(chat, 'username', None) or getattr(chat, 'title', None)

    if chat_name and chat_name not in allowed_sources:
        return

    if event.file and event.file.name.endswith('.txt'):
        print(f"[+] Found new file: {event.file.name} from {chat_name}")
        try:
            file_bytes = await event.download_media(file=bytes, progress_callback=simple_progress)
            print("\n[*] File downloaded, starting to decode...")

            try:
                text = io.BytesIO(file_bytes).read().decode('utf-8', errors='ignore')
                print("[*] File decoded successfully, extracting credentials...")
            except Exception as e:
                print(f"[ERROR] Failed to decode file: {e}")
                return

            creds = extract_credentials(text)
            print(f"[*] Credentials extracted: {len(creds)} entries found.")

            if creds:
                for cred in creds:
                    print(f"Uploading to MongoDB: {cred}")
                save_credentials(creds, {
                    "chat_id": event.chat_id,
                    "chat_name": chat_name,
                    "file_name": event.file.name,
                    "timestamp": event.date.isoformat()
                })
                print(f"[+] {len(creds)} credentials saved from {chat_name}")
            else:
                print("[*] No credentials found in this file.")
        except Exception as e:
            print(f"[ERROR] Failed to process file from {chat_name}: {e}")

# Start and run
print("[*] Connecting to Telegram...")
client.start()
print("[*] Connected to Telegram successfully!")
client.loop.run_until_complete(download_initial_files())
client.run_until_disconnected()
