import os
import re

from dotenv import load_dotenv

load_dotenv()

ID_INSTANCE = os.getenv("ID_INSTANCE")
API_TOKEN_INSTANCE = os.getenv("API_TOKEN_INSTANCE")
_green_api = None


def get_client():
    global _green_api
    if _green_api is None:
        from whatsapp_api_client_python import API
        _green_api = API.GreenApi(ID_INSTANCE, API_TOKEN_INSTANCE)
    return _green_api


def html_to_wa(text: str) -> str:
    """Convert basic Telegram HTML to WhatsApp-friendly markdown."""
    text = re.sub(r"<b>(.*?)</b>", r"*\1*", text)
    text = re.sub(r"<i>(.*?)</i>", r"_\1_", text)
    text = re.sub(r"<code>(.*?)</code>", r"\1", text)
    text = re.sub(r"<tg-spoiler>(.*?)</tg-spoiler>", r"\1", text)
    return text


def send_msg(wa_id: int, text: str):
    try:
        get_client().sending.sendMessage(f"{wa_id}@c.us", text)
    except Exception as e:
        print(f"Failed to send msg to {wa_id}: {e}")
