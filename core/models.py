"""
Core data models for the trading bot.

These classes define the structure of our data:
- Games and matches
- Teams and their stats
- Events that happen in games
- Trading signals and trades
- Positions and P&L

Think of these as the "vocabulary" our bot uses to talk about esports and trading.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import Enum


# ============================================================
# ENUMS (Categories/Types)
# ============================================================

class Game(Enum):
    """
    Supported games.
    
    Usage:
        game = Game.LOL
        if game == Game.LOL:
            print("League of Legends")
    """
    LOL = "lol"
    DOTA2 = "dota2"


class MatchStatus(Enum):
    """
    Status of a match.
    
    UPCOMING: Match hasn't started yet
    LIVE: Match is currently being played
    FINISHED: Match has ended
    """
    UPCOMING = "upcoming"
    LIVE = "live"
    FINISHED = "finished"


class OrderSide(Enum):
    """
    Which side of a trade.
    
    BUY: Buying shares (betting the price will go up)
    SELL: Selling shares (betting the price will go down)
    """
    BUY = "BUY"
    SELL = "SELL"


class TradeStatus(Enum):
    """Status of a trade order."""
    PENDING = "pending"      # Order submitted, waiting
    FILLED = "filled"        # Order completed
    PARTIAL = "partial"      # Partially filled
    CANCELLED = "cancelled"  # Order cancelled
    FAILED = "failed"        # Order failed


# ============================================================
# GAME DATA MODELS
# ============================================================

@dataclass
class Team:
    """
    Represents a team in a match.
    
    Stores both static info (name) and live stats (kills, gold, etc.)
    
    Example:
        team = Team(id="123", name="T1", acronym="T1")
        team.kills = 10
        team.gold = 45000
    """
    # Basic info
    id: str
    name: str
    acronym: Optional[str] = None
    
    # Live game stats (updated during match)
    kills: int = 0
    deaths: int = 0
    gold: int = 0           # LoL: gold, Dota: also tracks gold
    towers: int = 0
    
    # LoL specific stats
    dragons: int = 0
    barons: int = 0
    has_dragon_soul: bool = False
    has_elder: bool = False
    has_baron_buff: bool = False
    
    # Dota 2 specific stats
    net_worth: int = 0      # Total team net worth
    roshan_kills: int = 0
    has_aegis: bool = False
    
    def __str__(self) -> str:
        """String representation."""
        return f"{self.name} ({self.acronym or self.id})"


@dataclass
class GameState:
    """
    Complete state of a live game at a point in time.
    
    This is the main data structure we work with.
    It contains all the information about a match.
    
    Example:
        state = GameState(
            match_id="123",
            game=Game.LOL,
            status=MatchStatus.LIVE,
            team1=team1,
            team2=team2
        )
        print(f"Gold diff: {state.gold_diff}")
    """
    # Match identification
    match_id: str
    game: Game
    status: MatchStatus
    
    # Teams
    team1: Team
    team2: Team
    
    # Game timing (in seconds)
    game_time_seconds: int = 0
    
    # Series score (for best-of matches)
    team1_map_score: int = 0
    team2_map_score: int = 0
    best_of: int = 1  # Best of 1, 3, or 5
    
    # Metadata
    last_updated: datetime = field(default_factory=datetime.now)
    
    # ---- Computed Properties ----
    
    @property
    def game_time_minutes(self) -> float:
        """Game time in minutes (easier to read)."""
        return self.game_time_seconds / 60.0
    
    @property
    def gold_diff(self) -> int:
        """
        Gold/networth difference.
        Positive = team1 is ahead.
        Negative = team2 is ahead.
        """
        if self.game == Game.LOL:
            return self.team1.gold - self.team2.gold
        else:  # Dota 2
            return self.team1.net_worth - self.team2.net_worth
    
    @property
    def kill_diff(self) -> int:
        """Kill difference. Positive = team1 has more kills."""
        return self.team1.kills - self.team2.kills
    
    @property
    def tower_diff(self) -> int:
        """Tower difference. Positive = team1 has taken more towers."""
        return self.team1.towers - self.team2.towers
    
    @property
    def dragon_diff(self) -> int:
        """Dragon difference (LoL only)."""
        return self.team1.dragons - self.team2.dragons
    
    def summary(self) -> str:
        """Get a text summary of the game state."""
        return (
            f"{self.team1.name} vs {self.team2.name} | "
            f"{self.game_time_minutes:.1f}min | "
            f"Gold: {self.gold_diff:+d} | "
            f"Kills: {self.kill_diff:+d} | "
            f"Towers: {self.tower_diff:+d}"
        )


@dataclass
class GameEvent:
    """
    A single event that happened in a game.
    
    Events are things like:
    - A kill happened
    - A tower was destroyed
    - Dragon/Baron was taken
    - A teamfight occurred
    
    Example:
        event = GameEvent(
            timestamp=time.time(),
            event_type="kill",
            team=1,
            context="solo"
        )
    """
    # When the event happened (Unix timestamp)
    timestamp: float
    
    # What type of event: "kill", "tower", "dragon", "baron", "roshan", "teamfight"
    event_type: str
    
    # Which team got the event (1 or 2)
    team: int
    
    # Additional context: "solo", "first", "steal", "default"
    context: str = "default"
    
    # Extra details (varies by event type)
    details: Dict[str, Any] = field(default_factory=dict)
    
    # Calculated values (filled in by our engine)
    gold_value: int = 0
    probability_impact: float = 0.0
    
    def __str__(self) -> str:
        """String representation."""
        return f"Event: {self.event_type} (Team {self.team}, {self.context})"


# ============================================================
# PROBABILITY & PRICING MODELS
# ============================================================

@dataclass
class ProbabilityEstimate:
    """
    Our estimate of each team's win probability.
    
    This is the core output of our probability engine.
    We compare this to market prices to find trading opportunities.
    
    Example:
        prob = ProbabilityEstimate(
            team1_prob=0.65,
            team2_prob=0.35,
            confidence=0.8
        )
        print(f"Team 1 has {prob.team1_prob:.0%} chance to win")
    """
    # Probabilities (should sum to 1.0)
    team1_prob: float
    team2_prob: float
    
    # How confident we are in this estimate (0 to 1)
    # Higher confidence = more certain
    confidence: float
    
    # Breakdown of how we calculated this
    base_prob: float = 0.5          # Starting probability
    gold_adjustment: float = 0.0     # Adjustment from gold diff
    kill_adjustment: float = 0.0     # Adjustment from kills
    objective_adjustment: float = 0.0  # Adjustment from objectives
    
    # Human-readable explanation
    explanation: str = ""
    
    @property
    def team1_fair_price(self) -> float:
        """Fair price for team1 YES shares (same as probability)."""
        return self.team1_prob
    
    @property
    def team2_fair_price(self) -> float:
        """Fair price for team2 YES shares."""
        return self.team2_prob
    
    def __str__(self) -> str:
        return f"T1: {self.team1_prob:.1%} | T2: {self.team2_prob:.1%} (conf: {self.confidence:.0%})"


@dataclass
class MarketPrice:
    """
    Current prices from a prediction market (like Polymarket).
    
    Example:
        market = MarketPrice(
            market_id="0x123",
            token_id="456",
            best_bid=0.48,
            best_ask=0.52
        )
        print(f"Spread: {market.spread:.2%}")
    """
    market_id: str
    token_id: str
    
    # Orderbook prices
    best_bid: float = 0.0    # Highest price someone will buy at
    best_ask: float = 1.0    # Lowest price someone will sell at
    mid_price: float = 0.5   # Midpoint between bid and ask
    spread: float = 1.0      # Difference between ask and bid
    
    # Orderbook sizes
    bid_size: float = 0.0    # How many shares at best bid
    ask_size: float = 0.0    # How many shares at best ask
    
    timestamp: datetime = field(default_factory=datetime.now)
    
    @property
    def is_valid(self) -> bool:
        """Check if prices are valid."""
        return self.best_bid < self.best_ask and self.spread < 1.0


# ============================================================
# TRADING MODELS
# ============================================================

@dataclass
class TradingSignal:
    """
    A signal indicating a potential trading opportunity.
    
    Generated when our fair price differs from market price.
    
    Example:
        signal = TradingSignal(
            timestamp=datetime.now(),
            match_id="123",
            fair_price=0.55,
            market_price=0.50,
            edge=0.05
        )
        if signal.edge > 0.015:
            print("Trade opportunity!")
    """
    timestamp: datetime
    match_id: str
    
    # Prices
    fair_price: float      # What we think it's worth
    market_price: float    # What the market says
    edge: float           # Difference (our advantage)
    
    # Recommendation
    side: Optional[OrderSide] = None  # BUY or SELL
    recommended_size: float = 0.0     # How much to trade
    
    # Confidence in this signal
    confidence: float = 0.0
    
    @property
    def has_edge(self) -> bool:
        """Whether there's any tradeable edge."""
        return abs(self.edge) > 0
    
    @property
    def edge_percent(self) -> float:
        """Edge as a percentage."""
        return self.edge * 100
    
    def __str__(self) -> str:
        side_str = self.side.value if self.side else "NONE"
        return f"Signal: {side_str} | Edge: {self.edge:.3f} ({self.edge_percent:.1f}%)"


@dataclass
class Trade:
    """
    A trade that was placed (either paper or real).
    
    Records everything about a trade for tracking and analysis.
    """
    # Identification
    id: str
    timestamp: datetime
    
    # What we traded
    market_id: str
    token_id: str
    side: OrderSide
    
    # Trade details
    size: float              # Number of shares
    price: float             # Price per share
    
    # Our analysis at trade time
    fair_price: float        # What we thought it was worth
    edge: float              # Our edge when we traded
    
    # Execution details
    status: TradeStatus = TradeStatus.PENDING
    filled_size: float = 0.0
    filled_price: float = 0.0
    
    # P&L (filled in when position is closed)
    realized_pnl: float = 0.0
    
    # Performance metrics
    latency_ms: float = 0.0  # How long the trade took
    
    # Paper vs real
    is_paper: bool = True
    
    @property
    def notional_value(self) -> float:
        """Total value of the trade."""
        return self.size * self.price
    
    @property
    def expected_value(self) -> float:
        """Expected profit based on our edge."""
        return self.size * self.edge
    
    def __str__(self) -> str:
        return f"Trade {self.id}: {self.side.value} {self.size:.1f} @ {self.price:.3f}"


@dataclass
class Position:
    """
    Current position in a market.
    
    Tracks how many shares we hold and our P&L.
    """
    market_id: str
    token_id: str
    
    # Position
    size: float = 0.0           # Number of shares (positive = long)
    avg_price: float = 0.0      # Average price paid
    
    # Current values
    current_price: float = 0.0
    
    @property
    def unrealized_pnl(self) -> float:
        """Unrealized profit/loss."""
        if self.size == 0:
            return 0.0
        return self.size * (self.current_price - self.avg_price)
    
    @property
    def market_value(self) -> float:
        """Current market value of position."""
        return self.size * self.current_price
    
    def __str__(self) -> str:
        return f"Position: {self.size:.1f} shares @ {self.avg_price:.3f} (PnL: ${self.unrealized_pnl:.2f})"


# ============================================================
# SESSION TRACKING
# ============================================================

@dataclass
class TradingSession:
    """
    Tracks a complete trading session for one match.
    
    Collects statistics about events, trades, and performance.
    """
    session_id: str
    match_id: str
    market_id: str
    token_id: str
    
    # Timing
    start_time: datetime = field(default_factory=datetime.now)
    end_time: Optional[datetime] = None
    
    # Current state
    current_fair_price: float = 0.5
    current_market_price: float = 0.5
    game_time_minutes: float = 0.0
    
    # Statistics
    events_processed: int = 0
    signals_generated: int = 0
    trades_executed: int = 0
    total_pnl: float = 0.0
    
    # Latency tracking
    event_latencies: List[float] = field(default_factory=list)
    trade_latencies: List[float] = field(default_factory=list)
    
    @property
    def duration_minutes(self) -> float:
        """Session duration in minutes."""
        end = self.end_time or datetime.now()
        return (end - self.start_time).total_seconds() / 60
    
    @property
    def avg_event_latency_ms(self) -> float:
        """Average event processing latency in milliseconds."""
        if not self.event_latencies:
            return 0.0
        return sum(self.event_latencies) / len(self.event_latencies)
    
    @property
    def avg_trade_latency_ms(self) -> float:
        """Average trade execution latency in milliseconds."""
        if not self.trade_latencies:
            return 0.0
        return sum(self.trade_latencies) / len(self.trade_latencies)
    
    def summary(self) -> str:
        """Get session summary."""
        return (
            f"Session {self.session_id} | "
            f"Duration: {self.duration_minutes:.1f}min | "
            f"Events: {self.events_processed} | "
            f"Trades: {self.trades_executed} | "
            f"PnL: ${self.total_pnl:.2f}"
        )