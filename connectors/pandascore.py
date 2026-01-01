"""
PandaScore API Connector - Live esports data from professional matches.

PandaScore provides data for:
- League of Legends (LCS, LEC, LCK, Worlds, etc.)
- Dota 2 (The International, DPC, etc.)
- CS:GO, Valorant, and more

Free tier: 1000 requests per hour
Documentation: https://developers.pandascore.co/

This connector:
1. Fetches live match data
2. Detects events (kills, towers, objectives)
3. Notifies callbacks when events happen
"""

import asyncio
import aiohttp
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any

from config.settings import get_config
from core import Game, MatchStatus, Team, GameState, GameEvent
from .base import BaseConnector

logger = logging.getLogger(__name__)

# Get global config
config = get_config()


class PandaScoreConnector(BaseConnector):
    """
    Connector for PandaScore API.
    
    Usage:
        connector = PandaScoreConnector()
        
        def handle_event(event):
            print(f"Event: {event}")
        
        connector.register_callback(handle_event)
        
        await connector.start()
        matches = await connector.get_live_matches("lol")
        await connector.poll_match(match_id, "lol")
        await connector.stop()
    """
    
    def __init__(self):
        """Initialize the PandaScore connector."""
        super().__init__()
        
        # API configuration
        self.api_key = config.data_feed.pandascore_api_key
        self.base_url = config.data_feed.pandascore_base_url
        
        # HTTP session (created on start)
        self.session: Optional[aiohttp.ClientSession] = None
        
        # Cache of match states (for detecting changes)
        self._match_cache: Dict[str, GameState] = {}
        
        # Rate limiting
        self._request_count = 0
        self._last_reset = datetime.now()
        self._max_requests_per_hour = 900  # Stay under 1000 limit
    
    async def start(self):
        """Start the connector and create HTTP session."""
        if not self.api_key:
            logger.warning(
                "No PandaScore API key configured! "
                "Set PANDASCORE_API_KEY in your .env file."
            )
            return
        
        # Create HTTP session with auth header
        self.session = aiohttp.ClientSession(
            headers={"Authorization": f"Bearer {self.api_key}"}
        )
        
        self._running = True
        self._request_count = 0
        self._last_reset = datetime.now()
        
        logger.info("PandaScore connector started")
    
    async def stop(self):
        """Stop the connector and close HTTP session."""
        self._running = False
        
        if self.session:
            await self.session.close()
            self.session = None
        
        self._match_cache.clear()
        
        logger.info("PandaScore connector stopped")
    
    # ================================================================
    # API REQUEST METHODS
    # ================================================================
    
    async def _make_request(
        self, 
        endpoint: str, 
        params: Optional[Dict] = None
    ) -> Optional[Any]:
        """
        Make an API request with rate limiting.
        
        Args:
            endpoint: API endpoint (e.g., "/lol/matches/running")
            params: Optional query parameters
            
        Returns:
            JSON response data, or None if request failed
        """
        if not self.session or not self._running:
            logger.warning("Connector not started")
            return None
        
        # Check rate limit
        await self._check_rate_limit()
        
        url = f"{self.base_url}{endpoint}"
        
        try:
            async with self.session.get(url, params=params) as response:
                self._request_count += 1
                
                if response.status == 200:
                    return await response.json()
                
                elif response.status == 429:
                    # Rate limited - wait and retry
                    logger.warning("Rate limited by PandaScore, waiting 60s...")
                    await asyncio.sleep(60)
                    self._request_count = 0
                    return None
                
                elif response.status == 401:
                    logger.error("Invalid API key!")
                    return None
                
                elif response.status == 404:
                    logger.debug(f"Not found: {endpoint}")
                    return None
                
                else:
                    error_text = await response.text()
                    logger.error(f"API error {response.status}: {error_text}")
                    return None
                    
        except asyncio.TimeoutError:
            logger.error(f"Request timeout: {endpoint}")
            return None
        except aiohttp.ClientError as e:
            logger.error(f"Request failed: {e}")
            return None
    
    async def _check_rate_limit(self):
        """Check and handle rate limiting."""
        # Reset counter every hour
        now = datetime.now()
        hours_elapsed = (now - self._last_reset).total_seconds() / 3600
        
        if hours_elapsed >= 1:
            self._request_count = 0
            self._last_reset = now
        
        # If approaching limit, slow down
        if self._request_count >= self._max_requests_per_hour:
            wait_time = 3600 - (now - self._last_reset).total_seconds()
            logger.warning(f"Rate limit reached, waiting {wait_time:.0f}s...")
            await asyncio.sleep(max(1, wait_time))
            self._request_count = 0
            self._last_reset = datetime.now()
    
    # ================================================================
    # PUBLIC API METHODS
    # ================================================================
    
    async def get_live_matches(self, game: str = "lol") -> List[GameState]:
        """
        Get all currently live matches for a game.
        
        Args:
            game: "lol" or "dota2"
            
        Returns:
            List of GameState objects for live matches
        """
        endpoint = f"/{game}/matches/running"
        data = await self._make_request(endpoint)
        
        if not data:
            return []
        
        matches = []
        for match_data in data:
            try:
                match = self._parse_match(match_data, game)
                if match:
                    matches.append(match)
            except Exception as e:
                logger.error(f"Error parsing match: {e}")
        
        logger.info(f"Found {len(matches)} live {game.upper()} matches")
        return matches
    
    async def get_match_details(
        self, 
        match_id: str, 
        game: str = "lol"
    ) -> Optional[GameState]:
        """
        Get detailed information for a specific match.
        
        Args:
            match_id: The match ID
            game: "lol" or "dota2"
            
        Returns:
            GameState object, or None if not found
        """
        endpoint = f"/{game}/matches/{match_id}"
        data = await self._make_request(endpoint)
        
        if not data:
            return None
        
        return self._parse_match(data, game)
    
    async def get_upcoming_matches(
        self, 
        game: str = "lol",
        hours_ahead: int = 24
    ) -> List[Dict]:
        """
        Get upcoming matches.
        
        Args:
            game: "lol" or "dota2"
            hours_ahead: How many hours ahead to look
            
        Returns:
            List of upcoming match data (raw dicts)
        """
        endpoint = f"/{game}/matches/upcoming"
        params = {"per_page": 50}
        
        data = await self._make_request(endpoint, params)
        
        if not data:
            return []
        
        logger.info(f"Found {len(data)} upcoming {game.upper()} matches")
        return data
    
    async def get_recent_matches(
        self,
        game: str = "lol",
        count: int = 20
    ) -> List[Dict]:
        """
        Get recently completed matches.
        
        Useful for backtesting and analysis.
        
        Args:
            game: "lol" or "dota2"
            count: Number of matches to retrieve
            
        Returns:
            List of match data (raw dicts)
        """
        endpoint = f"/{game}/matches/past"
        params = {"per_page": count}
        
        data = await self._make_request(endpoint, params)
        return data or []
    
    # ================================================================
    # MATCH POLLING
    # ================================================================
    
    async def poll_match(
        self, 
        match_id: str, 
        game: str = "lol",
        interval_ms: int = 500
    ):
        """
        Continuously poll a match for updates.
        
        This is the main method for live trading. It:
        1. Fetches match state periodically
        2. Detects changes and events
        3. Notifies callbacks
        
        Args:
            match_id: The match ID to poll
            game: "lol" or "dota2"
            interval_ms: How often to poll (milliseconds)
        """
        logger.info(f"Starting to poll match {match_id} every {interval_ms}ms")
        
        previous_state: Optional[GameState] = None
        
        while self._running:
            try:
                # Fetch current state
                current_state = await self.get_match_details(match_id, game)
                
                if current_state:
                    # Check for changes
                    if self._has_meaningful_change(previous_state, current_state):
                        # Detect specific events
                        events = self._detect_events(previous_state, current_state)
                        
                        # Notify callbacks of events
                        for event in events:
                            await self._notify_callbacks(event)
                        
                        # Notify callbacks of state update
                        await self._notify_callbacks(current_state)
                    
                    # Update cache
                    previous_state = current_state
                    self._match_cache[match_id] = current_state
                    
                    # Check if match ended
                    if current_state.status == MatchStatus.FINISHED:
                        logger.info(f"Match {match_id} has finished")
                        break
                
                # Wait before next poll
                await asyncio.sleep(interval_ms / 1000)
                
            except asyncio.CancelledError:
                logger.info(f"Polling cancelled for match {match_id}")
                break
            except Exception as e:
                logger.error(f"Error polling match {match_id}: {e}")
                await asyncio.sleep(1)  # Wait a bit on error
        
        logger.info(f"Stopped polling match {match_id}")
    
    # ================================================================
    # DATA PARSING
    # ================================================================
    
    def _parse_match(self, data: Dict, game_str: str) -> Optional[GameState]:
        """
        Parse API response into GameState object.
        
        Args:
            data: Raw API response data
            game_str: "lol" or "dota2"
            
        Returns:
            GameState object, or None if parsing fails
        """
        try:
            # Get teams
            opponents = data.get("opponents", [])
            if len(opponents) < 2:
                logger.debug("Match doesn't have 2 opponents yet")
                return None
            
            team1_data = opponents[0].get("opponent", {})
            team2_data = opponents[1].get("opponent", {})
            
            # Create Team objects
            team1 = Team(
                id=str(team1_data.get("id", "t1")),
                name=team1_data.get("name", "Team 1"),
                acronym=team1_data.get("acronym")
            )
            
            team2 = Team(
                id=str(team2_data.get("id", "t2")),
                name=team2_data.get("name", "Team 2"),
                acronym=team2_data.get("acronym")
            )
            
            # Parse live game stats if available
            games_data = data.get("games", [])
            game_time_seconds = 0
            
            if games_data:
                current_game = games_data[-1]  # Most recent game
                game_time_seconds = self._parse_game_stats(
                    current_game, team1, team2, game_str
                )
            
            # Determine match status
            status_str = data.get("status", "").lower()
            if status_str == "running":
                status = MatchStatus.LIVE
            elif status_str == "finished":
                status = MatchStatus.FINISHED
            else:
                status = MatchStatus.UPCOMING
            
            # Series score (for best-of matches)
            results = data.get("results", [])
            t1_score = results[0].get("score", 0) if len(results) > 0 else 0
            t2_score = results[1].get("score", 0) if len(results) > 1 else 0
            
            # Determine game enum
            game_enum = Game.LOL if game_str.lower() == "lol" else Game.DOTA2
            
            return GameState(
                match_id=str(data.get("id", "")),
                game=game_enum,
                status=status,
                team1=team1,
                team2=team2,
                game_time_seconds=game_time_seconds,
                team1_map_score=t1_score,
                team2_map_score=t2_score,
                best_of=data.get("number_of_games", 1),
                last_updated=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"Error parsing match data: {e}")
            return None
    
    def _parse_game_stats(
        self, 
        game_data: Dict, 
        team1: Team, 
        team2: Team, 
        game_str: str
    ) -> int:
        """
        Parse live game statistics into Team objects.
        
        Args:
            game_data: Game data from API
            team1: Team 1 object to update
            team2: Team 2 object to update
            game_str: "lol" or "dota2"
            
        Returns:
            Game time in seconds
        """
        game_time = 0
        teams_stats = game_data.get("teams", [])
        
        if len(teams_stats) < 2:
            return game_time
        
        t1_stats = teams_stats[0]
        t2_stats = teams_stats[1]
        
        # Get game time if available
        game_time = game_data.get("length", 0) or 0
        
        if game_str.lower() == "lol":
            # LoL specific stats
            team1.kills = t1_stats.get("kills", 0) or 0
            team1.gold = t1_stats.get("gold", 0) or 0
            team1.towers = t1_stats.get("tower_kills", 0) or 0
            team1.dragons = t1_stats.get("dragon_kills", 0) or 0
            team1.barons = t1_stats.get("baron_kills", 0) or 0
            
            team2.kills = t2_stats.get("kills", 0) or 0
            team2.gold = t2_stats.get("gold", 0) or 0
            team2.towers = t2_stats.get("tower_kills", 0) or 0
            team2.dragons = t2_stats.get("dragon_kills", 0) or 0
            team2.barons = t2_stats.get("baron_kills", 0) or 0
            
        else:
            # Dota 2 specific stats
            team1.kills = t1_stats.get("kills", 0) or 0
            team1.net_worth = t1_stats.get("net_worth", 0) or 0
            team1.towers = t1_stats.get("tower_kills", 0) or 0
            team1.roshan_kills = t1_stats.get("roshan_kills", 0) or 0
            
            team2.kills = t2_stats.get("kills", 0) or 0
            team2.net_worth = t2_stats.get("net_worth", 0) or 0
            team2.towers = t2_stats.get("tower_kills", 0) or 0
            team2.roshan_kills = t2_stats.get("roshan_kills", 0) or 0
        
        return game_time
    
    # ================================================================
    # EVENT DETECTION
    # ================================================================
    
    def _has_meaningful_change(
        self, 
        old: Optional[GameState], 
        new: GameState
    ) -> bool:
        """
        Check if game state has meaningfully changed.
        
        We don't want to notify callbacks for every tiny change,
        only when something important happens.
        """
        if old is None:
            return True
        
        # Check for changes in key stats
        return (
            old.team1.kills != new.team1.kills or
            old.team2.kills != new.team2.kills or
            old.team1.towers != new.team1.towers or
            old.team2.towers != new.team2.towers or
            old.team1.dragons != new.team1.dragons or
            old.team2.dragons != new.team2.dragons or
            old.team1.barons != new.team1.barons or
            old.team2.barons != new.team2.barons or
            old.team1.roshan_kills != new.team1.roshan_kills or
            old.team2.roshan_kills != new.team2.roshan_kills or
            abs(old.gold_diff - new.gold_diff) > 500  # Significant gold change
        )
    
    def _detect_events(
        self, 
        old: Optional[GameState], 
        new: GameState
    ) -> List[GameEvent]:
        """
        Detect specific events by comparing game states.
        
        Args:
            old: Previous game state
            new: Current game state
            
        Returns:
            List of detected GameEvent objects
        """
        events = []
        
        if old is None:
            return events
        
        import time
        now = time.time()
        
        # ---- Detect kills ----
        kills_t1 = new.team1.kills - old.team1.kills
        kills_t2 = new.team2.kills - old.team2.kills
        
        if kills_t1 > 0:
            events.append(GameEvent(
                timestamp=now,
                event_type="kill",
                team=1,
                context="default",
                details={"count": kills_t1}
            ))
            logger.debug(f"Detected {kills_t1} kill(s) for Team 1")
        
        if kills_t2 > 0:
            events.append(GameEvent(
                timestamp=now,
                event_type="kill",
                team=2,
                context="default",
                details={"count": kills_t2}
            ))
            logger.debug(f"Detected {kills_t2} kill(s) for Team 2")
        
        # ---- Detect towers ----
        towers_t1 = new.team1.towers - old.team1.towers
        towers_t2 = new.team2.towers - old.team2.towers
        
        if towers_t1 > 0:
            events.append(GameEvent(
                timestamp=now,
                event_type="tower",
                team=1,
                context="default",
                details={"count": towers_t1}
            ))
            logger.debug(f"Detected {towers_t1} tower(s) for Team 1")
        
        if towers_t2 > 0:
            events.append(GameEvent(
                timestamp=now,
                event_type="tower",
                team=2,
                context="default",
                details={"count": towers_t2}
            ))
            logger.debug(f"Detected {towers_t2} tower(s) for Team 2")
        
        # ---- Detect dragons (LoL) ----
        if new.game == Game.LOL:
            dragons_t1 = new.team1.dragons - old.team1.dragons
            dragons_t2 = new.team2.dragons - old.team2.dragons
            
            if dragons_t1 > 0:
                # Check for dragon soul
                context = "soul" if new.team1.dragons >= 4 else "default"
                events.append(GameEvent(
                    timestamp=now,
                    event_type="dragon",
                    team=1,
                    context=context
                ))
                logger.debug(f"Detected dragon for Team 1 (total: {new.team1.dragons})")
            
            if dragons_t2 > 0:
                context = "soul" if new.team2.dragons >= 4 else "default"
                events.append(GameEvent(
                    timestamp=now,
                    event_type="dragon",
                    team=2,
                    context=context
                ))
                logger.debug(f"Detected dragon for Team 2 (total: {new.team2.dragons})")
            
            # ---- Detect barons ----
            barons_t1 = new.team1.barons - old.team1.barons
            barons_t2 = new.team2.barons - old.team2.barons
            
            if barons_t1 > 0:
                events.append(GameEvent(
                    timestamp=now,
                    event_type="baron",
                    team=1,
                    context="secure"
                ))
                logger.debug("Detected Baron for Team 1")
            
            if barons_t2 > 0:
                events.append(GameEvent(
                    timestamp=now,
                    event_type="baron",
                    team=2,
                    context="secure"
                ))
                logger.debug("Detected Baron for Team 2")
        
        # ---- Detect Roshan (Dota 2) ----
        if new.game == Game.DOTA2:
            roshan_t1 = new.team1.roshan_kills - old.team1.roshan_kills
            roshan_t2 = new.team2.roshan_kills - old.team2.roshan_kills
            
            if roshan_t1 > 0:
                # Determine Roshan number
                total = new.team1.roshan_kills
                context = "first" if total == 1 else ("second" if total == 2 else "third")
                events.append(GameEvent(
                    timestamp=now,
                    event_type="roshan",
                    team=1,
                    context=context
                ))
                logger.debug(f"Detected Roshan #{total} for Team 1")
            
            if roshan_t2 > 0:
                total = new.team2.roshan_kills
                context = "first" if total == 1 else ("second" if total == 2 else "third")
                events.append(GameEvent(
                    timestamp=now,
                    event_type="roshan",
                    team=2,
                    context=context
                ))
                logger.debug(f"Detected Roshan #{total} for Team 2")
        
        return events