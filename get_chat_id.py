"""TELEGRAM_BOT_TOKEN으로 최근 메시지를 조회해 chat_id만 출력 (토큰 값은 출력하지 않음)."""
import os

import requests
from dotenv import load_dotenv

load_dotenv()

token = os.environ.get("TELEGRAM_BOT_TOKEN")
if not token:
    raise SystemExit(".env에 TELEGRAM_BOT_TOKEN이 없습니다.")

resp = requests.get(f"https://api.telegram.org/bot{token}/getUpdates", timeout=10)
resp.raise_for_status()
updates = resp.json().get("result", [])

if not updates:
    print("메시지가 없습니다. 봇과의 대화창에서 먼저 아무 메시지나 보낸 뒤 다시 실행하세요.")
else:
    chat_id = updates[-1]["message"]["chat"]["id"]
    print(f"chat_id: {chat_id}")
