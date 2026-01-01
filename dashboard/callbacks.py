"""
Dashboard Callbacks - Handles interactive updates and data flow.

Callbacks are functions that update the dashboard when:
1. New data arrives
2. Timer fires (interval updates)
3. User interacts with components
"""

import plotly.graph_objects as go
from dash import html, callback, Output, Input, State
from dash.exceptions import PreventUpdate
import dash_bootstrap_components as dbc
from datetime import datetime
from typing import Dict, List, Any, Optional


class DashboardState:
    """
    Holds the current state of the dashboard.
    
    This is updated by the trading bot and read by callbacks.
    """
    
    def __init__(self):
        self.reset()
    
    def reset(self):
        """Reset all state."""
        # Match info
        self.match_id: Optional[str] = None
        self.team1_name: str = "Team 1"
        self.team2_name: str = "Team 2"
        self.game_time: float = 0.0
        self.is_connected: bool = False
        
        # Price history
        self.times: List[float] = []
        self.fair_prices: List[float] = []
        self.market_prices: List[float] = []
        
        # Metrics
        self.total_pnl: float = 0.0
        self.total_trades: int = 0
        self.winning_trades: int = 0
        self.current_position: float = 0.0
        self.bankroll: float = 1000.0
        self.initial_bankroll: float = 1000.0
        
        # Events and trades
        self.events: List[Dict] = []
        self.trades: List[Dict] = []
        
        # Average edge
        self.total_edge: float = 0.0
    
    def add_price_point(self, game_time: float, fair_price: float, market_price: float):
        """Add a price point to history."""
        self.times.append(game_time)
        self.fair_prices.append(fair_price)
        self.market_prices.append(market_price)
        self.game_time = game_time
    
    def add_event(self, event_type: str, team: int, context: str):
        """Add a game event."""
        self.events.insert(0, {
            'time': datetime.now().strftime("%H:%M:%S"),
            'game_time': f"{self.game_time:.1f}",
            'type': event_type,
            'team': team,
            'context': context
        })
        # Keep last 50 events
        self.events = self.events[:50]
    
    def add_trade(
        self, 
        side: str, 
        size: float, 
        price: float, 
        edge: float,
        pnl: Optional[float] = None
    ):
        """Add a trade."""
        self.trades.insert(0, {
            'time': datetime.now().strftime("%H:%M:%S"),
            'game_time': f"{self.game_time:.1f}",
            'side': side,
            'size': size,
            'price': price,
            'edge': edge,
            'pnl': pnl
        })
        
        self.total_trades += 1
        self.total_edge += edge
        
        if side == "BUY":
            self.current_position += size
        else:
            self.current_position -= size
        
        # Keep last 100 trades
        self.trades = self.trades[:100]
    
    def record_trade_result(self, pnl: float):
        """Record the result of a trade."""
        self.total_pnl += pnl
        if pnl > 0:
            self.winning_trades += 1
        self.bankroll += pnl
    
    @property
    def win_rate(self) -> float:
        """Calculate win rate."""
        if self.total_trades == 0:
            return 0.0
        return self.winning_trades / self.total_trades
    
    @property
    def average_edge(self) -> float:
        """Calculate average edge."""
        if self.total_trades == 0:
            return 0.0
        return self.total_edge / self.total_trades


# Global state instance
dashboard_state = DashboardState()


def get_dashboard_state() -> DashboardState:
    """Get the global dashboard state."""
    return dashboard_state


def create_price_chart(state: DashboardState) -> go.Figure:
    """Create the price chart figure."""
    fig = go.Figure()
    
    # Fair price line
    fig.add_trace(go.Scatter(
        x=state.times,
        y=state.fair_prices,
        name="Fair Price (Our Estimate)",
        line=dict(color="#00bc8c", width=2),
        mode="lines"
    ))
    
    # Market price line
    fig.add_trace(go.Scatter(
        x=state.times,
        y=state.market_prices,
        name="Market Price",
        line=dict(color="#3498db", width=2, dash="dash"),
        mode="lines"
    ))
    
    # Add trade markers
    buy_times = []
    buy_prices = []
    sell_times = []
    sell_prices = []
    
    for trade in state.trades:
        try:
            game_time = float(trade['game_time'])
            if trade['side'] == "BUY":
                buy_times.append(game_time)
                buy_prices.append(trade['price'])
            else:
                sell_times.append(game_time)
                sell_prices.append(trade['price'])
        except (ValueError, KeyError):
            pass
    
    if buy_times:
        fig.add_trace(go.Scatter(
            x=buy_times,
            y=buy_prices,
            name="BUY",
            mode="markers",
            marker=dict(color="#00bc8c", size=10, symbol="triangle-up")
        ))
    
    if sell_times:
        fig.add_trace(go.Scatter(
            x=sell_times,
            y=sell_prices,
            name="SELL",
            mode="markers",
            marker=dict(color="#e74c3c", size=10, symbol="triangle-down")
        ))
    
    # Layout
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=40, r=20, t=20, b=40),
        xaxis=dict(
            title="Game Time (min)",
            gridcolor="rgba(255,255,255,0.1)",
            range=[0, max(state.times) + 1] if state.times else [0, 30]
        ),
        yaxis=dict(
            title="Price / Probability",
            range=[0, 1],
            gridcolor="rgba(255,255,255,0.1)",
            tickformat=".0%"
        ),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        ),
        showlegend=True,
        hovermode="x unified"
    )
    
    return fig


def create_event_feed(state: DashboardState) -> List:
    """Create the event feed display."""
    if not state.events:
        return [html.P("No events yet...", className="text-muted")]
    
    items = []
    for event in state.events[:30]:  # Show last 30
        # Color based on event type
        if event['type'] in ['baron', 'dragon', 'roshan']:
            color = "warning"
            icon = "🏆"
        elif event['type'] == 'tower':
            color = "info"
            icon = "🏰"
        elif event['type'] == 'kill':
            color = "danger" if event['team'] == 2 else "success"
            icon = "⚔️"
        else:
            color = "secondary"
            icon = "📌"
        
        team_name = state.team1_name if event['team'] == 1 else state.team2_name
        
        items.append(
            html.Div([
                html.Span(f"{event['time']} ", className="text-muted"),
                html.Span(f"[{event['game_time']}m] ", className="text-info"),
                html.Span(f"{icon} "),
                html.Span(f"{team_name} ", className=f"text-{color}"),
                html.Span(f"{event['type']} ", className="fw-bold"),
                html.Span(f"({event['context']})", className="text-muted"),
            ], className="mb-1")
        )
    
    return items


def create_trade_log(state: DashboardState) -> dbc.Table:
    """Create the trade log table."""
    if not state.trades:
        return html.P("No trades yet...", className="text-muted")
    
    # Table header
    header = html.Thead(html.Tr([
        html.Th("Time"),
        html.Th("Game"),
        html.Th("Side"),
        html.Th("Size"),
        html.Th("Price"),
        html.Th("Edge"),
        html.Th("P&L"),
    ]))
    
    # Table rows
    rows = []
    for trade in state.trades[:20]:  # Show last 20
        side_color = "success" if trade['side'] == "BUY" else "danger"
        pnl_str = f"${trade['pnl']:.2f}" if trade['pnl'] is not None else "--"
        pnl_color = "success" if trade.get('pnl', 0) and trade['pnl'] > 0 else "danger"
        
        rows.append(html.Tr([
            html.Td(trade['time']),
            html.Td(f"{trade['game_time']}m"),
            html.Td(trade['side'], className=f"text-{side_color} fw-bold"),
            html.Td(f"{trade['size']:.1f}"),
            html.Td(f"${trade['price']:.3f}"),
            html.Td(f"{trade['edge']:.1%}"),
            html.Td(pnl_str, className=f"text-{pnl_color}" if trade.get('pnl') else ""),
        ]))
    
    body = html.Tbody(rows)
    
    return dbc.Table(
        [header, body],
        bordered=True,
        hover=True,
        responsive=True,
        size="sm",
        className="mb-0"
    )


def register_callbacks(app):
    """Register all dashboard callbacks."""
    
    @app.callback(
        [
            Output("status-indicator", "children"),
            Output("status-indicator", "className"),
            Output("match-teams", "children"),
            Output("match-info", "children"),
            Output("metric-pnl", "children"),
            Output("metric-pnl", "className"),
            Output("metric-trades", "children"),
            Output("metric-winrate", "children"),
            Output("metric-edge", "children"),
            Output("metric-position", "children"),
            Output("metric-bankroll", "children"),
            Output("price-chart", "figure"),
            Output("event-feed", "children"),
            Output("trade-log", "children"),
        ],
        Input("update-interval", "n_intervals")
    )
    def update_dashboard(n_intervals):
        """Update all dashboard components."""
        state = get_dashboard_state()
        
        # Status
        if state.is_connected:
            status = "● Connected"
            status_class = "text-success mb-0"
        else:
            status = "● Disconnected"
            status_class = "text-warning mb-0"
        
        # Match info
        if state.match_id:
            teams = f"{state.team1_name} vs {state.team2_name}"
            info = f"Game time: {state.game_time:.1f} min | Match ID: {state.match_id}"
        else:
            teams = "No active match"
            info = "Waiting for match..."
        
        # P&L with color
        pnl_str = f"${state.total_pnl:.2f}"
        pnl_class = "card-title text-success" if state.total_pnl >= 0 else "card-title text-danger"
        
        # Other metrics
        trades = str(state.total_trades)
        winrate = f"{state.win_rate:.1%}"
        edge = f"{state.average_edge:.2%}"
        position = f"{state.current_position:.1f}"
        bankroll = f"${state.bankroll:.2f}"
        
        # Chart
        chart = create_price_chart(state)
        
        # Event feed
        events = create_event_feed(state)
        
        # Trade log
        trade_log = create_trade_log(state)
        
        return (
            status, status_class,
            teams, info,
            pnl_str, pnl_class,
            trades, winrate, edge, position, bankroll,
            chart,
            events,
            trade_log
        )