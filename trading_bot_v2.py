#!/usr/bin/env python3
"""
Trading Bot V2 - Uses enhanced probability engine.

Integrates:
- V2 Impact Calculator (context-aware)
- V2 Probability Engine (Bayesian)
- Series State (BO5 tracking)
- PandaScore for game results
"""

import asyncio
import os
from datetime import datetime
from dotenv import load_dotenv

from core.v2 import (
    ImpactCalculatorV2,
    ProbabilityEngineV2,
    EventContext
)
from core.v2.models_v2 import SeriesState, SeriesFormat, TeamStrength

load_dotenv()

# Configuration
BANKROLL = 100.0
MIN_EDGE = 0.03  # 3% minimum edge
MAX_POSITION = 10.0

class TradingBotV2:
    def __init__(self, game: str = "lol"):
        self.engine = ProbabilityEngineV2(game)
        self.impact_calc = ImpactCalculatorV2(game)
        
        self.series: SeriesState = None
        self.position = None
        self.cash = BANKROLL
        self.pnl = 0.0
        
    def setup_match(
        self,
        team1_name: str,
        team2_name: str,
        team1_rating: float = 1500,
        team2_rating: float = 1500,
        format: SeriesFormat = SeriesFormat.BO5
    ):
        """Setup a new match."""
        # Set team priors
        self.engine.set_team_prior(team1_rating, team2_rating)
        
        # Setup series tracking
        self.series = SeriesState(
            format=format,
            team1_name=team1_name,
            team2_name=team2_name
        )
        
        print(f"\n{'='*60}")
        print(f"MATCH: {team1_name} vs {team2_name} (BO{format.value})")
        print(f"Ratings: {team1_name}={team1_rating}, {team2_name}={team2_rating}")
        print(f"Prior: {team1_name} {self.engine.current_probability:.1%}")
        print(f"{'='*60}\n")
    
    def set_series_score(self, team1_wins: int, team2_wins: int):
        """Set current series score."""
        if self.series:
            self.series.team1_wins = team1_wins
            self.series.team2_wins = team2_wins
            print(f"Series: {self.series}")
    
    def process_event(
        self,
        event_type: str,
        team: int,
        game_time: float,
        gold_diff: int = 0,
        **kwargs
    ):
        """Process a game event and get trading signal."""
        
        ctx = EventContext(
            game_time=game_time,
            gold_diff=gold_diff,
            **kwargs
        )
        
        # Update probability
        snapshot = self.engine.update_from_event(event_type, team, ctx)
        
        # Get series probability if in a series
        if self.series:
            series_prob = self.series.series_probability(snapshot.team1_prob)
        else:
            series_prob = snapshot.team1_prob
        
        team_name = self.series.team1_name if team == 1 else self.series.team2_name
        
        print(f"[{game_time:.1f}m] {team_name} {event_type}")
        print(f"  Game: {snapshot.team1_prob:.1%} | Series: {series_prob:.1%}")
        
        return snapshot, series_prob
    
    def get_fair_price(self, for_team: int = 1) -> float:
        """Get fair series price for a team."""
        if self.series:
            game_prob = self.engine.current_probability
            series_prob = self.series.series_probability(game_prob)
        else:
            series_prob = self.engine.current_probability
        
        if for_team == 1:
            return series_prob
        else:
            return 1 - series_prob
    
    def evaluate_trade(self, market_price: float, for_team: int = 1):
        """Evaluate trading opportunity."""
        
        fair = self.get_fair_price(for_team)
        edge = fair - market_price
        
        # Kelly criterion
        if edge > 0 and market_price < 1:
            kelly = edge / (1 - market_price)
            kelly = min(kelly, 0.25)  # Cap at 25%
        else:
            kelly = 0
        
        # Recommendation
        if edge > 0.05:
            rec = "STRONG BUY"
        elif edge > 0.02:
            rec = "BUY"
        elif edge > 0.01:
            rec = "SLIGHT BUY"
        elif edge < -0.05:
            rec = "STRONG SELL"
        elif edge < -0.02:
            rec = "SELL"
        elif edge < -0.01:
            rec = "SLIGHT SELL"
        else:
            rec = "HOLD"
        
        team_name = self.series.team1_name if for_team == 1 else self.series.team2_name
        
        print(f"\n📊 Trade Analysis for {team_name}:")
        print(f"  Fair: {fair:.1%} | Market: {market_price:.1%}")
        print(f"  Edge: {edge:+.1%} | Kelly: {kelly:.1%}")
        print(f"  Signal: {rec}")
        
        if edge >= MIN_EDGE:
            size = min(kelly * self.cash, MAX_POSITION)
            print(f"  ⚡ ACTION: BUY ${size:.2f} of {team_name}")
            return edge, "BUY", size
        elif edge <= -MIN_EDGE:
            print(f"  ⚡ ACTION: SELL {team_name} (or BUY opponent)")
            return edge, "SELL", 0
        else:
            print(f"  ⏸️  NO TRADE (edge {edge:+.1%} < ±{MIN_EDGE:.0%})")
            return edge, "HOLD", 0
    
    def record_game_win(self, winner: int):
        """Record a game win in the series."""
        if self.series:
            self.series.record_game_win(winner)
            
            team_name = self.series.team1_name if winner == 1 else self.series.team2_name
            print(f"\n🎮 {team_name} WINS GAME!")
            print(f"Series: {self.series}")
            
            if self.series.is_series_over:
                winner_name = self.series.team1_name if self.series.series_winner == 1 else self.series.team2_name
                print(f"🏆 {winner_name} WINS THE SERIES!")
            
            # Reset game probability for next game
            self.engine.reset(keep_priors=True)


def demo():
    """Demo the trading bot."""
    bot = TradingBotV2("lol")
    
    # Setup IG vs LNG match
    bot.setup_match(
        team1_name="IG",
        team2_name="LNG",
        team1_rating=1650,
        team2_rating=1700,
        format=SeriesFormat.BO5
    )
    
    # Set current series score
    bot.set_series_score(2, 1)  # IG leads 2-1
    
    # Initial series probability
    print(f"\n📈 Initial Series Probability:")
    print(f"  IG: {bot.get_fair_price(1):.1%}")
    print(f"  LNG: {bot.get_fair_price(2):.1%}")
    
    print("\n--- Game 4 Events ---\n")
    
    # Simulate some events
    bot.process_event("kill", team=1, game_time=5.0, gold_diff=0)
    bot.process_event("dragon_1", team=1, game_time=8.0, gold_diff=500)
    bot.process_event("tower_outer", team=1, game_time=12.0, gold_diff=1500)
    bot.process_event("kill", team=2, game_time=15.0, gold_diff=1200)
    bot.process_event("baron", team=1, game_time=25.0, gold_diff=3000)
    
    # Evaluate trade at current market price
    print("\n--- Trade Evaluation ---")
    
    # If market has IG at 55c, is that a good buy?
    bot.evaluate_trade(market_price=0.55, for_team=1)  # IG
    
    # What about LNG at 45c?
    bot.evaluate_trade(market_price=0.45, for_team=2)  # LNG
    
    # What if market is efficient at 78c?
    bot.evaluate_trade(market_price=0.78, for_team=1)  # IG at fair value
    
    # IG wins game 4
    bot.record_game_win(1)


if __name__ == "__main__":
    demo()
