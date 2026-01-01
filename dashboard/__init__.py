"""
Dashboard module - Real-time monitoring interface.

Usage:
    from dashboard import create_dashboard_app, get_dashboard_state, run_dashboard
    
    # Option 1: Run dashboard directly
    run_dashboard(port=8050)
    
    # Option 2: Create app and run manually
    app = create_dashboard_app()
    state = get_dashboard_state()
    
    # Update state from your trading bot
    state.is_connected = True
    state.match_id = "match_001"
    state.team1_name = "Cloud9"
    state.team2_name = "Team Liquid"
    state.add_price_point(15.0, 0.55, 0.52)
    state.add_event("kill", 1, "solo")
    state.add_trade("BUY", 10.0, 0.52, 0.03)
    
    # Run in background thread
    import threading
    thread = threading.Thread(target=lambda: app.run(port=8050))
    thread.daemon = True
    thread.start()
"""

from .app import create_dashboard_app, run_dashboard
from .callbacks import get_dashboard_state, DashboardState

__all__ = [
    "create_dashboard_app",
    "run_dashboard",
    "get_dashboard_state",
    "DashboardState",
]