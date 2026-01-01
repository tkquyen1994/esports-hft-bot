"""
Notification Manager - Unified interface for all notifications.

Manages:
- Multiple notification channels (Telegram, future: Discord, Email)
- Notification queuing and rate limiting
- Notification preferences and filtering
- Daily summary scheduling
"""

import asyncio
import logging
from datetime import datetime, time
from typing import Optional, Dict, Any, List, Callable
from dataclasses import dataclass, field
from enum import Enum

from .telegram_notifier import TelegramNotifier, NotificationType

logger = logging.getLogger(__name__)


class NotificationPriority(Enum):
    """Notification priority levels."""
    LOW = 1      # Info messages, can be batched
    NORMAL = 2   # Regular trade alerts
    HIGH = 3     # Important events (match end, warnings)
    CRITICAL = 4 # Errors, must send immediately


@dataclass
class Notification:
    """A notification to be sent."""
    type: NotificationType
    priority: NotificationPriority
    title: str
    message: str
    data: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)


class NotificationManager:
    """
    Centralized notification management.
    
    Usage:
        manager = NotificationManager()
        await manager.start()
        
        # Send notifications
        await manager.notify_trade(trade_data)
        await manager.notify_match_start(match_data)
        await manager.notify_error("Connection lost")
        
        await manager.stop()
    """
    
    def __init__(self):
        """Initialize the notification manager."""
        self.telegram = TelegramNotifier()
        
        # Notification queue
        self._queue: asyncio.Queue = asyncio.Queue()
        self._running = False
        self._worker_task: Optional[asyncio.Task] = None
        
        # Statistics
        self.notifications_sent = 0
        self.notifications_failed = 0
        
        # Preferences
        self.trade_notifications = True
        self.match_notifications = True
        self.error_notifications = True
        self.daily_summary_enabled = True
        self.daily_summary_time = time(hour=23, minute=59)  # 11:59 PM
        
        # Daily summary data
        self._daily_trades = 0
        self._daily_pnl = 0.0
        self._daily_matches = 0
        self._daily_wins = 0
        self._best_trade = 0.0
        self._worst_trade = 0.0
        
        logger.info("NotificationManager initialized")
    
    async def start(self):
        """Start the notification manager."""
        self._running = True
        self._worker_task = asyncio.create_task(self._process_queue())
        
        # Test connection
        if self.telegram.is_configured:
            connected = await self.telegram.test_connection()
            if connected:
                logger.info("Notification manager started with Telegram")
            else:
                logger.warning("Telegram connection test failed")
        else:
            logger.info("Notification manager started (Telegram not configured)")
    
    async def stop(self):
        """Stop the notification manager."""
        self._running = False
        
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
        
        await self.telegram.close()
        logger.info("Notification manager stopped")
    
    async def _process_queue(self):
        """Process notification queue."""
        while self._running:
            try:
                # Wait for notification with timeout
                try:
                    notification = await asyncio.wait_for(
                        self._queue.get(),
                        timeout=1.0
                    )
                except asyncio.TimeoutError:
                    continue
                
                # Process notification
                success = await self._send_notification(notification)
                
                if success:
                    self.notifications_sent += 1
                else:
                    self.notifications_failed += 1
                
                self._queue.task_done()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error processing notification: {e}")
    
    async def _send_notification(self, notification: Notification) -> bool:
        """Send a notification through appropriate channels."""
        try:
            # Currently only Telegram, but can add more channels
            if notification.type == NotificationType.TRADE:
                return await self.telegram.send_trade_alert(**notification.data)
            
            elif notification.type == NotificationType.MATCH_START:
                return await self.telegram.send_match_start(**notification.data)
            
            elif notification.type == NotificationType.MATCH_END:
                return await self.telegram.send_match_end(**notification.data)
            
            elif notification.type == NotificationType.DAILY_SUMMARY:
                return await self.telegram.send_daily_summary(**notification.data)
            
            elif notification.type == NotificationType.ERROR:
                return await self.telegram.send_error(
                    notification.message,
                    notification.data.get('context', '')
                )
            
            elif notification.type == NotificationType.WARNING:
                return await self.telegram.send_warning(
                    notification.message,
                    notification.data.get('context', '')
                )
            
            elif notification.type == NotificationType.INFO:
                return await self.telegram.send_info(notification.message)
            
            else:
                return await self.telegram.send_message(notification.message)
                
        except Exception as e:
            logger.error(f"Failed to send notification: {e}")
            return False
    
    def _enqueue(self, notification: Notification):
        """Add notification to queue."""
        try:
            self._queue.put_nowait(notification)
        except asyncio.QueueFull:
            logger.warning("Notification queue full, dropping notification")
    
    # ================================================================
    # PUBLIC NOTIFICATION METHODS
    # ================================================================
    
    async def notify_trade(
        self,
        side: str,
        size: float,
        price: float,
        edge: float,
        match_id: str,
        team1: str = "Team 1",
        team2: str = "Team 2",
        pnl: Optional[float] = None
    ):
        """
        Send trade notification.
        
        Also updates daily statistics.
        """
        if not self.trade_notifications:
            return
        
        # Update daily stats
        self._daily_trades += 1
        if pnl is not None:
            self._daily_pnl += pnl
            if pnl > 0:
                self._daily_wins += 1
            self._best_trade = max(self._best_trade, pnl)
            self._worst_trade = min(self._worst_trade, pnl)
        
        notification = Notification(
            type=NotificationType.TRADE,
            priority=NotificationPriority.NORMAL,
            title="Trade Executed",
            message=f"{side} {size} @ {price}",
            data={
                'side': side,
                'size': size,
                'price': price,
                'edge': edge,
                'match_id': match_id,
                'team1': team1,
                'team2': team2,
                'pnl': pnl
            }
        )
        
        self._enqueue(notification)
    
    async def notify_match_start(
        self,
        match_id: str,
        team1: str,
        team2: str,
        game: str = "LoL"
    ):
        """Send match start notification."""
        if not self.match_notifications:
            return
        
        self._daily_matches += 1
        
        notification = Notification(
            type=NotificationType.MATCH_START,
            priority=NotificationPriority.NORMAL,
            title="Match Started",
            message=f"{team1} vs {team2}",
            data={
                'match_id': match_id,
                'team1': team1,
                'team2': team2,
                'game': game
            }
        )
        
        self._enqueue(notification)
    
    async def notify_match_end(
        self,
        match_id: str,
        team1: str,
        team2: str,
        winner: int,
        total_trades: int,
        total_pnl: float,
        duration_minutes: float
    ):
        """Send match end notification."""
        if not self.match_notifications:
            return
        
        notification = Notification(
            type=NotificationType.MATCH_END,
            priority=NotificationPriority.HIGH,
            title="Match Ended",
            message=f"{team1} vs {team2} - Winner: T{winner}",
            data={
                'match_id': match_id,
                'team1': team1,
                'team2': team2,
                'winner': winner,
                'total_trades': total_trades,
                'total_pnl': total_pnl,
                'duration_minutes': duration_minutes
            }
        )
        
        self._enqueue(notification)
    
    async def notify_error(
        self,
        error_message: str,
        context: str = ""
    ):
        """Send error notification (high priority)."""
        if not self.error_notifications:
            return
        
        notification = Notification(
            type=NotificationType.ERROR,
            priority=NotificationPriority.CRITICAL,
            title="Error",
            message=error_message,
            data={'context': context}
        )
        
        self._enqueue(notification)
    
    async def notify_warning(
        self,
        warning_message: str,
        context: str = ""
    ):
        """Send warning notification."""
        notification = Notification(
            type=NotificationType.WARNING,
            priority=NotificationPriority.HIGH,
            title="Warning",
            message=warning_message,
            data={'context': context}
        )
        
        self._enqueue(notification)
    
    async def notify_info(self, message: str):
        """Send info notification."""
        notification = Notification(
            type=NotificationType.INFO,
            priority=NotificationPriority.LOW,
            title="Info",
            message=message
        )
        
        self._enqueue(notification)
    
    async def send_startup(self, bankroll: float, mode: str = "Paper Trading"):
        """Send bot startup notification."""
        await self.telegram.send_startup_message(bankroll, mode)
    
    async def send_shutdown(
        self,
        reason: str = "Normal shutdown",
        final_pnl: Optional[float] = None
    ):
        """Send bot shutdown notification."""
        await self.telegram.send_shutdown_message(reason, final_pnl)
    
    async def send_daily_summary(self, bankroll: float):
        """Send daily summary notification."""
        if not self.daily_summary_enabled:
            return
        
        win_rate = self._daily_wins / self._daily_trades if self._daily_trades > 0 else 0
        
        notification = Notification(
            type=NotificationType.DAILY_SUMMARY,
            priority=NotificationPriority.NORMAL,
            title="Daily Summary",
            message="Daily performance report",
            data={
                'total_matches': self._daily_matches,
                'total_trades': self._daily_trades,
                'total_pnl': self._daily_pnl,
                'win_rate': win_rate,
                'bankroll': bankroll,
                'best_trade': self._best_trade,
                'worst_trade': self._worst_trade
            }
        )
        
        self._enqueue(notification)
    
    def reset_daily_stats(self):
        """Reset daily statistics (call at midnight)."""
        self._daily_trades = 0
        self._daily_pnl = 0.0
        self._daily_matches = 0
        self._daily_wins = 0
        self._best_trade = 0.0
        self._worst_trade = 0.0
    
    def get_stats(self) -> Dict[str, Any]:
        """Get notification statistics."""
        return {
            'notifications_sent': self.notifications_sent,
            'notifications_failed': self.notifications_failed,
            'queue_size': self._queue.qsize(),
            'daily_trades': self._daily_trades,
            'daily_pnl': self._daily_pnl
        }