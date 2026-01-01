"""
Enhanced Models V2 - Advanced data structures for trading bot.

New models:
1. EnhancedGameState - More detailed game state tracking
2. MomentumTracker - Tracks recent event momentum
3. SeriesState - BO3/BO5 series context
4. ProbabilityDistribution - Full distribution, not just point estimate
5. TeamStrength - ELO-like team ratings
6. TradeOpportunity - Enhanced trading signals
"""

import math
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict, Tuple
from enum import Enum


# =================================================================
# ENUMS
# =================================================================

class GamePhase(Enum):
    EARLY_LANE = "early_lane"
    MID_LANE = "mid_lane"
    EARLY_MID = "early_mid"
    MID_GAME = "mid_game"
    LATE_MID = "late_mid"
    LATE_GAME = "late_game"
    ULTRA_LATE = "ultra_late"


class MomentumState(Enum):
    """Current momentum direction."""
    STRONG_TEAM1 = "strong_t1"      # Team 1 dominating recently
    SLIGHT_TEAM1 = "slight_t1"      # Team 1 has edge
    NEUTRAL = "neutral"              # Even or no clear momentum
    SLIGHT_TEAM2 = "slight_t2"      # Team 2 has edge
    STRONG_TEAM2 = "strong_t2"      # Team 2 dominating recently


class SeriesFormat(Enum):
    BO1 = 1
    BO3 = 3
    BO5 = 5


# =================================================================
# TEAM STRENGTH MODEL
# =================================================================

@dataclass
class TeamStrength:
    """
    Team strength rating (ELO-like).
    
    Used to set prior probabilities based on team skill.
    
    Example:
        t1 = TeamStrength(name="T1", rating=1850, recent_form=0.75)
        t2 = TeamStrength(name="Gen.G", rating=1820, recent_form=0.65)
        
        prior = t1.vs_probability(t2)  # ~0.54
    """
    name: str
    rating: float = 1500.0          # ELO-like rating
    recent_form: float = 0.5        # Win rate in last 10 games
    roster_stability: float = 1.0   # 1.0 = stable, lower = recent changes
    
    # Historical stats
    avg_game_time: float = 30.0     # Minutes
    early_game_rating: float = 0.5  # Strength in first 15 min
    late_game_rating: float = 0.5   # Strength after 30 min
    objective_control: float = 0.5  # Dragon/Baron secure rate
    
    def vs_probability(self, opponent: 'TeamStrength') -> float:
        """Calculate win probability vs opponent."""
        # Base ELO probability
        elo_diff = self.rating - opponent.rating
        base_prob = 1 / (1 + 10 ** (-elo_diff / 400))
        
        # Adjust for recent form
        form_diff = self.recent_form - opponent.recent_form
        form_adj = form_diff * 0.1  # Max ±5% from form
        
        # Adjust for roster stability
        stability_adj = (self.roster_stability - opponent.roster_stability) * 0.03
        
        final = base_prob + form_adj + stability_adj
        return max(0.1, min(0.9, final))
    
    def get_comeback_factor(self) -> float:
        """How likely this team is to comeback from deficit."""
        # Better late game = better comeback potential
        return 0.8 + self.late_game_rating * 0.4


# =================================================================
# ENHANCED GAME STATE
# =================================================================

@dataclass
class EnhancedGameState:
    """
    Complete game state with all tracked metrics.
    
    More detailed than V1 GameState.
    """
    # Match info
    match_id: str
    game_number: int = 1
    
    # Timing
    game_time_seconds: int = 0
    
    # Team 1 stats
    team1_kills: int = 0
    team1_deaths: int = 0
    team1_gold: int = 0
    team1_towers: int = 0
    team1_dragons: int = 0
    team1_barons: int = 0
    team1_heralds: int = 0
    team1_inhibs: int = 0
    team1_has_soul: bool = False
    team1_has_elder: bool = False
    team1_has_baron: bool = False  # Active buff
    
    # Team 2 stats
    team2_kills: int = 0
    team2_deaths: int = 0
    team2_gold: int = 0
    team2_towers: int = 0
    team2_dragons: int = 0
    team2_barons: int = 0
    team2_heralds: int = 0
    team2_inhibs: int = 0
    team2_has_soul: bool = False
    team2_has_elder: bool = False
    team2_has_baron: bool = False
    
    # Dota 2 specific
    team1_roshan: int = 0
    team2_roshan: int = 0
    team1_has_aegis: bool = False
    team2_has_aegis: bool = False
    team1_rax: int = 0  # Barracks destroyed
    team2_rax: int = 0
    
    # Map state
    team1_towers_remaining: int = 11
    team2_towers_remaining: int = 11
    
    # Metadata
    last_updated: datetime = field(default_factory=datetime.now)
    
    # ---- Computed Properties ----
    
    @property
    def game_time_minutes(self) -> float:
        return self.game_time_seconds / 60.0
    
    @property
    def gold_diff(self) -> int:
        """Positive = Team 1 ahead."""
        return self.team1_gold - self.team2_gold
    
    @property
    def kill_diff(self) -> int:
        return self.team1_kills - self.team2_kills
    
    @property
    def tower_diff(self) -> int:
        return self.team1_towers - self.team2_towers
    
    @property
    def dragon_diff(self) -> int:
        return self.team1_dragons - self.team2_dragons
    
    @property
    def objective_diff(self) -> int:
        """Combined objective score."""
        obj1 = self.team1_dragons * 2 + self.team1_barons * 5 + self.team1_heralds
        obj2 = self.team2_dragons * 2 + self.team2_barons * 5 + self.team2_heralds
        return obj1 - obj2
    
    @property
    def game_phase(self) -> GamePhase:
        """Current game phase."""
        t = self.game_time_minutes
        if t < 6:
            return GamePhase.EARLY_LANE
        elif t < 14:
            return GamePhase.MID_LANE
        elif t < 20:
            return GamePhase.EARLY_MID
        elif t < 28:
            return GamePhase.MID_GAME
        elif t < 35:
            return GamePhase.LATE_MID
        elif t < 45:
            return GamePhase.LATE_GAME
        else:
            return GamePhase.ULTRA_LATE
    
    @property
    def is_close_game(self) -> bool:
        """Whether game is close (within 3k gold)."""
        return abs(self.gold_diff) < 3000
    
    @property
    def is_stomp(self) -> bool:
        """Whether one team is dominating (>10k gold)."""
        return abs(self.gold_diff) > 10000
    
    def get_leader(self) -> Tuple[int, int]:
        """
        Get which team is winning and by how much.
        
        Returns:
            Tuple of (leading_team, gold_lead)
            leading_team is 1 or 2, gold_lead is positive
        """
        if self.gold_diff >= 0:
            return 1, self.gold_diff
        else:
            return 2, -self.gold_diff
    
    def summary(self) -> str:
        """Human-readable summary."""
        return (
            f"{self.game_time_minutes:.1f}min | "
            f"Gold: {self.gold_diff:+,} | "
            f"K: {self.team1_kills}-{self.team2_kills} | "
            f"T: {self.team1_towers}-{self.team2_towers} | "
            f"D: {self.team1_dragons}-{self.team2_dragons}"
        )


# =================================================================
# MOMENTUM TRACKER
# =================================================================

@dataclass
class MomentumEvent:
    """Single event for momentum tracking."""
    game_time: float
    event_type: str
    team: int
    impact: float


class MomentumTracker:
    """
    Tracks recent game momentum.
    
    Momentum = weighted sum of recent events.
    More recent events weighted more heavily.
    
    Usage:
        tracker = MomentumTracker()
        tracker.add_event(15.0, "kill", team=1, impact=0.01)
        tracker.add_event(15.5, "kill", team=1, impact=0.01)
        
        state = tracker.get_momentum_state()  # SLIGHT_TEAM1
        adj = tracker.get_momentum_adjustment()  # +0.015
    """
    
    def __init__(self, decay_minutes: float = 3.0):
        """
        Args:
            decay_minutes: How quickly old events decay in importance
        """
        self.decay_minutes = decay_minutes
        self.events: List[MomentumEvent] = []
        self._current_time: float = 0.0
    
    def add_event(
        self,
        game_time: float,
        event_type: str,
        team: int,
        impact: float
    ):
        """Add an event to momentum tracking."""
        self.events.append(MomentumEvent(
            game_time=game_time,
            event_type=event_type,
            team=team,
            impact=impact
        ))
        self._current_time = game_time
        
        # Prune old events
        self._prune_old_events()
    
    def _prune_old_events(self):
        """Remove events older than 2x decay window."""
        cutoff = self._current_time - (self.decay_minutes * 2)
        self.events = [e for e in self.events if e.game_time > cutoff]
    
    def get_momentum_score(self) -> float:
        """
        Get momentum score.
        
        Positive = Team 1 momentum
        Negative = Team 2 momentum
        """
        if not self.events:
            return 0.0
        
        score = 0.0
        for event in self.events:
            # Calculate time decay
            age = self._current_time - event.game_time
            decay = math.exp(-age / self.decay_minutes)
            
            # Add to score
            direction = 1 if event.team == 1 else -1
            score += event.impact * decay * direction
        
        return score
    
    def get_momentum_state(self) -> MomentumState:
        """Get categorical momentum state."""
        score = self.get_momentum_score()
        
        if score > 0.05:
            return MomentumState.STRONG_TEAM1
        elif score > 0.02:
            return MomentumState.SLIGHT_TEAM1
        elif score < -0.05:
            return MomentumState.STRONG_TEAM2
        elif score < -0.02:
            return MomentumState.SLIGHT_TEAM2
        else:
            return MomentumState.NEUTRAL
    
    def get_momentum_adjustment(self) -> float:
        """
        Get probability adjustment from momentum.
        
        Capped to prevent momentum from dominating.
        """
        score = self.get_momentum_score()
        # Cap at ±3% adjustment
        return max(-0.03, min(0.03, score * 0.5))
    
    def get_streak(self, team: int) -> int:
        """Get consecutive event streak for a team."""
        if not self.events:
            return 0
        
        streak = 0
        for event in reversed(self.events):
            if event.team == team:
                streak += 1
            else:
                break
        return streak
    
    def reset(self):
        """Reset momentum tracking."""
        self.events = []
        self._current_time = 0.0


# =================================================================
# SERIES STATE
# =================================================================

@dataclass
class SeriesState:
    """
    State of a BO3/BO5 series.
    
    Tracks series score and provides context for probability adjustments.
    """
    format: SeriesFormat = SeriesFormat.BO5
    team1_wins: int = 0
    team2_wins: int = 0
    
    # Team names for display
    team1_name: str = "Team 1"
    team2_name: str = "Team 2"
    
    # Games to win
    @property
    def games_to_win(self) -> int:
        if self.format == SeriesFormat.BO1:
            return 1
        elif self.format == SeriesFormat.BO3:
            return 2
        else:
            return 3
    
    @property
    def team1_needs(self) -> int:
        """Games Team 1 needs to win series."""
        return self.games_to_win - self.team1_wins
    
    @property
    def team2_needs(self) -> int:
        """Games Team 2 needs to win series."""
        return self.games_to_win - self.team2_wins
    
    @property
    def is_match_point_team1(self) -> bool:
        """Team 1 is one game from winning."""
        return self.team1_needs == 1
    
    @property
    def is_match_point_team2(self) -> bool:
        """Team 2 is one game from winning."""
        return self.team2_needs == 1
    
    @property
    def is_match_point_against(self) -> bool:
        """Either team at match point."""
        return self.is_match_point_team1 or self.is_match_point_team2
    
    @property
    def is_elimination_game(self) -> bool:
        """This game eliminates the loser."""
        return self.is_match_point_team1 and self.is_match_point_team2
    
    @property
    def current_game_number(self) -> int:
        """Current game number (1-indexed)."""
        return self.team1_wins + self.team2_wins + 1
    
    def series_probability(self, game_win_prob: float) -> float:
        """
        Calculate series win probability from single-game win probability.
        
        Uses recursive calculation of remaining game scenarios.
        
        Args:
            game_win_prob: Probability of Team 1 winning a single game
            
        Returns:
            Probability of Team 1 winning the series
        """
        return self._calc_series_prob(
            self.team1_wins,
            self.team2_wins,
            game_win_prob
        )
    
    def _calc_series_prob(self, t1: int, t2: int, p: float) -> float:
        """Recursive series probability calculation."""
        if t1 >= self.games_to_win:
            return 1.0
        if t2 >= self.games_to_win:
            return 0.0
        
        # P(win series) = P(win this game) * P(win series | won) + 
        #                 P(lose this game) * P(win series | lost)
        p_if_win = self._calc_series_prob(t1 + 1, t2, p)
        p_if_lose = self._calc_series_prob(t1, t2 + 1, p)
        
        return p * p_if_win + (1 - p) * p_if_lose
    
    def record_game_win(self, team: int):
        """Record a game win."""
        if team == 1:
            self.team1_wins += 1
        else:
            self.team2_wins += 1
    
    @property
    def is_series_over(self) -> bool:
        """Whether series has been decided."""
        return (self.team1_wins >= self.games_to_win or 
                self.team2_wins >= self.games_to_win)
    
    @property
    def series_winner(self) -> Optional[int]:
        """Winner of series (1, 2, or None if ongoing)."""
        if self.team1_wins >= self.games_to_win:
            return 1
        elif self.team2_wins >= self.games_to_win:
            return 2
        return None
    
    def __str__(self) -> str:
        return (
            f"{self.team1_name} {self.team1_wins}-{self.team2_wins} "
            f"{self.team2_name} (BO{self.format.value})"
        )


# =================================================================
# PROBABILITY DISTRIBUTION
# =================================================================

@dataclass
class ProbabilityDistribution:
    """
    Full probability distribution, not just point estimate.
    
    Represents uncertainty in our probability estimate.
    """
    mean: float = 0.5
    std: float = 0.1
    
    # For more complex distributions
    lower_5: float = 0.3    # 5th percentile
    lower_25: float = 0.4   # 25th percentile
    median: float = 0.5     # 50th percentile
    upper_75: float = 0.6   # 75th percentile
    upper_95: float = 0.7   # 95th percentile
    
    @property
    def confidence_90(self) -> Tuple[float, float]:
        """90% confidence interval."""
        return (self.lower_5, self.upper_95)
    
    @property
    def confidence_50(self) -> Tuple[float, float]:
        """50% confidence interval (IQR)."""
        return (self.lower_25, self.upper_75)
    
    @property
    def uncertainty(self) -> float:
        """Measure of uncertainty (width of 90% CI)."""
        return self.upper_95 - self.lower_5
    
    def sample(self) -> float:
        """Sample from the distribution."""
        import random
        return max(0.01, min(0.99, random.gauss(self.mean, self.std)))
    
    @classmethod
    def from_mean_std(cls, mean: float, std: float) -> 'ProbabilityDistribution':
        """Create distribution from mean and std."""
        return cls(
            mean=mean,
            std=std,
            lower_5=max(0.01, mean - 1.645 * std),
            lower_25=max(0.01, mean - 0.675 * std),
            median=mean,
            upper_75=min(0.99, mean + 0.675 * std),
            upper_95=min(0.99, mean + 1.645 * std)
        )


# =================================================================
# TRADE OPPORTUNITY
# =================================================================

@dataclass
class TradeOpportunity:
    """
    Enhanced trading signal with full analysis.
    """
    timestamp: datetime
    match_id: str
    team: int  # Which team to trade
    
    # Prices
    fair_price: float
    market_price: float
    
    # Edge analysis
    raw_edge: float                # fair - market
    confidence_adjusted_edge: float  # edge * confidence
    
    # Sizing
    kelly_fraction: float          # Optimal bet size
    recommended_size: float        # Actual recommended size
    max_size: float               # Maximum allowed
    
    # Risk metrics
    expected_value: float          # EV of trade
    variance: float               # Risk
    sharpe_estimate: float        # EV / sqrt(variance)
    
    # Context
    game_phase: GamePhase
    momentum_state: MomentumState
    confidence: float
    
    # Recommendation
    action: str  # "STRONG_BUY", "BUY", "HOLD", "SELL", "STRONG_SELL"
    reasoning: str
    
    @property
    def is_actionable(self) -> bool:
        """Whether this signal should be acted on."""
        return abs(self.confidence_adjusted_edge) >= 0.015 and self.confidence >= 0.6
    
    @property
    def urgency(self) -> str:
        """How urgent is this trade."""
        if abs(self.raw_edge) > 0.08:
            return "IMMEDIATE"
        elif abs(self.raw_edge) > 0.05:
            return "HIGH"
        elif abs(self.raw_edge) > 0.03:
            return "MEDIUM"
        else:
            return "LOW"
    
    def __str__(self) -> str:
        return (
            f"Trade: {self.action} T{self.team} | "
            f"Edge: {self.raw_edge:+.1%} | "
            f"Conf: {self.confidence:.0%} | "
            f"Size: ${self.recommended_size:.2f}"
        )


# =================================================================
# GAME RESULT
# =================================================================

@dataclass
class GameResult:
    """Result of a completed game."""
    match_id: str
    game_number: int
    
    winner: int  # 1 or 2
    duration_seconds: int
    
    # Final stats
    team1_kills: int
    team2_kills: int
    team1_gold: int
    team2_gold: int
    
    # Key events
    first_blood: int
    first_tower: int
    first_dragon: int
    first_baron: int
    
    # Our predictions
    our_final_prob: float
    market_final_price: float
    
    @property
    def duration_minutes(self) -> float:
        return self.duration_seconds / 60.0
    
    @property
    def gold_diff(self) -> int:
        return self.team1_gold - self.team2_gold
    
    @property
    def was_stomp(self) -> bool:
        return abs(self.gold_diff) > 15000 or self.duration_minutes < 25
    
    @property
    def our_prediction_correct(self) -> bool:
        if self.winner == 1:
            return self.our_final_prob > 0.5
        else:
            return self.our_final_prob < 0.5
