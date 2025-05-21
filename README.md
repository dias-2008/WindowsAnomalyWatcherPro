# Windows Anomaly Watcher PRO

A modular Windows monitoring application that runs silently in the background and sends alerts to Telegram when suspicious activities are detected.

## Features

- **Silent Background Operation**: Runs without any visible windows or tray icons
- **Automatic Startup**: Launches on Windows boot
- **Telegram Integration**: Sends alerts and allows remote control via Telegram bot
- **Smart Event Grouping**: Groups related events to avoid spam
- **Comprehensive Monitoring**:
  - Window focus changes
  - USB device connections/disconnections
  - Process launches
  - File modifications
- **Multilingual Support**: English and Russian
- **Simple First-Run Setup**: GUI for initial configuration
- **Security Features**: Code obfuscation and protection against reverse engineering

## Project Structure

```
WindowsAnomalyWatcherPRO/
├── config/                  # Configuration files and settings
│   ├── __init__.py
│   ├── config_manager.py    # Manages app configuration
│   └── settings.py          # Default settings and constants
├── data/                    # Data storage
│   └── .gitkeep
├── i18n/                    # Internationalization
│   ├── __init__.py
│   ├── en.json              # English translations
│   ├── ru.json              # Russian translations
│   └── translator.py        # Translation utilities
├── monitoring/              # System monitoring modules
│   ├── __init__.py
│   ├── event_grouper.py     # Groups related events
│   ├── file_monitor.py      # Monitors file changes
│   ├── process_monitor.py   # Monitors process creation/termination
│   ├── usb_monitor.py       # Monitors USB device connections
│   └── window_monitor.py    # Monitors window focus changes
├── setup/                   # First-run setup
│   ├── __init__.py
│   ├── setup_gui.py         # GUI for initial configuration
│   └── installer.py         # Installation utilities
├── telegram_bot/            # Telegram bot integration
│   ├── __init__.py
│   ├── bot.py               # Main bot functionality
│   ├── commands.py          # Bot command handlers
│   └── keyboards.py         # Inline keyboard utilities
├── utils/                   # Utility functions
│   ├── __init__.py
│   ├── crypto.py            # Encryption utilities
│   ├── logger.py            # Logging utilities
│   ├── screenshot.py        # Screenshot utilities
│   └── system_utils.py      # System-related utilities
├── .gitignore
├── main.py                  # Application entry point
├── README.md
└── requirements.txt         # Project dependencies
```

## Installation

1. Clone the repository
2. Install dependencies: `pip install -r requirements.txt`
3. Run the application: `python main.py`

## Building

To build the application as a standalone executable:

```
pyinstaller --onefile --noconsole --name WindowsAnomalyWatcherPRO main.py
```

For additional protection, use PyArmor before packaging with PyInstaller.