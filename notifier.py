import logging

import httpx

logger = logging.getLogger(__name__)

async def send_discord_webhook(webhook_url: str, item: dict):
    if not webhook_url:
        return

    item_name = item.get("item", {}).get("name", "Unknown Item")
    item_icon = item.get("item", {}).get("icon", "")
    price = item.get("price", 0)
    market_avg = item.get("market_avg", 0)
    profile_slug = item.get("profile_slug", "")

    # Calculate discount
    discount = 0
    if market_avg > 0 and price < market_avg:
        discount = round((market_avg - price) / market_avg * 100, 1)

    # Construct the link
    link = f"https://metaforge.app/profile/{profile_slug}?game=arc-raiders" if profile_slug else "https://metaforge.app"

    embed = {
        "title": f"🚨 Snipe Detected: {item_name}",
        "url": link,
        "color": 16711680, # Red
        "fields": [
            {
                "name": "Price",
                "value": f"{price} SEEDS",
                "inline": True
            },
            {
                "name": "Discount",
                "value": f"{discount}% (Avg: {market_avg})",
                "inline": True
            },
            {
                "name": "Link",
                "value": f"[Snipe Now]({link})",
                "inline": False
            }
        ]
    }

    if item_icon:
        embed["thumbnail"] = {"url": item_icon}

    payload = {
        "embeds": [embed]
    }

    try:
        async with httpx.AsyncClient() as client:
            await client.post(webhook_url, json=payload, timeout=10.0)
    except Exception as e:
        logger.error(f"Error sending Discord webhook: {e}")

def escape_markdown_v2(text: str) -> str:
    """Escapes markdown v2 special characters."""
    escape_chars = r'_*[]()~`>#+-=|{}.!'
    text = str(text)
    return ''.join(f'\\{char}' if char in escape_chars else char for char in text)

class TelegramNotifier:
    def __init__(self, bot_token: str, chat_id: str):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.api_url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"

    async def send_alert(self, item: dict):
        if not self.bot_token or not self.chat_id:
            return

        item_name = item.get("item", {}).get("name", "Unknown Item")
        price = item.get("price", 0)
        market_avg = item.get("market_avg", 0)
        alert_reason = item.get("alert_reason", "Alert")
        profile_slug = item.get("profile_slug", "")

        # Format message in MarkdownV2
        escaped_item_name = escape_markdown_v2(item_name)
        escaped_reason = escape_markdown_v2(alert_reason)
        escaped_price = escape_markdown_v2(price)
        escaped_avg = escape_markdown_v2(market_avg)

        text = (
            f"*{escaped_item_name}*\n"
            f"Reason: {escaped_reason}\n"
            f"Price: {escaped_price} SEEDS\n"
            f"Market Avg: {escaped_avg} SEEDS"
        )

        buy_url = f"https://metaforge.app/profile/{profile_slug}?game=arc-raiders"

        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": "MarkdownV2",
            "reply_markup": {
                "inline_keyboard": [
                    [
                        {
                            "text": "Buy / Snipe Now",
                            "url": buy_url
                        }
                    ]
                ]
            }
        }

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(self.api_url, json=payload)
                response.raise_for_status()
            except Exception as e:
                logger.error(f"Failed to send telegram alert: {e}")

