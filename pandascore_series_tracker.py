#!/usr/bin/env python3
"""
PandaScore Series Tracker - Works with FREE tier!

Strategy: React to GAME WINS faster than the market.
When a game ends, buy the winner before odds adjust.

This works because:
1. PandaScore updates game winners within seconds
2. Polymarket odds take 30-60 seconds to fully adjust
3. You can capture 2-5% edge per game win
"""

import os
import time
import requests
from datetime import datetime
from dotenv import load_dotenv
from dataclasses import dataclass
from typing import Optional, List, Dict

load_dotenv()

API_KEY = os.getenv("PANDASCORE_API_KEY")
HEADERS = {"Authorization": f"Bearer {API_KEY}"}
POLL_INTERVAL = 5  # Check every 5 seconds


@dataclass
class GameResult:
    game_number: int
    winner_id: int
    winner_acronym: str
    status: str
    length_seconds: Optional[int] = None


@dataclass
class MatchState:
    match_id: int
    team1_id: int
    team1_acronym: str
    team1_name: str
    team2_id: int
    team2_acronym: str
    team2_name: str
    team1_score: int
    team2_score: int
    best_of: int
    status: str
    current_game: int
    games: List[GameResult]
    
    @property
    def series_winner(self) -> Optional[str]:
        """Check if series is won."""
        wins_needed = (self.best_of // 2) + 1
        if self.team1_score >= wins_needed:
            return self.team1_acronym
        if self.team2_score >= wins_needed:
            return self.team2_acronym
        return None
    
    def get_winner_acronym(self, team_id: int) -> str:
        if team_id == self.team1_id:
            return self.team1_acronym
        return self.team2_acronym


class PandaScoreTracker:
    """Track live matches using PandaScore free tier."""
    
    def __init__(self):
        self.last_state: Optional[MatchState] = None
        self.callbacks: List[callable] = []
    
    def on_game_end(self, callback):
        """Register callback for when a game ends."""
        self.callbacks.append(callback)
    
    def get_running_matches(self) -> List[Dict]:
        """Get all running LoL matches."""
        url = "https://api.pandascore.co/lol/matches/running"
        resp = requests.get(url, headers=HEADERS, timeout=10)
        if resp.status_code == 200:
            return resp.json()
        return []
    
    def parse_match(self, data: Dict) -> MatchState:
        """Parse match data into MatchState."""
        opponents = data.get("opponents", [])
        t1 = opponents[0]["opponent"] if len(opponents) > 0 else {}
        t2 = opponents[1]["opponent"] if len(opponents) > 1 else {}
        
        results = {r["team_id"]: r["score"] for r in data.get("results", [])}
        
        games = []
        current_game = 1
        for g in data.get("games", []):
            winner_id = g.get("winner", {}).get("id")
            winner_acronym = ""
            if winner_id == t1.get("id"):
                winner_acronym = t1.get("acronym", "T1")
            elif winner_id == t2.get("id"):
                winner_acronym = t2.get("acronym", "T2")
            
            games.append(GameResult(
                game_number=g.get("position", 0),
                winner_id=winner_id or 0,
                winner_acronym=winner_acronym,
                status=g.get("status", ""),
                length_seconds=g.get("length")
            ))
            
            if g.get("status") == "running":
                current_game = g.get("position", 1)
        
        return MatchState(
            match_id=data.get("id", 0),
            team1_id=t1.get("id", 0),
            team1_acronym=t1.get("acronym", "T1"),
            team1_name=t1.get("name", "Team 1"),
            team2_id=t2.get("id", 0),
            team2_acronym=t2.get("acronym", "T2"),
            team2_name=t2.get("name", "Team 2"),
            team1_score=results.get(t1.get("id"), 0),
            team2_score=results.get(t2.get("id"), 0),
            best_of=data.get("number_of_games", 1),
            status=data.get("status", ""),
            current_game=current_game,
            games=games
        )
    
    def find_match(self, team1_code: str, team2_code: str) -> Optional[MatchState]:
        """Find a specific match by team codes."""
        matches = self.get_running_matches()
        team1_code = team1_code.upper()
        team2_code = team2_code.upper()
        
        for match_data in matches:
            state = self.parse_match(match_data)
            codes = {state.team1_acronym.upper(), state.team2_acronym.upper()}
            if team1_code in codes and team2_code in codes:
                return state
        return None
    
    def detect_changes(self, old: MatchState, new: MatchState) -> List[str]:
        """Detect what changed between states."""
        events = []
        
        # Check for score changes (game ended)
        if new.team1_score > old.team1_score:
            events.append(f"GAME_WIN:{new.team1_acronym}")
        if new.team2_score > old.team2_score:
            events.append(f"GAME_WIN:{new.team2_acronym}")
        
        # Check for series end
        if new.series_winner and not old.series_winner:
            events.append(f"SERIES_WIN:{new.series_winner}")
        
        # Check for new game starting
        if new.current_game > old.current_game:
            events.append(f"GAME_START:{new.current_game}")
        
        return events
    
    def track_match(self, team1: str, team2: str):
        """
        Track a match and print updates.
        This is the main loop for monitoring.
        """
        print(f"\n{'='*60}")
        print(f"TRACKING: {team1} vs {team2}")
        print(f"{'='*60}")
        print(f"Polling every {POLL_INTERVAL} seconds...")
        print("Press Ctrl+C to stop\n")
        
        while True:
            try:
                state = self.find_match(team1, team2)
                
                if not state:
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] Match not found or ended")
                    time.sleep(POLL_INTERVAL)
                    continue
                
                # First poll - just store state
                if self.last_state is None:
                    self.last_state = state
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] Connected!")
                    print(f"   {state.team1_acronym} {state.team1_score}-{state.team2_score} {state.team2_acronym}")
                    print(f"   Game {state.current_game} in progress (BO{state.best_of})")
                    time.sleep(POLL_INTERVAL)
                    continue
                
                # Detect changes
                events = self.detect_changes(self.last_state, state)
                
                if events:
                    timestamp = datetime.now().strftime('%H:%M:%S')
                    
                    for event in events:
                        event_type, value = event.split(":")
                        
                        if event_type == "GAME_WIN":
                            print(f"\n{'🎮'*20}")
                            print(f"[{timestamp}] 🏆 {value} WINS GAME {state.current_game - 1}!")
                            print(f"   Series: {state.team1_acronym} {state.team1_score}-{state.team2_score} {state.team2_acronym}")
                            print(f"{'🎮'*20}")
                            
                            # TRADING SIGNAL!
                            print(f"\n   ⚡ TRADING SIGNAL: BUY {value}")
                            print(f"   ⚡ Probability shift expected!")
                            
                            # Trigger callbacks
                            for cb in self.callbacks:
                                cb(event_type, value, state)
                        
                        elif event_type == "SERIES_WIN":
                            print(f"\n{'🏆'*20}")
                            print(f"[{timestamp}] 🏆🏆🏆 {value} WINS THE SERIES!")
                            print(f"   Final: {state.team1_acronym} {state.team1_score}-{state.team2_score} {state.team2_acronym}")
                            print(f"{'🏆'*20}")
                            return  # Match is over
                        
                        elif event_type == "GAME_START":
                            print(f"\n[{timestamp}] 🎮 Game {value} starting!")
                
                self.last_state = state
                time.sleep(POLL_INTERVAL)
                
            except KeyboardInterrupt:
                print("\n\nStopped tracking.")
                break
            except Exception as e:
                print(f"Error: {e}")
                time.sleep(POLL_INTERVAL)


def main():
    """Demo: Track IG vs LNG match."""
    tracker = PandaScoreTracker()
    
    # Example callback for trading
    def on_game_result(event_type, winner, state):
        if event_type == "GAME_WIN":
            print(f"\n   [TRADE BOT] Would execute: BUY {winner}")
            print(f"   [TRADE BOT] Current odds should favor {winner} more now")
    
    tracker.on_game_end(on_game_result)
    
    # Start tracking
    tracker.track_match("IG", "LNG")


if __name__ == "__main__":
    main()
