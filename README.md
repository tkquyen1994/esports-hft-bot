# Esports HFT Trading Bot

A high-frequency trading bot for esports prediction markets on Polymarket.

## Features

- **Probability Engine** - Real-time win probability calculation based on game events
- **Live Data Feeds** - PandaScore API integration for LoL/Dota 2 game data
- **Trading System** - Edge detection with Kelly criterion position sizing
- **Backtesting** - Historical data analysis and strategy testing
- **Dashboard** - Real-time web interface for monitoring
- **Notifications** - Telegram alerts for trades and events

## Project Structure
```
esports-hft-bot/
├── config/          # Configuration and settings
├── connectors/      # API connectors (PandaScore, Polymarket)
├── core/            # Probability engine and models
├── trading/         # Trading logic and risk management
├── analysis/        # Backtesting engine
├── dashboard/       # Web dashboard
├── storage/         # Database and logging
├── notifications/   # Telegram notifications
└── utils/           # Health monitoring and utilities
```

## Setup

1. Clone the repository
2. Create virtual environment: `python -m venv venv`
3. Activate: `source venv/bin/activate`
4. Install dependencies: `pip install -r requirements.txt`
5. Copy `.env.example` to `.env` and fill in your API keys
6. Run: `python main.py`

## Configuration

Copy `.env.example` to `.env` and configure:

- `PANDASCORE_API_KEY` - For live game data
- `POLYMARKET_API_KEY` - For trading
- `TELEGRAM_BOT_TOKEN` - For notifications

## ⚠️ Disclaimer

This bot is for educational purposes. Trading involves risk. Always use paper trading mode first.

## License

MIT
