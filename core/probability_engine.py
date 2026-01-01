"""
Probability Engine - Real-time win probability calculation.

This is the brain of our trading bot. It maintains a running estimate
of each team's win probability and updates it when events happen.

Key features:
1. Fast updates from game state (gold, kills, towers, objectives)
2. Instant incremental updates when events happen
3. Teamfight detection and impact calculation

The goal is to calculate probabilities FASTER than the market adjusts,
giving us a window to trade on mispricing.
"""

import math
import logging
from typing import Optional, Tuple
from dataclasses import dataclass

from .models import Game, GameState, GameEvent, ProbabilityEstimate
from .impact_calculator import ImpactCalculator

logger = logging.getLogger(__name__)


class ProbabilityEngine:
    """
    Calculates and maintains win probability estimates.
    
    Usage:
        # Initialize
        engine = ProbabilityEngine("lol")
        
        # Calculate from full game state
        prob = engine.calculate_from_state(game_state)
        print(f"Team 1 win probability: {prob.team1_prob:.1%}")
        
        # Fast update from single event
        new_prob = engine.update_from_event(event)
        
        # Get fair price for trading
        fair_price = engine.get_fair_price(for_team=1)
    
    The engine uses multiple factors:
    1. Gold/economy differential
    2. Kill differential  
    3. Tower differential
    4. Objective control (dragons, baron, roshan)
    5. Time-based weighting (leads matter more late game)
    """
    
    def __init__(self, game: str = "lol"):
        """
        Initialize the probability engine.
        
        Args:
            game: "lol" or "dota2"
        """
        self.game = game.lower()
        self.impact_calculator = ImpactCalculator(game)
        
        # Current state
        self._current_prob: float = 0.5
        self._game_time: float = 0.0
        
        # Configuration based on game
        if self.game == "lol":
            # Gold difference that gives roughly 75% win probability
            self.gold_scale = 8000.0
        else:
            # Dota 2 net worth scale
            self.gold_scale = 12000.0
        
        logger.debug(f"ProbabilityEngine initialized for {self.game}")
    
    # ================================================================
    # PROPERTIES
    # ================================================================
    
    @property
    def current_probability(self) -> float:
        """Current team 1 win probability."""
        return self._current_prob
    
    @property
    def game_time(self) -> float:
        """Current game time in minutes."""
        return self._game_time
    
    # ================================================================
    # CORE METHODS
    # ================================================================
    
    def reset(self, initial_prob: float = 0.5):
        """
        Reset the engine to initial state.
        
        Call this when starting a new match.
        """
        self._current_prob = initial_prob
        self._game_time = 0.0
        logger.debug(f"Engine reset to {initial_prob:.1%}")
    
    def update_game_time(self, minutes: float):
        """Update the current game time."""
        self._game_time = minutes
    
    def calculate_from_state(self, state: GameState) -> ProbabilityEstimate:
        """
        Calculate probability from complete game state.
        
        Use this for:
        - Initial calculation when joining a match
        - Periodic full recalculation to correct drift
        
        Args:
            state: Complete game state
            
        Returns:
            ProbabilityEstimate with full breakdown
        """
        self._game_time = state.game_time_minutes
        
        # Start with base probability (50% if no pre-match data)
        base_prob = 0.5
        
        # ---- Calculate adjustments ----
        
        # 1. Gold/economy adjustment (biggest factor)
        gold_diff = state.gold_diff
        gold_adj = self._sigmoid_adjustment(gold_diff, self.gold_scale)
        
        # 2. Kill adjustment (smaller, partially overlaps with gold)
        kill_diff = state.kill_diff
        kill_adj = kill_diff * 0.004  # 0.4% per kill
        
        # 3. Tower adjustment
        tower_diff = state.tower_diff
        tower_adj = tower_diff * 0.015  # 1.5% per tower
        
        # 4. Objective adjustment (game-specific)
        obj_adj = self._calculate_objective_adjustment(state)
        
        # ---- Combine adjustments with time weighting ----
        
        time_factor = self._get_time_factor()
        total_adj = (gold_adj + kill_adj + tower_adj + obj_adj) * time_factor
        
        # ---- Calculate final probability ----
        
        raw_prob = base_prob + total_adj
        
        # Clamp to avoid extreme values
        team1_prob = max(0.02, min(0.98, raw_prob))
        
        # Update internal state
        self._current_prob = team1_prob
        
        # Calculate confidence
        confidence = self._calculate_confidence(state, abs(total_adj))
        
        # Build explanation string
        explanation = self._build_explanation(
            state, gold_adj, kill_adj, tower_adj, obj_adj
        )
        
        return ProbabilityEstimate(
            team1_prob=team1_prob,
            team2_prob=1 - team1_prob,
            confidence=confidence,
            base_prob=base_prob,
            gold_adjustment=gold_adj,
            kill_adjustment=kill_adj,
            objective_adjustment=obj_adj + tower_adj,
            explanation=explanation
        )
    
    def update_from_event(self, event: GameEvent) -> float:
        """
        Fast incremental update from a single event.
        
        This is the key speed advantage - instead of recalculating
        everything, we just apply the delta from the event.
        
        Args:
            event: The game event that happened
            
        Returns:
            New team 1 win probability
        """
        # Get impact from lookup table
        impact, impact_info = self.impact_calculator.get_event_impact(
            event_type=event.event_type,
            context=event.context,
            game_time_minutes=self._game_time,
            current_prob=self._current_prob
        )
        
        # Apply direction based on which team got the event
        # Team 1 event = positive impact for team 1
        # Team 2 event = negative impact for team 1
        if event.team == 2:
            impact = -impact
        
        # Update probability
        new_prob = self._current_prob + impact
        
        # Clamp to valid range
        self._current_prob = max(0.02, min(0.98, new_prob))
        
        logger.debug(
            f"Event update: {event.event_type} (T{event.team}) | "
            f"Impact: {impact:+.4f} | "
            f"New prob: {self._current_prob:.4f}"
        )
        
        return self._current_prob
    
    def update_from_fight(
        self,
        kills_t1: int,
        deaths_t1: int,
        kills_t2: int,
        deaths_t2: int
    ) -> Tuple[float, str]:
        """
        Update probability from a teamfight result.
        
        Args:
            kills_t1: Kills by team 1 in the fight
            deaths_t1: Deaths of team 1 in the fight
            kills_t2: Kills by team 2 in the fight
            deaths_t2: Deaths of team 2 in the fight
            
        Returns:
            Tuple of (new_probability, description)
        """
        impact, description = self.impact_calculator.calculate_fight_impact(
            kills_team1=kills_t1,
            deaths_team1=deaths_t1,
            kills_team2=kills_t2,
            deaths_team2=deaths_t2,
            game_time_minutes=self._game_time,
            current_prob=self._current_prob
        )
        
        # Update probability
        new_prob = self._current_prob + impact
        self._current_prob = max(0.02, min(0.98, new_prob))
        
        logger.info(
            f"Fight update: {description} | "
            f"Impact: {impact:+.4f} | "
            f"New prob: {self._current_prob:.4f}"
        )
        
        return self._current_prob, description
    
    def get_fair_price(self, for_team: int = 1) -> float:
        """
        Get fair market price for a team.
        
        In prediction markets, price ≈ probability.
        
        Args:
            for_team: 1 or 2
            
        Returns:
            Fair price (0 to 1)
        """
        if for_team == 1:
            return self._current_prob
        else:
            return 1 - self._current_prob
    
    # ================================================================
    # HELPER METHODS
    # ================================================================
    
    def _sigmoid_adjustment(self, diff: float, scale: float) -> float:
        """
        Convert a differential to probability adjustment using sigmoid.
        
        The sigmoid function provides smooth scaling:
        - Small differences → small adjustments
        - Large differences → larger adjustments (but bounded)
        
        Maps diff to approximately [-0.4, +0.4] range.
        """
        try:
            # Sigmoid: 2 / (1 + exp(-x)) - 1
            # This maps (-∞, +∞) to (-1, +1)
            sigmoid = 2 / (1 + math.exp(-diff / scale)) - 1
        except OverflowError:
            # Handle extreme values
            sigmoid = 1.0 if diff > 0 else -1.0
        
        # Scale to max ±40% adjustment
        return sigmoid * 0.4
    
    def _calculate_objective_adjustment(self, state: GameState) -> float:
        """
        Calculate probability adjustment from objectives.
        
        This handles game-specific objectives like dragons, baron, roshan.
        """
        adj = 0.0
        
        if self.game == "lol":
            # Dragon difference
            dragon_diff = state.team1.dragons - state.team2.dragons
            adj += dragon_diff * 0.015  # 1.5% per dragon
            
            # Dragon soul (having 4 dragons)
            if state.team1.has_dragon_soul:
                adj += 0.10  # 10% bonus
            elif state.team2.has_dragon_soul:
                adj -= 0.10
            
            # Elder dragon (super buff)
            if state.team1.has_elder:
                adj += 0.15  # 15% bonus
            elif state.team2.has_elder:
                adj -= 0.15
            
            # Baron buff (temporary but strong)
            if state.team1.has_baron_buff:
                adj += 0.06
            elif state.team2.has_baron_buff:
                adj -= 0.06
            
            # Baron kill count (indicates team strength)
            baron_diff = state.team1.barons - state.team2.barons
            adj += baron_diff * 0.02
            
        else:  # Dota 2
            # Roshan kills
            roshan_diff = state.team1.roshan_kills - state.team2.roshan_kills
            adj += roshan_diff * 0.03  # 3% per roshan
            
            # Aegis (temporary but crucial)
            if state.team1.has_aegis:
                adj += 0.04
            elif state.team2.has_aegis:
                adj -= 0.04
        
        return adj
    
    def _get_time_factor(self) -> float:
        """
        Get time-based weight factor.
        
        Leads matter more as game progresses.
        Early game is more volatile, late game is more decisive.
        """
        if self._game_time < 5:
            return 0.6
        elif self._game_time < 10:
            return 0.7 + (self._game_time - 5) * 0.02
        elif self._game_time < 20:
            return 0.8 + (self._game_time - 10) * 0.02
        elif self._game_time < 30:
            return 1.0 + (self._game_time - 20) * 0.015
        else:
            # Cap at 1.3
            return min(1.3, 1.15 + (self._game_time - 30) * 0.01)
    
    def _calculate_confidence(self, state: GameState, total_adj: float) -> float:
        """
        Calculate confidence in our probability estimate.
        
        Higher confidence when:
        - Game has progressed further (more data)
        - Lead is more decisive
        """
        # Time-based confidence (more confident later in game)
        time_conf = min(0.5 + state.game_time_minutes * 0.015, 0.85)
        
        # Lead-based confidence (more confident with clear lead)
        lead_conf = min(0.5 + abs(total_adj) * 1.2, 0.90)
        
        # Average the two
        return (time_conf + lead_conf) / 2
    
    def _build_explanation(
        self,
        state: GameState,
        gold_adj: float,
        kill_adj: float,
        tower_adj: float,
        obj_adj: float
    ) -> str:
        """Build human-readable explanation of probability."""
        parts = []
        
        parts.append(f"{state.game_time_minutes:.1f}min")
        
        if self.game == "lol":
            parts.append(f"Gold:{state.gold_diff:+d}({gold_adj:+.3f})")
        else:
            parts.append(f"NW:{state.gold_diff:+d}({gold_adj:+.3f})")
        
        parts.append(f"K:{state.kill_diff:+d}({kill_adj:+.3f})")
        parts.append(f"T:{state.tower_diff:+d}({tower_adj:+.3f})")
        
        if abs(obj_adj) > 0.005:
            parts.append(f"Obj:{obj_adj:+.3f}")
        
        return " | ".join(parts)


class FastProbabilityUpdater:
    """
    Ultra-fast probability updater for HFT scenarios.
    
    This is a simplified version optimized purely for speed.
    Use when you need maximum update rate.
    
    Usage:
        updater = FastProbabilityUpdater("lol")
        updater.set_initial_state(game_time=15.0, probability=0.55)
        
        # Fast event updates
        new_prob = updater.update("kill", team=1, context="solo")
        new_prob = updater.update("tower", team=2, context="inner")
    """
    
    def __init__(self, game: str = "lol"):
        """Initialize the fast updater."""
        self.calculator = ImpactCalculator(game)
        self._prob = 0.5
        self._game_time = 0.0
    
    def set_initial_state(self, game_time: float, probability: float):
        """Set initial state."""
        self._game_time = game_time
        self._prob = probability
    
    def update(
        self,
        event_type: str,
        team: int,
        context: str = "default"
    ) -> float:
        """
        Fast update from event.
        
        Returns new probability.
        """
        impact, _ = self.calculator.get_event_impact(
            event_type=event_type,
            context=context,
            game_time_minutes=self._game_time,
            current_prob=self._prob
        )
        
        if team == 2:
            impact = -impact
        
        self._prob = max(0.02, min(0.98, self._prob + impact))
        return self._prob
    
    @property
    def probability(self) -> float:
        """Current probability."""
        return self._prob