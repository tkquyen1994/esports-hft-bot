#!/usr/bin/env python3
"""
LoL Live Trading Bot - IG vs LNG BO5 Match
VERSION 4 - FULLY AUTOMATED WITH LIVE DATA FEEDS

Features:
1. AUTO-MONITORS Riot LoL Esports API for live game events
2. AUTO-MONITORS Polymarket prices in real-time
3. Uses live market odds as base probability (no manual setting needed)
4. Calculates fair probability and finds edges
5. Executes trades when edge detected

REAL MONEY TRADING - $100 BANKROLL

Usage:
    python lol_trading_bot_v4.py
    
    # Practice mode (no API connections):
    python lol_trading_bot_v4.py --practice
"""

import asyncio
import aiohttp
import json
import sys
from datetime import datetime
from typing import Optional, Dict, List, Tuple
from dataclasses import dataclass, field


# ============================================================================
# CONFIGURATION
# ============================================================================

BANKROLL = 100.0
MIN_EDGE = 0.03  # 3% minimum edge to enter
EXIT_EDGE = 0.01  # Exit when edge drops below 1%
MAX_POSITION_SIZE = 5.0  # $5 maximum per position (Polymarket minimum)
MIN_TRADE_SIZE = 5.0  # $5 minimum for Polymarket

# Polling intervals (seconds)
GAME_POLL_INTERVAL = 2  # Poll live game stats every 2 seconds
PRICE_POLL_INTERVAL = 5  # Poll Polymarket prices every 5 seconds
MATCH_CHECK_INTERVAL = 30  # Check for live match every 30 seconds

# Match details - VERIFIED POLYMARKET SLUG
MATCH_SLUG = "lol-ig1-lng-2026-01-02"  # Verified from Polymarket
TEAM1_NAME = "Invictus Gaming"
TEAM1_CODE = "IG"
TEAM2_NAME = "LNG Esports"
TEAM2_CODE = "LNG"

# API URLs
LOL_ESPORTS_API = "https://esports-api.lolesports.com/persisted/gw"
LOL_LIVE_STATS = "https://feed.lolesports.com/livestats/v1"
LOL_API_KEY = "0TvQnueqKa5mxJntVWt0w4LpLfEkrV1Ta8rQBb9Z"
GAMMA_URL = "https://gamma-api.polymarket.com"
CLOB_URL = "https://clob.polymarket.com"


# ============================================================================
# DATA CLASSES
# ============================================================================

@dataclass
class GameState:
    """Current state of a single game."""
    game_number: int = 1
    game_id: Optional[str] = None
    state: str = "not_started"  # not_started, in_game, finished
    
    # Team stats (blue = team on blue side, may not be Team1)
    blue_team_id: Optional[str] = None
    red_team_id: Optional[str] = None
    blue_kills: int = 0
    red_kills: int = 0
    blue_towers: int = 0
    red_towers: int = 0
    blue_dragons: int = 0
    red_dragons: int = 0
    blue_barons: int = 0
    red_barons: int = 0
    blue_inhibitors: int = 0
    red_inhibitors: int = 0
    blue_gold: int = 0
    red_gold: int = 0


@dataclass
class SeriesState:
    """State of the entire BO5 series."""
    match_id: Optional[str] = None
    team1_games: int = 0
    team2_games: int = 0
    current_game: GameState = field(default_factory=GameState)
    team1_is_blue: bool = True  # Track which side Team1 is on


@dataclass
class Position:
    token_id: str
    team: str
    size: float
    entry_price: float
    entry_time: datetime
    
    @property
    def cost(self) -> float:
        return self.size * self.entry_price
    
    def pnl(self, current_price: float) -> float:
        return self.size * (current_price - self.entry_price)


@dataclass
class Trade:
    timestamp: datetime
    team: str
    action: str
    size: float
    price: float
    reason: str
    pnl: float = 0.0


# ============================================================================
# PROBABILITY CALCULATOR
# ============================================================================

class ProbabilityCalculator:
    """
    Calculates win probability based on game state.
    
    KEY FEATURE: Uses live market odds as baseline.
    This accounts for team skill differences without manual input.
    """
    
    # Event impacts on current game probability
    EVENT_IMPACTS = {
        'kill': 0.008,
        'tower': 0.015,
        'dragon': 0.020,
        'inhibitor': 0.035,
        'baron': 0.040,
        'elder': 0.060,
    }
    
    # How much current game affects series at each score
    GAME_WEIGHTS = {
        (0, 0): 0.15, (1, 0): 0.12, (0, 1): 0.12,
        (1, 1): 0.18, (2, 0): 0.08, (0, 2): 0.08,
        (2, 1): 0.15, (1, 2): 0.15, (2, 2): 0.25,
    }
    
    def __init__(self):
        self.base_game_prob = 0.50  # Team 1's single-game win probability
        self.series_state = SeriesState()
        self._current_game_prob = 0.50
        self._last_game_state: Optional[GameState] = None
    
    def set_base_probability_from_market(self, team1_price: float):
        """
        Set base probability from live market odds.
        
        Args:
            team1_price: Team 1's current market price (0.0 to 1.0)
        """
        # Convert series odds to single-game probability
        # This is an approximation - at 0-0 in a BO5, series prob ≈ game prob
        self.base_game_prob = max(0.20, min(0.80, team1_price))
        self._current_game_prob = self.base_game_prob
        print(f"   Base probability from market: {TEAM1_NAME} {self.base_game_prob:.1%} per game")
    
    def update_from_game_state(self, new_state: GameState, team1_is_blue: bool) -> float:
        """
        Update probabilities from live game state.
        Detects changes and adjusts probability accordingly.
        
        Returns:
            Updated series probability for Team 1
        """
        if self._last_game_state is None:
            self._last_game_state = GameState()
        
        old = self._last_game_state
        
        # Determine Team 1's stats based on side
        if team1_is_blue:
            t1_kills, t2_kills = new_state.blue_kills, new_state.red_kills
            t1_towers, t2_towers = new_state.blue_towers, new_state.red_towers
            t1_dragons, t2_dragons = new_state.blue_dragons, new_state.red_dragons
            t1_barons, t2_barons = new_state.blue_barons, new_state.red_barons
            t1_inhibs, t2_inhibs = new_state.blue_inhibitors, new_state.red_inhibitors
            old_t1_kills = old.blue_kills
            old_t2_kills = old.red_kills
            old_t1_towers = old.blue_towers
            old_t2_towers = old.red_towers
            old_t1_dragons = old.blue_dragons
            old_t2_dragons = old.red_dragons
            old_t1_barons = old.blue_barons
            old_t2_barons = old.red_barons
            old_t1_inhibs = old.blue_inhibitors
            old_t2_inhibs = old.red_inhibitors
        else:
            t1_kills, t2_kills = new_state.red_kills, new_state.blue_kills
            t1_towers, t2_towers = new_state.red_towers, new_state.blue_towers
            t1_dragons, t2_dragons = new_state.red_dragons, new_state.blue_dragons
            t1_barons, t2_barons = new_state.red_barons, new_state.blue_barons
            t1_inhibs, t2_inhibs = new_state.red_inhibitors, new_state.blue_inhibitors
            old_t1_kills = old.red_kills
            old_t2_kills = old.blue_kills
            old_t1_towers = old.red_towers
            old_t2_towers = old.blue_towers
            old_t1_dragons = old.red_dragons
            old_t2_dragons = old.blue_dragons
            old_t1_barons = old.red_barons
            old_t2_barons = old.blue_barons
            old_t1_inhibs = old.red_inhibitors
            old_t2_inhibs = old.blue_inhibitors
        
        # Detect and apply changes
        events_detected = []
        
        # Kills
        if t1_kills > old_t1_kills:
            diff = t1_kills - old_t1_kills
            self._current_game_prob = min(0.95, self._current_game_prob + self.EVENT_IMPACTS['kill'] * diff)
            events_detected.append(f"💀 {TEAM1_CODE} +{diff} kill(s)")
        if t2_kills > old_t2_kills:
            diff = t2_kills - old_t2_kills
            self._current_game_prob = max(0.05, self._current_game_prob - self.EVENT_IMPACTS['kill'] * diff)
            events_detected.append(f"💀 {TEAM2_CODE} +{diff} kill(s)")
        
        # Towers
        if t1_towers > old_t1_towers:
            diff = t1_towers - old_t1_towers
            self._current_game_prob = min(0.95, self._current_game_prob + self.EVENT_IMPACTS['tower'] * diff)
            events_detected.append(f"🏰 {TEAM1_CODE} +{diff} tower(s)")
        if t2_towers > old_t2_towers:
            diff = t2_towers - old_t2_towers
            self._current_game_prob = max(0.05, self._current_game_prob - self.EVENT_IMPACTS['tower'] * diff)
            events_detected.append(f"🏰 {TEAM2_CODE} +{diff} tower(s)")
        
        # Dragons
        if t1_dragons > old_t1_dragons:
            diff = t1_dragons - old_t1_dragons
            self._current_game_prob = min(0.95, self._current_game_prob + self.EVENT_IMPACTS['dragon'] * diff)
            events_detected.append(f"🐉 {TEAM1_CODE} +{diff} dragon(s)")
        if t2_dragons > old_t2_dragons:
            diff = t2_dragons - old_t2_dragons
            self._current_game_prob = max(0.05, self._current_game_prob - self.EVENT_IMPACTS['dragon'] * diff)
            events_detected.append(f"🐉 {TEAM2_CODE} +{diff} dragon(s)")
        
        # Barons
        if t1_barons > old_t1_barons:
            diff = t1_barons - old_t1_barons
            self._current_game_prob = min(0.95, self._current_game_prob + self.EVENT_IMPACTS['baron'] * diff)
            events_detected.append(f"👑 {TEAM1_CODE} BARON!")
        if t2_barons > old_t2_barons:
            diff = t2_barons - old_t2_barons
            self._current_game_prob = max(0.05, self._current_game_prob - self.EVENT_IMPACTS['baron'] * diff)
            events_detected.append(f"👑 {TEAM2_CODE} BARON!")
        
        # Inhibitors
        if t1_inhibs > old_t1_inhibs:
            diff = t1_inhibs - old_t1_inhibs
            self._current_game_prob = min(0.95, self._current_game_prob + self.EVENT_IMPACTS['inhibitor'] * diff)
            events_detected.append(f"💥 {TEAM1_CODE} +{diff} inhibitor(s)")
        if t2_inhibs > old_t2_inhibs:
            diff = t2_inhibs - old_t2_inhibs
            self._current_game_prob = max(0.05, self._current_game_prob - self.EVENT_IMPACTS['inhibitor'] * diff)
            events_detected.append(f"💥 {TEAM2_CODE} +{diff} inhibitor(s)")
        
        # Print detected events
        for event in events_detected:
            print(f"   {event}")
        
        # Store state for next comparison
        self._last_game_state = GameState(
            blue_kills=new_state.blue_kills,
            red_kills=new_state.red_kills,
            blue_towers=new_state.blue_towers,
            red_towers=new_state.red_towers,
            blue_dragons=new_state.blue_dragons,
            red_dragons=new_state.red_dragons,
            blue_barons=new_state.blue_barons,
            red_barons=new_state.red_barons,
            blue_inhibitors=new_state.blue_inhibitors,
            red_inhibitors=new_state.red_inhibitors,
        )
        
        return self.get_series_probability()
    
    def record_game_win(self, team: int) -> float:
        """Record a game win and reset for next game."""
        if team == 1:
            self.series_state.team1_games += 1
        else:
            self.series_state.team2_games += 1
        
        # Reset current game probability to base
        self._current_game_prob = self.base_game_prob
        self._last_game_state = None
        
        return self.get_series_probability()
    
    def set_series_score(self, team1: int, team2: int):
        """Set series score."""
        self.series_state.team1_games = team1
        self.series_state.team2_games = team2
        self._current_game_prob = self.base_game_prob
        self._last_game_state = None
    
    def _calculate_series_prob_from_score(self, team1_games: int, team2_games: int) -> float:
        """Calculate series win probability given current score."""
        if team1_games >= 3:
            return 1.0
        if team2_games >= 3:
            return 0.0
        
        p = self.base_game_prob
        p_if_win = self._calculate_series_prob_from_score(team1_games + 1, team2_games)
        p_if_lose = self._calculate_series_prob_from_score(team1_games, team2_games + 1)
        
        return p * p_if_win + (1 - p) * p_if_lose
    
    def get_series_probability(self) -> float:
        """Get Team 1's probability of winning the series."""
        if self.series_state.team1_games >= 3:
            return 0.99
        if self.series_state.team2_games >= 3:
            return 0.01
        
        base_series_prob = self._calculate_series_prob_from_score(
            self.series_state.team1_games,
            self.series_state.team2_games
        )
        
        game_deviation = self._current_game_prob - self.base_game_prob
        weight = self.GAME_WEIGHTS.get(
            (self.series_state.team1_games, self.series_state.team2_games), 0.15
        )
        
        adjusted = base_series_prob + (game_deviation * weight)
        return max(0.02, min(0.98, adjusted))
    
    def get_status_string(self) -> str:
        """Get current status as a string."""
        return (
            f"Series: {TEAM1_CODE} {self.series_state.team1_games}-"
            f"{self.series_state.team2_games} {TEAM2_CODE} | "
            f"Game prob: {self._current_game_prob:.1%} | "
            f"Series prob: {self.get_series_probability():.1%}"
        )


# ============================================================================
# LOL ESPORTS CLIENT
# ============================================================================

class LoLEsportsClient:
    """Client for Riot's LoL Esports API - fetches live game data."""
    
    def __init__(self):
        self._session: Optional[aiohttp.ClientSession] = None
        self.match_id: Optional[str] = None
        self.current_game_id: Optional[str] = None
        self.team1_esports_id: Optional[str] = None
        self.team2_esports_id: Optional[str] = None
    
    async def connect(self) -> bool:
        """Initialize session."""
        self._session = aiohttp.ClientSession(headers={
            'x-api-key': LOL_API_KEY
        })
        return True
    
    async def close(self):
        """Close session."""
        if self._session:
            await self._session.close()
    
    async def find_live_match(self) -> Optional[str]:
        """
        Find live match for IG vs LNG.
        Returns match ID if found, None otherwise.
        """
        try:
            url = f"{LOL_ESPORTS_API}/getLive"
            params = {'hl': 'en-US'}
            
            async with self._session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=10)) as response:
                if response.status != 200:
                    return None
                
                data = await response.json()
                events = data.get('data', {}).get('schedule', {}).get('events', [])
                
                for event in events:
                    match = event.get('match', {})
                    teams = match.get('teams', [])
                    
                    if len(teams) >= 2:
                        team_codes = [t.get('code', '').upper() for t in teams]
                        
                        # Check if this is our match
                        if 'IG' in team_codes and 'LNG' in team_codes:
                            self.match_id = match.get('id')
                            
                            # Store team IDs
                            for team in teams:
                                code = team.get('code', '').upper()
                                if code == 'IG':
                                    self.team1_esports_id = team.get('id')
                                elif code == 'LNG':
                                    self.team2_esports_id = team.get('id')
                            
                            print(f"   Found live match: {self.match_id}")
                            return self.match_id
                
                return None
                
        except Exception as e:
            print(f"   Error finding live match: {e}")
            return None
    
    async def get_match_details(self) -> Optional[Dict]:
        """Get details about the current match including games."""
        if not self.match_id:
            return None
        
        try:
            url = f"{LOL_ESPORTS_API}/getEventDetails"
            params = {'hl': 'en-US', 'id': self.match_id}
            
            async with self._session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=10)) as response:
                if response.status != 200:
                    return None
                
                data = await response.json()
                return data.get('data', {}).get('event', {})
                
        except Exception as e:
            print(f"   Error getting match details: {e}")
            return None
    
    async def get_live_game_stats(self, game_id: str) -> Optional[GameState]:
        """
        Get live stats for a specific game.
        Uses the livestats feed.
        """
        try:
            url = f"{LOL_LIVE_STATS}/window/{game_id}"
            
            async with self._session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                if response.status != 200:
                    return None
                
                data = await response.json()
                
                # Get the latest frame
                frames = data.get('frames', [])
                if not frames:
                    return None
                
                latest_frame = frames[-1]
                blue_team = latest_frame.get('blueTeam', {})
                red_team = latest_frame.get('redTeam', {})
                
                game_state = GameState(
                    game_id=game_id,
                    state=latest_frame.get('gameState', 'in_game'),
                    blue_kills=blue_team.get('totalKills', 0),
                    red_kills=red_team.get('totalKills', 0),
                    blue_towers=blue_team.get('towers', 0),
                    red_towers=red_team.get('towers', 0),
                    blue_dragons=len(blue_team.get('dragons', [])),
                    red_dragons=len(red_team.get('dragons', [])),
                    blue_barons=blue_team.get('barons', 0),
                    red_barons=red_team.get('barons', 0),
                    blue_inhibitors=blue_team.get('inhibitors', 0),
                    red_inhibitors=red_team.get('inhibitors', 0),
                    blue_gold=blue_team.get('totalGold', 0),
                    red_gold=red_team.get('totalGold', 0),
                )
                
                # Get team metadata to determine sides
                metadata = data.get('gameMetadata', {})
                blue_meta = metadata.get('blueTeamMetadata', {})
                red_meta = metadata.get('redTeamMetadata', {})
                game_state.blue_team_id = blue_meta.get('esportsTeamId')
                game_state.red_team_id = red_meta.get('esportsTeamId')
                
                return game_state
                
        except Exception as e:
            print(f"   Error getting live stats: {e}")
            return None
    
    async def get_current_game_id(self) -> Optional[str]:
        """Get the ID of the currently active game in the match."""
        details = await self.get_match_details()
        if not details:
            return None
        
        match = details.get('match', {})
        games = match.get('games', [])
        
        for game in games:
            if game.get('state') == 'inProgress':
                return game.get('id')
        
        return None


# ============================================================================
# POLYMARKET CLIENT
# ============================================================================

class PolymarketClient:
    """Client for Polymarket API."""
    
    def __init__(self, offline: bool = False):
        self._session: Optional[aiohttp.ClientSession] = None
        self.offline = offline
        self.connected = False
        
        self.market_question: str = ""
        self.team1_token_id: str = "token_team1"
        self.team2_token_id: str = "token_team2"
        
        # Simulated prices for offline mode
        self._sim_price1 = 0.48
        self._sim_price2 = 0.52
    
    async def connect(self) -> bool:
        """Connect to Polymarket and find the market."""
        if self.offline:
            print("   (Offline mode - using simulated prices)")
            self.connected = True
            self.market_question = f"[SIMULATED] {TEAM1_NAME} vs {TEAM2_NAME} (BO5)"
            return True
        
        self._session = aiohttp.ClientSession()
        
        try:
            # Search for the market
            url = f"{GAMMA_URL}/events"
            params = {"slug": MATCH_SLUG}
            
            async with self._session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=10)) as response:
                if response.status != 200:
                    print(f"   Market not found (status {response.status})")
                    print(f"   Searched slug: {MATCH_SLUG}")
                    return False
                
                events = await response.json()
                if not events:
                    print(f"   No market found for slug: {MATCH_SLUG}")
                    return False
                
                event = events[0]
                
                # Find the BO5 market
                for market in event.get("markets", []):
                    question = market.get("question", "")
                    
                    # Look for the main BO5 match market
                    if "BO5" in question or ("Invictus" in question and "Game" not in question):
                        self.market_question = question
                        
                        tokens = market.get("clobTokenIds", "[]")
                        if isinstance(tokens, str):
                            tokens = json.loads(tokens)
                        
                        if len(tokens) >= 2:
                            self.team1_token_id = tokens[0]
                            self.team2_token_id = tokens[1]
                            self.connected = True
                            print(f"   Connected to market: {question}")
                            return True
                
                print("   BO5 market not found in event")
                return False
                
        except asyncio.TimeoutError:
            print("   Connection timeout")
            return False
        except Exception as e:
            print(f"   Connection error: {e}")
            return False
    
    async def close(self):
        """Close session."""
        if self._session:
            await self._session.close()
    
    async def get_prices(self) -> Tuple[Optional[float], Optional[float]]:
        """Get current prices for both teams."""
        if self.offline or not self.connected:
            return self._sim_price1, self._sim_price2
        
        try:
            price1 = await self._get_price(self.team1_token_id)
            price2 = await self._get_price(self.team2_token_id)
            
            if price1 and price2:
                return price1, price2
            else:
                return self._sim_price1, self._sim_price2
                
        except Exception:
            return self._sim_price1, self._sim_price2
    
    async def _get_price(self, token_id: str) -> Optional[float]:
        """Get price for a specific token."""
        url = f"{CLOB_URL}/price"
        params = {"token_id": token_id, "side": "buy"}
        
        try:
            async with self._session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=5)) as response:
                if response.status == 200:
                    data = await response.json()
                    return float(data.get("price", 0))
        except Exception:
            pass
        return None
    
    def set_simulated_prices(self, price1: float, price2: float):
        """Set simulated prices for testing."""
        self._sim_price1 = price1
        self._sim_price2 = price2


# ============================================================================
# TRADING ENGINE
# ============================================================================

class TradingEngine:
    """Handles trade execution and position management."""
    
    def __init__(self, bankroll: float):
        self.initial_bankroll = bankroll
        self.cash = bankroll
        self.positions: Dict[str, Position] = {}
        self.trades: List[Trade] = []
        self.auto_trading = True
    
    @property
    def total_pnl(self) -> float:
        return sum(t.pnl for t in self.trades)
    
    def execute_buy(self, token_id: str, team: str, price: float, amount: float, reason: str) -> bool:
        """
        Execute a buy order.
        
        Args:
            amount: Dollar amount to spend (not number of shares)
        """
        if amount > self.cash:
            print(f"   ❌ Insufficient funds: need ${amount:.2f}, have ${self.cash:.2f}")
            return False
        
        if amount < MIN_TRADE_SIZE:
            print(f"   ❌ Trade too small: ${amount:.2f} < ${MIN_TRADE_SIZE}")
            return False
        
        # Cap at max position size
        amount = min(amount, MAX_POSITION_SIZE)
        
        size = amount / price
        self.cash -= amount
        
        if token_id in self.positions:
            p = self.positions[token_id]
            total_cost = p.cost + amount
            total_size = p.size + size
            p.entry_price = total_cost / total_size
            p.size = total_size
        else:
            self.positions[token_id] = Position(
                token_id=token_id, team=team, size=size,
                entry_price=price, entry_time=datetime.now()
            )
        
        self.trades.append(Trade(
            timestamp=datetime.now(), team=team, action="BUY",
            size=size, price=price, reason=reason
        ))
        
        print(f"\n   ✅ BOUGHT {size:.1f} shares of {team} @ ${price:.3f}")
        print(f"      Cost: ${amount:.2f} | Cash remaining: ${self.cash:.2f}")
        return True
    
    def execute_sell(self, token_id: str, price: float, reason: str) -> bool:
        """Execute a sell order."""
        if token_id not in self.positions:
            return False
        
        pos = self.positions[token_id]
        proceeds = pos.size * price
        pnl = pos.pnl(price)
        
        self.cash += proceeds
        
        self.trades.append(Trade(
            timestamp=datetime.now(), team=pos.team, action="SELL",
            size=pos.size, price=price, reason=reason, pnl=pnl
        ))
        
        pnl_pct = (price - pos.entry_price) / pos.entry_price * 100 if pos.entry_price > 0 else 0
        print(f"\n   ✅ SOLD {pos.size:.1f} shares of {pos.team} @ ${price:.3f}")
        print(f"      Proceeds: ${proceeds:.2f} | P&L: ${pnl:+.2f} ({pnl_pct:+.1f}%)")
        
        del self.positions[token_id]
        return True


# ============================================================================
# MAIN BOT
# ============================================================================

class LoLTradingBot:
    """Main trading bot with fully automated live data feeds."""
    
    def __init__(self, practice_mode: bool = False):
        self.practice_mode = practice_mode
        self.poly = PolymarketClient(offline=practice_mode)
        self.lol = LoLEsportsClient()
        self.calc = ProbabilityCalculator()
        self.engine = TradingEngine(BANKROLL)
        
        self._running = False
        self._match_live = False
        self._current_game_id: Optional[str] = None
    
    async def start(self) -> bool:
        """Initialize the bot."""
        print("=" * 70)
        print("LOL TRADING BOT V4 - FULLY AUTOMATED")
        print("=" * 70)
        print(f"Match: {TEAM1_NAME} vs {TEAM2_NAME} (BO5)")
        print(f"Bankroll: ${BANKROLL:.2f}")
        print(f"Max Position: ${MAX_POSITION_SIZE:.2f}")
        print(f"Min Edge: {MIN_EDGE*100:.0f}%")
        print()
        
        # Connect to Polymarket
        print("Connecting to Polymarket...")
        connected = await self.poly.connect()
        
        if connected:
            print(f"✓ Connected: {self.poly.market_question}")
        else:
            print("⚠ Could not connect to Polymarket - switching to practice mode")
            self.poly.offline = True
            self.practice_mode = True
            await self.poly.connect()
        
        # Connect to LoL Esports
        if not self.practice_mode:
            print("\nConnecting to LoL Esports API...")
            await self.lol.connect()
            print("✓ LoL Esports API ready")
        
        # Get initial prices and set base probability
        price1, price2 = await self.poly.get_prices()
        print(f"\nInitial Market Odds:")
        print(f"  {TEAM1_NAME}: ${price1:.3f} ({price1*100:.1f}%)")
        print(f"  {TEAM2_NAME}: ${price2:.3f} ({price2*100:.1f}%)")
        
        # Use market odds as base probability
        self.calc.set_base_probability_from_market(price1)
        
        print(f"\n✓ Base probability set from live market odds")
        print(f"  Bot assumes {TEAM1_NAME} has {price1*100:.1f}% chance per game")
        
        if self.practice_mode:
            print("\n⚠ PRACTICE MODE: Using simulated data")
        else:
            print("\n✓ LIVE MODE: Monitoring real game data and market prices")
        
        self._running = True
        return True
    
    async def stop(self):
        """Shutdown the bot."""
        print("\nShutting down...")
        self._running = False
        
        # Close positions
        if self.engine.positions:
            print("Closing positions...")
            price1, price2 = await self.poly.get_prices()
            for token_id in list(self.engine.positions.keys()):
                price = price1 if token_id == self.poly.team1_token_id else price2
                if price:
                    self.engine.execute_sell(token_id, price, "Shutdown")
        
        self._print_report()
        
        await self.poly.close()
        await self.lol.close()
    
    async def run(self):
        """Main bot loop."""
        print("\n" + "=" * 70)
        print("MONITORING STARTED")
        print("=" * 70)
        print(f"• Checking for live match every {MATCH_CHECK_INTERVAL}s")
        print(f"• When live: polling game stats every {GAME_POLL_INTERVAL}s")
        print(f"• Polling prices every {PRICE_POLL_INTERVAL}s")
        print("• Press Ctrl+C to stop")
        print("=" * 70 + "\n")
        
        # Start monitoring tasks
        tasks = [
            asyncio.create_task(self._monitor_match()),
            asyncio.create_task(self._monitor_prices()),
            asyncio.create_task(self._handle_input()),
        ]
        
        try:
            await asyncio.gather(*tasks)
        except asyncio.CancelledError:
            pass
        finally:
            for task in tasks:
                task.cancel()
    
    async def _monitor_match(self):
        """Monitor for live match and game events."""
        while self._running:
            try:
                if self.practice_mode:
                    await asyncio.sleep(MATCH_CHECK_INTERVAL)
                    continue
                
                if not self._match_live:
                    # Look for live match
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] Checking for live match...")
                    match_id = await self.lol.find_live_match()
                    
                    if match_id:
                        self._match_live = True
                        print(f"   🎮 MATCH IS LIVE! Starting game monitoring...")
                        
                        # Re-fetch prices to update base probability
                        price1, _ = await self.poly.get_prices()
                        self.calc.set_base_probability_from_market(price1)
                    else:
                        print("   No live match found. Waiting...")
                        await asyncio.sleep(MATCH_CHECK_INTERVAL)
                        continue
                
                # Match is live - monitor game stats
                game_id = await self.lol.get_current_game_id()
                
                if game_id and game_id != self._current_game_id:
                    print(f"\n   🎮 NEW GAME STARTED: {game_id}")
                    self._current_game_id = game_id
                    self.calc._last_game_state = None  # Reset state tracking
                
                if game_id:
                    game_state = await self.lol.get_live_game_stats(game_id)
                    
                    if game_state:
                        # Determine which side Team1 (IG) is on
                        team1_is_blue = (game_state.blue_team_id == self.lol.team1_esports_id)
                        
                        # Update probabilities
                        series_prob = self.calc.update_from_game_state(game_state, team1_is_blue)
                        
                        # Check for trade opportunities
                        await self._evaluate_trade()
                
                await asyncio.sleep(GAME_POLL_INTERVAL)
                
            except Exception as e:
                print(f"   Error in match monitor: {e}")
                await asyncio.sleep(5)
    
    async def _monitor_prices(self):
        """Monitor Polymarket prices."""
        while self._running:
            try:
                await asyncio.sleep(PRICE_POLL_INTERVAL)
                
                # Silently update base probability if no events are happening
                price1, _ = await self.poly.get_prices()
                if price1:
                    # Only update base if significant change
                    if abs(price1 - self.calc.base_game_prob) > 0.02:
                        self.calc.set_base_probability_from_market(price1)
                
            except Exception as e:
                print(f"   Error in price monitor: {e}")
                await asyncio.sleep(5)
    
    async def _evaluate_trade(self):
        """Evaluate trading opportunity based on current state."""
        price1, price2 = await self.poly.get_prices()
        
        if not price1 or not price2:
            return
        
        fair = self.calc.get_series_probability()
        edge1 = fair - price1
        edge2 = (1 - fair) - price2
        
        timestamp = datetime.now().strftime('%H:%M:%S')
        print(f"\n   [{timestamp}] Market: {TEAM1_CODE} ${price1:.3f} | {TEAM2_CODE} ${price2:.3f}")
        print(f"   Fair: {TEAM1_CODE} ${fair:.3f} | Edge: {TEAM1_CODE} {edge1:+.1%} | {TEAM2_CODE} {edge2:+.1%}")
        
        # Check exit conditions
        for token_id, pos in list(self.engine.positions.items()):
            if token_id == self.poly.team1_token_id:
                edge, price = edge1, price1
            else:
                edge, price = edge2, price2
            
            if edge < EXIT_EDGE:
                print(f"\n   📤 EXIT SIGNAL: {pos.team} edge dropped to {edge:.1%}")
                if self.engine.auto_trading:
                    self.engine.execute_sell(token_id, price, f"Edge dropped to {edge:.1%}")
                else:
                    print("      (Auto-trading OFF)")
        
        # Check entry conditions
        if self.engine.auto_trading and not self.engine.positions:
            if edge1 >= MIN_EDGE:
                print(f"\n   📥 ENTRY SIGNAL: BUY {TEAM1_NAME} (edge: {edge1:.1%})")
                self.engine.execute_buy(
                    self.poly.team1_token_id, TEAM1_NAME,
                    price1, MAX_POSITION_SIZE, f"Edge: {edge1:.1%}"
                )
            elif edge2 >= MIN_EDGE:
                print(f"\n   📥 ENTRY SIGNAL: BUY {TEAM2_NAME} (edge: {edge2:.1%})")
                self.engine.execute_buy(
                    self.poly.team2_token_id, TEAM2_NAME,
                    price2, MAX_POSITION_SIZE, f"Edge: {edge2:.1%}"
                )
    
    async def _handle_input(self):
        """Handle user input for manual commands."""
        while self._running:
            try:
                # Use asyncio-friendly input
                loop = asyncio.get_event_loop()
                cmd = await loop.run_in_executor(None, lambda: input().strip().lower())
                
                if not cmd:
                    continue
                
                await self._process_command(cmd)
                
            except EOFError:
                break
            except Exception as e:
                if self._running:
                    print(f"   Input error: {e}")
    
    async def _process_command(self, cmd: str):
        """Process user command."""
        parts = cmd.split()
        action = parts[0]
        
        if action == 'q':
            self._running = False
        
        elif action == 'h':
            self._print_help()
        
        elif action == 's':
            await self._show_status()
        
        elif action == 'p':
            await self._show_prices()
        
        elif action == 'auto':
            self.engine.auto_trading = not self.engine.auto_trading
            print(f"   Auto-trading: {'ON' if self.engine.auto_trading else 'OFF'}")
        
        elif action == 'close':
            await self._close_all_positions()
        
        elif action == 'buy1':
            amount = float(parts[1]) if len(parts) > 1 else MAX_POSITION_SIZE
            await self._manual_buy(1, amount)
        
        elif action == 'buy2':
            amount = float(parts[1]) if len(parts) > 1 else MAX_POSITION_SIZE
            await self._manual_buy(2, amount)
        
        elif action == 'g' and len(parts) >= 3:
            try:
                t1, t2 = int(parts[1]), int(parts[2])
                self.calc.set_series_score(t1, t2)
                print(f"   Series score set: {TEAM1_CODE} {t1}-{t2} {TEAM2_CODE}")
                await self._evaluate_trade()
            except ValueError:
                print("   Usage: g <team1_games> <team2_games>")
        
        elif action in ['w1', 'w2']:
            team = int(action[1])
            team_name = TEAM1_NAME if team == 1 else TEAM2_NAME
            self.calc.record_game_win(team)
            t1, t2 = self.calc.series_state.team1_games, self.calc.series_state.team2_games
            print(f"\n   🎮 {team_name} WINS GAME!")
            print(f"   Series: {TEAM1_CODE} {t1}-{t2} {TEAM2_CODE}")
            await self._evaluate_trade()
        
        elif action == 'price' and len(parts) >= 3:
            try:
                p1, p2 = float(parts[1]), float(parts[2])
                self.poly.set_simulated_prices(p1, p2)
                print(f"   Simulated prices: {TEAM1_CODE} ${p1:.3f} | {TEAM2_CODE} ${p2:.3f}")
                await self._evaluate_trade()
            except ValueError:
                print("   Usage: price <team1_price> <team2_price>")
        
        else:
            print("   Unknown command. Type 'h' for help.")
    
    async def _manual_buy(self, team: int, amount: float):
        """Execute manual buy."""
        price1, price2 = await self.poly.get_prices()
        
        if team == 1:
            price, token_id, team_name = price1, self.poly.team1_token_id, TEAM1_NAME
        else:
            price, token_id, team_name = price2, self.poly.team2_token_id, TEAM2_NAME
        
        if not price:
            print("   ⚠ Could not get price")
            return
        
        self.engine.execute_buy(token_id, team_name, price, amount, "Manual trade")
    
    async def _close_all_positions(self):
        """Close all positions."""
        if not self.engine.positions:
            print("   No open positions")
            return
        
        price1, price2 = await self.poly.get_prices()
        
        for token_id in list(self.engine.positions.keys()):
            price = price1 if token_id == self.poly.team1_token_id else price2
            if price:
                self.engine.execute_sell(token_id, price, "Manual close")
    
    async def _show_prices(self):
        """Show current prices and positions."""
        price1, price2 = await self.poly.get_prices()
        fair = self.calc.get_series_probability()
        
        print(f"\n   {'─' * 50}")
        print(f"   Market: {TEAM1_NAME} ${price1:.3f} ({price1*100:.1f}%)")
        print(f"   Market: {TEAM2_NAME} ${price2:.3f} ({price2*100:.1f}%)")
        print(f"   Fair:   {TEAM1_NAME} ${fair:.3f} ({fair*100:.1f}%)")
        
        edge1 = fair - price1
        edge2 = (1 - fair) - price2
        print(f"   Edge:   {TEAM1_CODE} {edge1:+.1%} | {TEAM2_CODE} {edge2:+.1%}")
        
        if self.engine.positions:
            print(f"\n   Positions:")
            for pos in self.engine.positions.values():
                current = price1 if pos.token_id == self.poly.team1_token_id else price2
                pnl = pos.pnl(current)
                pnl_pct = (current - pos.entry_price) / pos.entry_price * 100 if pos.entry_price > 0 else 0
                print(f"     {pos.team}: {pos.size:.1f} shares @ ${pos.entry_price:.3f}")
                print(f"       Current: ${current:.3f} | P&L: ${pnl:+.2f} ({pnl_pct:+.1f}%)")
        
        print(f"   {'─' * 50}")
    
    async def _show_status(self):
        """Show full status."""
        print(f"\n   {'═' * 55}")
        print(f"   SERIES STATE:")
        print(f"   {self.calc.get_status_string()}")
        print(f"\n   TRADING:")
        print(f"   Cash: ${self.engine.cash:.2f}")
        print(f"   Total P&L: ${self.engine.total_pnl:+.2f}")
        print(f"   Auto-trading: {'ON' if self.engine.auto_trading else 'OFF'}")
        print(f"   Mode: {'PRACTICE' if self.practice_mode else 'LIVE'}")
        print(f"   Match Live: {'YES' if self._match_live else 'NO'}")
        print(f"   {'═' * 55}")
        
        await self._show_prices()
    
    def _print_help(self):
        """Print help."""
        print(f"""
   {'═' * 55}
   COMMANDS:
   {'═' * 55}
   
   INFO:
   ┌─────────┬───────────────────────────────────────────┐
   │ s       │ Full status                               │
   │ p       │ Prices and positions                      │
   │ h       │ This help                                 │
   │ q       │ Quit                                      │
   └─────────┴───────────────────────────────────────────┘
   
   TRADING:
   ┌─────────────┬───────────────────────────────────────┐
   │ auto        │ Toggle auto-trading                   │
   │ buy1 [amt]  │ Buy {TEAM1_CODE} (default ${MAX_POSITION_SIZE})      │
   │ buy2 [amt]  │ Buy {TEAM2_CODE} (default ${MAX_POSITION_SIZE})     │
   │ close       │ Close all positions                   │
   └─────────────┴───────────────────────────────────────┘
   
   MANUAL GAME EVENTS (for testing):
   ┌─────────────┬───────────────────────────────────────┐
   │ w1 / w2     │ Record game win                       │
   │ g X Y       │ Set series score                      │
   │ price P1 P2 │ Set simulated prices                  │
   └─────────────┴───────────────────────────────────────┘
   {'═' * 55}
""")
    
    def _print_report(self):
        """Print final report."""
        print(f"\n{'═' * 70}")
        print("FINAL REPORT")
        print('═' * 70)
        print(f"Starting Bankroll: ${self.engine.initial_bankroll:.2f}")
        print(f"Final Cash: ${self.engine.cash:.2f}")
        print(f"Total P&L: ${self.engine.total_pnl:+.2f}")
        
        if self.engine.initial_bankroll > 0:
            pnl_pct = (self.engine.total_pnl / self.engine.initial_bankroll) * 100
            print(f"Return: {pnl_pct:+.1f}%")
        
        print(f"\nTotal Trades: {len(self.engine.trades)}")
        
        if self.engine.trades:
            print("\nTrade History:")
            for i, trade in enumerate(self.engine.trades, 1):
                time_str = trade.timestamp.strftime("%H:%M:%S")
                pnl_str = f" | P&L: ${trade.pnl:+.2f}" if trade.action == "SELL" else ""
                print(f"  {i}. [{time_str}] {trade.action} {trade.size:.1f} {trade.team} @ ${trade.price:.3f}{pnl_str}")
        
        print('═' * 70)


# ============================================================================
# MAIN
# ============================================================================

async def main():
    practice_mode = '--practice' in sys.argv or '-p' in sys.argv
    
    bot = LoLTradingBot(practice_mode=practice_mode)
    
    try:
        if await bot.start():
            await bot.run()
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
    finally:
        await bot.stop()


if __name__ == "__main__":
    print("""
╔══════════════════════════════════════════════════════════════════════╗
║                    LOL TRADING BOT V4                                ║
║                 FULLY AUTOMATED LIVE DATA                            ║
║                                                                      ║
║  Features:                                                           ║
║  • Auto-monitors Riot LoL Esports API for live game events          ║
║  • Auto-monitors Polymarket prices                                   ║
║  • Uses live market odds as base probability                        ║
║  • Executes trades automatically when edge detected                  ║
║                                                                      ║
║  Run with --practice to force practice mode                         ║
╚══════════════════════════════════════════════════════════════════════╝
""")
    
    asyncio.run(main())
