#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Settings Module

This module contains default settings and constants for the Windows Anomaly Watcher PRO application.
"""

import os
from pathlib import Path

# Application information
APP_NAME = "Windows Anomaly Watcher PRO"
VERSION = "1.0.0"
AUTHOR = "Windows Anomaly Watcher Team"

# Paths
APP_DIR = Path(__file__).parent.parent
DATA_DIR = APP_DIR / "data"
CONFIG_DIR = APP_DIR / "config"
LOG_DIR = DATA_DIR / "logs"

# Configuration file
CONFIG_FILE = DATA_DIR / "config.json"

# Encryption
ENCRYPTION_KEY_FILE = DATA_DIR / "crypto.key"
ENCRYPTION_SALT = b"WindowsAnomalyWatcherPRO_Salt_2023"

# Logging
LOG_FILE = LOG_DIR / "app.log"
LOG_LEVEL = "INFO"  # DEBUG, INFO, WARNING, ERROR, CRITICAL
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
LOG_MAX_SIZE = 10 * 1024 * 1024  # 10 MB
LOG_BACKUP_COUNT = 5

# Telegram
TELEGRAM_API_URL = "https://api.telegram.org"
TELEGRAM_POLL_INTERVAL = 1.0  # seconds
TELEGRAM_TIMEOUT = 60  # seconds
TELEGRAM_PROXY_URL = None  # Set to proxy URL if needed (e.g., 'http://user:pass@host:port' or 'socks5://user:pass@host:port')

# Monitoring
MONITORING_INTERVAL = 0.5  # seconds
WINDOW_POLL_INTERVAL = 0.5  # seconds
PROCESS_POLL_INTERVAL = 1.0  # seconds
USB_POLL_INTERVAL = 2.0  # seconds
FILE_POLL_INTERVAL = 1.0  # seconds

# Screenshot
SCREENSHOT_RATE_LIMIT_SECONDS = 60 # Default rate limit of 60 seconds

# Event grouping
EVENT_GROUP_TIMEOUT = 5  # seconds
MAX_EVENTS_PER_GROUP = 10

EVENT_GROUPING_INTERVAL = 60  # seconds
EVENT_GROUPING_THRESHOLD = 500

# System file alert grouping
SYSTEM_FILE_ALERT_THRESHOLD = 3  # Minimum alerts to group before sending
SYSTEM_FILE_ALERT_WINDOW = 60  # Time window in seconds for grouping similar alerts

# USB Event Grouping
USB_GROUPING_TIMEOUT = 5  # seconds

# Suspicious processes (lowercase)
SUSPICIOUS_PROCESSES = [
    "cmd.exe",
    "powershell.exe",
    "wscript.exe",
    "cscript.exe",
    "reg.exe",
    "regedit.exe",
    "taskmgr.exe",
    "mmc.exe",
    "netsh.exe",
    "psexec.exe",
    "mimikatz.exe",
    "procdump.exe",
    "wireshark.exe",
    "processhacker.exe",
    "autoruns.exe",
    "tcpview.exe",
    "procexp.exe",
    "procmon.exe"
]

# Suspicious file extensions (lowercase)
SUSPICIOUS_EXTENSIONS = [
    ".exe",
    ".bat",
    ".cmd",
    ".ps1",
    ".vbs",
    ".js",
    ".hta",
    ".scr",
    ".dll",
    ".sys"
]

# Default settings
DEFAULT_SETTINGS = {
    "language": "en",
    "start_with_windows": True,
    "telegram_token": "",
    "telegram_chat_id": "",
    "telegram_proxy_url": None,  # New setting for proxy support
    "monitored_folders": [
        os.path.expanduser("~\Desktop"),
        os.path.expanduser("~\Documents")
    ],
    "monitoring_enabled": True,
    "window_monitoring": True,
    "process_monitoring": True,
    "usb_monitoring": True,
    "file_monitoring": True,
    "notify_file_deletion": True,
    "notify_suspicious_file_modified": True,
    "system_file_alert_threshold": SYSTEM_FILE_ALERT_THRESHOLD,
    "system_file_alert_window": SYSTEM_FILE_ALERT_WINDOW
}

# Translations (add new keys here)
TRANSLATIONS = {
    "en": {
        "alerts.window.title": "Window Activity Detected",
        "alerts.window.activity_detected": "Activity detected",
        "alerts.file_created.title": "File Created",
        "alerts.file_modified.title": "File Modified",
        "alerts.file_deleted.title": "File Deleted",
        "alerts.file_moved.title": "File Moved",
        "alerts.suspicious_file_created.title": "Suspicious File Created",
        "alerts.suspicious_file_modified.title": "Suspicious File Modified",
        "alerts.process_created.title": "Process Created",
        "alerts.process_terminated.title": "Process Terminated",
        "alerts.suspicious_process.title": "Suspicious Process Detected",
        "alerts.usb_connected.title": "USB Device Connected",
        "alerts.usb_disconnected.title": "USB Device Disconnected",
        "alerts.grouped_file_activity.title": "File/Folder Activity Detected",
        "telegram.buttons.yes_its_me": "Yes, it's me ✅",
        "telegram.buttons.show_details": "Show Details 📋",
        "telegram.buttons.lock_pc": "Lock PC 🔒",
        "telegram.buttons.shutdown_pc": "Shutdown PC 🔌",
        "telegram.buttons.take_screenshot": "Screenshot 📸",
        "telegram.buttons.acknowledge": "Acknowledge",
        "telegram.buttons.ignore": "Ignore",
        "application_started_successfully": "Application started successfully."
    }
}