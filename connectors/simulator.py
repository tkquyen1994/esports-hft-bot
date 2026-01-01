"""
Simulated Data Feed - Generates realistic fake match data for testing.

Use this when:
- No live matches are available
- Testing your bot logic
- Backtesting strategies
- Developing new features

The simulator generates:
- Realistic game progression (gold, kills, towers)
- Random events (kills, objectives)
- Match endings (based on tower/gold advantages)
"""

import asyncio
import random
import time
import logging
from datetime import datetime
from typing import Optional, List, Dict

from core import Game, MatchStatus, Team, GameState, GameEvent
from .base import BaseConnector

logger = logging.getLogger(__name__)


class SimulatedDataFeed(BaseConnector):
    """
    Simulated data feed for testing.
    
    Generates realistic match data without needing API access.
    
    Usage:
        feed = SimulatedDataFeed(game="lol")
        
        def handle_data(data):
            if isinstance(data, GameEvent):
                print(f"Event: {data.event_type}")
            elif isinstance(data, GameState):
                print(f"State: {data.summary()}")
        
        feed.register_callback(handle_data)
        
        await feed.start()
        await feed.run_simulation()
        await feed.stop()
    """
    
    def __init__(self, game: str = "lol"):
        """
        Initialize the simulator.
        
        Args:
            game: "lol" or "dota2"
        """
        super().__init__()
        self.game = Game.LOL if game.lower() == "lol" else Game.DOTA2
        self.game_str = game.lower()
        
        # Current match state
        self._match: Optional[GameState] = None
        
        # Simulation parameters
        self.team1_strength = 0.5  # 0 to 1, 0.5 = even
        self.volatility = 0.3     # How swingy the game is
    
    async def start(self):
        """Start the simulator."""
        self._running = True
        self._create_new_match()
        logger.info(f"Simulated data feed started ({self.game_str.upper()})")
    
    async def stop(self):
        """Stop the simulator."""
        self._running = False
        logger.info("Simulated data feed stopped")
    
    def _create_new_match(self):
        """Create a new simulated match."""
        # Random team names
        team_names_pool = [
            ("Cloud9", "C9"), ("Team Liquid", "TL"), 
            ("T1", "T1"), ("G2 Esports", "G2"),
            ("Fnatic", "FNC"), ("100 Thieves", "100T"),
            ("Gen.G", "GEN"), ("DRX", "DRX"),
            ("Evil Geniuses", "EG"), ("NRG", "NRG"),
        ]
        
        # Pick two random teams
        random.shuffle(team_names_pool)
        t1_name, t1_acro = team_names_pool[0]
        t2_name, t2_acro = team_names_pool[1]
        
        team1 = Team(
            id="sim_t1",
            name=t1_name,
            acronym=t1_acro
        )
        team2 = Team(
            id="sim_t2",
            name=t2_name,
            acronym=t2_acro
        )
        
        # Initialize gold
        if self.game == Game.LOL:
            team1.gold = 2500  # Starting gold (5 players x 500)
            team2.gold = 2500
        else:
            team1.net_worth = 3000
            team2.net_worth = 3000
        
        self._match = GameState(
            match_id=f"sim_{int(time.time())}",
            game=self.game,
            status=MatchStatus.LIVE,
            team1=team1,
            team2=team2,
            game_time_seconds=0,
            best_of=1
        )
        
        # Randomize team strength slightly
        self.team1_strength = 0.5 + random.uniform(-0.15, 0.15)
        
        logger.info(
            f"New match: {team1.name} vs {team2.name} "
            f"(T1 strength: {self.team1_strength:.2f})"
        )
    
    def get_current_state(self) -> Optional[GameState]:
        """Get the current match state."""
        return self._match
    
    async def run_simulation(
        self, 
        tick_interval_ms: int = 2000,
        max_duration_minutes: int = 45
    ):
        """
        Run the match simulation.
        
        Args:
            tick_interval_ms: Time between simulation ticks (milliseconds)
            max_duration_minutes: Maximum game duration
        """
        if not self._match:
            self._create_new_match()
        
        logger.info(
            f"Starting simulation: {self._match.team1.name} vs {self._match.team2.name}"
        )
        
        while self._running and self._match.status == MatchStatus.LIVE:
            # Advance game time
            time_advance = random.randint(10, 30)  # 10-30 seconds per tick
            self._match.game_time_seconds += time_advance
            
            # Generate passive gold/networth
            self._generate_passive_income()
            
            # Random chance of event
            event_chance = self._calculate_event_chance()
            
            if random.random() < event_chance:
                event = self._generate_event()
                if event:
                    # Notify of event
                    await self._notify_callbacks(event)
            
            # Update timestamp
            self._match.last_updated = datetime.now()
            
            # Notify of state update
            await self._notify_callbacks(self._match)
            
            # Check for game end
            if self._should_game_end():
                self._match.status = MatchStatus.FINISHED
                logger.info(
                    f"Match ended at {self._match.game_time_minutes:.1f} min - "
                    f"{self._match.team1.name} {self._match.team1.kills} vs "
                    f"{self._match.team2.kills} {self._match.team2.name}"
                )
                await self._notify_callbacks(self._match)
                break
            
            # Safety check - max duration
            if self._match.game_time_minutes > max_duration_minutes:
                self._match.status = MatchStatus.FINISHED
                logger.info(f"Match reached max duration ({max_duration_minutes} min)")
                await self._notify_callbacks(self._match)
                break
            
            # Wait for next tick
            await asyncio.sleep(tick_interval_ms / 1000)
        
        logger.info("Simulation ended")
    
    def _generate_passive_income(self):
        """Generate passive gold/networth income."""
        # Gold per second varies by game time
        minutes = self._match.game_time_minutes
        
        if self.game == Game.LOL:
            # LoL passive gold is roughly 20.4 gold/10sec per player
            # 5 players = ~102 gold/10sec = ~10 gold/sec per team
            base_gold = int(10 * (self._match.game_time_seconds / 60))
            
            # Add some randomness
            self._match.team1.gold += random.randint(80, 150)
            self._match.team2.gold += random.randint(80, 150)
        else:
            # Dota 2 has more variable income
            self._match.team1.net_worth += random.randint(100, 200)
            self._match.team2.net_worth += random.randint(100, 200)
    
    def _calculate_event_chance(self) -> float:
        """
        Calculate the chance of an event happening this tick.
        
        Events are more likely as game progresses.
        """
        minutes = self._match.game_time_minutes
        
        if minutes < 3:
            return 0.05  # Very few events early
        elif minutes < 10:
            return 0.15  # Laning phase
        elif minutes < 20:
            return 0.25  # Mid game - more action
        elif minutes < 30:
            return 0.35  # Late mid - lots of fights
        else:
            return 0.40  # Late game - constant action
    
    def _generate_event(self) -> Optional[GameEvent]:
        """Generate a random game event."""
        minutes = self._match.game_time_minutes
        
        # Determine event type based on game time
        if minutes < 5:
            # Very early - only kills possible
            event_type = "kill"
        elif minutes < 14:
            # Early-mid - kills and towers
            weights = {"kill": 0.7, "tower": 0.2, "dragon" if self.game == Game.LOL else "roshan": 0.1}
            event_type = random.choices(
                list(weights.keys()), 
                weights=list(weights.values())
            )[0]
        elif minutes < 20:
            # Mid game
            if self.game == Game.LOL:
                weights = {"kill": 0.5, "tower": 0.25, "dragon": 0.20, "herald": 0.05}
            else:
                weights = {"kill": 0.5, "tower": 0.30, "roshan": 0.20}
            event_type = random.choices(
                list(weights.keys()),
                weights=list(weights.values())
            )[0]
        else:
            # Late game - all events possible
            if self.game == Game.LOL:
                weights = {"kill": 0.4, "tower": 0.20, "dragon": 0.15, "baron": 0.15, "teamfight": 0.10}
            else:
                weights = {"kill": 0.4, "tower": 0.25, "roshan": 0.20, "barracks": 0.10, "teamfight": 0.05}
            event_type = random.choices(
                list(weights.keys()),
                weights=list(weights.values())
            )[0]
        
        # Determine which team gets the event
        # Stronger team more likely to get positive events
        team1_chance = self.team1_strength
        
        # Adjust based on current gold lead
        gold_diff = self._match.gold_diff
        if self.game == Game.LOL:
            # Normalize gold diff (-10k to +10k maps to -0.1 to +0.1)
            gold_factor = gold_diff / 100000
        else:
            gold_factor = gold_diff / 150000
        
        team1_chance += gold_factor
        team1_chance = max(0.25, min(0.75, team1_chance))  # Clamp
        
        team = 1 if random.random() < team1_chance else 2
        
        # Generate the event
        return self._create_event(event_type, team)
    
    def _create_event(self, event_type: str, team: int) -> GameEvent:
        """Create an event and update match state."""
        now = time.time()
        context = "default"
        
        # Get team references
        if team == 1:
            active_team = self._match.team1
            passive_team = self._match.team2
        else:
            active_team = self._match.team2
            passive_team = self._match.team1
        
        # Process event and update state
        if event_type == "kill":
            active_team.kills += 1
            passive_team.deaths += 1
            
            # Add kill gold
            if self.game == Game.LOL:
                active_team.gold += 300
            else:
                active_team.net_worth += 250
            
            # Random context
            context = random.choice(["solo", "default", "default", "default"])
            
        elif event_type == "tower":
            active_team.towers += 1
            
            if self.game == Game.LOL:
                active_team.gold += 550
                # Determine tower type
                if active_team.towers <= 3:
                    context = "outer"
                elif active_team.towers <= 6:
                    context = "inner"
                else:
                    context = "inhibitor_tower"
            else:
                active_team.net_worth += 500
                if active_team.towers <= 3:
                    context = "tier1"
                elif active_team.towers <= 6:
                    context = "tier2"
                else:
                    context = "tier3"
        
        elif event_type == "dragon":
            active_team.dragons += 1
            if self.game == Game.LOL:
                active_team.gold += 200
            
            # Check for dragon soul
            if active_team.dragons >= 4:
                context = "soul"
                active_team.has_dragon_soul = True
            else:
                context = random.choice(["infernal", "mountain", "ocean", "cloud"])
        
        elif event_type == "baron":
            active_team.barons += 1
            if self.game == Game.LOL:
                active_team.gold += 1500
            active_team.has_baron_buff = True
            context = "secure"
        
        elif event_type == "herald":
            if self.game == Game.LOL:
                active_team.gold += 200
            context = "default"
        
        elif event_type == "roshan":
            active_team.roshan_kills += 1
            if self.game == Game.DOTA2:
                active_team.net_worth += 700
            active_team.has_aegis = True
            
            # Roshan number
            if active_team.roshan_kills == 1:
                context = "first"
            elif active_team.roshan_kills == 2:
                context = "second"
            else:
                context = "third"
        
        elif event_type == "barracks":
            if self.game == Game.DOTA2:
                active_team.net_worth += 200
            context = random.choice(["melee", "ranged"])
        
        elif event_type == "teamfight":
            # Simulate a teamfight
            if random.random() < 0.6:  # Winner more likely to win fights
                kills = random.randint(2, 4)
                deaths = random.randint(0, 2)
            else:
                kills = random.randint(0, 2)
                deaths = random.randint(2, 4)
            
            active_team.kills += kills
            passive_team.kills += deaths
            passive_team.deaths += kills
            active_team.deaths += deaths
            
            # Gold from teamfight
            if self.game == Game.LOL:
                active_team.gold += kills * 300
                passive_team.gold += deaths * 300
            else:
                active_team.net_worth += kills * 250
                passive_team.net_worth += deaths * 250
            
            if kills > deaths:
                context = "won_big" if kills - deaths >= 2 else "won_small"
            else:
                context = "lost"
        
        return GameEvent(
            timestamp=now,
            event_type=event_type,
            team=team,
            context=context,
            details={
                "game_time": self._match.game_time_minutes
            }
        )
    
    def _should_game_end(self) -> bool:
        """Determine if the game should end."""
        minutes = self._match.game_time_minutes
        
        # Games can't end before 15 minutes (usually)
        if minutes < 15:
            return False
        
        # Check tower difference
        tower_diff = abs(self._match.tower_diff)
        
        # Check gold/networth difference
        if self.game == Game.LOL:
            gold_diff = abs(self._match.gold_diff)
            
            # Surrender conditions (one team very far ahead)
            if tower_diff >= 7 and gold_diff > 10000:
                return random.random() < 0.3
            
            # Nexus push (lots of towers down)
            if tower_diff >= 9:
                return random.random() < 0.5
            
            # Late game with big lead
            if minutes > 30 and gold_diff > 15000:
                return random.random() < 0.2
            
            # Very late game - random chance to end
            if minutes > 35:
                return random.random() < 0.1
            if minutes > 40:
                return random.random() < 0.2
                
        else:  # Dota 2
            nw_diff = abs(self._match.gold_diff)
            
            # Barracks down = likely to end soon
            if tower_diff >= 8:
                return random.random() < 0.4
            
            # Big networth lead late
            if minutes > 35 and nw_diff > 20000:
                return random.random() < 0.3
            
            # Very late
            if minutes > 45:
                return random.random() < 0.15
        
        return False
    
    def set_team_strength(self, team1_strength: float):
        """
        Set the relative strength of team 1.
        
        Args:
            team1_strength: 0 to 1, where 0.5 is even
        """
        self.team1_strength = max(0.2, min(0.8, team1_strength))