"""
Dashboard App - Main entry point for the dashboard.

This creates the Dash application and starts the web server.
The dashboard runs on http://localhost:8050

Usage:
    # Import and use in your bot
    from dashboard import create_dashboard_app, get_dashboard_state
    
    app = create_dashboard_app()
    state = get_dashboard_state()
    
    # Update state from your bot
    state.add_price_point(game_time=15.0, fair_price=0.55, market_price=0.52)
    state.add_event("kill", team=1, context="solo")
    
    # Run dashboard (blocking)
    app.run(debug=False, port=8050)
    
    # Or run in background thread
    import threading
    thread = threading.Thread(target=lambda: app.run(debug=False, port=8050))
    thread.daemon = True
    thread.start()
"""

import dash
import dash_bootstrap_components as dbc
from dash import html

from .layout import create_layout
from .callbacks import register_callbacks, get_dashboard_state, DashboardState


def create_dashboard_app() -> dash.Dash:
    """
    Create and configure the Dash application.
    
    Returns:
        Configured Dash app instance
    """
    # Create app with dark theme
    app = dash.Dash(
        __name__,
        external_stylesheets=[dbc.themes.DARKLY],
        title="Esports HFT Bot",
        update_title=None,  # Don't change title on updates
        suppress_callback_exceptions=True
    )
    
    # Set layout
    app.layout = create_layout()
    
    # Register callbacks
    register_callbacks(app)
    
    return app


def run_dashboard(port: int = 8050, debug: bool = False):
    """
    Run the dashboard server.
    
    Args:
        port: Port to run on (default 8050)
        debug: Enable debug mode (default False)
    """
    app = create_dashboard_app()
    
    print(f"\n{'='*50}")
    print("DASHBOARD STARTING")
    print(f"{'='*50}")
    print(f"Open your browser to: http://localhost:{port}")
    print(f"Press Ctrl+C to stop")
    print(f"{'='*50}\n")
    
    app.run(debug=debug, port=port, host="0.0.0.0")


# For direct execution
if __name__ == "__main__":
    run_dashboard(debug=True)