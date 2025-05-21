#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Windows Anomaly Watcher PRO - Main Entry Point

This is the main entry point for the Windows Anomaly Watcher PRO application.
It handles initialization, first-run setup, and starts the monitoring services.
"""

import os
import sys
import time
import logging
import threading
from pathlib import Path
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

# Add project root to path to ensure imports work correctly
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Internal imports
from config.config_manager import ConfigManager
from config.settings import APP_NAME, VERSION, DEFAULT_SETTINGS
from utils.logger import setup_logger
from utils.system_utils import hide_console_window, add_to_startup
from setup.setup_gui import show_setup_gui
from telegram_bot.bot import TelegramBot
from monitoring.window_monitor import WindowMonitor
from monitoring.process_monitor import ProcessMonitor
from monitoring.usb_monitor import USBMonitor
from monitoring.file_monitor import FileMonitor
from monitoring.event_grouper import EventGrouper
from i18n.translator import Translator
from typing import Optional
import asyncio


class Application:
    """Main application class."""
    def __init__(self):
        logging.debug("Application __init__ started.")
        self.config: Optional[ConfigManager] = None
        self.translator = None
        self.telegram_bot = None
        self.monitors = []
        self.monitor_threads = []
        self.pause_timer = None
        self._paused = threading.Event() # Event to signal pause state
        self._is_monitoring_running = False # Track if monitoring is running
        # Hide console window in production
        if getattr(sys, 'frozen', False):
            hide_console_window()

        # Setup logging
        setup_logger()

        # Log application start
        logging.info(f"Starting {APP_NAME} v{VERSION}")

        # Initialize ConfigManager
        logging.debug("Initializing ConfigManager.")
        self.config = ConfigManager()
        logging.debug("ConfigManager initialized.")

        # Check if config file exists (first run)
        if not self.config.config_file.exists():
            logging.info("Config file not found. Running first-time setup.")
            # Load default settings before showing setup GUI
            self.config.config = DEFAULT_SETTINGS.copy()
            # Show setup GUI
            logging.debug("Showing setup GUI.")
            setup_completed = show_setup_gui(self.config)
            logging.debug(f"Setup GUI completed. Success: {setup_completed}")
            if not setup_completed:
                logging.error("Setup not completed. Exiting.")
                sys.exit(1) # Exit if setup is not completed
            # Save the initial configuration after setup
            logging.debug("Saving initial configuration after setup.")
            self.config.save()
            logging.debug("Initial configuration saved.")

        # Reload configuration after setup might have saved new settings
        # Or load existing config if not first run
        # Ensure config is loaded before initializing components that depend on it
        logging.debug("Loading configuration after potential setup.")
        self.config.load()
        logging.debug("Configuration loaded.")

        # Ensure default monitored folders if not set
        monitored_folders = self.config.get('monitored_folders', [])
        if not monitored_folders:
            default_folders = DEFAULT_SETTINGS['monitored_folders']
            logging.info(f"Setting default monitored folders: {default_folders}")
            self.config.set('monitored_folders', default_folders)

        logging.info(f"Monitored folders: {self.config.get('monitored_folders')}")
        logging.info(f"Configuration after setup: {self.config.config}")
        # Initialize translator with configured language
        logging.debug("Initializing Translator.")
        self.translator = Translator(str(self.config.get('language', 'en')))
        logging.debug("Translator initialized.")

        # Add to startup if enabled
        if self.config.get('start_with_windows', True):
            logging.debug("Attempting to add to startup.")
            add_to_startup()
            logging.debug("Add to startup process completed.")

    def start_monitoring(self):
        """Start all monitoring services."""
        logging.debug("start_monitoring called.")
        if self.config is None:
            logging.error("Configuration not initialized. Cannot start monitoring.")
            return

        if self._is_monitoring_running:
            # Check if translator is initialized before calling get()
            if self.translator:
                logging.info(self.translator.get("monitoring_already_running"))
            else:
                logging.info("Monitoring is already running")
            return # Exit if already running

        self._is_monitoring_running = True

        # Initialize event grouper
        logging.info("Initializing event grouper")
        # Initialize event grouper
        # Pass the telegram_bot instance and the paused event to the EventGrouper
        self.event_grouper = EventGrouper(self.telegram_bot, self.translator, self._paused)
        logging.info("Event grouper initialized")

        # Get monitored folders from config
        monitored_folders = self.config.get('monitored_folders', [])
        logging.info(f"Using monitored folders from config: {monitored_folders}")

        # Initialize and start monitors
        logging.info("Initializing monitoring services")
        # Pass the bot's event loop to the monitors
        bot_loop = self.telegram_bot._bot_loop if self.telegram_bot else None
        self.monitors = [
            WindowMonitor(self.event_grouper, self._paused, bot_loop),
            ProcessMonitor(self.event_grouper, self._paused, bot_loop),
            USBMonitor(self.event_grouper, self._paused, bot_loop),
            FileMonitor(self.event_grouper, monitored_folders, self._paused, bot_loop)
        ]

        # Start all ors in separate threads
        self.monitor_threads = []
        for monitor in self.monitors:
            monitor_name = monitor.__class__.__name__
            logging.info(f"{monitor_name} initialized")
            
            # Log monitored folders for FileMonitor
            if monitor_name == 'FileMonitor':
                logging.info(f"FileMonitor configured with folders: {monitored_folders}")
            
            thread = threading.Thread(target=monitor.start, daemon=True)
            thread.start()
            self.monitor_threads.append(thread)
            logging.info(f"Started {monitor_name} successfully")
    
    def pause_monitoring(self, minutes):
        """Pause monitoring for specified minutes."""
        logging.info(f"Attempting to pause monitoring for {minutes} minutes")

        # Cancel any existing timer
        if self.pause_timer:
            logging.info("Cancelling existing pause timer.")
            self.pause_timer.cancel()

        # Signal monitors to pause
        self._paused.set()
        logging.info(f"Monitoring paused signal set for {minutes} minutes")

        # Set up timer to resume monitoring
        self.pause_timer = threading.Timer(minutes * 60, self.resume_monitoring)
        self.pause_timer.daemon = True
        self.pause_timer.start()

    def start_pause_selection(self):
        """Immediately sets the paused state for buffering events when pause is initiated."""
        logging.info("Immediately setting paused state for pause selection.")
        self._paused.set()
        # Clear any buffered events that occurred before initiating pause selection
        if self.event_grouper:
            self.event_grouper.clear_paused_buffered_events()


    def resume_monitoring(self):
        """Resume monitoring after pause."""
        logging.info("Attempting to resume monitoring")
        # Clear the paused signal
        self._paused.clear()
        self.pause_timer = None
        logging.info("Monitoring pause signal cleared. Resuming monitoring.")

        # Send notification that monitoring has resumed and offer review
        if self.telegram_bot:
            asyncio.run_coroutine_threadsafe(
                self.telegram_bot.send_resume_notification(),
                self.telegram_bot._bot_loop # Use the bot's event loop
            )



    async def run(self):
        """Main application entry point."""
        logging.debug("Application run method started.")
        try:
            # Initialize application
            logging.debug("Calling initialize_app.")
            self.initialize_app()
            logging.info("Application initialized successfully")

            # Initialize Telegram bot, passing the main application instance
            logging.debug("Initializing TelegramBot.")
            self.telegram_bot = TelegramBot(self.config, self.translator, app_instance=self)
            logging.debug("TelegramBot initialized.")
            # Start the Telegram bot (this will start its internal polling thread)
            logging.debug("Starting TelegramBot polling.")
            self.telegram_bot.start()

            logging.info("Telegram bot thread started")

            # Wait for the bot polling to be ready before sending the startup message
            logging.debug("Waiting for Telegram bot polling to be ready.")
            if self.telegram_bot._polling_ready_event.wait(timeout=15): # Wait up to 15 seconds for polling to start
                logging.info("Telegram bot polling is ready.")
                # Send startup notification
                try:
                    logging.debug("Attempting to send startup notification.")
                    # Create inline keyboard for startup message
                    startup_keyboard = [
                        [InlineKeyboardButton(self.translator.get("telegram.buttons.start_monitoring"), callback_data='start_monitoring')],
                        [InlineKeyboardButton(self.translator.get("telegram.buttons.stop_monitoring"), callback_data='stop_monitoring')]
                    ]
                    startup_reply_markup = InlineKeyboardMarkup(startup_keyboard)
                    await self.telegram_bot.send_message(self.translator.get("application_started_successfully"), reply_markup=startup_reply_markup)
                    logging.info("Sent startup notification via Telegram")
                    logging.debug("Startup notification sent.")
                except Exception as e:
                    logging.error(f"Failed to send startup notification: {e}")

                # Monitoring will now start only when the user presses the button in Telegram.
                # self.start_monitoring()
                # logging.info(self.translator.get("monitoring_started"))
                # logging.info(f"Started {len(self.monitor_threads)} monitoring threads")
            else:
                logging.warning("Telegram bot polling did not become ready within the timeout. Cannot send startup notification.")
            
            # Keep the main thread alive
            try:
                while True:
                    await asyncio.sleep(1)
            except KeyboardInterrupt:
                logging.info("KeyboardInterrupt received, initiating shutdown.")

        except Exception as e:
            logging.exception(f"An unhandled exception occurred: {e}")
            sys.exit(1)
        finally:
            # Ensure graceful shutdown
            await self.shutdown()

    async def shutdown(self):
        """Handles graceful application shutdown."""
        logging.info("Application shutting down...")
        # Stop Telegram bot polling if it's running
        if self.telegram_bot:
            try:
                # Stop the bot synchronously
                logging.info("Stopping Telegram bot...")
                # Ensure the bot's event loop is running before stopping
                # Use the synchronous shutdown method
                self.telegram_bot.shutdown()
                logging.info("Telegram bot stopped.")
            except Exception as e:
                logging.error(f"Error stopping Telegram bot: {e}")
        # Add any other cleanup logic here
        logging.info("Application shutdown complete.")

    def initialize_app(self):
        """Initializes core application components."""
        logging.debug("initialize_app method started.")
        # This method is currently empty in the provided code snippet.
        # Add any necessary initialization steps here if needed in the future.
        pass

    def stop_monitoring(self):
        """Stop all monitoring services."""
        logging.debug("stop_monitoring called.")
        if not self._is_monitoring_running:
            logging.info(self.translator.get("monitoring_already_stopped"))
            logging.info(self.translator.get("monitoring_stopped"))
            # Send Telegram notification
            if self.telegram_bot:
                asyncio.run_coroutine_threadsafe(
                    self.telegram_bot.send_message(self.translator.get("telegram.monitoring_stopped")),
                    self.telegram_bot._bot_loop
                )
            
            self._is_monitoring_running = False
            # Signal monitors to stop
            self.monitors = []
            self.monitor_threads = []

    def start_pause_selection(self):
        """Immediately sets the paused state for buffering events when pause is initiated."""
        logging.info("Immediately setting paused state for pause selection.")
        self._paused.set()
        # Clear any buffered events that occurred before initiating pause selection
        if self.event_grouper:
            self.event_grouper.clear_paused_buffered_events()


    def resume_monitoring(self):
        """Resume monitoring after pause."""
        logging.info("Attempting to resume monitoring")
        # Clear the paused signal
        self._paused.clear()
        self.pause_timer = None
        logging.info("Monitoring pause signal cleared. Resuming monitoring.")

        # Send notification that monitoring has resumed and offer review
        if self.telegram_bot:
            asyncio.run_coroutine_threadsafe(
                self.telegram_bot.send_resume_notification(),
                self.telegram_bot._bot_loop # Use the bot's event loop
            )



    async def run(self):
        """Main application entry point."""
        logging.debug("Application run method started.")
        try:
            # Initialize application
            logging.debug("Calling initialize_app.")
            self.initialize_app()
            logging.info("Application initialized successfully")

            # Initialize Telegram bot, passing the main application instance
            logging.debug("Initializing TelegramBot.")
            self.telegram_bot = TelegramBot(self.config, self.translator, app_instance=self)
            logging.debug("TelegramBot initialized.")
            # Start the Telegram bot (this will start its internal polling thread)
            logging.debug("Starting TelegramBot polling.")
            self.telegram_bot.start()

            logging.info("Telegram bot thread started")

            # Wait for the bot polling to be ready before sending the startup message
            logging.debug("Waiting for Telegram bot polling to be ready.")
            if self.telegram_bot._polling_ready_event.wait(timeout=15): # Wait up to 15 seconds for polling to start
                logging.info("Telegram bot polling is ready.")
                # Send startup notification
                try:
                    logging.debug("Attempting to send startup notification.")
                    # Create inline keyboard for startup message
                    startup_keyboard = [
                        [InlineKeyboardButton(self.translator.get("telegram.buttons.start_monitoring"), callback_data='start_monitoring')],
                        [InlineKeyboardButton(self.translator.get("telegram.buttons.stop_monitoring"), callback_data='stop_monitoring')]
                    ]
                    startup_reply_markup = InlineKeyboardMarkup(startup_keyboard)
                    await self.telegram_bot.send_message(self.translator.get("application_started_successfully"), reply_markup=startup_reply_markup)
                    logging.info("Sent startup notification via Telegram")
                    logging.debug("Startup notification sent.")
                except Exception as e:
                    logging.error(f"Failed to send startup notification: {e}")

                # Monitoring will now start only when the user presses the button in Telegram.
                # self.start_monitoring()
                # logging.info(self.translator.get("monitoring_started"))
                # logging.info(f"Started {len(self.monitor_threads)} monitoring threads")
            else:
                logging.warning("Telegram bot polling did not become ready within the timeout. Cannot send startup notification.")
            
            # Keep the main thread alive
            try:
                while True:
                    await asyncio.sleep(1)
            except KeyboardInterrupt:
                logging.info("KeyboardInterrupt received, initiating shutdown.")

        except Exception as e:
            logging.exception(f"An unhandled exception occurred: {e}")
            sys.exit(1)
        finally:
            # Ensure graceful shutdown
            await self.shutdown()

    async def shutdown(self):
        """Handles graceful application shutdown."""
        logging.info("Application shutting down...")
        # Stop Telegram bot polling if it's running
        if self.telegram_bot:
            try:
                # Stop the bot synchronously
                logging.info("Stopping Telegram bot...")
                # Ensure the bot's event loop is running before stopping
                # Use the synchronous shutdown method
                self.telegram_bot.shutdown()
                logging.info("Telegram bot stopped.")
            except Exception as e:
                logging.error(f"Error stopping Telegram bot: {e}")
        # Add any other cleanup logic here
        logging.info("Application shutdown complete.")

if __name__ == "__main__":
    app = Application()
    asyncio.run(app.run())