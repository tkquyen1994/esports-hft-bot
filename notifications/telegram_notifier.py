"""
Telegram Notifier - Send alerts via Telegram.

Sends notifications for:
- Trade executions
- Match starts/ends
- Daily summaries
- Errors and warnings

Requires:
- TELEGRAM_BOT_TOKEN in .env
- TELEGRAM_CHAT_ID in .env
"""

import asyncio
import aiohttp
import logging
from datetime import datetime
from typing import Optional, Dict, Any, List
from enum import Enum

from config.settings import get_config

logger = logging.getLogger(__name__)
config = get_config()


class NotificationType(Enum):
    """Types of notifications."""
    TRADE = "trade"
    MATCH_START = "match_start"
    MATCH_END = "match_end"
    DAILY_SUMMARY = "daily_summary"
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class TelegramNotifier:
    """
    Sends notifications via Telegram bot.
    
    Usage:
        notifier = TelegramNotifier()
        
        # Check if configured
        if notifier.is_configured:
            await notifier.send_message("Hello from the bot!")
            await notifier.send_trade_alert(trade_data)
    """
    
    # Emoji mappings for different notification types
    EMOJIS = {
        NotificationType.TRADE: "💰",
        NotificationType.MATCH_START: "🎮",
        NotificationType.MATCH_END: "🏁",
        NotificationType.DAILY_SUMMARY: "📊",
        NotificationType.ERROR: "🚨",
        NotificationType.WARNING: "⚠️",
        NotificationType.INFO: "ℹ️",
    }
    
    def __init__(self):
        """Initialize the Telegram notifier."""
        self.bot_token = config.notifications.telegram_bot_token
        self.chat_id = config.notifications.telegram_chat_id
        self.enabled = config.notifications.enabled
        
        self._session: Optional[aiohttp.ClientSession] = None
        self._rate_limit_delay = 0.1  # Seconds between messages
        self._last_message_time = 0
        
        if self.is_configured:
            logger.info("TelegramNotifier initialized and configured")
        else:
            logger.warning("TelegramNotifier not configured - notifications disabled")
    
    @property
    def is_configured(self) -> bool:
        """Check if Telegram is properly configured."""
        return bool(self.bot_token and self.chat_id and self.enabled)
    
    @property
    def api_url(self) -> str:
        """Get the Telegram API base URL."""
        return f"https://api.telegram.org/bot{self.bot_token}"
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create HTTP session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session
    
    async def close(self):
        """Close the HTTP session."""
        if self._session and not self._session.closed:
            await self._session.close()
    
    async def send_message(
        self,
        text: str,
        parse_mode: str = "HTML",
        disable_notification: bool = False
    ) -> bool:
        """
        Send a text message via Telegram.
        
        Args:
            text: Message text (supports HTML formatting)
            parse_mode: "HTML" or "Markdown"
            disable_notification: If True, send silently
            
        Returns:
            True if message sent successfully
        """
        if not self.is_configured:
            logger.debug(f"Telegram not configured, skipping: {text[:50]}...")
            return False
        
        # Rate limiting
        now = asyncio.get_event_loop().time()
        if now - self._last_message_time < self._rate_limit_delay:
            await asyncio.sleep(self._rate_limit_delay)
        
        try:
            session = await self._get_session()
            
            url = f"{self.api_url}/sendMessage"
            payload = {
                "chat_id": self.chat_id,
                "text": text,
                "parse_mode": parse_mode,
                "disable_notification": disable_notification
            }
            
            async with session.post(url, json=payload) as response:
                self._last_message_time = asyncio.get_event_loop().time()
                
                if response.status == 200:
                    logger.debug(f"Telegram message sent: {text[:50]}...")
                    return True
                else:
                    error = await response.text()
                    logger.error(f"Telegram API error: {response.status} - {error}")
                    return False
                    
        except Exception as e:
            logger.error(f"Failed to send Telegram message: {e}")
            return False
    
    async def send_trade_alert(
        self,
        side: str,
        size: float,
        price: float,
        edge: float,
        match_id: str,
        team1: str = "Team 1",
        team2: str = "Team 2",
        pnl: Optional[float] = None
    ) -> bool:
        """
        Send a trade execution alert.
        
        Args:
            side: BUY or SELL
            size: Position size
            price: Execution price
            edge: Edge at trade time
            match_id: Match identifier
            team1: Team 1 name
            team2: Team 2 name
            pnl: Realized P&L if available
        """
        emoji = "🟢" if side == "BUY" else "🔴"
        pnl_str = f"\n💵 P&L: <b>${pnl:.2f}</b>" if pnl is not None else ""
        
        message = f"""
{self.EMOJIS[NotificationType.TRADE]} <b>TRADE EXECUTED</b>

{emoji} <b>{side}</b> {size:.1f} shares @ ${price:.3f}
📊 Edge: {edge:.2%}
🎮 Match: {team1} vs {team2}{pnl_str}
🕐 {datetime.now().strftime('%H:%M:%S')}
"""
        
        return await self.send_message(message.strip())
    
    async def send_match_start(
        self,
        match_id: str,
        team1: str,
        team2: str,
        game: str = "LoL"
    ) -> bool:
        """Send notification when a match starts."""
        message = f"""
{self.EMOJIS[NotificationType.MATCH_START]} <b>MATCH STARTED</b>

🏆 {team1} vs {team2}
🎮 Game: {game}
🆔 ID: {match_id}
🕐 {datetime.now().strftime('%H:%M:%S')}

Bot is now monitoring this match.
"""
        
        return await self.send_message(message.strip())
    
    async def send_match_end(
        self,
        match_id: str,
        team1: str,
        team2: str,
        winner: int,
        total_trades: int,
        total_pnl: float,
        duration_minutes: float
    ) -> bool:
        """Send notification when a match ends."""
        winner_name = team1 if winner == 1 else team2
        pnl_emoji = "📈" if total_pnl >= 0 else "📉"
        
        message = f"""
{self.EMOJIS[NotificationType.MATCH_END]} <b>MATCH ENDED</b>

🏆 Winner: <b>{winner_name}</b>
🎮 {team1} vs {team2}
⏱ Duration: {duration_minutes:.1f} min

<b>Trading Results:</b>
{pnl_emoji} P&L: <b>${total_pnl:.2f}</b>
📊 Trades: {total_trades}
"""
        
        return await self.send_message(message.strip())
    
    async def send_daily_summary(
        self,
        total_matches: int,
        total_trades: int,
        total_pnl: float,
        win_rate: float,
        bankroll: float,
        best_trade: float,
        worst_trade: float
    ) -> bool:
        """Send daily performance summary."""
        pnl_emoji = "📈" if total_pnl >= 0 else "📉"
        
        message = f"""
{self.EMOJIS[NotificationType.DAILY_SUMMARY]} <b>DAILY SUMMARY</b>
📅 {datetime.now().strftime('%Y-%m-%d')}

<b>Performance:</b>
{pnl_emoji} Total P&L: <b>${total_pnl:.2f}</b>
💰 Bankroll: ${bankroll:.2f}
📊 Win Rate: {win_rate:.1%}

<b>Activity:</b>
🎮 Matches: {total_matches}
💹 Trades: {total_trades}

<b>Best/Worst:</b>
🏆 Best Trade: ${best_trade:.2f}
💔 Worst Trade: ${worst_trade:.2f}
"""
        
        return await self.send_message(message.strip())
    
    async def send_error(
        self,
        error_message: str,
        context: str = ""
    ) -> bool:
        """Send error alert."""
        message = f"""
{self.EMOJIS[NotificationType.ERROR]} <b>ERROR ALERT</b>

❌ {error_message}
{f'📍 Context: {context}' if context else ''}
🕐 {datetime.now().strftime('%H:%M:%S')}

Please check the bot logs.
"""
        
        return await self.send_message(message.strip(), disable_notification=False)
    
    async def send_warning(
        self,
        warning_message: str,
        context: str = ""
    ) -> bool:
        """Send warning alert."""
        message = f"""
{self.EMOJIS[NotificationType.WARNING]} <b>WARNING</b>

⚠️ {warning_message}
{f'📍 {context}' if context else ''}
🕐 {datetime.now().strftime('%H:%M:%S')}
"""
        
        return await self.send_message(message.strip(), disable_notification=True)
    
    async def send_info(
        self,
        info_message: str
    ) -> bool:
        """Send informational message."""
        message = f"""
{self.EMOJIS[NotificationType.INFO]} {info_message}
"""
        
        return await self.send_message(message.strip(), disable_notification=True)
    
    async def send_startup_message(
        self,
        bankroll: float,
        mode: str = "Paper Trading"
    ) -> bool:
        """Send bot startup notification."""
        message = f"""
🚀 <b>BOT STARTED</b>

✅ Esports HFT Bot is now running
💰 Bankroll: ${bankroll:.2f}
📋 Mode: {mode}
🕐 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

Ready to trade!
"""
        
        return await self.send_message(message.strip())
    
    async def send_shutdown_message(
        self,
        reason: str = "Normal shutdown",
        final_pnl: Optional[float] = None
    ) -> bool:
        """Send bot shutdown notification."""
        pnl_str = f"\n💰 Session P&L: ${final_pnl:.2f}" if final_pnl is not None else ""
        
        message = f"""
🛑 <b>BOT STOPPED</b>

📋 Reason: {reason}{pnl_str}
🕐 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        
        return await self.send_message(message.strip())
    
    async def test_connection(self) -> bool:
        """
        Test the Telegram connection.
        
        Returns:
            True if connection successful
        """
        if not self.is_configured:
            logger.warning("Telegram not configured")
            return False
        
        try:
            session = await self._get_session()
            url = f"{self.api_url}/getMe"
            
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    bot_name = data.get('result', {}).get('username', 'Unknown')
                    logger.info(f"Telegram connection successful: @{bot_name}")
                    return True
                else:
                    logger.error(f"Telegram connection failed: {response.status}")
                    return False
                    
        except Exception as e:
            logger.error(f"Telegram connection test failed: {e}")
            return False