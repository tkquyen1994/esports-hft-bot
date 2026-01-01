"""
Database Manager - SQLite database for persistent storage.

Stores:
- Trade history
- Match data
- Performance metrics
- Session logs

SQLite is perfect for our needs:
- No server required (file-based)
- Fast for our data volumes
- Built into Python
- Easy to query and analyze
"""

import sqlite3
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Any
from contextlib import contextmanager

logger = logging.getLogger(__name__)


class DatabaseManager:
    """
    Manages SQLite database operations.
    
    Usage:
        db = DatabaseManager("data/trading.db")
        db.initialize()
        
        # Insert trade
        db.insert_trade({
            'match_id': 'match_001',
            'side': 'BUY',
            'size': 10.0,
            'price': 0.55,
            ...
        })
        
        # Query trades
        trades = db.get_trades_by_match('match_001')
    """
    
    def __init__(self, db_path: str = "data/trading.db"):
        """
        Initialize database manager.
        
        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = Path(db_path)
        
        # Ensure directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        self._connection: Optional[sqlite3.Connection] = None
        
        logger.info(f"DatabaseManager initialized: {self.db_path}")
    
    @contextmanager
    def get_connection(self):
        """
        Context manager for database connections.
        
        Usage:
            with db.get_connection() as conn:
                cursor = conn.execute("SELECT * FROM trades")
        """
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row  # Enable column access by name
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"Database error: {e}")
            raise
        finally:
            conn.close()
    
    def initialize(self):
        """Create database tables if they don't exist."""
        
        with self.get_connection() as conn:
            # Trades table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    trade_id TEXT UNIQUE,
                    timestamp TEXT NOT NULL,
                    match_id TEXT NOT NULL,
                    market_id TEXT,
                    side TEXT NOT NULL,
                    size REAL NOT NULL,
                    price REAL NOT NULL,
                    fair_price REAL,
                    edge REAL,
                    status TEXT,
                    filled_size REAL,
                    filled_price REAL,
                    pnl REAL,
                    is_paper INTEGER DEFAULT 1,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Matches table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS matches (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    match_id TEXT UNIQUE,
                    game TEXT NOT NULL,
                    team1_name TEXT,
                    team2_name TEXT,
                    winner INTEGER,
                    duration_seconds INTEGER,
                    start_time TEXT,
                    end_time TEXT,
                    total_trades INTEGER DEFAULT 0,
                    total_pnl REAL DEFAULT 0,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Sessions table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT UNIQUE,
                    start_time TEXT NOT NULL,
                    end_time TEXT,
                    initial_bankroll REAL,
                    final_bankroll REAL,
                    total_matches INTEGER DEFAULT 0,
                    total_trades INTEGER DEFAULT 0,
                    total_pnl REAL DEFAULT 0,
                    win_rate REAL,
                    sharpe_ratio REAL,
                    max_drawdown REAL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Events table (game events)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    match_id TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    game_time_seconds INTEGER,
                    event_type TEXT NOT NULL,
                    team INTEGER,
                    context TEXT,
                    fair_price_before REAL,
                    fair_price_after REAL,
                    market_price REAL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Price history table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS price_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    match_id TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    game_time_seconds INTEGER,
                    fair_price REAL,
                    market_price REAL,
                    team1_gold INTEGER,
                    team2_gold INTEGER,
                    team1_kills INTEGER,
                    team2_kills INTEGER,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Performance metrics table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS performance_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT NOT NULL,
                    metric_name TEXT NOT NULL,
                    metric_value REAL,
                    metadata TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create indexes for faster queries
            conn.execute("CREATE INDEX IF NOT EXISTS idx_trades_match ON trades(match_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_trades_timestamp ON trades(timestamp)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_events_match ON events(match_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_price_history_match ON price_history(match_id)")
            
            logger.info("Database tables initialized")
    
    # ================================================================
    # TRADE OPERATIONS
    # ================================================================
    
    def insert_trade(self, trade: Dict[str, Any]) -> int:
        """
        Insert a trade record.
        
        Args:
            trade: Trade data dictionary
            
        Returns:
            ID of inserted record
        """
        with self.get_connection() as conn:
            cursor = conn.execute("""
                INSERT INTO trades (
                    trade_id, timestamp, match_id, market_id, side,
                    size, price, fair_price, edge, status,
                    filled_size, filled_price, pnl, is_paper
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                trade.get('trade_id'),
                trade.get('timestamp', datetime.now().isoformat()),
                trade.get('match_id'),
                trade.get('market_id'),
                trade.get('side'),
                trade.get('size'),
                trade.get('price'),
                trade.get('fair_price'),
                trade.get('edge'),
                trade.get('status'),
                trade.get('filled_size'),
                trade.get('filled_price'),
                trade.get('pnl'),
                1 if trade.get('is_paper', True) else 0
            ))
            
            logger.debug(f"Inserted trade: {trade.get('trade_id')}")
            return cursor.lastrowid
    
    def update_trade_pnl(self, trade_id: str, pnl: float):
        """Update trade P&L after settlement."""
        with self.get_connection() as conn:
            conn.execute("""
                UPDATE trades SET pnl = ? WHERE trade_id = ?
            """, (pnl, trade_id))
            
            logger.debug(f"Updated trade {trade_id} P&L: {pnl}")
    
    def get_trade(self, trade_id: str) -> Optional[Dict]:
        """Get a single trade by ID."""
        with self.get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM trades WHERE trade_id = ?",
                (trade_id,)
            )
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def get_trades_by_match(self, match_id: str) -> List[Dict]:
        """Get all trades for a match."""
        with self.get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM trades WHERE match_id = ? ORDER BY timestamp",
                (match_id,)
            )
            return [dict(row) for row in cursor.fetchall()]
    
    def get_recent_trades(self, limit: int = 100) -> List[Dict]:
        """Get most recent trades."""
        with self.get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM trades ORDER BY timestamp DESC LIMIT ?",
                (limit,)
            )
            return [dict(row) for row in cursor.fetchall()]
    
    def get_trades_by_date_range(
        self,
        start_date: str,
        end_date: str
    ) -> List[Dict]:
        """Get trades within a date range."""
        with self.get_connection() as conn:
            cursor = conn.execute("""
                SELECT * FROM trades
                WHERE timestamp BETWEEN ? AND ?
                ORDER BY timestamp
            """, (start_date, end_date))
            return [dict(row) for row in cursor.fetchall()]
    
    # ================================================================
    # MATCH OPERATIONS
    # ================================================================
    
    def insert_match(self, match: Dict[str, Any]) -> int:
        """Insert a match record."""
        with self.get_connection() as conn:
            cursor = conn.execute("""
                INSERT OR REPLACE INTO matches (
                    match_id, game, team1_name, team2_name,
                    winner, duration_seconds, start_time, end_time,
                    total_trades, total_pnl
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                match.get('match_id'),
                match.get('game'),
                match.get('team1_name'),
                match.get('team2_name'),
                match.get('winner'),
                match.get('duration_seconds'),
                match.get('start_time'),
                match.get('end_time'),
                match.get('total_trades', 0),
                match.get('total_pnl', 0)
            ))
            
            logger.debug(f"Inserted match: {match.get('match_id')}")
            return cursor.lastrowid
    
    def update_match_results(
        self,
        match_id: str,
        winner: int,
        total_trades: int,
        total_pnl: float
    ):
        """Update match with final results."""
        with self.get_connection() as conn:
            conn.execute("""
                UPDATE matches
                SET winner = ?, total_trades = ?, total_pnl = ?, end_time = ?
                WHERE match_id = ?
            """, (winner, total_trades, total_pnl, datetime.now().isoformat(), match_id))
    
    def get_match(self, match_id: str) -> Optional[Dict]:
        """Get a single match by ID."""
        with self.get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM matches WHERE match_id = ?",
                (match_id,)
            )
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def get_recent_matches(self, limit: int = 50) -> List[Dict]:
        """Get most recent matches."""
        with self.get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM matches ORDER BY start_time DESC LIMIT ?",
                (limit,)
            )
            return [dict(row) for row in cursor.fetchall()]
    
    # ================================================================
    # SESSION OPERATIONS
    # ================================================================
    
    def insert_session(self, session: Dict[str, Any]) -> int:
        """Insert a trading session record."""
        with self.get_connection() as conn:
            cursor = conn.execute("""
                INSERT INTO sessions (
                    session_id, start_time, initial_bankroll
                ) VALUES (?, ?, ?)
            """, (
                session.get('session_id'),
                session.get('start_time', datetime.now().isoformat()),
                session.get('initial_bankroll')
            ))
            
            logger.debug(f"Inserted session: {session.get('session_id')}")
            return cursor.lastrowid
    
    def update_session(self, session_id: str, data: Dict[str, Any]):
        """Update session with final data."""
        with self.get_connection() as conn:
            conn.execute("""
                UPDATE sessions
                SET end_time = ?, final_bankroll = ?, total_matches = ?,
                    total_trades = ?, total_pnl = ?, win_rate = ?,
                    sharpe_ratio = ?, max_drawdown = ?
                WHERE session_id = ?
            """, (
                data.get('end_time', datetime.now().isoformat()),
                data.get('final_bankroll'),
                data.get('total_matches'),
                data.get('total_trades'),
                data.get('total_pnl'),
                data.get('win_rate'),
                data.get('sharpe_ratio'),
                data.get('max_drawdown'),
                session_id
            ))
    
    # ================================================================
    # EVENT OPERATIONS
    # ================================================================
    
    def insert_event(self, event: Dict[str, Any]) -> int:
        """Insert a game event record."""
        with self.get_connection() as conn:
            cursor = conn.execute("""
                INSERT INTO events (
                    match_id, timestamp, game_time_seconds, event_type,
                    team, context, fair_price_before, fair_price_after, market_price
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                event.get('match_id'),
                event.get('timestamp', datetime.now().isoformat()),
                event.get('game_time_seconds'),
                event.get('event_type'),
                event.get('team'),
                event.get('context'),
                event.get('fair_price_before'),
                event.get('fair_price_after'),
                event.get('market_price')
            ))
            return cursor.lastrowid
    
    def get_events_by_match(self, match_id: str) -> List[Dict]:
        """Get all events for a match."""
        with self.get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM events WHERE match_id = ? ORDER BY game_time_seconds",
                (match_id,)
            )
            return [dict(row) for row in cursor.fetchall()]
    
    # ================================================================
    # PRICE HISTORY OPERATIONS
    # ================================================================
    
    def insert_price_point(self, data: Dict[str, Any]) -> int:
        """Insert a price history point."""
        with self.get_connection() as conn:
            cursor = conn.execute("""
                INSERT INTO price_history (
                    match_id, timestamp, game_time_seconds,
                    fair_price, market_price,
                    team1_gold, team2_gold, team1_kills, team2_kills
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                data.get('match_id'),
                data.get('timestamp', datetime.now().isoformat()),
                data.get('game_time_seconds'),
                data.get('fair_price'),
                data.get('market_price'),
                data.get('team1_gold'),
                data.get('team2_gold'),
                data.get('team1_kills'),
                data.get('team2_kills')
            ))
            return cursor.lastrowid
    
    def get_price_history(self, match_id: str) -> List[Dict]:
        """Get price history for a match."""
        with self.get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM price_history WHERE match_id = ? ORDER BY game_time_seconds",
                (match_id,)
            )
            return [dict(row) for row in cursor.fetchall()]
    
    # ================================================================
    # PERFORMANCE METRICS
    # ================================================================
    
    def insert_metric(self, name: str, value: float, metadata: str = None):
        """Insert a performance metric."""
        with self.get_connection() as conn:
            conn.execute("""
                INSERT INTO performance_metrics (date, metric_name, metric_value, metadata)
                VALUES (?, ?, ?, ?)
            """, (datetime.now().date().isoformat(), name, value, metadata))
    
    def get_metrics_by_name(self, name: str, days: int = 30) -> List[Dict]:
        """Get metrics by name for recent days."""
        with self.get_connection() as conn:
            cursor = conn.execute("""
                SELECT * FROM performance_metrics
                WHERE metric_name = ?
                ORDER BY date DESC
                LIMIT ?
            """, (name, days))
            return [dict(row) for row in cursor.fetchall()]
    
    # ================================================================
    # STATISTICS QUERIES
    # ================================================================
    
    def get_trade_statistics(self) -> Dict[str, Any]:
        """Get overall trade statistics."""
        with self.get_connection() as conn:
            cursor = conn.execute("""
                SELECT
                    COUNT(*) as total_trades,
                    SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) as winning_trades,
                    SUM(CASE WHEN pnl < 0 THEN 1 ELSE 0 END) as losing_trades,
                    SUM(pnl) as total_pnl,
                    AVG(pnl) as avg_pnl,
                    MAX(pnl) as max_win,
                    MIN(pnl) as max_loss,
                    AVG(edge) as avg_edge,
                    AVG(size) as avg_size
                FROM trades
                WHERE pnl IS NOT NULL
            """)
            row = cursor.fetchone()
            return dict(row) if row else {}
    
    def get_daily_pnl(self, days: int = 30) -> List[Dict]:
        """Get daily P&L for recent days."""
        with self.get_connection() as conn:
            cursor = conn.execute("""
                SELECT
                    DATE(timestamp) as date,
                    COUNT(*) as trades,
                    SUM(pnl) as pnl,
                    AVG(edge) as avg_edge
                FROM trades
                WHERE pnl IS NOT NULL
                GROUP BY DATE(timestamp)
                ORDER BY date DESC
                LIMIT ?
            """, (days,))
            return [dict(row) for row in cursor.fetchall()]