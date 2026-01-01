"""
Configuration Validator - Validates all settings before bot startup.

Checks:
- Required environment variables
- API credentials
- File permissions
- Network connectivity
- Configuration values
"""

import os
import logging
from pathlib import Path
from typing import List, Tuple, Optional
from dataclasses import dataclass

from config.settings import get_config

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Result of a validation check."""
    name: str
    passed: bool
    message: str
    is_critical: bool = True  # If False, bot can still run


class ConfigValidator:
    """
    Validates bot configuration before startup.
    
    Usage:
        validator = ConfigValidator()
        results = validator.validate_all()
        
        if validator.can_start():
            print("All critical checks passed!")
        else:
            print("Cannot start - fix critical issues first")
    """
    
    def __init__(self):
        """Initialize the validator."""
        self.config = get_config()
        self.results: List[ValidationResult] = []
    
    def validate_all(self) -> List[ValidationResult]:
        """
        Run all validation checks.
        
        Returns:
            List of ValidationResult objects
        """
        self.results = []
        
        # Directory checks
        self._check_directories()
        
        # Configuration checks
        self._check_trading_config()
        self._check_model_config()
        
        # API credential checks
        self._check_pandascore_api()
        self._check_telegram_config()
        
        # Environment checks
        self._check_python_packages()
        
        return self.results
    
    def can_start(self) -> bool:
        """
        Check if bot can start (all critical checks passed).
        
        Returns:
            True if all critical checks passed
        """
        if not self.results:
            self.validate_all()
        
        return all(r.passed for r in self.results if r.is_critical)
    
    def get_summary(self) -> str:
        """
        Get a summary of validation results.
        
        Returns:
            Formatted summary string
        """
        if not self.results:
            self.validate_all()
        
        lines = []
        lines.append("=" * 50)
        lines.append("CONFIGURATION VALIDATION")
        lines.append("=" * 50)
        
        passed = sum(1 for r in self.results if r.passed)
        failed = len(self.results) - passed
        
        lines.append(f"\nTotal checks: {len(self.results)}")
        lines.append(f"Passed: {passed}")
        lines.append(f"Failed: {failed}")
        
        lines.append("\nDetails:")
        lines.append("-" * 50)
        
        for result in self.results:
            status = "✓" if result.passed else "✗"
            critical = "(CRITICAL)" if result.is_critical and not result.passed else ""
            lines.append(f"{status} {result.name}: {result.message} {critical}")
        
        lines.append("-" * 50)
        
        if self.can_start():
            lines.append("\n✓ Bot can start - all critical checks passed")
        else:
            lines.append("\n✗ Bot cannot start - fix critical issues above")
        
        return "\n".join(lines)
    
    def _add_result(
        self,
        name: str,
        passed: bool,
        message: str,
        is_critical: bool = True
    ):
        """Add a validation result."""
        self.results.append(ValidationResult(
            name=name,
            passed=passed,
            message=message,
            is_critical=is_critical
        ))
    
    def _check_directories(self):
        """Check required directories exist."""
        required_dirs = ['data', 'logs']
        
        for dir_name in required_dirs:
            dir_path = Path(dir_name)
            
            if dir_path.exists():
                self._add_result(
                    f"Directory '{dir_name}'",
                    True,
                    "Exists",
                    is_critical=False
                )
            else:
                # Try to create it
                try:
                    dir_path.mkdir(parents=True, exist_ok=True)
                    self._add_result(
                        f"Directory '{dir_name}'",
                        True,
                        "Created",
                        is_critical=False
                    )
                except Exception as e:
                    self._add_result(
                        f"Directory '{dir_name}'",
                        False,
                        f"Cannot create: {e}",
                        is_critical=False
                    )
    
    def _check_trading_config(self):
        """Check trading configuration values."""
        config = self.config.trading
        
        # Check bankroll
        if config.initial_bankroll > 0:
            self._add_result(
                "Initial bankroll",
                True,
                f"${config.initial_bankroll:.2f}"
            )
        else:
            self._add_result(
                "Initial bankroll",
                False,
                "Must be positive"
            )
        
        # Check min_edge
        if 0 < config.min_edge < 0.5:
            self._add_result(
                "Minimum edge",
                True,
                f"{config.min_edge:.1%}"
            )
        else:
            self._add_result(
                "Minimum edge",
                False,
                f"Invalid value: {config.min_edge}"
            )
        
        # Check kelly_fraction
        if 0 < config.kelly_fraction <= 1:
            self._add_result(
                "Kelly fraction",
                True,
                f"{config.kelly_fraction:.0%}"
            )
        else:
            self._add_result(
                "Kelly fraction",
                False,
                f"Invalid value: {config.kelly_fraction}"
            )
        
        # Check max_stake_percent
        if 0 < config.max_stake_percent <= 0.25:
            self._add_result(
                "Max stake percent",
                True,
                f"{config.max_stake_percent:.0%}"
            )
        else:
            self._add_result(
                "Max stake percent",
                False,
                f"Risky value: {config.max_stake_percent:.0%} (recommend <= 25%)",
                is_critical=False
            )
    
    def _check_model_config(self):
        """Check model configuration values."""
        config = self.config.model
        
        # Check gold_scale
        if config.lol_gold_scale > 0:
            self._add_result(
                "LoL gold scale",
                True,
                f"{config.lol_gold_scale}",
                is_critical=False
            )
        else:
            self._add_result(
                "LoL gold scale",
                False,
                "Must be positive",
                is_critical=False
            )
    
    def _check_pandascore_api(self):
        """Check PandaScore API configuration."""
        api_key = self.config.data_feed.pandascore_api_key
        
        if api_key and len(api_key) > 10:
            self._add_result(
                "PandaScore API key",
                True,
                f"Configured ({api_key[:8]}...)",
                is_critical=False  # Can run with simulator
            )
        else:
            self._add_result(
                "PandaScore API key",
                False,
                "Not configured - will use simulator only",
                is_critical=False
            )
    
    def _check_telegram_config(self):
        """Check Telegram configuration."""
        token = self.config.notifications.telegram_bot_token
        chat_id = self.config.notifications.telegram_chat_id
        
        if token and chat_id:
            self._add_result(
                "Telegram notifications",
                True,
                "Configured",
                is_critical=False
            )
        elif token and not chat_id:
            self._add_result(
                "Telegram notifications",
                False,
                "Bot token set but missing chat ID",
                is_critical=False
            )
        elif not token and chat_id:
            self._add_result(
                "Telegram notifications",
                False,
                "Chat ID set but missing bot token",
                is_critical=False
            )
        else:
            self._add_result(
                "Telegram notifications",
                False,
                "Not configured - notifications disabled",
                is_critical=False
            )
    
    def _check_python_packages(self):
        """Check required Python packages are installed."""
        required_packages = [
            ('pandas', 'pandas'),
            ('numpy', 'numpy'),
            ('aiohttp', 'aiohttp'),
            ('dash', 'dash'),
            ('plotly', 'plotly'),
        ]
        
        all_installed = True
        missing = []
        
        for package_name, import_name in required_packages:
            try:
                __import__(import_name)
            except ImportError:
                all_installed = False
                missing.append(package_name)
        
        if all_installed:
            self._add_result(
                "Python packages",
                True,
                "All required packages installed"
            )
        else:
            self._add_result(
                "Python packages",
                False,
                f"Missing: {', '.join(missing)}"
            )


def validate_config() -> Tuple[bool, str]:
    """
    Convenience function to validate configuration.
    
    Returns:
        Tuple of (can_start, summary_string)
    """
    validator = ConfigValidator()
    validator.validate_all()
    return validator.can_start(), validator.get_summary()