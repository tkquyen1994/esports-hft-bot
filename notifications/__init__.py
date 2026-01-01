"""
Notifications module - Alert system for the trading bot.

Usage:
    from notifications import NotificationManager
    
    manager = NotificationManager()
    await manager.start()
    
    # Send notifications
    await manager.notify_trade(
        side="BUY",
        size=10.0,
        price=0.55,
        edge=0.05,
        match_id="match_001",
        team1="Cloud9",
        team2="Team Liquid"
    )
    
    await manager.notify_error("Connection lost", context="PandaScore API")
    
    await manager.stop()
"""

from .telegram_notifier import TelegramNotifier, NotificationType
from .notification_manager import NotificationManager, NotificationPriority

__all__ = [
    "TelegramNotifier",
    "NotificationType",
    "NotificationManager",
    "NotificationPriority",
]