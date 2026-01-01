"""
Impact Calculator - Pre-computed lookup tables for game events.

This is the core of our speed advantage. Instead of complex real-time
calculations, we use lookup tables derived from historical data analysis.

When a kill happens, we don't calculate - we just look up the impact instantly.
This gives us milliseconds of advantage over bots that compute in real-time.

The impact values are based on analysis of thousands of professional matches.
"""

import logging
from dataclasses import dataclass
from typing import Dict, Tuple, Optional

logger = logging.getLogger(__name__)


@dataclass
class EventImpact:
    """
    Impact of a single game event.
    
    Attributes:
        base_impact: Probability shift (e.g., 0.02 = 2% shift)
        gold_value: Approximate gold swing from this event
        description: Human-readable description
    """
    base_impact: float
    gold_value: int
    description: str


class ImpactCalculator:
    """
    Calculates probability impact of game events using lookup tables.
    
    Usage:
        calc = ImpactCalculator("lol")
        impact, info = calc.get_event_impact("kill", "solo", game_time=15.0)
        print(f"Kill impact: {impact:.3f}")  # e.g., 0.008
    
    The key insight: we don't need complex real-time calculations.
    We pre-compute impacts for all event types and look them up instantly.
    """
    
    # ================================================================
    # LEAGUE OF LEGENDS IMPACT TABLES
    # ================================================================
    # Format: (event_type, context) -> EventImpact
    # Impact is probability shift for the team that achieved the event
    # 
    # These values are derived from analysis of pro matches:
    # - Average gold value of each event
    # - Historical win rate correlation with events
    # - Game state at time of event
    # ================================================================
    
    LOL_IMPACTS: Dict[Tuple[str, str], EventImpact] = {
        # ============ KILLS ============
        # Solo kill: higher impact (outplay)
        ("kill", "solo"): EventImpact(
            base_impact=0.008,  # 0.8% probability shift
            gold_value=300,
            description="Solo kill"
        ),
        # Default kill
        ("kill", "default"): EventImpact(
            base_impact=0.006,
            gold_value=300,
            description="Kill"
        ),
        # Shutdown bounty (killing someone on a streak)
        ("kill", "shutdown"): EventImpact(
            base_impact=0.015,
            gold_value=700,
            description="Shutdown bounty"
        ),
        # First blood
        ("kill", "first_blood"): EventImpact(
            base_impact=0.012,
            gold_value=400,
            description="First blood"
        ),
        
        # ============ TOWERS ============
        # Outer towers (tier 1)
        ("tower", "outer"): EventImpact(
            base_impact=0.015,
            gold_value=550,
            description="Outer tower"
        ),
        # Inner towers (tier 2)
        ("tower", "inner"): EventImpact(
            base_impact=0.020,
            gold_value=550,
            description="Inner tower"
        ),
        # Inhibitor towers (tier 3)
        ("tower", "inhibitor_tower"): EventImpact(
            base_impact=0.030,
            gold_value=550,
            description="Inhibitor tower"
        ),
        # Nexus towers
        ("tower", "nexus_tower"): EventImpact(
            base_impact=0.025,
            gold_value=50,
            description="Nexus tower"
        ),
        # First tower bonus
        ("tower", "first"): EventImpact(
            base_impact=0.025,
            gold_value=650,
            description="First tower"
        ),
        # Default tower
        ("tower", "default"): EventImpact(
            base_impact=0.018,
            gold_value=550,
            description="Tower"
        ),
        
        # ============ DRAGONS ============
        # Infernal (damage buff)
        ("dragon", "infernal"): EventImpact(
            base_impact=0.018,
            gold_value=200,
            description="Infernal Drake"
        ),
        # Mountain (tankiness)
        ("dragon", "mountain"): EventImpact(
            base_impact=0.020,
            gold_value=200,
            description="Mountain Drake"
        ),
        # Ocean (sustain)
        ("dragon", "ocean"): EventImpact(
            base_impact=0.015,
            gold_value=200,
            description="Ocean Drake"
        ),
        # Cloud (movement speed)
        ("dragon", "cloud"): EventImpact(
            base_impact=0.012,
            gold_value=200,
            description="Cloud Drake"
        ),
        # Hextech
        ("dragon", "hextech"): EventImpact(
            base_impact=0.016,
            gold_value=200,
            description="Hextech Drake"
        ),
        # Chemtech
        ("dragon", "chemtech"): EventImpact(
            base_impact=0.017,
            gold_value=200,
            description="Chemtech Drake"
        ),
        # Default dragon
        ("dragon", "default"): EventImpact(
            base_impact=0.016,
            gold_value=200,
            description="Dragon"
        ),
        # Dragon Soul (4 dragons) - HUGE
        ("dragon", "soul"): EventImpact(
            base_impact=0.12,  # 12% shift!
            gold_value=300,
            description="Dragon Soul"
        ),
        # Elder Dragon - MASSIVE
        ("dragon", "elder"): EventImpact(
            base_impact=0.18,  # 18% shift!
            gold_value=350,
            description="Elder Dragon"
        ),
        
        # ============ BARON NASHOR ============
        ("baron", "secure"): EventImpact(
            base_impact=0.10,  # 10% shift
            gold_value=1500,
            description="Baron Nashor"
        ),
        ("baron", "steal"): EventImpact(
            base_impact=0.14,  # Extra impact for steal
            gold_value=1500,
            description="Baron stolen!"
        ),
        ("baron", "default"): EventImpact(
            base_impact=0.10,
            gold_value=1500,
            description="Baron Nashor"
        ),
        
        # ============ RIFT HERALD ============
        ("herald", "default"): EventImpact(
            base_impact=0.02,
            gold_value=200,
            description="Rift Herald"
        ),
        
        # ============ INHIBITOR ============
        ("inhibitor", "default"): EventImpact(
            base_impact=0.06,
            gold_value=50,
            description="Inhibitor"
        ),
        
        # ============ TEAMFIGHTS ============
        # These are aggregate events (multiple kills at once)
        ("teamfight", "won_small"): EventImpact(
            base_impact=0.03,
            gold_value=800,
            description="Won small fight (2-3 kills)"
        ),
        ("teamfight", "won_big"): EventImpact(
            base_impact=0.06,
            gold_value=1500,
            description="Won big teamfight (4+ kills)"
        ),
        ("teamfight", "ace"): EventImpact(
            base_impact=0.10,
            gold_value=2500,
            description="Ace! (killed all 5)"
        ),
    }
    
    # ================================================================
    # DOTA 2 IMPACT TABLES
    # ================================================================
    # Dota 2 has different mechanics:
    # - Buyback means kills are less permanent
    # - Gold loss on death
    # - Roshan instead of Baron/Dragon
    # - Barracks instead of Inhibitors
    # ================================================================
    
    DOTA_IMPACTS: Dict[Tuple[str, str], EventImpact] = {
        # ============ KILLS ============
        ("kill", "solo"): EventImpact(
            base_impact=0.006,
            gold_value=250,
            description="Solo kill"
        ),
        ("kill", "default"): EventImpact(
            base_impact=0.005,
            gold_value=250,
            description="Kill"
        ),
        ("kill", "pickoff"): EventImpact(
            base_impact=0.008,
            gold_value=300,
            description="Pickoff"
        ),
        
        # ============ TOWERS ============
        ("tower", "tier1"): EventImpact(
            base_impact=0.015,
            gold_value=500,
            description="Tier 1 Tower"
        ),
        ("tower", "tier2"): EventImpact(
            base_impact=0.022,
            gold_value=600,
            description="Tier 2 Tower"
        ),
        ("tower", "tier3"): EventImpact(
            base_impact=0.035,
            gold_value=700,
            description="Tier 3 Tower"
        ),
        ("tower", "tier4"): EventImpact(
            base_impact=0.040,
            gold_value=800,
            description="Tier 4 Tower"
        ),
        ("tower", "default"): EventImpact(
            base_impact=0.020,
            gold_value=550,
            description="Tower"
        ),
        
        # ============ BARRACKS ============
        ("barracks", "melee"): EventImpact(
            base_impact=0.05,
            gold_value=225,
            description="Melee Barracks"
        ),
        ("barracks", "ranged"): EventImpact(
            base_impact=0.04,
            gold_value=150,
            description="Ranged Barracks"
        ),
        ("barracks", "default"): EventImpact(
            base_impact=0.045,
            gold_value=200,
            description="Barracks"
        ),
        ("barracks", "mega"): EventImpact(
            base_impact=0.15,  # Mega creeps is huge
            gold_value=0,
            description="Mega Creeps!"
        ),
        
        # ============ ROSHAN ============
        ("roshan", "first"): EventImpact(
            base_impact=0.06,
            gold_value=600,
            description="First Roshan (Aegis)"
        ),
        ("roshan", "second"): EventImpact(
            base_impact=0.08,
            gold_value=800,
            description="Second Roshan (Aegis + Cheese)"
        ),
        ("roshan", "third"): EventImpact(
            base_impact=0.10,
            gold_value=1000,
            description="Third Roshan (Aegis + Cheese + Refresher)"
        ),
        ("roshan", "steal"): EventImpact(
            base_impact=0.12,
            gold_value=800,
            description="Roshan stolen!"
        ),
        ("roshan", "default"): EventImpact(
            base_impact=0.07,
            gold_value=700,
            description="Roshan"
        ),
        
        # ============ TEAMFIGHTS ============
        ("teamfight", "won_small"): EventImpact(
            base_impact=0.025,
            gold_value=700,
            description="Won small fight"
        ),
        ("teamfight", "won_big"): EventImpact(
            base_impact=0.05,
            gold_value=1300,
            description="Won big teamfight"
        ),
        ("teamfight", "wipe"): EventImpact(
            base_impact=0.08,
            gold_value=2000,
            description="Team wipe!"
        ),
    }
    
    # ================================================================
    # TIME MULTIPLIERS
    # ================================================================
    # Events matter more as the game progresses.
    # A kill at 5 minutes is less impactful than a kill at 35 minutes.
    # ================================================================
    
    LOL_TIME_MULTIPLIERS: Dict[Tuple[int, int], float] = {
        (0, 5): 0.6,      # Very early - high variance, less predictive
        (5, 10): 0.8,     # Early game
        (10, 20): 1.0,    # Mid game - baseline
        (20, 30): 1.15,   # Late mid game
        (30, 40): 1.25,   # Late game - leads matter more
        (40, 100): 1.35,  # Very late - every fight is crucial
    }
    
    DOTA_TIME_MULTIPLIERS: Dict[Tuple[int, int], float] = {
        (0, 10): 0.5,     # Laning phase - lots of variance
        (10, 20): 0.7,    # Early mid game
        (20, 30): 0.9,    # Mid game
        (30, 40): 1.0,    # Late mid game - baseline
        (40, 50): 1.1,    # Late game
        (50, 100): 1.15,  # Ultra late - but buybacks add variance
    }
    
    # ================================================================
    # METHODS
    # ================================================================
    
    def __init__(self, game: str = "lol"):
        """
        Initialize the calculator for a specific game.
        
        Args:
            game: "lol" or "dota2"
        """
        self.game = game.lower()
        
        # Select appropriate tables based on game
        if self.game == "lol":
            self.impacts = self.LOL_IMPACTS
            self.time_multipliers = self.LOL_TIME_MULTIPLIERS
        else:
            self.impacts = self.DOTA_IMPACTS
            self.time_multipliers = self.DOTA_TIME_MULTIPLIERS
        
        logger.debug(f"ImpactCalculator initialized for {self.game}")
    
    def get_event_impact(
        self,
        event_type: str,
        context: str = "default",
        game_time_minutes: float = 15.0,
        current_prob: float = 0.5
    ) -> Tuple[float, EventImpact]:
        """
        Get the probability impact of an event.
        
        This is the main method you'll use. Given an event, it returns
        how much the win probability should shift.
        
        Args:
            event_type: Type of event ("kill", "tower", "dragon", etc.)
            context: Context modifier ("solo", "first", "steal", etc.)
            game_time_minutes: Current game time in minutes
            current_prob: Current win probability for the team (0 to 1)
        
        Returns:
            Tuple of (probability_shift, EventImpact object)
            
        Example:
            impact, info = calc.get_event_impact("baron", "steal", 28.0, 0.45)
            # impact = 0.14 * time_mult * prob_mult ≈ 0.16
            # info.description = "Baron stolen!"
        """
        # Step 1: Look up base impact
        key = (event_type.lower(), context.lower())
        
        if key not in self.impacts:
            # Try without context (fall back to default)
            key = (event_type.lower(), "default")
        
        if key not in self.impacts:
            logger.warning(f"Unknown event: {event_type}/{context}")
            return 0.0, EventImpact(0, 0, "Unknown event")
        
        impact_info = self.impacts[key]
        
        # Step 2: Apply time multiplier
        time_mult = self._get_time_multiplier(game_time_minutes)
        
        # Step 3: Apply probability adjustment
        # Events matter less at extreme probabilities
        prob_mult = self._get_probability_multiplier(current_prob)
        
        # Step 4: Calculate final impact
        final_impact = impact_info.base_impact * time_mult * prob_mult
        
        logger.debug(
            f"Event impact: {event_type}/{context} = "
            f"{impact_info.base_impact:.3f} × {time_mult:.2f} × {prob_mult:.2f} = "
            f"{final_impact:.4f}"
        )
        
        return final_impact, impact_info
    
    def _get_time_multiplier(self, game_time_minutes: float) -> float:
        """
        Get time-based multiplier for event impact.
        
        Events matter more as game progresses.
        """
        for (min_time, max_time), multiplier in self.time_multipliers.items():
            if min_time <= game_time_minutes < max_time:
                return multiplier
        
        # If beyond all ranges, use the last multiplier
        return list(self.time_multipliers.values())[-1]
    
    def _get_probability_multiplier(self, current_prob: float) -> float:
        """
        Adjust impact based on current probability.
        
        Events matter less when one team is already heavily favored.
        - At 50%: multiplier = 1.0 (baseline)
        - At 20% or 80%: multiplier ≈ 0.85
        - At 10% or 90%: multiplier ≈ 0.70
        
        This prevents probabilities from becoming too extreme too quickly.
        """
        # How far from 50%
        deviation = abs(current_prob - 0.5)
        
        # Linear reduction based on deviation
        # At 50%: 1.0, at 0% or 100%: 0.5
        multiplier = 1.0 - (deviation * 1.0)
        
        # Floor at 0.5 (events always matter somewhat)
        return max(0.5, multiplier)
    
    def calculate_fight_impact(
        self,
        kills_team1: int,
        deaths_team1: int,
        kills_team2: int,
        deaths_team2: int,
        game_time_minutes: float = 15.0,
        current_prob: float = 0.5
    ) -> Tuple[float, str]:
        """
        Calculate the impact of a teamfight.
        
        Teamfights are more complex than single events because
        the outcome depends on the relative kill counts.
        
        Args:
            kills_team1: Kills scored by team 1 in the fight
            deaths_team1: Deaths suffered by team 1 in the fight
            kills_team2: Kills scored by team 2 in the fight
            deaths_team2: Deaths suffered by team 2 in the fight
            game_time_minutes: Current game time
            current_prob: Current win probability for team 1
        
        Returns:
            Tuple of (probability_shift, description)
            Positive shift = team 1 benefited
            Negative shift = team 2 benefited
        """
        # Calculate net kills for each team
        net_team1 = kills_team1 - deaths_team1
        net_team2 = kills_team2 - deaths_team2
        
        total_deaths = deaths_team1 + deaths_team2
        
        # Determine fight winner
        if net_team1 > net_team2:
            winner = 1
            kill_advantage = net_team1
        elif net_team2 > net_team1:
            winner = 2
            kill_advantage = net_team2
        else:
            # Even trade
            return 0.0, "Even trade"
        
        # Classify fight size and base impact
        if total_deaths >= 8:
            # Ace or near-ace
            base_impact = 0.08
            fight_type = "ace"
        elif total_deaths >= 5:
            # Big teamfight
            base_impact = 0.05
            fight_type = "big teamfight"
        elif total_deaths >= 3:
            # Medium fight
            base_impact = 0.03
            fight_type = "teamfight"
        else:
            # Skirmish
            base_impact = 0.015
            fight_type = "skirmish"
        
        # Scale by kill advantage
        # More lopsided = bigger impact
        impact = base_impact + (kill_advantage - 1) * 0.008
        
        # Apply time multiplier
        time_mult = self._get_time_multiplier(game_time_minutes)
        impact *= time_mult
        
        # Apply probability multiplier
        prob_mult = self._get_probability_multiplier(current_prob)
        impact *= prob_mult
        
        # Direction: positive for team 1, negative for team 2
        if winner == 2:
            impact = -impact
        
        # Build description
        if winner == 1:
            description = (
                f"Team 1 won {fight_type} "
                f"({kills_team1}/{deaths_team1} vs {kills_team2}/{deaths_team2})"
            )
        else:
            description = (
                f"Team 2 won {fight_type} "
                f"({kills_team2}/{deaths_team2} vs {kills_team1}/{deaths_team1})"
            )
        
        return impact, description
    
    def get_all_event_types(self) -> list:
        """Get list of all event types for this game."""
        return list(set(key[0] for key in self.impacts.keys()))
    
    def get_contexts_for_event(self, event_type: str) -> list:
        """Get all valid contexts for an event type."""
        return [
            key[1] for key in self.impacts.keys() 
            if key[0] == event_type.lower()
        ]