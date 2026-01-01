"""
Historical Data Generator - Creates realistic match data for backtesting.

Since we don't have access to real historical match data with tick-by-tick
game state, we generate synthetic data that mimics real match patterns.

The generator creates:
- Realistic game progression (gold, kills, towers over time)
- Event sequences that follow typical match patterns
- Market prices that react to events with realistic lag
- Final outcomes correlated with game state

This allows us to backtest our strategy before we have real data.
"""

import random
import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
import logging

from core import Game, Team, GameState, GameEvent, MatchStatus

logger = logging.getLogger(__name__)


@dataclass
class HistoricalTick:
    """
    A single point in time during a historical match.
    
    Contains all the information we would have at that moment:
    - Game state (gold, kills, towers, etc.)
    - Our calculated fair price
    - The market price at that time
    - Any events that just happened
    """
    timestamp: datetime
    game_time_seconds: int
    
    # Game state
    team1_gold: int
    team2_gold: int
    team1_kills: int
    team2_kills: int
    team1_towers: int
    team2_towers: int
    team1_dragons: int
    team2_dragons: int
    team1_barons: int
    team2_barons: int
    
    # Prices
    fair_price: float  # What we calculate
    market_price: float  # What the market shows
    
    # Events at this tick
    events: List[GameEvent] = field(default_factory=list)
    
    @property
    def gold_diff(self) -> int:
        return self.team1_gold - self.team2_gold
    
    @property
    def kill_diff(self) -> int:
        return self.team1_kills - self.team2_kills


@dataclass
class HistoricalMatch:
    """
    A complete historical match with all tick data.
    """
    match_id: str
    game: Game
    team1_name: str
    team2_name: str
    
    # Match outcome
    winner: int  # 1 or 2
    final_game_time: int  # seconds
    
    # Tick-by-tick data
    ticks: List[HistoricalTick] = field(default_factory=list)
    
    # Metadata
    date: datetime = field(default_factory=datetime.now)
    
    @property
    def duration_minutes(self) -> float:
        return self.final_game_time / 60


class HistoricalDataGenerator:
    """
    Generates realistic historical match data for backtesting.
    
    Usage:
        generator = HistoricalDataGenerator(game="lol")
        
        # Generate a single match
        match = generator.generate_match()
        
        # Generate multiple matches
        matches = generator.generate_matches(count=100)
    """
    
    # Team name pools
    LOL_TEAMS = [
        ("T1", "T1"), ("Gen.G", "GEN"), ("DRX", "DRX"),
        ("Cloud9", "C9"), ("Team Liquid", "TL"), ("100 Thieves", "100T"),
        ("G2 Esports", "G2"), ("Fnatic", "FNC"), ("MAD Lions", "MAD"),
        ("JD Gaming", "JDG"), ("Top Esports", "TES"), ("Weibo Gaming", "WBG"),
    ]
    
    DOTA_TEAMS = [
        ("Team Spirit", "Spirit"), ("Gaimin Gladiators", "GG"),
        ("Team Liquid", "Liquid"), ("OG", "OG"),
        ("PSG.LGD", "LGD"), ("Team Aster", "Aster"),
        ("Tundra Esports", "Tundra"), ("BetBoom Team", "BB"),
    ]
    
    def __init__(self, game: str = "lol"):
        """
        Initialize the generator.
        
        Args:
            game: "lol" or "dota2"
        """
        self.game = Game.LOL if game.lower() == "lol" else Game.DOTA2
        self.teams = self.LOL_TEAMS if self.game == Game.LOL else self.DOTA_TEAMS
        
        # Generation parameters
        self.tick_interval_seconds = 30  # One tick every 30 seconds
        self.market_lag_factor = 0.4  # How fast market follows fair price
        self.market_noise = 0.015  # Random noise in market price
    
    def generate_match(
        self,
        team1_strength: float = None,
        match_id: str = None
    ) -> HistoricalMatch:
        """
        Generate a single historical match.
        
        Args:
            team1_strength: Relative strength of team 1 (0.3 to 0.7)
                           If None, randomly generated.
            match_id: Optional match ID. If None, auto-generated.
            
        Returns:
            HistoricalMatch with complete tick data
        """
        # Pick teams
        team_indices = random.sample(range(len(self.teams)), 2)
        team1_name, team1_abbr = self.teams[team_indices[0]]
        team2_name, team2_abbr = self.teams[team_indices[1]]
        
        # Generate team strength (affects who wins)
        if team1_strength is None:
            team1_strength = random.uniform(0.35, 0.65)
        
        # Generate match duration (25-45 minutes typically)
        if self.game == Game.LOL:
            base_duration = random.gauss(32, 6)  # Mean 32 min, std 6
        else:
            base_duration = random.gauss(38, 8)  # Dota games longer
        
        duration_minutes = max(20, min(55, base_duration))
        duration_seconds = int(duration_minutes * 60)
        
        # Generate match ID
        if match_id is None:
            match_id = f"hist_{random.randint(10000, 99999)}"
        
        # Generate tick-by-tick data
        ticks = self._generate_ticks(
            duration_seconds=duration_seconds,
            team1_strength=team1_strength
        )
        
        # Determine winner based on final state
        final_tick = ticks[-1]
        
        # Winner is probabilistic based on final fair price
        win_prob = final_tick.fair_price
        winner = 1 if random.random() < win_prob else 2
        
        return HistoricalMatch(
            match_id=match_id,
            game=self.game,
            team1_name=team1_name,
            team2_name=team2_name,
            winner=winner,
            final_game_time=duration_seconds,
            ticks=ticks,
            date=datetime.now() - timedelta(days=random.randint(1, 365))
        )
    
    def generate_matches(
        self,
        count: int = 100,
        balanced: bool = True
    ) -> List[HistoricalMatch]:
        """
        Generate multiple historical matches.
        
        Args:
            count: Number of matches to generate
            balanced: If True, ensure roughly 50% win rate for each side
            
        Returns:
            List of HistoricalMatch objects
        """
        matches = []
        
        for i in range(count):
            # For balanced dataset, alternate advantage
            if balanced:
                team1_strength = 0.5 + (random.random() - 0.5) * 0.3
                if i % 2 == 1:
                    team1_strength = 1 - team1_strength
            else:
                team1_strength = None
            
            match = self.generate_match(
                team1_strength=team1_strength,
                match_id=f"hist_{i:05d}"
            )
            matches.append(match)
            
            if (i + 1) % 20 == 0:
                logger.debug(f"Generated {i + 1}/{count} matches")
        
        logger.info(f"Generated {count} historical matches")
        return matches
    
    def _generate_ticks(
        self,
        duration_seconds: int,
        team1_strength: float
    ) -> List[HistoricalTick]:
        """Generate tick-by-tick data for a match."""
        ticks = []
        
        # Initialize state
        state = {
            'team1_gold': 2500 if self.game == Game.LOL else 3000,
            'team2_gold': 2500 if self.game == Game.LOL else 3000,
            'team1_kills': 0,
            'team2_kills': 0,
            'team1_towers': 0,
            'team2_towers': 0,
            'team1_dragons': 0,
            'team2_dragons': 0,
            'team1_barons': 0,
            'team2_barons': 0,
        }
        
        # Market starts at 50%
        market_price = 0.5
        fair_price = 0.5
        
        # Generate ticks
        num_ticks = duration_seconds // self.tick_interval_seconds
        
        for tick_num in range(num_ticks + 1):
            game_time = tick_num * self.tick_interval_seconds
            game_minutes = game_time / 60
            
            # Generate events for this tick
            events = self._generate_events(
                game_minutes=game_minutes,
                team1_strength=team1_strength,
                state=state
            )
            
            # Apply events to state
            for event in events:
                self._apply_event(event, state)
            
            # Calculate fair price from state
            fair_price = self._calculate_fair_price(state, game_minutes)
            
            # Update market price (with lag and noise)
            market_price = self._update_market_price(
                market_price, fair_price
            )
            
            # Add passive gold
            self._add_passive_gold(state, game_minutes)
            
            # Create tick
            tick = HistoricalTick(
                timestamp=datetime.now(),
                game_time_seconds=game_time,
                team1_gold=state['team1_gold'],
                team2_gold=state['team2_gold'],
                team1_kills=state['team1_kills'],
                team2_kills=state['team2_kills'],
                team1_towers=state['team1_towers'],
                team2_towers=state['team2_towers'],
                team1_dragons=state['team1_dragons'],
                team2_dragons=state['team2_dragons'],
                team1_barons=state['team1_barons'],
                team2_barons=state['team2_barons'],
                fair_price=fair_price,
                market_price=market_price,
                events=events
            )
            
            ticks.append(tick)
        
        return ticks
    
    def _generate_events(
        self,
        game_minutes: float,
        team1_strength: float,
        state: Dict
    ) -> List[GameEvent]:
        """Generate events for a tick."""
        events = []
        
        # Event probability increases with game time
        if game_minutes < 3:
            event_prob = 0.05
        elif game_minutes < 10:
            event_prob = 0.15
        elif game_minutes < 20:
            event_prob = 0.25
        else:
            event_prob = 0.35
        
        # Adjust team1 win probability based on current state
        gold_diff = state['team1_gold'] - state['team2_gold']
        current_advantage = gold_diff / 15000  # Normalize
        adjusted_strength = team1_strength + current_advantage * 0.1
        adjusted_strength = max(0.25, min(0.75, adjusted_strength))
        
        # Check for kill
        if random.random() < event_prob:
            team = 1 if random.random() < adjusted_strength else 2
            context = random.choice(['default', 'default', 'solo'])
            events.append(GameEvent(
                timestamp=0,
                event_type='kill',
                team=team,
                context=context
            ))
        
        # Check for tower (less frequent)
        if random.random() < event_prob * 0.3 and game_minutes > 8:
            team = 1 if random.random() < adjusted_strength else 2
            events.append(GameEvent(
                timestamp=0,
                event_type='tower',
                team=team,
                context='default'
            ))
        
        # Check for dragon (LoL)
        if self.game == Game.LOL and game_minutes > 5:
            if random.random() < event_prob * 0.15:
                team = 1 if random.random() < adjusted_strength else 2
                # Check for soul
                current_dragons = state[f'team{team}_dragons']
                context = 'soul' if current_dragons >= 3 else 'default'
                events.append(GameEvent(
                    timestamp=0,
                    event_type='dragon',
                    team=team,
                    context=context
                ))
        
        # Check for baron (LoL, after 20 min)
        if self.game == Game.LOL and game_minutes > 20:
            if random.random() < event_prob * 0.08:
                team = 1 if random.random() < adjusted_strength else 2
                events.append(GameEvent(
                    timestamp=0,
                    event_type='baron',
                    team=team,
                    context='secure'
                ))
        
        return events
    
    def _apply_event(self, event: GameEvent, state: Dict):
        """Apply event to state."""
        team_prefix = f'team{event.team}_'
        
        if event.event_type == 'kill':
            state[team_prefix + 'kills'] += 1
            state[team_prefix + 'gold'] += 300
            
        elif event.event_type == 'tower':
            state[team_prefix + 'towers'] += 1
            state[team_prefix + 'gold'] += 550
            
        elif event.event_type == 'dragon':
            state[team_prefix + 'dragons'] += 1
            state[team_prefix + 'gold'] += 200
            
        elif event.event_type == 'baron':
            state[team_prefix + 'barons'] += 1
            state[team_prefix + 'gold'] += 1500
    
    def _calculate_fair_price(self, state: Dict, game_minutes: float) -> float:
        """Calculate fair price from game state."""
        # Gold difference effect
        gold_diff = state['team1_gold'] - state['team2_gold']
        gold_factor = math.tanh(gold_diff / 10000) * 0.35
        
        # Kill difference (smaller effect, overlaps with gold)
        kill_diff = state['team1_kills'] - state['team2_kills']
        kill_factor = kill_diff * 0.005
        
        # Tower difference
        tower_diff = state['team1_towers'] - state['team2_towers']
        tower_factor = tower_diff * 0.02
        
        # Dragon difference
        dragon_diff = state['team1_dragons'] - state['team2_dragons']
        dragon_factor = dragon_diff * 0.02
        
        # Baron difference
        baron_diff = state['team1_barons'] - state['team2_barons']
        baron_factor = baron_diff * 0.03
        
        # Time factor (advantages matter more late)
        time_mult = 0.7 + min(game_minutes / 40, 0.6)
        
        # Combine
        total = gold_factor + kill_factor + tower_factor + dragon_factor + baron_factor
        total *= time_mult
        
        # Convert to probability
        fair_price = 0.5 + total
        return max(0.05, min(0.95, fair_price))
    
    def _update_market_price(self, current: float, target: float) -> float:
        """Update market price toward target with lag and noise."""
        # Move toward target
        new_price = current + (target - current) * self.market_lag_factor
        
        # Add noise
        noise = random.gauss(0, self.market_noise)
        new_price += noise
        
        return max(0.05, min(0.95, new_price))
    
    def _add_passive_gold(self, state: Dict, game_minutes: float):
        """Add passive gold income."""
        # Gold per tick (roughly 10 gold/sec per team)
        passive = int(50 + game_minutes * 2)
        
        state['team1_gold'] += passive + random.randint(-20, 20)
        state['team2_gold'] += passive + random.randint(-20, 20)