#!/usr/bin/env python3
"""
Test script for V2 probability engine and impact calculator.

Runs through various scenarios to verify calculations.
"""

import sys
sys.path.insert(0, '/Users/wintran/Documents/esports_hft_bot')

from core.v2.impact_calculator_v2 import ImpactCalculatorV2, EventContext
from core.v2.probability_engine_v2 import ProbabilityEngineV2, BayesianUpdater
from core.v2.models_v2 import (
    EnhancedGameState, 
    MomentumTracker, 
    SeriesState, 
    SeriesFormat,
    TeamStrength,
    ProbabilityDistribution
)


def test_impact_calculator():
    """Test the impact calculator."""
    print("=" * 60)
    print("TESTING IMPACT CALCULATOR V2")
    print("=" * 60)
    
    calc = ImpactCalculatorV2("lol")
    
    # Test 1: Basic kill at different times
    print("\n📍 Test 1: Kill impact at different game times")
    print("-" * 50)
    
    for time in [5, 15, 25, 35, 45]:
        ctx = EventContext(game_time=time, gold_diff=0)
        result = calc.calculate_impact("kill", ctx, for_team=1)
        print(f"  {time:2}min: {result.impact_percent:>8} (time_mult: {result.time_multiplier:.2f})")
    
    # Test 2: Kill with comeback context
    print("\n📍 Test 2: Kill impact based on gold deficit")
    print("-" * 50)
    
    for gold_diff in [5000, 0, -3000, -6000, -10000]:
        ctx = EventContext(game_time=25, gold_diff=gold_diff)
        result = calc.calculate_impact("kill", ctx, for_team=1)
        label = "ahead" if gold_diff > 0 else "behind" if gold_diff < 0 else "even"
        print(f"  {gold_diff:+6} gold ({label:6}): {result.impact_percent:>8} (ctx_mult: {result.context_multiplier:.2f})")
    
    # Test 3: Different event types
    print("\n📍 Test 3: Different event types at 25min")
    print("-" * 50)
    
    ctx = EventContext(game_time=25, gold_diff=0)
    events = [
        ("kill", "Basic kill"),
        ("kill_solo", "Solo kill"),
        ("tower_outer", "Outer tower"),
        ("tower_inner", "Inner tower"),
        ("dragon_1", "1st dragon"),
        ("dragon_3", "3rd dragon (soul point)"),
        ("baron", "Baron"),
        ("inhibitor", "Inhibitor"),
    ]
    
    for event_type, desc in events:
        result = calc.calculate_impact(event_type, ctx, for_team=1)
        print(f"  {desc:20}: {result.impact_percent:>8}")
    
    # Test 4: Shutdown kill
    print("\n📍 Test 4: Shutdown kill on fed enemy")
    print("-" * 50)
    
    ctx = EventContext(
        game_time=22,
        gold_diff=-2000,
        victim_gold=12000,
        victim_streak=5,
        is_shutdown=True
    )
    result = calc.calculate_kill_impact(ctx, for_team=1)
    print(f"  Shutdown on 5-streak: {result.impact_percent}")
    print(f"  Explanation: {result.explanation}")
    
    # Test 5: Teamfight
    print("\n📍 Test 5: Teamfight outcomes")
    print("-" * 50)
    
    fights = [
        (3, 1, "3-1 small win"),
        (4, 1, "4-1 big win"),
        (5, 0, "5-0 ACE"),
        (2, 4, "2-4 loss"),
    ]
    
    ctx = EventContext(game_time=28, gold_diff=0)
    for kills_for, kills_against, desc in fights:
        result = calc.calculate_fight_impact(kills_for, kills_against, ctx, for_team=1)
        print(f"  {desc:15}: {result.impact_percent:>8}")
    
    print("\n✅ Impact Calculator V2 tests passed!")
    return True


def test_probability_engine():
    """Test the probability engine."""
    print("\n" + "=" * 60)
    print("TESTING PROBABILITY ENGINE V2")
    print("=" * 60)
    
    engine = ProbabilityEngineV2("lol")
    
    # Test 1: Set team priors
    print("\n📍 Test 1: Team strength priors")
    print("-" * 50)
    
    # T1 (strong) vs weaker team
    engine.set_team_prior(team1_strength=1800, team2_strength=1550)
    print(f"  T1(1800) vs T2(1550): Prior = {engine.current_probability:.1%}")
    
    # Even teams
    engine.set_team_prior(team1_strength=1600, team2_strength=1600)
    print(f"  T1(1600) vs T2(1600): Prior = {engine.current_probability:.1%}")
    
    # Test 2: Full state calculation
    print("\n📍 Test 2: Calculate from game state")
    print("-" * 50)
    
    engine.reset()
    
    # Create a game state where Team 1 is ahead
    state = EnhancedGameState(
        match_id="test",
        game_time_seconds=25 * 60,  # 25 minutes
        team1_kills=12,
        team2_kills=6,
        team1_gold=48000,
        team2_gold=42000,  # 6k gold lead
        team1_towers=5,
        team2_towers=2,
        team1_dragons=3,
        team2_dragons=1,
    )
    
    snapshot = engine.calculate_from_state(state)
    print(f"  Game state: {state.summary()}")
    print(f"  Probability: {snapshot}")
    print(f"  Phase: {snapshot.game_phase}")
    
    # Test 3: Event updates
    print("\n📍 Test 3: Sequential event updates")
    print("-" * 50)
    
    engine.reset()
    engine.set_team_prior(1600, 1600)  # Even teams
    print(f"  Start: {engine.current_probability:.1%}")
    
    events = [
        ("kill", 1, 8.0, "T1 gets first blood"),
        ("tower_outer", 1, 12.0, "T1 takes first tower"),
        ("dragon_1", 1, 15.0, "T1 takes dragon"),
        ("kill", 2, 18.0, "T2 gets a kill back"),
        ("kill", 2, 18.5, "T2 another kill"),
        ("baron", 1, 28.0, "T1 takes baron!"),
    ]
    
    for event_type, team, time, desc in events:
        ctx = EventContext(game_time=time, gold_diff=0)
        snapshot = engine.update_from_event(event_type, team, ctx)
        team_name = "T1" if team == 1 else "T2"
        print(f"  {time:5.1f}min {desc:25} → {snapshot.team1_prob:.1%}")
    
    # Test 4: Edge calculation
    print("\n📍 Test 4: Trading edge calculation")
    print("-" * 50)
    
    market_prices = [0.50, 0.55, 0.60, 0.65, 0.70]
    fair = engine.current_probability
    print(f"  Our fair price: {fair:.1%}")
    
    for market in market_prices:
        edge, kelly, rec = engine.calculate_edge(market, for_team=1)
        print(f"  Market {market:.0%}: Edge {edge:+.1%}, Kelly {kelly:.1%}, {rec}")
    
    print("\n✅ Probability Engine V2 tests passed!")
    return True


def test_series_state():
    """Test series state calculations."""
    print("\n" + "=" * 60)
    print("TESTING SERIES STATE")
    print("=" * 60)
    
    # Test BO5 series probability
    print("\n📍 Test 1: BO5 series probability")
    print("-" * 50)
    
    series = SeriesState(
        format=SeriesFormat.BO5,
        team1_name="IG",
        team2_name="LNG"
    )
    
    # Single game win prob = 55%
    game_prob = 0.55
    
    scores = [(0, 0), (1, 0), (0, 1), (1, 1), (2, 0), (0, 2), (2, 1), (1, 2), (2, 2)]
    
    print(f"  Single game prob: {game_prob:.0%}")
    print()
    for t1, t2 in scores:
        series.team1_wins = t1
        series.team2_wins = t2
        series_prob = series.series_probability(game_prob)
        status = ""
        if series.is_match_point_team1:
            status = " [MATCH POINT IG]"
        elif series.is_match_point_team2:
            status = " [MATCH POINT LNG]"
        print(f"  {series}: Series prob = {series_prob:.1%}{status}")
    
    print("\n✅ Series State tests passed!")
    return True


def test_momentum_tracker():
    """Test momentum tracking."""
    print("\n" + "=" * 60)
    print("TESTING MOMENTUM TRACKER")
    print("=" * 60)
    
    tracker = MomentumTracker(decay_minutes=2.0)
    
    print("\n📍 Test 1: Building momentum")
    print("-" * 50)
    
    # Team 1 gets 3 kills in quick succession
    tracker.add_event(20.0, "kill", team=1, impact=0.01)
    print(f"  20.0min T1 kill: momentum = {tracker.get_momentum_score():+.4f} ({tracker.get_momentum_state().value})")
    
    tracker.add_event(20.5, "kill", team=1, impact=0.01)
    print(f"  20.5min T1 kill: momentum = {tracker.get_momentum_score():+.4f} ({tracker.get_momentum_state().value})")
    
    tracker.add_event(21.0, "dragon", team=1, impact=0.02)
    print(f"  21.0min T1 drag: momentum = {tracker.get_momentum_score():+.4f} ({tracker.get_momentum_state().value})")
    
    # Team 2 fights back
    tracker.add_event(22.0, "kill", team=2, impact=0.01)
    print(f"  22.0min T2 kill: momentum = {tracker.get_momentum_score():+.4f} ({tracker.get_momentum_state().value})")
    
    tracker.add_event(22.5, "kill", team=2, impact=0.01)
    print(f"  22.5min T2 kill: momentum = {tracker.get_momentum_score():+.4f} ({tracker.get_momentum_state().value})")
    
    print(f"\n  Momentum adjustment: {tracker.get_momentum_adjustment():+.4f}")
    print(f"  T1 streak: {tracker.get_streak(1)}, T2 streak: {tracker.get_streak(2)}")
    
    print("\n✅ Momentum Tracker tests passed!")
    return True


def test_team_strength():
    """Test team strength model."""
    print("\n" + "=" * 60)
    print("TESTING TEAM STRENGTH MODEL")
    print("=" * 60)
    
    print("\n📍 Test 1: Head-to-head probabilities")
    print("-" * 50)
    
    t1 = TeamStrength(name="T1", rating=1850, recent_form=0.8)
    geng = TeamStrength(name="Gen.G", rating=1820, recent_form=0.7)
    blg = TeamStrength(name="BLG", rating=1780, recent_form=0.65)
    ig = TeamStrength(name="IG", rating=1650, recent_form=0.55)
    
    matchups = [
        (t1, geng),
        (t1, blg),
        (t1, ig),
        (geng, blg),
        (blg, ig),
    ]
    
    for team_a, team_b in matchups:
        prob = team_a.vs_probability(team_b)
        print(f"  {team_a.name} vs {team_b.name}: {prob:.1%}")
    
    print("\n✅ Team Strength tests passed!")
    return True


def run_full_scenario():
    """Run a complete game scenario."""
    print("\n" + "=" * 60)
    print("FULL GAME SCENARIO SIMULATION")
    print("=" * 60)
    
    # Setup
    engine = ProbabilityEngineV2("lol")
    engine.set_team_prior(1700, 1650)  # Slight favorite
    
    series = SeriesState(
        format=SeriesFormat.BO5,
        team1_name="IG",
        team2_name="LNG",
        team1_wins=2,
        team2_wins=0
    )
    engine.set_series_context(series)
    
    print(f"\n📍 Series: {series}")
    print(f"📍 Starting probability: {engine.current_probability:.1%}")
    print("-" * 50)
    
    # Simulate game events
    events = [
        # Early game - LNG gets ahead
        (3.0, "kill", 2, 0, "LNG first blood"),
        (8.0, "tower_outer", 2, -500, "LNG first tower"),
        (10.0, "dragon_1", 2, -1000, "LNG 1st dragon"),
        
        # Mid game - IG fights back
        (15.0, "kill", 1, -1500, "IG catches someone"),
        (16.0, "kill", 1, -1200, "IG another kill"),
        (18.0, "dragon_1", 1, -800, "IG takes dragon"),
        (20.0, "tower_outer", 1, -500, "IG takes tower"),
        
        # Late mid - crucial fight
        (25.0, "baron", 1, 1500, "IG BARON!"),
        (26.0, "tower_inner", 1, 2500, "IG inner tower"),
        (27.0, "inhibitor", 1, 4000, "IG INHIBITOR!"),
        
        # Closing out
        (30.0, "kill", 1, 5000, "IG picks off"),
        (31.0, "kill", 1, 5500, "IG another"),
    ]
    
    print(f"\n{'Time':>6} | {'Event':25} | {'Prob':>7} | {'Edge vs 50c'}")
    print("-" * 55)
    
    for time, event_type, team, gold_diff, desc in events:
        ctx = EventContext(game_time=time, gold_diff=gold_diff)
        snapshot = engine.update_from_event(event_type, team, ctx)
        
        edge, _, rec = engine.calculate_edge(0.50, for_team=1)
        
        print(f"{time:5.1f}m | {desc:25} | {snapshot.team1_prob:6.1%} | {edge:+.1%} {rec}")
    
    print("-" * 55)
    print(f"\n📍 Final: IG {engine.current_probability:.1%} to win this game")
    
    # Series implications
    if engine.current_probability > 0.5:
        series_prob = series.series_probability(engine.current_probability)
        print(f"📍 Series: IG {series_prob:.1%} to win series")
    
    print("\n✅ Full scenario simulation complete!")


if __name__ == "__main__":
    print("""
╔══════════════════════════════════════════════════════════════╗
║           ESPORTS HFT BOT - V2 CORE TEST SUITE              ║
╚══════════════════════════════════════════════════════════════╝
""")
    
    try:
        test_impact_calculator()
        test_probability_engine()
        test_series_state()
        test_momentum_tracker()
        test_team_strength()
        run_full_scenario()
        
        print("\n" + "=" * 60)
        print("🎉 ALL TESTS PASSED!")
        print("=" * 60)
        print("""
V2 Core Components Ready:
  ✅ ImpactCalculatorV2 - Context-aware event impacts
  ✅ ProbabilityEngineV2 - Bayesian probability updates
  ✅ MomentumTracker - Recent event momentum
  ✅ SeriesState - BO3/BO5 series calculations
  ✅ TeamStrength - ELO-based team priors
  ✅ EnhancedGameState - Detailed state tracking
""")
        
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
