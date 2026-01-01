#!/usr/bin/env python3
"""
Backtesting Engine - Test V2 probability model against historical matches.

Metrics tracked:
1. Prediction accuracy (did we predict the winner?)
2. Calibration (when we say 70%, does it happen 70% of the time?)
3. Edge detection (would our edges have been profitable?)
4. Brier score (probability prediction quality)
"""

import sys
sys.path.insert(0, '/Users/wintran/Documents/esports_hft_bot')

from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional
from datetime import datetime
import math

from core.v2 import ProbabilityEngineV2, EventContext
from core.v2.models_v2 import SeriesState, SeriesFormat
from backtest.historical_data import load_historical_matches, MatchResult, GameResult, GameEvent


@dataclass
class TradeRecord:
    """Record of a simulated trade."""
    game_time: float
    event: str
    our_prob: float
    market_prob: float
    edge: float
    action: str  # BUY, SELL, HOLD
    size: float
    outcome_pnl: float = 0.0


@dataclass
class GameBacktestResult:
    """Result of backtesting a single game."""
    game_number: int
    actual_winner: int
    our_final_prob: float
    market_prob: float
    predicted_winner: int
    correct: bool
    brier_score: float
    trades: List[TradeRecord] = field(default_factory=list)
    probability_path: List[Tuple[float, float]] = field(default_factory=list)  # (time, prob)


@dataclass
class MatchBacktestResult:
    """Result of backtesting a complete match."""
    match_id: str
    tournament: str
    team1: str
    team2: str
    actual_winner: int
    actual_score: Tuple[int, int]
    
    # Series-level predictions
    opening_market_prob: float
    our_opening_prob: float
    our_final_prob: float
    predicted_winner: int
    correct: bool
    
    # Metrics
    brier_score: float
    total_pnl: float
    num_trades: int
    
    # Per-game results
    game_results: List[GameBacktestResult] = field(default_factory=list)


@dataclass
class BacktestSummary:
    """Summary of all backtests."""
    total_matches: int
    correct_predictions: int
    accuracy: float
    
    avg_brier_score: float
    total_pnl: float
    total_trades: int
    winning_trades: int
    win_rate: float
    
    # By match type
    favorites_correct: int
    favorites_total: int
    underdogs_correct: int
    underdogs_total: int
    
    # Calibration buckets
    calibration: Dict[str, Tuple[int, int]]  # bucket -> (correct, total)


class BacktestEngine:
    """
    Backtests the V2 probability model against historical matches.
    """
    
    def __init__(self, min_edge: float = 0.03, max_position: float = 10.0):
        self.min_edge = min_edge
        self.max_position = max_position
        self.results: List[MatchBacktestResult] = []
    
    def run_backtest(self, matches: List[MatchResult]) -> BacktestSummary:
        """Run backtest on all matches."""
        print("=" * 70)
        print("BACKTESTING V2 PROBABILITY ENGINE")
        print("=" * 70)
        print(f"Matches: {len(matches)}")
        print(f"Min Edge: {self.min_edge:.0%}")
        print(f"Max Position: ${self.max_position}")
        print("=" * 70)
        
        self.results = []
        
        for match in matches:
            result = self._backtest_match(match)
            self.results.append(result)
        
        summary = self._calculate_summary()
        self._print_summary(summary)
        
        return summary
    
    def _backtest_match(self, match: MatchResult) -> MatchBacktestResult:
        """Backtest a single match."""
        print(f"\n{'─' * 60}")
        print(f"{match.tournament}: {match.team1_name} vs {match.team2_name}")
        print(f"Actual: {match.team1_score}-{match.team2_score} → {match.team1_name if match.winner == 1 else match.team2_name}")
        print(f"Market opening: {match.team1_name} {match.opening_odds_team1:.0%}")
        print(f"{'─' * 60}")
        
        # Initialize engine
        engine = ProbabilityEngineV2("lol")
        engine.set_team_prior(match.team1_rating, match.team2_rating)
        
        # Initialize series
        series = SeriesState(
            format=SeriesFormat(match.format),
            team1_name=match.team1_name,
            team2_name=match.team2_name
        )
        
        our_opening_prob = series.series_probability(engine.current_probability)
        print(f"Our opening: {match.team1_name} {our_opening_prob:.0%}")
        
        game_results = []
        all_trades = []
        total_pnl = 0.0
        
        # Simulate market price (starts at opening, moves toward fair)
        market_prob = match.opening_odds_team1
        
        # Process each game
        for game in match.games:
            game_result, trades, market_prob = self._backtest_game(
                engine, series, game, market_prob, match
            )
            game_results.append(game_result)
            all_trades.extend(trades)
            
            # Record game result
            series.record_game_win(game.winner)
            engine.reset(keep_priors=True)
            
            winner_name = match.team1_name if game.winner == 1 else match.team2_name
            print(f"  Game {game.game_number}: {winner_name} wins | Our prob: {game_result.our_final_prob:.0%} | Correct: {'✓' if game_result.correct else '✗'}")
        
        # Calculate final metrics
        our_final_prob = series.series_probability(engine.current_probability)
        predicted_winner = 1 if our_final_prob > 0.5 else 2
        correct = predicted_winner == match.winner
        
        # Calculate PnL from trades
        for trade in all_trades:
            if trade.action != "HOLD":
                # Simplified: if we bet on winner, we win
                if (trade.edge > 0 and match.winner == 1) or (trade.edge < 0 and match.winner == 2):
                    trade.outcome_pnl = abs(trade.edge) * trade.size
                else:
                    trade.outcome_pnl = -abs(trade.edge) * trade.size
                total_pnl += trade.outcome_pnl
        
        # Brier score (lower is better)
        # Brier = (forecast - outcome)^2
        outcome = 1 if match.winner == 1 else 0
        brier = (our_opening_prob - outcome) ** 2
        
        result = MatchBacktestResult(
            match_id=match.match_id,
            tournament=match.tournament,
            team1=match.team1_name,
            team2=match.team2_name,
            actual_winner=match.winner,
            actual_score=(match.team1_score, match.team2_score),
            opening_market_prob=match.opening_odds_team1,
            our_opening_prob=our_opening_prob,
            our_final_prob=our_final_prob,
            predicted_winner=predicted_winner,
            correct=correct,
            brier_score=brier,
            total_pnl=total_pnl,
            num_trades=len([t for t in all_trades if t.action != "HOLD"]),
            game_results=game_results
        )
        
        status = "✓ CORRECT" if correct else "✗ WRONG"
        print(f"\n  {status} | PnL: ${total_pnl:+.2f} | Trades: {result.num_trades}")
        
        return result
    
    def _backtest_game(
        self,
        engine: ProbabilityEngineV2,
        series: SeriesState,
        game: GameResult,
        market_prob: float,
        match: MatchResult
    ) -> Tuple[GameBacktestResult, List[TradeRecord], float]:
        """Backtest a single game."""
        trades = []
        prob_path = []
        
        # Process events
        for event in game.events:
            ctx = EventContext(
                game_time=event.game_time,
                gold_diff=event.gold_diff
            )
            
            # Update probability
            snapshot = engine.update_from_event(event.event_type, event.team, ctx)
            series_prob = series.series_probability(snapshot.team1_prob)
            
            prob_path.append((event.game_time, series_prob))
            
            # Simulate market movement (market slowly adjusts toward fair)
            market_prob = market_prob * 0.95 + series_prob * 0.05
            
            # Check for trade opportunity
            edge = series_prob - market_prob
            
            if abs(edge) >= self.min_edge:
                action = "BUY" if edge > 0 else "SELL"
                size = min(self.max_position, abs(edge) * 100)
                
                trades.append(TradeRecord(
                    game_time=event.game_time,
                    event=event.event_type,
                    our_prob=series_prob,
                    market_prob=market_prob,
                    edge=edge,
                    action=action,
                    size=size
                ))
        
        # Final game probability
        final_game_prob = engine.current_probability
        final_series_prob = series.series_probability(final_game_prob)
        
        predicted_game_winner = 1 if final_game_prob > 0.5 else 2
        correct = predicted_game_winner == game.winner
        
        outcome = 1 if game.winner == 1 else 0
        brier = (final_game_prob - outcome) ** 2
        
        result = GameBacktestResult(
            game_number=game.game_number,
            actual_winner=game.winner,
            our_final_prob=final_game_prob,
            market_prob=market_prob,
            predicted_winner=predicted_game_winner,
            correct=correct,
            brier_score=brier,
            trades=trades,
            probability_path=prob_path
        )
        
        return result, trades, market_prob
    
    def _calculate_summary(self) -> BacktestSummary:
        """Calculate summary statistics."""
        total = len(self.results)
        correct = sum(1 for r in self.results if r.correct)
        
        brier_scores = [r.brier_score for r in self.results]
        avg_brier = sum(brier_scores) / len(brier_scores) if brier_scores else 0
        
        total_pnl = sum(r.total_pnl for r in self.results)
        total_trades = sum(r.num_trades for r in self.results)
        
        # Count winning trades
        winning_trades = 0
        for r in self.results:
            for g in r.game_results:
                for t in g.trades:
                    if t.outcome_pnl > 0:
                        winning_trades += 1
        
        win_rate = winning_trades / total_trades if total_trades > 0 else 0
        
        # Favorites vs underdogs
        favorites_correct = sum(1 for r in self.results if r.opening_market_prob > 0.5 and r.actual_winner == 1)
        favorites_correct += sum(1 for r in self.results if r.opening_market_prob < 0.5 and r.actual_winner == 2)
        favorites_total = total
        
        underdogs_correct = total - favorites_correct
        underdogs_total = total
        
        # Calibration buckets
        calibration = {}
        buckets = [(0, 0.3, "0-30%"), (0.3, 0.45, "30-45%"), (0.45, 0.55, "45-55%"), 
                   (0.55, 0.7, "55-70%"), (0.7, 1.0, "70-100%")]
        
        for low, high, label in buckets:
            bucket_results = [r for r in self.results if low <= r.our_opening_prob < high]
            bucket_correct = sum(1 for r in bucket_results if r.correct)
            calibration[label] = (bucket_correct, len(bucket_results))
        
        return BacktestSummary(
            total_matches=total,
            correct_predictions=correct,
            accuracy=correct / total if total > 0 else 0,
            avg_brier_score=avg_brier,
            total_pnl=total_pnl,
            total_trades=total_trades,
            winning_trades=winning_trades,
            win_rate=win_rate,
            favorites_correct=favorites_correct,
            favorites_total=favorites_total,
            underdogs_correct=underdogs_correct,
            underdogs_total=underdogs_total,
            calibration=calibration
        )
    
    def _print_summary(self, summary: BacktestSummary):
        """Print summary statistics."""
        print("\n" + "=" * 70)
        print("BACKTEST SUMMARY")
        print("=" * 70)
        
        print(f"\n📊 PREDICTION ACCURACY")
        print(f"  Overall: {summary.correct_predictions}/{summary.total_matches} ({summary.accuracy:.1%})")
        print(f"  Favorites won: {summary.favorites_correct}/{summary.favorites_total}")
        
        print(f"\n📈 PROBABILITY QUALITY")
        print(f"  Avg Brier Score: {summary.avg_brier_score:.4f} (lower is better)")
        print(f"  (Perfect = 0.0, Random = 0.25)")
        
        print(f"\n💰 TRADING PERFORMANCE")
        print(f"  Total PnL: ${summary.total_pnl:+.2f}")
        print(f"  Total Trades: {summary.total_trades}")
        print(f"  Win Rate: {summary.win_rate:.1%}")
        
        print(f"\n📐 CALIBRATION (when we say X%, it happens X%)")
        print(f"  {'Bucket':<12} | {'Correct':>8} | {'Total':>6} | {'Actual':>8}")
        print(f"  {'-'*12}-+-{'-'*8}-+-{'-'*6}-+-{'-'*8}")
        for bucket, (correct, total) in summary.calibration.items():
            if total > 0:
                actual = correct / total
                print(f"  {bucket:<12} | {correct:>8} | {total:>6} | {actual:>7.0%}")
        
        print("\n" + "=" * 70)
        
        # Interpretation
        print("\n📋 INTERPRETATION:")
        
        if summary.accuracy >= 0.65:
            print("  ✅ Good prediction accuracy (>65%)")
        elif summary.accuracy >= 0.55:
            print("  ⚠️  Moderate prediction accuracy (55-65%)")
        else:
            print("  ❌ Poor prediction accuracy (<55%)")
        
        if summary.avg_brier_score < 0.15:
            print("  ✅ Excellent probability calibration (Brier < 0.15)")
        elif summary.avg_brier_score < 0.20:
            print("  ⚠️  Good probability calibration (Brier < 0.20)")
        else:
            print("  ❌ Poor probability calibration (Brier > 0.20)")
        
        if summary.total_pnl > 0:
            print(f"  ✅ Profitable: ${summary.total_pnl:.2f}")
        else:
            print(f"  ❌ Unprofitable: ${summary.total_pnl:.2f}")


def main():
    """Run backtest."""
    matches = load_historical_matches()
    engine = BacktestEngine(min_edge=0.03, max_position=10.0)
    summary = engine.run_backtest(matches)
    
    return summary


if __name__ == "__main__":
    main()
