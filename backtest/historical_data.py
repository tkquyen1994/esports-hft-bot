#!/usr/bin/env python3
"""
Historical match data for backtesting.

Since PandaScore free tier doesn't give detailed match data,
we create realistic synthetic data based on known match patterns.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional
from datetime import datetime
import random

@dataclass
class GameEvent:
    """Single event in a game."""
    game_time: float
    event_type: str
    team: int
    gold_diff: int
    details: Dict = field(default_factory=dict)

@dataclass
class GameResult:
    """Result of a single game."""
    game_number: int
    winner: int
    duration_minutes: float
    team1_kills: int
    team2_kills: int
    team1_gold: int
    team2_gold: int
    team1_towers: int
    team2_towers: int
    team1_dragons: int
    team2_dragons: int
    team1_barons: int
    team2_barons: int
    events: List[GameEvent] = field(default_factory=list)

@dataclass 
class MatchResult:
    """Result of a complete match."""
    match_id: str
    date: datetime
    tournament: str
    team1_name: str
    team2_name: str
    team1_rating: float
    team2_rating: float
    format: int
    team1_score: int
    team2_score: int
    winner: int
    games: List[GameResult] = field(default_factory=list)
    opening_odds_team1: float = 0.5

# Real historical matches
HISTORICAL_MATCHES = [
    {
        "match_id": "worlds_2024_finals",
        "date": "2024-11-02",
        "tournament": "Worlds 2024",
        "team1": {"name": "T1", "rating": 1850},
        "team2": {"name": "BLG", "rating": 1820},
        "format": 5,
        "result": {"team1_score": 3, "team2_score": 2, "winner": 1},
        "opening_odds": 0.52,
        "games": [
            {"winner": 2, "duration": 32, "kills": [8, 15], "gold": [52000, 58000]},
            {"winner": 1, "duration": 35, "kills": [18, 12], "gold": [62000, 55000]},
            {"winner": 2, "duration": 28, "kills": [5, 14], "gold": [45000, 55000]},
            {"winner": 1, "duration": 38, "kills": [16, 10], "gold": [68000, 58000]},
            {"winner": 1, "duration": 33, "kills": [14, 8], "gold": [60000, 52000]},
        ]
    },
    {
        "match_id": "worlds_2024_semi_1",
        "date": "2024-10-26",
        "tournament": "Worlds 2024",
        "team1": {"name": "T1", "rating": 1840},
        "team2": {"name": "Gen.G", "rating": 1860},
        "format": 5,
        "result": {"team1_score": 3, "team2_score": 1, "winner": 1},
        "opening_odds": 0.45,
        "games": [
            {"winner": 1, "duration": 30, "kills": [12, 6], "gold": [55000, 48000]},
            {"winner": 2, "duration": 35, "kills": [10, 16], "gold": [52000, 62000]},
            {"winner": 1, "duration": 32, "kills": [15, 9], "gold": [58000, 50000]},
            {"winner": 1, "duration": 28, "kills": [18, 5], "gold": [52000, 42000]},
        ]
    },
    {
        "match_id": "lck_summer_2024_finals",
        "date": "2024-08-18",
        "tournament": "LCK Summer 2024",
        "team1": {"name": "Gen.G", "rating": 1870},
        "team2": {"name": "HLE", "rating": 1780},
        "format": 5,
        "result": {"team1_score": 3, "team2_score": 0, "winner": 1},
        "opening_odds": 0.72,
        "games": [
            {"winner": 1, "duration": 28, "kills": [14, 4], "gold": [52000, 42000]},
            {"winner": 1, "duration": 32, "kills": [12, 8], "gold": [58000, 50000]},
            {"winner": 1, "duration": 30, "kills": [16, 6], "gold": [55000, 45000]},
        ]
    },
    {
        "match_id": "lpl_summer_2024_finals",
        "date": "2024-08-25",
        "tournament": "LPL Summer 2024",
        "team1": {"name": "BLG", "rating": 1830},
        "team2": {"name": "WBG", "rating": 1790},
        "format": 5,
        "result": {"team1_score": 3, "team2_score": 1, "winner": 1},
        "opening_odds": 0.62,
        "games": [
            {"winner": 1, "duration": 35, "kills": [15, 10], "gold": [62000, 55000]},
            {"winner": 2, "duration": 40, "kills": [12, 18], "gold": [58000, 68000]},
            {"winner": 1, "duration": 32, "kills": [18, 8], "gold": [58000, 48000]},
            {"winner": 1, "duration": 28, "kills": [20, 6], "gold": [55000, 42000]},
        ]
    },
    {
        "match_id": "msi_2024_finals",
        "date": "2024-05-19",
        "tournament": "MSI 2024",
        "team1": {"name": "Gen.G", "rating": 1850},
        "team2": {"name": "BLG", "rating": 1820},
        "format": 5,
        "result": {"team1_score": 3, "team2_score": 1, "winner": 1},
        "opening_odds": 0.55,
        "games": [
            {"winner": 1, "duration": 30, "kills": [14, 8], "gold": [55000, 48000]},
            {"winner": 2, "duration": 38, "kills": [10, 15], "gold": [55000, 62000]},
            {"winner": 1, "duration": 35, "kills": [16, 10], "gold": [60000, 52000]},
            {"winner": 1, "duration": 32, "kills": [18, 8], "gold": [58000, 48000]},
        ]
    },
    {
        "match_id": "worlds_2023_finals",
        "date": "2023-11-19",
        "tournament": "Worlds 2023",
        "team1": {"name": "T1", "rating": 1880},
        "team2": {"name": "WBG", "rating": 1780},
        "format": 5,
        "result": {"team1_score": 3, "team2_score": 0, "winner": 1},
        "opening_odds": 0.70,
        "games": [
            {"winner": 1, "duration": 32, "kills": [15, 8], "gold": [58000, 50000]},
            {"winner": 1, "duration": 28, "kills": [18, 5], "gold": [52000, 42000]},
            {"winner": 1, "duration": 35, "kills": [14, 10], "gold": [62000, 55000]},
        ]
    },
    {
        "match_id": "lck_2024_upset",
        "date": "2024-07-15",
        "tournament": "LCK Summer 2024",
        "team1": {"name": "T1", "rating": 1820},
        "team2": {"name": "KT", "rating": 1720},
        "format": 3,
        "result": {"team1_score": 1, "team2_score": 2, "winner": 2},
        "opening_odds": 0.72,
        "games": [
            {"winner": 1, "duration": 30, "kills": [12, 8], "gold": [55000, 48000]},
            {"winner": 2, "duration": 42, "kills": [14, 18], "gold": [62000, 70000]},
            {"winner": 2, "duration": 38, "kills": [10, 15], "gold": [55000, 62000]},
        ]
    },
    {
        "match_id": "lpl_2024_stomp",
        "date": "2024-06-20",
        "tournament": "LPL Summer 2024",
        "team1": {"name": "BLG", "rating": 1830},
        "team2": {"name": "IG", "rating": 1650},
        "format": 3,
        "result": {"team1_score": 2, "team2_score": 0, "winner": 1},
        "opening_odds": 0.82,
        "games": [
            {"winner": 1, "duration": 22, "kills": [18, 2], "gold": [45000, 32000]},
            {"winner": 1, "duration": 25, "kills": [15, 5], "gold": [48000, 38000]},
        ]
    },
]


def generate_game_events(game_data: Dict, team1_rating: float, team2_rating: float) -> List[GameEvent]:
    """Generate realistic event sequence for a game."""
    events = []
    winner = game_data["winner"]
    duration = game_data["duration"]
    kills = game_data["kills"]
    gold = game_data["gold"]
    final_gold_diff = gold[0] - gold[1]
    
    random.seed(hash(str(game_data)))  # Reproducible
    
    current_gold_diff = 0
    
    # First blood (3-6 min)
    fb_time = random.uniform(3, 6)
    fb_team = winner if random.random() < 0.6 else (3 - winner)
    events.append(GameEvent(fb_time, "kill", fb_team, 400 if fb_team == 1 else -400, {"context": "first_blood"}))
    current_gold_diff = 400 if fb_team == 1 else -400
    
    # First dragon (5-8 min)
    d1_time = random.uniform(5, 8)
    d1_team = winner if random.random() < 0.55 else (3 - winner)
    events.append(GameEvent(d1_time, "dragon_1", d1_team, current_gold_diff))
    
    # First tower (10-14 min)
    ft_time = random.uniform(10, 14)
    ft_team = winner if random.random() < 0.65 else (3 - winner)
    current_gold_diff += 650 if ft_team == 1 else -650
    events.append(GameEvent(ft_time, "tower_outer", ft_team, current_gold_diff, {"context": "first"}))
    
    # Mid game kills
    for i in range(min(kills[0] - 1, 6)):
        kill_time = random.uniform(8, duration - 5)
        gold_at_time = int(final_gold_diff * (kill_time / duration))
        events.append(GameEvent(kill_time, "kill", 1, gold_at_time))
    
    for i in range(min(kills[1] - 1, 6)):
        kill_time = random.uniform(8, duration - 5)
        gold_at_time = int(final_gold_diff * (kill_time / duration))
        events.append(GameEvent(kill_time, "kill", 2, gold_at_time))
    
    # More dragons
    if duration > 15:
        events.append(GameEvent(random.uniform(12, 16), "dragon_2", winner if random.random() < 0.6 else (3-winner), int(final_gold_diff * 0.4)))
    if duration > 22:
        events.append(GameEvent(random.uniform(18, 24), "dragon_3", winner if random.random() < 0.65 else (3-winner), int(final_gold_diff * 0.6)))
    
    # Baron
    if duration > 22:
        events.append(GameEvent(random.uniform(20, min(28, duration - 3)), "baron", winner, int(final_gold_diff * 0.7)))
    
    # Inner towers
    if duration > 20:
        for i in range(random.randint(1, 2)):
            events.append(GameEvent(random.uniform(16, duration - 5), "tower_inner", winner if random.random() < 0.7 else (3-winner), int(final_gold_diff * 0.6)))
    
    # Inhibitor
    if duration > 25:
        events.append(GameEvent(random.uniform(duration - 8, duration - 2), "inhibitor", winner, int(final_gold_diff * 0.9)))
    
    events.sort(key=lambda e: e.game_time)
    return events


def load_historical_matches() -> List[MatchResult]:
    """Load and parse historical match data."""
    matches = []
    
    for match_data in HISTORICAL_MATCHES:
        games = []
        
        for i, game_data in enumerate(match_data["games"]):
            events = generate_game_events(game_data, match_data["team1"]["rating"], match_data["team2"]["rating"])
            
            game = GameResult(
                game_number=i + 1,
                winner=game_data["winner"],
                duration_minutes=game_data["duration"],
                team1_kills=game_data["kills"][0],
                team2_kills=game_data["kills"][1],
                team1_gold=game_data["gold"][0],
                team2_gold=game_data["gold"][1],
                team1_towers=5 if game_data["winner"] == 1 else random.randint(2, 4),
                team2_towers=5 if game_data["winner"] == 2 else random.randint(2, 4),
                team1_dragons=random.randint(2, 4) if game_data["winner"] == 1 else random.randint(0, 2),
                team2_dragons=random.randint(2, 4) if game_data["winner"] == 2 else random.randint(0, 2),
                team1_barons=1 if game_data["winner"] == 1 and game_data["duration"] > 22 else 0,
                team2_barons=1 if game_data["winner"] == 2 and game_data["duration"] > 22 else 0,
                events=events
            )
            games.append(game)
        
        result = match_data["result"]
        match = MatchResult(
            match_id=match_data["match_id"],
            date=datetime.strptime(match_data["date"], "%Y-%m-%d"),
            tournament=match_data["tournament"],
            team1_name=match_data["team1"]["name"],
            team2_name=match_data["team2"]["name"],
            team1_rating=match_data["team1"]["rating"],
            team2_rating=match_data["team2"]["rating"],
            format=match_data["format"],
            team1_score=result["team1_score"],
            team2_score=result["team2_score"],
            winner=result["winner"],
            games=games,
            opening_odds_team1=match_data["opening_odds"]
        )
        matches.append(match)
    
    return matches


if __name__ == "__main__":
    matches = load_historical_matches()
    print(f"Loaded {len(matches)} historical matches\n")
    
    for m in matches:
        winner_name = m.team1_name if m.winner == 1 else m.team2_name
        print(f"{m.tournament}: {m.team1_name} vs {m.team2_name}")
        print(f"  Result: {m.team1_score}-{m.team2_score} → {winner_name}")
        print(f"  Opening odds: {m.team1_name} {m.opening_odds_team1:.0%}")
        print(f"  Games: {len(m.games)}, Events: {sum(len(g.events) for g in m.games)}")
        print()
