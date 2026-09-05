import asyncio
import csv
import io
import json
import os
from collections import defaultdict
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from statistics import median

import httpx
from fastapi import Body, FastAPI, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.templating import Jinja2Templates

from config_models import AppConfig
from notifier import TelegramNotifier, send_discord_webhook
from worker import DealsWorker


class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception as e:
                print(f"Broadcast error: {e}")

manager = ConnectionManager()


# File-based Persistence
CONFIG_FILE = "config.json"
DEFAULT_CONFIG = {
    "settings": {
        "snipe_legendary_threshold": 60,
        "snipe_epic_threshold": 15,
        "max_listings_cache": 100,
        "poll_interval": 20,
        "supabase_token": "",
        "discord_webhook_url": "",
        "telegram_bot_token": "",
        "telegram_chat_id": ""

    },
    "owned_blueprints": [],
    "ignore_list": ["familiar-duck"],
    "completed_quests": [],
    "needed_items": {}, 
    "watchlist": {
        "jupiter-i": 400,
        "anvil-iv": 150
    }
}

def load_config():
    if not os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "w") as f:
            json.dump(DEFAULT_CONFIG, f, indent=4)
        cfg = DEFAULT_CONFIG
    else:
        with open(CONFIG_FILE, "r") as f:
            cfg = json.load(f)
            if "needed_items" not in cfg: cfg["needed_items"] = {}
            if "completed_quests" not in cfg: cfg["completed_quests"] = []

    # Validate and convert back to dict
    return AppConfig.model_validate(cfg).model_dump()

def save_config(config):
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=4)

# State
config = load_config()
seen_deal_ids: set[str] = set()
market_state = {
    "all_listings": [],
    "snipes": [],
    "watchlist_matches": [],
    "priority_matches": [],
    "item_stats": {}, 
    "stats": {"avg_legendary": 0, "total_volume": 0, "last_update": "Never"},
    "notified_snipes": set()
}
alerted_listings: set[str] = set()

def get_profile_slug(username):
    return username.replace("#", "-") if username else ""

async def process_market_data(listings):
    global market_state, config, seen_deal_ids, alerted_listings

    snipes, watchlist_matches, priority_matches, filtered_listings, legendary_prices = [], [], [], [], []
    new_deals = []
    
    bot_token = config.get("settings", {}).get("telegram_bot_token", "")
    chat_id = config.get("settings", {}).get("telegram_chat_id", "")
    notifier = TelegramNotifier(bot_token, chat_id)

    # Calculate item-specific averages first
    item_prices = defaultdict(list)
    for item in listings:
        p = item.get("price")
        iid = item.get("item_id")
        if p and iid: item_prices[iid].append(p)
    
    item_stats = {}
    for iid, prices in item_prices.items():
        item_stats[iid] = round(median(prices), 1)
    market_state["item_stats"] = item_stats

    for item in listings:
        item_id = item.get("item_id")
        
        # ENSURE market_avg IS ALWAYS SET
        item["market_avg"] = item_stats.get(item_id, 0)
        item["profile_slug"] = get_profile_slug(item.get("user_profile", {}).get("username", ""))
        item["is_priority"] = False # Default
        
        if item_id in config["ignore_list"] or item_id in config["owned_blueprints"]:
            continue
            
        price = item.get("price")
        rarity = item.get("item", {}).get("rarity", "")
        
        if price:
            if rarity == "Legendary": legendary_prices.append(price)

            if item_id in config["needed_items"]:
                item["alert_reason"] = config["needed_items"][item_id]
                item["is_priority"] = True
                priority_matches.append(item)

            elif item_id in config["watchlist"] and price <= config["watchlist"][item_id]:
                item["alert_reason"] = f"Watchlist Match: {config['watchlist'][item_id]}"
                watchlist_matches.append(item)

            elif rarity == "Legendary" and price <= config["settings"]["snipe_legendary_threshold"]:
                item["alert_reason"] = f"Legendary Snipe (<{config['settings']['snipe_legendary_threshold']})"
                snipes.append(item)

            elif rarity == "Epic" and price <= config["settings"]["snipe_epic_threshold"]:
                item["alert_reason"] = f"Epic Snipe (<{config['settings']['snipe_epic_threshold']})"
                snipes.append(item)
            if "alert_reason" in item:
                deal_id = item.get("id")
                if deal_id and deal_id not in seen_deal_ids:
                    seen_deal_ids.add(deal_id)
                    new_deals.append(item)
                if deal_id and deal_id not in alerted_listings:
                    await notifier.send_alert(item)
                    alerted_listings.add(deal_id)


        filtered_listings.append(item)

    market_state["all_listings"] = filtered_listings[:config["settings"]["max_listings_cache"]]
    market_state["snipes"] = snipes
    market_state["watchlist_matches"] = watchlist_matches
    market_state["priority_matches"] = priority_matches
    market_state["stats"]["avg_legendary"] = round(median(legendary_prices), 1) if legendary_prices else 0
    market_state["stats"]["total_volume"] = len(listings)
    market_state["stats"]["last_update"] = datetime.now().strftime("%H:%M:%S")

    webhook_url = config.get("settings", {}).get("discord_webhook_url", "")
    if webhook_url:
        for snipe in snipes:
            snipe_id = snipe.get("id")
            if snipe_id and snipe_id not in market_state["notified_snipes"]:
                asyncio.create_task(send_discord_webhook(webhook_url, snipe))
                market_state["notified_snipes"].add(snipe_id)

    if new_deals:
        await manager.broadcast(json.dumps(new_deals))

async def fetch_listings():
    async with httpx.AsyncClient() as client:
        try:
            params = {"page": 1, "limit": 60, "sortBy": "created_at", "sortOrder": "desc", "listing_type": "sell"}
            response = await client.get("https://metaforge.app/api/arc-raiders/trade/listings", params=params)
            if response.status_code == 200:
                await process_market_data(response.json().get("data", []))
        except Exception as e: print(f"Update Error: {e}")

worker_instance = DealsWorker()

@asynccontextmanager
async def lifespan(app: FastAPI):
    worker_instance.start(fetch_listings, lambda: config["settings"]["poll_interval"])
    yield
    await worker_instance.stop()

app = FastAPI(lifespan=lifespan)
templates = Jinja2Templates(directory="templates")

@app.websocket("/ws/deals")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # Keep the connection open and wait for messages
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)

@app.get("/", response_class=HTMLResponse, tags=["Frontend"], description="Renders the main frontend dashboard.")
async def index(request: Request):
    return templates.TemplateResponse(request=request, name="index.html", context={"state": market_state, "config": config})

@app.post("/api/settings", tags=["Configuration"], description="Updates application settings and triggers a market data refresh.")
async def update_settings(new_config: dict = Body(...)):
    global config
    config = AppConfig.model_validate(new_config).model_dump()
    save_config(config)
    await fetch_listings()
    return {"status": "success"}

@app.post("/api/import/bulk", tags=["Import"], description="Bulk imports data (blueprints, projects, tracker, quests) and updates configuration.")
async def bulk_import(data: dict = Body(...)):
    type, raw = data.get("type"), data.get("raw", "").strip()
    if raw.startswith("'") and raw.endswith("'"): raw = raw[1:-1]
    try:
        parsed = json.loads(raw)
        if type == "blueprints":
            ids = [x.get("item_id") if isinstance(x, dict) else x for x in parsed]
            config["owned_blueprints"] = list(set(config["owned_blueprints"] + ids))
        elif type == "projects":
            for key in parsed:
                parts = key.split(":")
                if len(parts) >= 4: config["needed_items"][parts[3]] = f"Project: {parts[1]} ({parts[2]})"
        elif type == "tracker":
            for category in parsed:
                for item in category.get("items", []):
                    curr, req = item.get("currentQuantity", 0), item.get("requiredQuantity", 0)
                    if curr < req: config["needed_items"][item["id"]] = f"Tracker: {category['name']} - Need {req-curr}"
        elif type == "quests":
            if isinstance(parsed, dict) and "completedQuests" in parsed:
                config["completed_quests"] = list(set(config["completed_quests"] + parsed["completedQuests"]))
                to_remove = [k for k, v in config["needed_items"].items() if any(q in v for q in parsed["completedQuests"])]
                for k in to_remove: del config["needed_items"][k]
            elif isinstance(parsed, dict):
                for q_id, q_data in parsed.items():
                    if isinstance(q_data, dict) and q_data.get("needed_items"):
                        for item in q_data["needed_items"]: config["needed_items"][item["id"]] = f"Quest: {q_id}"
        save_config(config); await fetch_listings(); return {"status": "success", "message": "Import successful"}
    except Exception as e: return {"status": "error", "message": f"Parse Error: {e!s}"}

@app.post("/api/actions/owned", tags=["Actions"], description="Marks a specific item as owned in the configuration.")
async def mark_owned(data: dict = Body(...)):
    item_id = data.get("item_id"); config["owned_blueprints"].append(item_id) if item_id not in config["owned_blueprints"] else None
    save_config(config); await fetch_listings(); return {"status": "success"}
 
def _read_deals_file():
    try:
        with open("deals.json") as f:
            return json.load(f)
    except FileNotFoundError:
        return []


@app.get("/api/v1/export/trades", tags=["Export"], description="Export trade data with optional date range filtering.")
async def export_trades(
    format: str = "json",
    start_date: datetime | None = None,
    end_date: datetime | None = None,
):
    trades = _read_deals_file()

    # Filter by date range
    if start_date or end_date:
        # Normalize parsed datetimes to be timezone-aware (UTC) if they are naive
        if start_date and start_date.tzinfo is None:
            start_date = start_date.replace(tzinfo=timezone.utc)
        if end_date and end_date.tzinfo is None:
            end_date = end_date.replace(tzinfo=timezone.utc)

        filtered_trades = []
        for trade in trades:
            try:
                created_dt = datetime.fromisoformat(trade.get("created_at", "").replace("Z", "+00:00"))
                if created_dt.tzinfo is None:
                    created_dt = created_dt.replace(tzinfo=timezone.utc)

                include = True
                if start_date and created_dt < start_date:
                    include = False
                if end_date and created_dt > end_date:
                    include = False

                if include:
                    filtered_trades.append(trade)
            except (ValueError, TypeError):
                continue
        trades = filtered_trades

    if format == "csv":
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["id", "item_id", "listing_type", "quantity", "price", "status", "created_at"])
        for t in trades:
            writer.writerow([
                t.get("id", ""),
                t.get("item_id", ""),
                t.get("listing_type", ""),
                t.get("quantity", ""),
                t.get("price", ""),
                t.get("status", ""),
                t.get("created_at", ""),
            ])
        return Response(content=output.getvalue(), media_type="text/csv")

    return JSONResponse(content=trades)


@app.get("/api/v1/history/{item_id}", tags=["History"], description="Returns aggregated price data grouped by hour or day.")
async def get_item_history(item_id: str, group_by: str = Query("hour", pattern="^(hour|day)$")):
    filtered = []
    for item in market_state.get("all_listings", []):
        if item.get("item_id") == item_id and "price" in item and "quantity" in item and "created_at" in item:
            try:
                # Handle isoformat string which might have 'Z' or '+00:00'
                dt_str = item["created_at"].replace("Z", "+00:00")
                dt = datetime.fromisoformat(dt_str)
                filtered.append((dt, item["price"], item["quantity"]))
            except ValueError:
                continue

    if not filtered:
        return []

    groups = defaultdict(list)
    for dt, price, quantity in filtered:
        if group_by == "hour":
            group_key = dt.replace(minute=0, second=0, microsecond=0).isoformat()
        else:
            group_key = dt.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()

        groups[group_key].append({"price": price, "quantity": quantity})

    results = []
    for key in sorted(groups.keys()):
        items = groups[key]
        prices = [x["price"] for x in items]
        volume = sum(x["quantity"] for x in items)
        results.append({
            "timestamp": key,
            "min": min(prices),
            "max": max(prices),
            "median": median(prices),
            "volume": volume,
        })

    return results


@app.get("/health", tags=["System"], description="Health check endpoint returning system status, memory usage, and loaded deal counts.")
async def health_check():
    import resource
    memory_mb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024

    return {
        "status": "ok",
        "memory_mb": round(memory_mb, 2),
        "deals": {
            "all_listings": len(market_state.get("all_listings", [])),
            "snipes": len(market_state.get("snipes", [])),
            "watchlist_matches": len(market_state.get("watchlist_matches", [])),
            "priority_matches": len(market_state.get("priority_matches", []))
        }
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8011)
