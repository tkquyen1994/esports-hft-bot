"""
Trade Repository - High-level interface for trade storage.

Provides easy-to-use methods for:
- Saving trades
- Retrieving trade history
- Calculating statistics
- Generating reports

This layer abstracts the database operations.
"""

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
from dataclasses import asdict

from core import Trade, OrderSide, TradeStatus
from .database import DatabaseManager
from .logger import TradingLogger

logger = logging.getLogger(__name__)


class TradeRepository:
    """
    Repository for trade data storage and retrieval.
    
    Usage:
        repo = TradeRepository()
        
        # Save a trade
        repo.save_trade(trade)
        
        # Get trade history
        trades = repo.get_recent_trades(limit=50)
        
        # Get statistics
        stats = repo.get_statistics()
    """
    
    def __init__(self, db_path: str = "data/trading.db"):
        """
        Initialize the trade repository.
        
        Args:
            db_path: Path to SQLite database
        """
        self.db = DatabaseManager(db_path)
        self.db.initialize()
        
        logger.info("TradeRepository initialized")
    
    def save_trade(self, trade: Trade) -> int:
        """
        Save a trade to the database.
        
        Args:
            trade: Trade object to save
            
        Returns:
            Database record ID
        """
        trade_data = {
            'trade_id': trade.id,
            'timestamp': trade.timestamp.isoformat() if trade.timestamp else datetime.now().isoformat(),
            'match_id': trade.market_id,  # Using market_id as match_id
            'market_id': trade.market_id,
            'side': trade.side.value if trade.side else None,
            'size': trade.size,
            'price': trade.price,
            'fair_price': trade.fair_price,
            'edge': trade.edge,
            'status': trade.status.value if trade.status else None,
            'filled_size': trade.filled_size,
            'filled_price': trade.filled_price,
            'pnl': trade.realized_pnl,
            'is_paper': trade.is_paper
        }
        
        record_id = self.db.insert_trade(trade_data)
        
        # Also log the trade
        TradingLogger.log_trade(
            side=trade.side.value if trade.side else "UNKNOWN",
            size=trade.size,
            price=trade.price,
            edge=trade.edge or 0,
            match_id=trade.market_id,
            pnl=trade.realized_pnl
        )
        
        return record_id
    
    def update_trade_pnl(self, trade_id: str, pnl: float):
        """
        Update trade with realized P&L.
        
        Args:
            trade_id: Trade identifier
            pnl: Realized P&L
        """
        self.db.update_trade_pnl(trade_id, pnl)
        logger.debug(f"Updated trade {trade_id} P&L: ${pnl:.2f}")
    
    def get_trade(self, trade_id: str) -> Optional[Dict]:
        """
        Get a single trade by ID.
        
        Args:
            trade_id: Trade identifier
            
        Returns:
            Trade data dictionary or None
        """
        return self.db.get_trade(trade_id)
    
    def get_trades_by_match(self, match_id: str) -> List[Dict]:
        """
        Get all trades for a specific match.
        
        Args:
            match_id: Match identifier
            
        Returns:
            List of trade dictionaries
        """
        return self.db.get_trades_by_match(match_id)
    
    def get_recent_trades(self, limit: int = 100) -> List[Dict]:
        """
        Get most recent trades.
        
        Args:
            limit: Maximum number of trades to return
            
        Returns:
            List of trade dictionaries
        """
        return self.db.get_recent_trades(limit)
    
    def get_trades_today(self) -> List[Dict]:
        """Get all trades from today."""
        today = datetime.now().date().isoformat()
        tomorrow = (datetime.now().date() + timedelta(days=1)).isoformat()
        return self.db.get_trades_by_date_range(today, tomorrow)
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get comprehensive trade statistics.
        
        Returns:
            Dictionary with statistics
        """
        raw_stats = self.db.get_trade_statistics()
        
        if not raw_stats or raw_stats.get('total_trades', 0) == 0:
            return {
                'total_trades': 0,
                'winning_trades': 0,
                'losing_trades': 0,
                'win_rate': 0.0,
                'total_pnl': 0.0,
                'avg_pnl': 0.0,
                'max_win': 0.0,
                'max_loss': 0.0,
                'avg_edge': 0.0,
                'avg_size': 0.0,
                'profit_factor': 0.0
            }
        
        total = raw_stats.get('total_trades', 0)
        winning = raw_stats.get('winning_trades', 0)
        losing = raw_stats.get('losing_trades', 0)
        
        # Calculate profit factor
        max_win = raw_stats.get('max_win', 0) or 0
        max_loss = abs(raw_stats.get('max_loss', 0) or 0)
        profit_factor = winning / losing if losing > 0 else float('inf')
        
        return {
            'total_trades': total,
            'winning_trades': winning,
            'losing_trades': losing,
            'win_rate': winning / total if total > 0 else 0.0,
            'total_pnl': raw_stats.get('total_pnl', 0) or 0,
            'avg_pnl': raw_stats.get('avg_pnl', 0) or 0,
            'max_win': max_win,
            'max_loss': -max_loss,
            'avg_edge': raw_stats.get('avg_edge', 0) or 0,
            'avg_size': raw_stats.get('avg_size', 0) or 0,
            'profit_factor': profit_factor
        }
    
    def get_daily_performance(self, days: int = 30) -> List[Dict]:
        """
        Get daily P&L breakdown.
        
        Args:
            days: Number of days to retrieve
            
        Returns:
            List of daily performance records
        """
        return self.db.get_daily_pnl(days)
    
    def generate_report(self) -> str:
        """
        Generate a text report of trading performance.
        
        Returns:
            Formatted report string
        """
        stats = self.get_statistics()
        daily = self.get_daily_performance(7)
        
        report = []
        report.append("=" * 50)
        report.append("TRADING PERFORMANCE REPORT")
        report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append("=" * 50)
        
        report.append("\nOVERALL STATISTICS:")
        report.append(f"  Total Trades: {stats['total_trades']}")
        report.append(f"  Winning Trades: {stats['winning_trades']}")
        report.append(f"  Losing Trades: {stats['losing_trades']}")
        report.append(f"  Win Rate: {stats['win_rate']:.1%}")
        report.append(f"  Total P&L: ${stats['total_pnl']:.2f}")
        report.append(f"  Avg P&L/Trade: ${stats['avg_pnl']:.2f}")
        report.append(f"  Largest Win: ${stats['max_win']:.2f}")
        report.append(f"  Largest Loss: ${stats['max_loss']:.2f}")
        report.append(f"  Avg Edge: {stats['avg_edge']:.2%}")
        report.append(f"  Profit Factor: {stats['profit_factor']:.2f}")
        
        if daily:
            report.append("\nDAILY BREAKDOWN (Last 7 days):")
            report.append(f"  {'Date':<12} {'Trades':<8} {'P&L':<12} {'Avg Edge':<10}")
            report.append(f"  {'-'*12} {'-'*8} {'-'*12} {'-'*10}")
            
            for day in daily[:7]:
                date = day.get('date', 'Unknown')
                trades = day.get('trades', 0)
                pnl = day.get('pnl', 0) or 0
                edge = day.get('avg_edge', 0) or 0
                report.append(f"  {date:<12} {trades:<8} ${pnl:<11.2f} {edge:<.2%}")
        
        report.append("\n" + "=" * 50)
        
        return "\n".join(report)


class MatchRepository:
    """
    Repository for match data storage and retrieval.
    """
    
    def __init__(self, db_path: str = "data/trading.db"):
        """Initialize the match repository."""
        self.db = DatabaseManager(db_path)
        self.db.initialize()
    
    def save_match(
        self,
        match_id: str,
        game: str,
        team1_name: str,
        team2_name: str,
        start_time: datetime = None
    ) -> int:
        """Save a new match."""
        match_data = {
            'match_id': match_id,
            'game': game,
            'team1_name': team1_name,
            'team2_name': team2_name,
            'start_time': (start_time or datetime.now()).isoformat()
        }
        return self.db.insert_match(match_data)
    
    def update_match_result(
        self,
        match_id: str,
        winner: int,
        total_trades: int,
        total_pnl: float
    ):
        """Update match with final results."""
        self.db.update_match_results(match_id, winner, total_trades, total_pnl)
    
    def get_match(self, match_id: str) -> Optional[Dict]:
        """Get match by ID."""
        return self.db.get_match(match_id)
    
    def get_recent_matches(self, limit: int = 50) -> List[Dict]:
        """Get recent matches."""
        return self.db.get_recent_matches(limit)


class EventRepository:
    """
    Repository for game event storage.
    """
    
    def __init__(self, db_path: str = "data/trading.db"):
        """Initialize the event repository."""
        self.db = DatabaseManager(db_path)
        self.db.initialize()
    
    def save_event(
        self,
        match_id: str,
        event_type: str,
        team: int,
        context: str,
        game_time_seconds: int,
        fair_price_before: float,
        fair_price_after: float,
        market_price: float
    ) -> int:
        """Save a game event."""
        event_data = {
            'match_id': match_id,
            'timestamp': datetime.now().isoformat(),
            'game_time_seconds': game_time_seconds,
            'event_type': event_type,
            'team': team,
            'context': context,
            'fair_price_before': fair_price_before,
            'fair_price_after': fair_price_after,
            'market_price': market_price
        }
        return self.db.insert_event(event_data)
    
    def get_events_by_match(self, match_id: str) -> List[Dict]:
        """Get all events for a match."""
        return self.db.get_events_by_match(match_id)