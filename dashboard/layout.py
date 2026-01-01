"""
Dashboard Layout - Defines the visual structure of the dashboard.

The dashboard has:
1. Header with title and status
2. Main metrics cards (P&L, trades, win rate, etc.)
3. Probability chart (fair price vs market price)
4. Trade log table
5. Event feed
"""

import dash_bootstrap_components as dbc
from dash import html, dcc


def create_metric_card(title: str, value_id: str, color: str = "primary") -> dbc.Card:
    """Create a metric display card."""
    return dbc.Card(
        dbc.CardBody([
            html.H6(title, className="card-subtitle mb-2 text-muted"),
            html.H3(id=value_id, children="--", className=f"card-title text-{color}")
        ]),
        className="mb-3"
    )


def create_layout() -> dbc.Container:
    """Create the main dashboard layout."""
    
    return dbc.Container([
        # ============================================================
        # HEADER
        # ============================================================
        dbc.Row([
            dbc.Col([
                html.H1("🎮 Esports HFT Trading Bot", className="text-primary mb-0"),
                html.P("Real-time monitoring dashboard", className="text-muted")
            ], width=8),
            dbc.Col([
                dbc.Card(
                    dbc.CardBody([
                        html.H6("Status", className="card-subtitle mb-1 text-muted"),
                        html.H4(id="status-indicator", children="● Disconnected", 
                               className="text-warning mb-0")
                    ]),
                    className="text-end"
                )
            ], width=4)
        ], className="mb-4 mt-3"),
        
        html.Hr(),
        
        # ============================================================
        # MATCH INFO
        # ============================================================
        dbc.Row([
            dbc.Col([
                dbc.Card(
                    dbc.CardBody([
                        html.H5("Current Match", className="card-title"),
                        html.H3(id="match-teams", children="No active match", 
                               className="text-info"),
                        html.P(id="match-info", children="Waiting for match...",
                              className="text-muted mb-0")
                    ])
                )
            ], width=12)
        ], className="mb-4"),
        
        # ============================================================
        # METRICS CARDS
        # ============================================================
        dbc.Row([
            dbc.Col(create_metric_card("Total P&L", "metric-pnl", "success"), width=2),
            dbc.Col(create_metric_card("Trades", "metric-trades", "info"), width=2),
            dbc.Col(create_metric_card("Win Rate", "metric-winrate", "primary"), width=2),
            dbc.Col(create_metric_card("Avg Edge", "metric-edge", "warning"), width=2),
            dbc.Col(create_metric_card("Position", "metric-position", "secondary"), width=2),
            dbc.Col(create_metric_card("Bankroll", "metric-bankroll", "success"), width=2),
        ], className="mb-4"),
        
        # ============================================================
        # MAIN CONTENT - CHARTS AND TABLES
        # ============================================================
        dbc.Row([
            # Left column - Probability Chart
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader("📈 Price Chart"),
                    dbc.CardBody([
                        dcc.Graph(
                            id="price-chart",
                            config={"displayModeBar": False},
                            style={"height": "350px"}
                        )
                    ])
                ])
            ], width=8),
            
            # Right column - Event Feed
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader("⚡ Live Events"),
                    dbc.CardBody([
                        html.Div(
                            id="event-feed",
                            style={
                                "height": "350px",
                                "overflowY": "auto",
                                "fontSize": "0.85rem"
                            }
                        )
                    ])
                ])
            ], width=4)
        ], className="mb-4"),
        
        # ============================================================
        # TRADE LOG
        # ============================================================
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader("📋 Trade Log"),
                    dbc.CardBody([
                        html.Div(
                            id="trade-log",
                            style={
                                "height": "250px",
                                "overflowY": "auto"
                            }
                        )
                    ])
                ])
            ], width=12)
        ], className="mb-4"),
        
        # ============================================================
        # FOOTER
        # ============================================================
        dbc.Row([
            dbc.Col([
                html.Hr(),
                html.P(
                    "Esports HFT Bot v1.0 | Paper Trading Mode",
                    className="text-muted text-center"
                )
            ])
        ]),
        
        # ============================================================
        # INTERVAL COMPONENT FOR UPDATES
        # ============================================================
        dcc.Interval(
            id="update-interval",
            interval=500,  # Update every 500ms
            n_intervals=0
        ),
        
        # Hidden div for storing data
        dcc.Store(id="dashboard-data", data={})
        
    ], fluid=True, className="px-4")


def create_empty_chart():
    """Create an empty placeholder chart."""
    import plotly.graph_objects as go
    
    fig = go.Figure()
    
    fig.add_trace(go.Scatter(
        x=[],
        y=[],
        name="Fair Price",
        line=dict(color="#00bc8c", width=2)
    ))
    
    fig.add_trace(go.Scatter(
        x=[],
        y=[],
        name="Market Price",
        line=dict(color="#3498db", width=2, dash="dash")
    ))
    
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=40, r=20, t=20, b=40),
        xaxis=dict(
            title="Game Time (min)",
            gridcolor="rgba(255,255,255,0.1)"
        ),
        yaxis=dict(
            title="Price",
            range=[0, 1],
            gridcolor="rgba(255,255,255,0.1)"
        ),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        ),
        showlegend=True
    )
    
    return fig