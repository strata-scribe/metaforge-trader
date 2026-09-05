
from pydantic import BaseModel, ConfigDict, Field, RootModel


class Settings(BaseModel):
    model_config = ConfigDict(extra="ignore")
    snipe_legendary_threshold: int | float
    snipe_epic_threshold: int | float
    max_listings_cache: int
    poll_interval: int
    supabase_token: str = ""
    discord_webhook_url: str = ""
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""

class OwnedBlueprints(RootModel[list[str]]):
    model_config = ConfigDict(strict=True)

class Watchlist(RootModel[dict[str, int | float]]):
    model_config = ConfigDict(strict=True)

class NeededItems(RootModel[dict[str, str]]):
    model_config = ConfigDict(strict=True)

class AppConfig(BaseModel):
    model_config = ConfigDict(strict=True)
    settings: Settings
    owned_blueprints: OwnedBlueprints = Field(default_factory=list)
    ignore_list: list[str] = Field(default_factory=list)
    completed_quests: list[str] = Field(default_factory=list)
    needed_items: NeededItems = Field(default_factory=dict)
    watchlist: Watchlist = Field(default_factory=dict)
