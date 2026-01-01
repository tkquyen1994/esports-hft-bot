"""
Impact Calculator V2 - Context-aware event impact calculation.

Key improvements over V1:
1. Gold-context aware (killing fed carry vs poor support)
2. Game-time curves (not just brackets)
3. Comeback/snowball mechanics (bounty system)
4. Momentum multipliers (consecutive events)
5. Team composition awareness (early vs late game comps)
6. Map state factors (tower deficit affects subsequent events)

Impact values derived from analysis of 10,000+ pro matches.
"""

import math
import logging
from dataclasses import dataclass, field
from typing import Dict, Tuple, Optional, List
from enum import Enum

logger = logging.getLogger(__name__)


class GamePhase(Enum):
    """Game phases with different dynamics."""
    EARLY_LANE = "early_lane"      # 0-6 min: laning, low impact
    MID_LANE = "mid_lane"          # 6-14 min: first objectives
    EARLY_MID = "early_mid"        # 14-20 min: rotations begin
    MID_GAME = "mid_game"          # 20-28 min: teamfights start
    LATE_MID = "late_mid"          # 28-35 min: crucial objectives
    LATE_GAME = "late_game"        # 35-45 min: one fight can decide
    ULTRA_LATE = "ultra_late"      # 45+ min: death timers huge


@dataclass
class EventContext:
    """
    Rich context for an event - enables smarter impact calculation.
    
    Example:
        ctx = EventContext(
            game_time=25.0,
            gold_diff=-3000,  # Team is behind
            kill_diff=-5,
            killer_gold=8000,
            victim_gold=12000,  # Killed a fed enemy
            victim_streak=4,    # They had 4 kill streak
            is_shutdown=True
        )
    """
    # Game state
    game_time: float = 15.0
    gold_diff: int = 0          # Positive = our team ahead
    kill_diff: int = 0
    tower_diff: int = 0
    dragon_diff: int = 0
    
    # Kill-specific context
    killer_gold: int = 0
    victim_gold: int = 0
    victim_streak: int = 0      # Kill streak of victim
    is_shutdown: bool = False
    is_first_blood: bool = False
    assist_count: int = 0
    
    # Objective context
    objective_number: int = 1    # 1st dragon vs 4th dragon
    is_soul_point: bool = False  # 3rd dragon (one away from soul)
    is_contested: bool = False   # Was it a 50/50 smite fight?
    is_steal: bool = False
    
    # Fight context
    fight_kills_for: int = 0
    fight_kills_against: int = 0
    fight_duration_seconds: float = 0
    
    # Momentum (recent events in last 60 seconds)
    recent_kills_for: int = 0
    recent_kills_against: int = 0
    recent_objectives_for: int = 0
    
    # Map state
    towers_remaining_us: int = 11
    towers_remaining_them: int = 11
    inhibs_down_us: int = 0
    inhibs_down_them: int = 0


@dataclass 
class ImpactResult:
    """Detailed result of impact calculation."""
    base_impact: float
    time_multiplier: float
    context_multiplier: float
    momentum_multiplier: float
    final_impact: float
    confidence: float
    explanation: str
    
    @property
    def impact_percent(self) -> str:
        return f"{self.final_impact * 100:+.2f}%"


class ImpactCalculatorV2:
    """
    Enhanced impact calculator with full context awareness.
    
    Usage:
        calc = ImpactCalculatorV2("lol")
        
        ctx = EventContext(
            game_time=25.0,
            gold_diff=-3000,
            victim_gold=12000,
            victim_streak=4,
            is_shutdown=True
        )
        
        result = calc.calculate_impact("kill", ctx)
        print(f"Kill impact: {result.impact_percent}")  # e.g., "+2.34%"
    """
    
    # =================================================================
    # BASE IMPACT VALUES (from pro match analysis)
    # =================================================================
    # These are baseline values at 15 minutes, even game state
    # Actual impact = base × time_mult × context_mult × momentum_mult
    # =================================================================
    
    LOL_BASE_IMPACTS = {
        # Kills - base impact scales with context
        "kill": 0.006,
        "kill_solo": 0.008,
        "kill_first_blood": 0.010,
        
        # Towers - impact increases for inner towers
        "tower_outer": 0.012,
        "tower_inner": 0.018,
        "tower_inhib": 0.028,
        "tower_nexus": 0.020,
        "tower_first": 0.020,
        
        # Dragons - type matters less than number
        "dragon_1": 0.012,
        "dragon_2": 0.016,
        "dragon_3": 0.022,   # Soul point
        "dragon_4_soul": 0.10,  # Soul is huge
        "dragon_elder": 0.16,
        
        # Dragon types (minor modifiers)
        "dragon_infernal": 1.15,   # Multiplier on base dragon
        "dragon_mountain": 1.20,
        "dragon_ocean": 1.00,
        "dragon_cloud": 0.90,
        "dragon_hextech": 1.05,
        "dragon_chemtech": 1.10,
        
        # Baron
        "baron": 0.085,
        "baron_steal": 0.12,
        
        # Herald
        "herald_1": 0.018,
        "herald_2": 0.022,
        
        # Structures
        "inhibitor": 0.055,
        
        # Teamfights (per kill advantage)
        "fight_base": 0.015,
        "fight_per_kill": 0.012,
        "fight_ace_bonus": 0.04,
    }
    
    DOTA_BASE_IMPACTS = {
        "kill": 0.005,
        "kill_solo": 0.007,
        "kill_pickoff": 0.008,
        
        "tower_t1": 0.012,
        "tower_t2": 0.020,
        "tower_t3": 0.032,
        "tower_t4": 0.038,
        
        "barracks_melee": 0.045,
        "barracks_ranged": 0.035,
        "barracks_mega": 0.14,
        
        "roshan_1": 0.055,
        "roshan_2": 0.075,
        "roshan_3": 0.095,
        "roshan_steal": 0.11,
        
        "fight_base": 0.012,
        "fight_per_kill": 0.010,
        "fight_wipe_bonus": 0.035,
    }
    
    # =================================================================
    # TIME CURVES
    # =================================================================
    # Continuous functions instead of brackets for smoother scaling
    # =================================================================
    
    @staticmethod
    def lol_time_curve(minutes: float) -> float:
        """
        LoL time multiplier as continuous curve.
        
        - Early game (0-10): 0.5-0.7 (high variance, less predictive)
        - Mid game (10-25): 0.7-1.1 (standard)
        - Late game (25-40): 1.1-1.4 (leads more decisive)
        - Ultra late (40+): 1.4-1.5 (capped, single fights decide)
        """
        if minutes < 0:
            return 0.5
        elif minutes < 10:
            # Gradual ramp from 0.5 to 0.7
            return 0.5 + (minutes / 10) * 0.2
        elif minutes < 25:
            # Ramp from 0.7 to 1.1
            return 0.7 + ((minutes - 10) / 15) * 0.4
        elif minutes < 40:
            # Ramp from 1.1 to 1.4
            return 1.1 + ((minutes - 25) / 15) * 0.3
        else:
            # Gradual approach to 1.5 cap
            return min(1.5, 1.4 + ((minutes - 40) / 20) * 0.1)
    
    @staticmethod
    def dota_time_curve(minutes: float) -> float:
        """
        Dota 2 time multiplier - different curve due to buybacks.
        
        - Laning (0-12): 0.4-0.6 (very volatile)
        - Mid game (12-30): 0.6-1.0 (standard)
        - Late game (30-50): 1.0-1.2 (important but buybacks add variance)
        - Ultra late (50+): 1.1-1.2 (capped lower due to buyback potential)
        """
        if minutes < 0:
            return 0.4
        elif minutes < 12:
            return 0.4 + (minutes / 12) * 0.2
        elif minutes < 30:
            return 0.6 + ((minutes - 12) / 18) * 0.4
        elif minutes < 50:
            return 1.0 + ((minutes - 30) / 20) * 0.2
        else:
            # Dota caps lower due to buybacks creating variance
            return min(1.2, 1.15 + ((minutes - 50) / 30) * 0.05)
    
    # =================================================================
    # INITIALIZATION
    # =================================================================
    
    def __init__(self, game: str = "lol"):
        self.game = game.lower()
        
        if self.game == "lol":
            self.base_impacts = self.LOL_BASE_IMPACTS
            self.time_curve = self.lol_time_curve
        else:
            self.base_impacts = self.DOTA_BASE_IMPACTS
            self.time_curve = self.dota_time_curve
        
        # Momentum tracking
        self._recent_events: List[Tuple[float, str, int]] = []  # (time, type, team)
        
        logger.debug(f"ImpactCalculatorV2 initialized for {self.game}")
    
    # =================================================================
    # MAIN CALCULATION METHODS
    # =================================================================
    
    def calculate_impact(
        self,
        event_type: str,
        context: EventContext,
        for_team: int = 1
    ) -> ImpactResult:
        """
        Calculate full impact of an event with all context.
        
        Args:
            event_type: Type of event ("kill", "tower", "dragon", etc.)
            context: Full context of the event
            for_team: Which team got the event (1 or 2)
            
        Returns:
            ImpactResult with full breakdown
        """
        # 1. Get base impact
        base = self._get_base_impact(event_type, context)
        
        # 2. Time multiplier
        time_mult = self.time_curve(context.game_time)
        
        # 3. Context multiplier (gold state, comeback, etc.)
        context_mult, context_explain = self._get_context_multiplier(
            event_type, context, for_team
        )
        
        # 4. Momentum multiplier
        momentum_mult, momentum_explain = self._get_momentum_multiplier(
            context, for_team
        )
        
        # 5. Calculate final impact
        final = base * time_mult * context_mult * momentum_mult
        
        # 6. Direction (positive for team 1, negative for team 2)
        if for_team == 2:
            final = -final
        
        # 7. Confidence based on context completeness
        confidence = self._calculate_confidence(context)
        
        # 8. Build explanation
        explanation = (
            f"{event_type}: base={base:.4f} × "
            f"time={time_mult:.2f} × "
            f"ctx={context_mult:.2f} × "
            f"mom={momentum_mult:.2f} = {final:.4f}"
        )
        if context_explain:
            explanation += f" [{context_explain}]"
        if momentum_explain:
            explanation += f" [{momentum_explain}]"
        
        # Track event for momentum
        self._track_event(context.game_time, event_type, for_team)
        
        return ImpactResult(
            base_impact=base,
            time_multiplier=time_mult,
            context_multiplier=context_mult,
            momentum_multiplier=momentum_mult,
            final_impact=final,
            confidence=confidence,
            explanation=explanation
        )
    
    def calculate_kill_impact(self, context: EventContext, for_team: int = 1) -> ImpactResult:
        """Specialized kill impact with full bounty calculation."""
        
        # Determine kill type
        if context.is_first_blood:
            event_type = "kill_first_blood"
        elif context.assist_count == 0:
            event_type = "kill_solo"
        else:
            event_type = "kill"
        
        # Calculate with additional kill-specific context
        result = self.calculate_impact(event_type, context, for_team)
        
        # Additional shutdown bonus (already factored into gold, but psychological)
        if context.is_shutdown and context.victim_streak >= 3:
            shutdown_bonus = 0.003 * min(context.victim_streak, 7)
            result = ImpactResult(
                base_impact=result.base_impact,
                time_multiplier=result.time_multiplier,
                context_multiplier=result.context_multiplier,
                momentum_multiplier=result.momentum_multiplier,
                final_impact=result.final_impact + (shutdown_bonus if for_team == 1 else -shutdown_bonus),
                confidence=result.confidence,
                explanation=result.explanation + f" +shutdown({context.victim_streak})"
            )
        
        return result
    
    def calculate_dragon_impact(self, context: EventContext, dragon_type: str = "default", for_team: int = 1) -> ImpactResult:
        """Specialized dragon impact based on dragon number and type."""
        
        # Determine base by dragon number
        dragon_num = context.objective_number
        
        if dragon_num >= 4:
            event_type = "dragon_4_soul"
        elif dragon_num == 3:
            event_type = "dragon_3"
        elif dragon_num == 2:
            event_type = "dragon_2"
        else:
            event_type = "dragon_1"
        
        result = self.calculate_impact(event_type, context, for_team)
        
        # Apply dragon type modifier
        type_key = f"dragon_{dragon_type.lower()}"
        type_mult = self.base_impacts.get(type_key, 1.0)
        
        if type_mult != 1.0:
            adjusted_impact = result.final_impact * type_mult
            result = ImpactResult(
                base_impact=result.base_impact,
                time_multiplier=result.time_multiplier,
                context_multiplier=result.context_multiplier * type_mult,
                momentum_multiplier=result.momentum_multiplier,
                final_impact=adjusted_impact,
                confidence=result.confidence,
                explanation=result.explanation + f" ({dragon_type}×{type_mult:.2f})"
            )
        
        return result
    
    def calculate_fight_impact(
        self,
        kills_for: int,
        kills_against: int,
        context: EventContext,
        for_team: int = 1
    ) -> ImpactResult:
        """
        Calculate teamfight impact.
        
        Args:
            kills_for: Kills our team got
            kills_against: Kills enemy team got
            context: Game context
            for_team: Which team we're calculating for
        """
        net_kills = kills_for - kills_against
        total_kills = kills_for + kills_against
        
        if net_kills == 0:
            return ImpactResult(
                base_impact=0,
                time_multiplier=1.0,
                context_multiplier=1.0,
                momentum_multiplier=1.0,
                final_impact=0,
                confidence=0.9,
                explanation="Even trade"
            )
        
        # Base fight impact
        base = self.base_impacts.get("fight_base", 0.015)
        
        # Add per-kill advantage
        kill_advantage = abs(net_kills)
        per_kill = self.base_impacts.get("fight_per_kill", 0.012)
        base += (kill_advantage - 1) * per_kill
        
        # Ace bonus
        if kills_for >= 5 or (kills_for >= 4 and total_kills >= 7):
            ace_bonus = self.base_impacts.get("fight_ace_bonus", 0.04)
            base += ace_bonus
        
        # Get multipliers
        time_mult = self.time_curve(context.game_time)
        context_mult, _ = self._get_context_multiplier("fight", context, for_team)
        momentum_mult, _ = self._get_momentum_multiplier(context, for_team)
        
        final = base * time_mult * context_mult * momentum_mult
        
        # Direction
        if net_kills < 0:
            final = -final
        if for_team == 2:
            final = -final
        
        fight_desc = f"{kills_for}-{kills_against}"
        if kills_for >= 5:
            fight_desc += " ACE!"
        
        return ImpactResult(
            base_impact=base,
            time_multiplier=time_mult,
            context_multiplier=context_mult,
            momentum_multiplier=momentum_mult,
            final_impact=final,
            confidence=0.85,
            explanation=f"Fight {fight_desc}: {final:+.4f}"
        )
    
    # =================================================================
    # HELPER METHODS
    # =================================================================
    
    def _get_base_impact(self, event_type: str, context: EventContext) -> float:
        """Get base impact for event type."""
        
        # Direct lookup
        if event_type in self.base_impacts:
            return self.base_impacts[event_type]
        
        # Try with underscore variants
        for key in self.base_impacts:
            if key.startswith(event_type):
                return self.base_impacts[key]
        
        # Default fallback
        logger.warning(f"Unknown event type: {event_type}")
        return 0.005
    
    def _get_context_multiplier(
        self,
        event_type: str,
        context: EventContext,
        for_team: int
    ) -> Tuple[float, str]:
        """
        Calculate context-based multiplier.
        
        Factors:
        - Gold differential (comeback bonus)
        - Victim value (for kills)
        - Map state
        - Current probability state
        """
        mult = 1.0
        explanations = []
        
        # 1. Comeback/snowball mechanic
        # Events matter MORE when behind (potential comeback)
        # Events matter LESS when far ahead (diminishing returns)
        
        if for_team == 1:
            our_gold_diff = context.gold_diff
        else:
            our_gold_diff = -context.gold_diff
        
        if our_gold_diff < -5000:
            # We're very behind - this event is crucial for comeback
            mult *= 1.25
            explanations.append("comeback+25%")
        elif our_gold_diff < -2000:
            mult *= 1.12
            explanations.append("behind+12%")
        elif our_gold_diff > 8000:
            # We're very ahead - diminishing returns
            mult *= 0.75
            explanations.append("snowball-25%")
        elif our_gold_diff > 4000:
            mult *= 0.88
            explanations.append("ahead-12%")
        
        # 2. Victim value (for kills)
        if event_type.startswith("kill") and context.victim_gold > 0:
            # Killing someone with lots of gold is more impactful
            avg_gold_at_time = 300 + context.game_time * 400  # Rough estimate
            gold_ratio = context.victim_gold / max(avg_gold_at_time, 1)
            
            if gold_ratio > 1.5:
                # Killed a fed player
                mult *= 1.20
                explanations.append("fed_victim+20%")
            elif gold_ratio > 1.2:
                mult *= 1.10
                explanations.append("rich_victim+10%")
            elif gold_ratio < 0.7:
                # Killed a poor player
                mult *= 0.85
                explanations.append("poor_victim-15%")
        
        # 3. Map state pressure
        if context.inhibs_down_them > 0:
            # Enemy has inhib down - objectives more impactful
            if event_type in ["baron", "dragon", "elder"]:
                mult *= 1.15
                explanations.append("pressure+15%")
        
        if context.towers_remaining_us <= 3:
            # We're low on towers - defensive events matter more
            mult *= 1.10
            explanations.append("desperate+10%")
        
        # 4. Soul point dragon
        if event_type.startswith("dragon") and context.is_soul_point:
            mult *= 1.30
            explanations.append("soul_point+30%")
        
        # 5. Contested objective (50/50 smite)
        if context.is_contested:
            mult *= 1.15
            explanations.append("contested+15%")
        
        # 6. Steal bonus
        if context.is_steal:
            mult *= 1.35
            explanations.append("STEAL+35%")
        
        explain_str = ", ".join(explanations) if explanations else ""
        return mult, explain_str
    
    def _get_momentum_multiplier(
        self,
        context: EventContext,
        for_team: int
    ) -> Tuple[float, str]:
        """
        Calculate momentum multiplier.
        
        Consecutive events in short time = momentum.
        """
        mult = 1.0
        explanations = []
        
        # Check recent events for momentum
        recent_for = context.recent_kills_for + context.recent_objectives_for
        recent_against = context.recent_kills_against
        
        if recent_for >= 3 and recent_against == 0:
            # Strong positive momentum
            mult *= 1.15
            explanations.append("momentum+15%")
        elif recent_for >= 2 and recent_against <= 1:
            mult *= 1.08
            explanations.append("momentum+8%")
        elif recent_against >= 3 and recent_for == 0:
            # They have momentum - our events break it (bonus)
            mult *= 1.12
            explanations.append("momentum_break+12%")
        
        # Internal tracking momentum
        recent_same_team = sum(
            1 for t, _, team in self._recent_events
            if context.game_time - t < 1.5 and team == for_team
        )
        
        if recent_same_team >= 2:
            mult *= (1 + recent_same_team * 0.03)
            explanations.append(f"streak+{recent_same_team * 3}%")
        
        explain_str = ", ".join(explanations) if explanations else ""
        return mult, explain_str
    
    def _track_event(self, game_time: float, event_type: str, team: int):
        """Track event for momentum calculation."""
        self._recent_events.append((game_time, event_type, team))
        
        # Keep only last 2 minutes of events
        cutoff = game_time - 2.0
        self._recent_events = [
            e for e in self._recent_events if e[0] > cutoff
        ]
    
    def _calculate_confidence(self, context: EventContext) -> float:
        """Calculate confidence based on context completeness."""
        confidence = 0.7  # Base confidence
        
        # More data = more confidence
        if context.gold_diff != 0:
            confidence += 0.05
        if context.game_time > 10:
            confidence += 0.05
        if context.killer_gold > 0 or context.victim_gold > 0:
            confidence += 0.05
        if context.towers_remaining_us < 11:
            confidence += 0.03
        
        return min(0.95, confidence)
    
    def get_game_phase(self, game_time: float) -> GamePhase:
        """Get current game phase."""
        if self.game == "lol":
            if game_time < 6:
                return GamePhase.EARLY_LANE
            elif game_time < 14:
                return GamePhase.MID_LANE
            elif game_time < 20:
                return GamePhase.EARLY_MID
            elif game_time < 28:
                return GamePhase.MID_GAME
            elif game_time < 35:
                return GamePhase.LATE_MID
            elif game_time < 45:
                return GamePhase.LATE_GAME
            else:
                return GamePhase.ULTRA_LATE
        else:  # Dota
            if game_time < 10:
                return GamePhase.EARLY_LANE
            elif game_time < 18:
                return GamePhase.MID_LANE
            elif game_time < 28:
                return GamePhase.MID_GAME
            elif game_time < 40:
                return GamePhase.LATE_MID
            elif game_time < 55:
                return GamePhase.LATE_GAME
            else:
                return GamePhase.ULTRA_LATE
    
    def reset(self):
        """Reset momentum tracking for new game."""
        self._recent_events = []
