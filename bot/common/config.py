import os
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
# Note: BOT_TOKEN validation is done in main.py to allow importing modules for testing

DATA_DIR = Path("data")
DATA_DIR.mkdir(parents=True, exist_ok=True)

SERVER_TZINFO = datetime.now().astimezone().tzinfo
MAX_TELEGRAM_LEN = 4096
