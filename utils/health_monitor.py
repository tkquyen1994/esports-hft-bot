"""
Health Monitor - Tracks bot health and handles recovery.

Monitors:
- Component status (connectors, trading, etc.)
- Error rates
- Memory usage
- Latency metrics
- Automatic recovery attempts
"""

import asyncio
import logging
import time
import psutil
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Callable, List
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class HealthStatus(Enum):
    """Health status levels."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class ComponentHealth:
    """Health status of a single component."""
    name: str
    status: HealthStatus = HealthStatus.UNKNOWN
    last_check: Optional[datetime] = None
    last_success: Optional[datetime] = None
    error_count: int = 0
    message: str = ""
    
    def mark_healthy(self, message: str = "OK"):
        """Mark component as healthy."""
        self.status = HealthStatus.HEALTHY
        self.last_check = datetime.now()
        self.last_success = datetime.now()
        self.error_count = 0
        self.message = message
    
    def mark_unhealthy(self, message: str):
        """Mark component as unhealthy."""
        self.status = HealthStatus.UNHEALTHY
        self.last_check = datetime.now()
        self.error_count += 1
        self.message = message
    
    def mark_degraded(self, message: str):
        """Mark component as degraded."""
        self.status = HealthStatus.DEGRADED
        self.last_check = datetime.now()
        self.message = message


@dataclass
class HealthMetrics:
    """Overall health metrics."""
    uptime_seconds: float = 0
    total_errors: int = 0
    events_processed: int = 0
    trades_executed: int = 0
    
    # Latency tracking
    avg_event_latency_ms: float = 0
    avg_trade_latency_ms: float = 0
    
    # Memory
    memory_usage_mb: float = 0
    memory_percent: float = 0
    
    # Rates
    events_per_minute: float = 0
    trades_per_minute: float = 0
    errors_per_minute: float = 0


class HealthMonitor:
    """
    Monitors bot health and coordinates recovery.
    
    Usage:
        monitor = HealthMonitor()
        
        # Register components
        monitor.register_component("data_feed")
        monitor.register_component("trading")
        
        # Start monitoring
        await monitor.start()
        
        # Update health from components
        monitor.mark_healthy("data_feed")
        monitor.mark_unhealthy("trading", "Connection lost")
        
        # Get health report
        report = monitor.get_health_report()
        
        await monitor.stop()
    """
    
    def __init__(self, check_interval_seconds: float = 30):
        """
        Initialize the health monitor.
        
        Args:
            check_interval_seconds: How often to run health checks
        """
        self.check_interval = check_interval_seconds
        self.start_time = datetime.now()
        
        # Components
        self.components: Dict[str, ComponentHealth] = {}
        
        # Metrics
        self.metrics = HealthMetrics()
        
        # Tracking
        self._event_times: List[float] = []
        self._trade_times: List[float] = []
        self._error_times: List[float] = []
        self._latencies: List[float] = []
        
        # Control
        self._running = False
        self._monitor_task: Optional[asyncio.Task] = None
        
        # Callbacks
        self._on_unhealthy: Optional[Callable] = None
        self._on_recovery: Optional[Callable] = None
        
        logger.info("HealthMonitor initialized")
    
    def register_component(self, name: str):
        """Register a component to monitor."""
        self.components[name] = ComponentHealth(name=name)
        logger.debug(f"Registered component: {name}")
    
    def set_callbacks(
        self,
        on_unhealthy: Optional[Callable] = None,
        on_recovery: Optional[Callable] = None
    ):
        """Set callback functions for health events."""
        self._on_unhealthy = on_unhealthy
        self._on_recovery = on_recovery
    
    async def start(self):
        """Start the health monitor."""
        self._running = True
        self.start_time = datetime.now()
        self._monitor_task = asyncio.create_task(self._monitor_loop())
        logger.info("HealthMonitor started")
    
    async def stop(self):
        """Stop the health monitor."""
        self._running = False
        
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
        
        logger.info("HealthMonitor stopped")
    
    async def _monitor_loop(self):
        """Main monitoring loop."""
        while self._running:
            try:
                await self._run_health_checks()
                await asyncio.sleep(self.check_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Health check error: {e}")
                await asyncio.sleep(5)
    
    async def _run_health_checks(self):
        """Run all health checks."""
        # Update metrics
        self._update_metrics()
        
        # Check for stale components
        now = datetime.now()
        stale_threshold = timedelta(minutes=5)
        
        for name, component in self.components.items():
            if component.last_success:
                time_since_success = now - component.last_success
                
                if time_since_success > stale_threshold:
                    if component.status != HealthStatus.UNHEALTHY:
                        component.mark_degraded(
                            f"No success for {time_since_success.seconds}s"
                        )
        
        # Log health status
        overall = self.get_overall_status()
        if overall != HealthStatus.HEALTHY:
            logger.warning(f"Bot health: {overall.value}")
    
    def _update_metrics(self):
        """Update health metrics."""
        now = time.time()
        
        # Calculate uptime
        self.metrics.uptime_seconds = (datetime.now() - self.start_time).total_seconds()
        
        # Calculate rates (events in last minute)
        one_minute_ago = now - 60
        
        self._event_times = [t for t in self._event_times if t > one_minute_ago]
        self._trade_times = [t for t in self._trade_times if t > one_minute_ago]
        self._error_times = [t for t in self._error_times if t > one_minute_ago]
        
        self.metrics.events_per_minute = len(self._event_times)
        self.metrics.trades_per_minute = len(self._trade_times)
        self.metrics.errors_per_minute = len(self._error_times)
        
        # Calculate average latency
        recent_latencies = self._latencies[-100:]  # Last 100
        if recent_latencies:
            self.metrics.avg_event_latency_ms = sum(recent_latencies) / len(recent_latencies)
        
        # Memory usage
        try:
            process = psutil.Process()
            memory_info = process.memory_info()
            self.metrics.memory_usage_mb = memory_info.rss / (1024 * 1024)
            self.metrics.memory_percent = process.memory_percent()
        except Exception:
            pass
    
    # ================================================================
    # PUBLIC METHODS
    # ================================================================
    
    def mark_healthy(self, component: str, message: str = "OK"):
        """Mark a component as healthy."""
        if component in self.components:
            was_unhealthy = self.components[component].status == HealthStatus.UNHEALTHY
            self.components[component].mark_healthy(message)
            
            # Trigger recovery callback
            if was_unhealthy and self._on_recovery:
                try:
                    self._on_recovery(component)
                except Exception as e:
                    logger.error(f"Recovery callback error: {e}")
    
    def mark_unhealthy(self, component: str, message: str):
        """Mark a component as unhealthy."""
        if component in self.components:
            was_healthy = self.components[component].status == HealthStatus.HEALTHY
            self.components[component].mark_unhealthy(message)
            
            # Trigger unhealthy callback
            if was_healthy and self._on_unhealthy:
                try:
                    self._on_unhealthy(component, message)
                except Exception as e:
                    logger.error(f"Unhealthy callback error: {e}")
    
    def mark_degraded(self, component: str, message: str):
        """Mark a component as degraded."""
        if component in self.components:
            self.components[component].mark_degraded(message)
    
    def record_event(self):
        """Record an event was processed."""
        self._event_times.append(time.time())
        self.metrics.events_processed += 1
    
    def record_trade(self):
        """Record a trade was executed."""
        self._trade_times.append(time.time())
        self.metrics.trades_executed += 1
    
    def record_error(self):
        """Record an error occurred."""
        self._error_times.append(time.time())
        self.metrics.total_errors += 1
    
    def record_latency(self, latency_ms: float):
        """Record event processing latency."""
        self._latencies.append(latency_ms)
        # Keep last 1000
        if len(self._latencies) > 1000:
            self._latencies = self._latencies[-1000:]
    
    def get_overall_status(self) -> HealthStatus:
        """Get overall bot health status."""
        if not self.components:
            return HealthStatus.UNKNOWN
        
        statuses = [c.status for c in self.components.values()]
        
        if all(s == HealthStatus.HEALTHY for s in statuses):
            return HealthStatus.HEALTHY
        elif any(s == HealthStatus.UNHEALTHY for s in statuses):
            return HealthStatus.UNHEALTHY
        elif any(s == HealthStatus.DEGRADED for s in statuses):
            return HealthStatus.DEGRADED
        else:
            return HealthStatus.UNKNOWN
    
    def get_health_report(self) -> Dict[str, Any]:
        """Get comprehensive health report."""
        self._update_metrics()
        
        return {
            'overall_status': self.get_overall_status().value,
            'uptime_seconds': self.metrics.uptime_seconds,
            'uptime_formatted': self._format_uptime(),
            'components': {
                name: {
                    'status': comp.status.value,
                    'message': comp.message,
                    'error_count': comp.error_count,
                    'last_check': comp.last_check.isoformat() if comp.last_check else None
                }
                for name, comp in self.components.items()
            },
            'metrics': {
                'events_processed': self.metrics.events_processed,
                'trades_executed': self.metrics.trades_executed,
                'total_errors': self.metrics.total_errors,
                'events_per_minute': self.metrics.events_per_minute,
                'trades_per_minute': self.metrics.trades_per_minute,
                'errors_per_minute': self.metrics.errors_per_minute,
                'avg_latency_ms': self.metrics.avg_event_latency_ms,
                'memory_mb': self.metrics.memory_usage_mb,
                'memory_percent': self.metrics.memory_percent
            }
        }
    
    def _format_uptime(self) -> str:
        """Format uptime as human-readable string."""
        seconds = int(self.metrics.uptime_seconds)
        
        hours, remainder = divmod(seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        
        if hours > 0:
            return f"{hours}h {minutes}m {seconds}s"
        elif minutes > 0:
            return f"{minutes}m {seconds}s"
        else:
            return f"{seconds}s"
    
    def get_summary(self) -> str:
        """Get a text summary of health status."""
        report = self.get_health_report()
        
        lines = []
        lines.append(f"Status: {report['overall_status'].upper()}")
        lines.append(f"Uptime: {report['uptime_formatted']}")
        lines.append(f"Events: {report['metrics']['events_processed']}")
        lines.append(f"Trades: {report['metrics']['trades_executed']}")
        lines.append(f"Errors: {report['metrics']['total_errors']}")
        lines.append(f"Memory: {report['metrics']['memory_mb']:.1f} MB")
        
        return " | ".join(lines)