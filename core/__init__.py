"""
Core module - data models, probability engine, and impact calculator.

Usage:
    # Import models
    from core import Game, GameState, Team, GameEvent
    from core import ProbabilityEstimate, TradingSignal, Trade
    
    # Import calculators
    from core import ImpactCalculator, ProbabilityEngine
"""

# Models
from .models import (
    # Enums
    Game,
    MatchStatus,
    OrderSide,
    TradeStatus,
    # Game data
    Team,
    GameState,
    GameEvent,
    # Probability & Pricing
    ProbabilityEstimate,
    MarketPrice,
    # Trading
    TradingSignal,
    Trade,
    Position,
    TradingSession,
)

# Calculators
from .impact_calculator import ImpactCalculator, EventImpact
from .probability_engine import ProbabilityEngine, FastProbabilityUpdater

__all__ = [
    # Enums
    "Game",
    "MatchStatus",
    "OrderSide",
    "TradeStatus",
    # Game data
    "Team",
    "GameState",
    "GameEvent",
    # Probability & Pricing
    "ProbabilityEstimate",
    "MarketPrice",
    # Trading
    "TradingSignal",
    "Trade",
    "Position",
    "TradingSession",
    # Calculators
    "ImpactCalculator",
    "EventImpact",
    "ProbabilityEngine",
    "FastProbabilityUpdater",
]