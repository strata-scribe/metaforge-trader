import httpx
import asyncio

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
        print(f"Error sending Discord webhook: {e}")
