import os
import time
import json
import logging
import requests
import dropbox
from telegram import Bot
from datetime import datetime
from pytz import timezone
import random

class DropboxToThreadsUploader:
    DROPBOX_TOKEN_URL = "https://api.dropbox.com/oauth2/token"
    THREADS_API_BASE = "https://graph.threads.net/v1.0"

    def __init__(self, account_name, threads_user_id, threads_access_token, dropbox_app_key, dropbox_app_secret, dropbox_refresh_token, dropbox_folder, telegram_bot_token=None, telegram_chat_id=None, schedule_file="caption/config.json"):
        self.account_name = account_name
        self.script_name = f"{account_name}_threads_post.py"
        self.ist = timezone('Asia/Kolkata')
        self.account_key = account_name
        self.schedule_file = schedule_file

        # Logging
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger()

        # Account-specific secrets
        self.threads_access_token = threads_access_token.strip() if threads_access_token else None
        self.threads_user_id = threads_user_id
        self.dropbox_app_key = dropbox_app_key
        self.dropbox_app_secret = dropbox_app_secret
        self.dropbox_refresh_token = dropbox_refresh_token
        self.dropbox_folder = dropbox_folder
        self.telegram_bot_token = telegram_bot_token or os.getenv("TELEGRAM_BOT_TOKEN")
        self.telegram_chat_id = telegram_chat_id or os.getenv("TELEGRAM_CHAT_ID")

        if self.telegram_bot_token is not None:
            self.telegram_bot = Bot(token=self.telegram_bot_token)
        else:
            self.telegram_bot = None
        self.start_time = time.time()

    def send_message(self, msg, level=logging.INFO):
        full_msg = f"[{self.account_name}] [{self.script_name}]\n" + msg
        try:
            if self.telegram_bot is not None:
                self.telegram_bot.send_message(chat_id=self.telegram_chat_id, text=full_msg)
            else:
                self.logger.warning("Telegram bot is not configured. Message not sent to Telegram.")
            self.logger.log(level, full_msg)
        except Exception as e:
            self.logger.error(f"Telegram send error: {e}")

    def refresh_dropbox_token(self):
        data = {
            "grant_type": "refresh_token",
            "refresh_token": self.dropbox_refresh_token,
            "client_id": self.dropbox_app_key,
            "client_secret": self.dropbox_app_secret,
        }
        r = requests.post(self.DROPBOX_TOKEN_URL, data=data)
        r.raise_for_status()
        return r.json().get("access_token")

    def list_dropbox_files(self, dbx):
        files = dbx.files_list_folder(self.dropbox_folder).entries
        valid_exts = ('.mp4', '.mov', '.jpg', '.jpeg', '.png')
        return [f for f in files if f.name.lower().endswith(valid_exts)]

    def get_caption_from_config(self):
        try:
            with open(self.schedule_file, 'r') as f:
                config = json.load(f)
            today = datetime.now(self.ist).strftime("%A")
            return config.get(self.account_key, {}).get(today, {}).get("caption", f"✨ #{self.account_name} ✨")
        except Exception as e:
            self.logger.warning(f"Could not load caption from config: {e}")
            return f"✨ #{self.account_name} ✨"

    def post_to_threads(self, dbx, file, caption):
        name = file.name.lower()
        media_type = "VIDEO" if name.endswith((".mp4", ".mov")) else "IMAGE"

        temp_link = dbx.files_get_temporary_link(file.path_lower).link
        total_files = len(self.list_dropbox_files(dbx))

        self.send_message(f"🚀 Uploading to Threads: {file.name}\n📐 Type: {media_type}\n📦 Remaining: {total_files}")

        post_url = f"{self.THREADS_API_BASE}/{self.threads_user_id}/threads"
        data = {
            "access_token": self.threads_access_token,
            "text": caption,
        }

        if temp_link:
            if media_type == "VIDEO":
                data["video_url"] = temp_link
                data["media_type"] = "VIDEO"
            else:
                data["image_url"] = temp_link
                data["media_type"] = "IMAGE"
        else:
            data["media_type"] = "TEXT_POST"

        res = requests.post(post_url, data=data)
        if res.status_code == 200:
            self.send_message(f"✅ Successfully posted to Threads: {file.name}")
            return True
        else:
            self.send_message(f"❌ Threads post failed: {file.name}\n{res.text}", level=logging.ERROR)
            return False

    def authenticate_dropbox(self):
        access_token = self.refresh_dropbox_token()
        return dropbox.Dropbox(oauth2_access_token=access_token)

    def run(self):
        self.send_message(f"📡 Threads Run started at: {datetime.now(self.ist).strftime('%Y-%m-%d %H:%M:%S')}")
        try:
            caption = self.get_caption_from_config()
            dbx = self.authenticate_dropbox()
            files = self.list_dropbox_files(dbx)
            if not files:
                self.send_message("📭 No files found in Dropbox folder.")
                return

            file = random.choice(files)  # Pick a random file to post
            success = self.post_to_threads(dbx, file, caption)
            try:
                dbx.files_delete_v2(file.path_lower)
                self.send_message(f"🗑️ Deleted file after attempt: {file.name}")
            except Exception as e:
                self.send_message(f"⚠️ Failed to delete file {file.name}: {e}", level=logging.WARNING)

        except Exception as e:
            self.send_message(f"❌ Script crashed: {e}", level=logging.ERROR)
        finally:
            duration = time.time() - self.start_time
            self.send_message(f"🏁 Run complete in {duration:.1f} seconds")

# --- Multi-account logic ---

ACCOUNTS = [
    {
        "account_name": "eclipsed.by.you",
        "threads_user_id": os.getenv("THREADS_USER_ID_1"),
        "threads_access_token": os.getenv("THREADS_ACCESS_TOKEN_1"),
        "dropbox_app_key": os.getenv("DROPBOX_APP_KEY_1"),
        "dropbox_app_secret": os.getenv("DROPBOX_APP_SECRET_1"),
        "dropbox_refresh_token": os.getenv("DROPBOX_REFRESH_TOKEN_1"),
        "dropbox_folder": "/Threads_1",
    },
    {
        "account_name": "inkwisp",
        "threads_user_id": os.getenv("THREADS_USER_ID_2"),
        "threads_access_token": os.getenv("THREADS_ACCESS_TOKEN_2"),
        "dropbox_app_key": os.getenv("DROPBOX_APP_KEY_2"),
        "dropbox_app_secret": os.getenv("DROPBOX_APP_SECRET_2"),
        "dropbox_refresh_token": os.getenv("DROPBOX_REFRESH_TOKEN_2"),
        "dropbox_folder": "/threads_2",
    },
    {
        "account_name": "ink_wisps",
        "threads_user_id": os.getenv("THREADS_USER_ID_3"),
        "threads_access_token": os.getenv("THREADS_ACCESS_TOKEN_3"),
        "dropbox_app_key": os.getenv("DROPBOX_APP_KEY_3"),
        "dropbox_app_secret": os.getenv("DROPBOX_APP_SECRET_3"),
        "dropbox_refresh_token": os.getenv("DROPBOX_REFRESH_TOKEN_3"),
        "dropbox_folder": "/Threads_3",
    }
]

if __name__ == "__main__":
    for account in ACCOUNTS:
        uploader = DropboxToThreadsUploader(**account)
        uploader.run()
