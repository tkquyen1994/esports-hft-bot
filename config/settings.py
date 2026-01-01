"""
Configuration settings for the esports HFT trading bot.

This file contains all configurable parameters in one place.
You can adjust these settings without changing the main code.
"""

import os
from dataclasses import dataclass, field
from typing import List, Optional
from dotenv import load_dotenv

# Load environment variables from .env file
# This reads your API keys and other secrets
load_dotenv()


@dataclass
class DataFeedConfig:
    """
    Settings for live data feeds.
    
    These control how we get game data.
    """
    # PandaScore API key (from your .env file)
    pandascore_api_key: str = os.getenv("PANDASCORE_API_KEY", "")
    pandascore_base_url: str = "https://api.pandascore.co"
    
    # How often to check for updates (in milliseconds)
    # 500ms = 0.5 seconds = 2 checks per second
    poll_interval_ms: int = 500
    
    # Games we support
    supported_games: List[str] = field(default_factory=lambda: ["lol", "dota2"])


@dataclass
class TradingConfig:
    """
    Trading parameters and risk management.
    
    IMPORTANT: Always start with paper_trading = True!
    """
    # Paper trading mode (simulated, no real money)
    # NEVER set this to False until you've tested extensively
    paper_trading: bool = True
    
    # Starting bankroll for paper trading (in USD)
    initial_bankroll: float = 1000.0
    
    # Minimum edge required to place a trade
    # 0.015 = 1.5 cents = 1.5% edge
    # If our fair price is 0.50 and market is 0.485, edge = 0.015
    min_edge: float = 0.015
    
    # Maximum stake as percentage of bankroll
    # 0.05 = 5% max per trade
    max_stake_percent: float = 0.05
    
    # Kelly criterion fraction
    # Full Kelly is too aggressive, we use 1/4 Kelly for safety
    # 0.25 = quarter Kelly
    kelly_fraction: float = 0.25
    
    # Minimum time between trades (milliseconds)
    # Prevents overtrading on the same event
    trade_cooldown_ms: int = 500
    
    # Maximum position size (number of shares)
    max_position: float = 100.0
    
    # Minimum trade size (in dollars)
    min_trade_size: float = 5.0


@dataclass 
class ModelConfig:
    """
    Probability model parameters.
    
    These control how we calculate win probabilities.
    Derived from historical esports data analysis.
    """
    # Gold scaling factors
    # This is the gold difference that gives roughly 75% win probability
    # Higher number = gold matters less
    lol_gold_scale: float = 8000.0
    dota_networth_scale: float = 12000.0
    
    # Impact per kill (probability shift)
    # 0.008 = 0.8% probability shift per kill
    kill_impact: float = 0.008
    
    # Impact per tower
    # 0.02 = 2% probability shift per tower
    tower_impact: float = 0.02
    
    # LoL objective impacts
    dragon_impact: float = 0.018      # Regular dragon
    dragon_soul_impact: float = 0.12   # Dragon soul (4 dragons)
    elder_dragon_impact: float = 0.18  # Elder dragon (huge buff)
    baron_impact: float = 0.10         # Baron Nashor
    
    # Dota 2 objective impacts
    roshan_impact: float = 0.06        # Roshan kill
    barracks_impact: float = 0.05      # Barracks destroyed


@dataclass
class PolymarketConfig:
    """Polymarket API settings."""
    api_key: str = ""
    api_secret: str = ""
    passphrase: str = ""
    
    # Trading settings
    enabled: bool = False
    max_order_size: float = 100.0  # Maximum shares per order
    max_position_size: float = 500.0  # Maximum shares per market
    min_order_size: float = 1.0  # Minimum shares per order
    
    # Safety settings
    max_daily_loss: float = 100.0  # Stop trading if daily loss exceeds this
    max_open_orders: int = 10  # Maximum concurrent open orders
    
    def __post_init__(self):
        """Load from environment."""
        self.api_key = os.getenv("POLYMARKET_API_KEY", "")
        self.api_secret = os.getenv("POLYMARKET_API_SECRET", "")
        self.passphrase = os.getenv("POLYMARKET_PASSPHRASE", "")
        
        # Enable if credentials are set
        self.enabled = bool(self.api_key and self.api_secret)

@dataclass
class NotificationConfig:
    """Notification settings."""
    enabled: bool = True
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    
    # Notification preferences
    trade_alerts: bool = True
    match_alerts: bool = True
    error_alerts: bool = True
    daily_summary: bool = True
    
    def __post_init__(self):
        """Load from environment."""
        self.telegram_bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
        self.telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID", "")

@dataclass
class Config:
    """
    Main configuration container.
    
    This combines all the config sections into one object.
    Access settings like: config.trading.min_edge
    """
    data_feed: DataFeedConfig = field(default_factory=DataFeedConfig)
    trading: TradingConfig = field(default_factory=TradingConfig)
    model: ModelConfig = field(default_factory=ModelConfig)
    polymarket: PolymarketConfig = field(default_factory=PolymarketConfig)
    notifications: NotificationConfig = field(default_factory=NotificationConfig)

    # Current game we're trading
    game: str = os.getenv("GAME", "lol")
    
    # Logging level: DEBUG, INFO, WARNING, ERROR
    log_level: str = "INFO"
    
    # Where to store the database
    database_path: str = "data/trades.db"


# Create a single global config instance
# Other files import this to access settings
config = Config()


def get_config() -> Config:
    """
    Get the global configuration object.
    
    Usage in other files:
        from config.settings import get_config
        config = get_config()
        print(config.trading.min_edge)
    """
    return config


def print_config_summary():
    """Print a summary of current configuration."""
    print("=" * 50)
    print("CONFIGURATION SUMMARY")
    print("=" * 50)
    print(f"Game: {config.game}")
    print(f"Paper Trading: {config.trading.paper_trading}")
    print(f"Initial Bankroll: ${config.trading.initial_bankroll}")
    print(f"Min Edge: {config.trading.min_edge:.1%}")
    print(f"Max Stake: {config.trading.max_stake_percent:.1%}")
    print(f"Kelly Fraction: {config.trading.kelly_fraction}")
    print(f"PandaScore API Key: {'Set' if config.data_feed.pandascore_api_key else 'Not Set'}")
    print(f"Polymarket Keys: {'Set' if config.polymarket.api_key else 'Not Set'}")
    print("=" * 50)