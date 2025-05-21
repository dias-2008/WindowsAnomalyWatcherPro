#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Window Monitor Module

This module provides functionality for monitoring active window changes on Windows systems.
It detects suspicious window activity and tracks user interactions.
"""

import time
import logging
from datetime import datetime
import asyncio

# Import required modules
try:
    import win32gui
    import win32process
    import win32api
    import psutil
except ImportError:
    logging.error("Failed to import win32 or psutil modules. Make sure they are installed.")

from config.settings import WINDOW_POLL_INTERVAL
from utils.screenshot import take_screenshot


class WindowMonitor:
    """Monitors active window changes on Windows systems."""
    
    def __init__(self, event_grouper, paused_event, bot_loop):
        """Initialize the window monitor.
        
        Args:
            event_grouper: The event grouper to send events to.
            paused_event (threading.Event): Event to signal pause state.
        """
        self.event_grouper = event_grouper
        self._paused = paused_event
        self._bot_loop = bot_loop
        self.current_window = None
        self._last_active_window_info = None # Store information of the last window that triggered an event
        self.suspicious_titles = [
            "password", "login", "credential", "admin", "security",
            "hack", "crack", "keylogger", "spy", "remote access",
            "TeamViewer", "AnyDesk", "Remote Desktop", "VNC", "RDP"
        ]
        self.browser_process_names = [
            "chrome.exe", "firefox.exe", "msedge.exe", "opera.exe", "brave.exe"
        ]
        self.running = False
        logging.info("Window monitor initialized")
    
    def start(self):
        """Start monitoring active window changes."""
        self.running = True
        logging.info("Window monitoring started")
        
        async def _async_start():
            try:
                while self.running:
                    # Wait if paused
                    if self._paused.is_set():
                        logging.debug("WindowMonitor paused.")
                        self._paused.wait() # Block until the event is cleared
                        logging.debug("WindowMonitor resumed.")

                    await self._check_active_window()
                    await asyncio.sleep(WINDOW_POLL_INTERVAL)
            except Exception as e:
                logging.error(f"Error in window monitoring: {e}")
                self.running = False

        asyncio.run(_async_start())
    
    def stop(self):
        """Stop monitoring active window changes."""
        self.running = False
        logging.info("Window monitoring stopped")
    
    async def _check_active_window(self):
        """Check the currently active window and detect changes."""
        try:
            # Get the active window handle
            hwnd = win32gui.GetForegroundWindow()
            
            # Get window title
            title = win32gui.GetWindowText(hwnd)
            
            # Get process ID and name
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            process_name = "Unknown"
            process_path = "Unknown"
            if pid > 0:
                try:
                    process = psutil.Process(pid)
                    process_name = process.name()
                    process_path = process.exe()
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    process_name = "Unknown"
                    process_path = "Unknown"
            
            # Create window info
            window_info = {
                "hwnd": hwnd,
                "title": title,
                "pid": pid,
                "process_name": process_name,
                "process_path": process_path,
                "timestamp": datetime.now()
            }
            
            # Only proceed if process name and path were successfully retrieved
            if process_name != "Unknown" and process_path != "Unknown":
                # Check if window has changed
                if self._has_window_changed(window_info):
                    # Update the last active window info before handling the change
                    self._last_active_window_info = window_info
                    await self._handle_window_change(window_info)

                # Check for suspicious window titles
                if self._is_suspicious_window(window_info):
                    self._handle_suspicious_window(window_info)

                # Update current window (for _has_window_changed comparison in the next poll)
                self.current_window = window_info
            else:
                logging.debug(f"Skipping window change event due to unknown process details: Title='{title}', PID={pid}")

        except Exception as e:
            logging.error(f"Error checking active window: {e}")
    
    def _has_window_changed(self, window_info):
        """Check if the active window has changed significantly.
        
        Args:
            window_info (dict): Information about the current window.
        
        Returns:
            bool: True if the window has changed significantly, False otherwise.
        """
        if self._last_active_window_info is None:
            return True
            
        # Only consider it a significant change if the process has changed
        # or if it's a known browser and the title has changed.
        if self._last_active_window_info["process_name"] != window_info["process_name"]:
            return True

        # Check for title changes within the same browser process
        if window_info["process_name"].lower() in self.browser_process_names:
            if self._last_active_window_info["title"] != window_info["title"]:
                return True

        return False

    
    def _is_suspicious_window(self, window_info):
        """Check if the window title contains suspicious keywords.
        
        Args:
            window_info (dict): Information about the window.
        
        Returns:
            bool: True if the window is suspicious, False otherwise.
        """
        title = window_info["title"].lower()
        process_name = window_info["process_name"].lower()
        
        for keyword in self.suspicious_titles:
            if keyword.lower() in title or keyword.lower() in process_name:
                return True
        
        return False
    
    async def _handle_window_change(self, window_info):
        """Handle a window change event.
        
        Args:
            window_info (dict): Information about the new window.
        """
        try:
            # Create window event
            event = {
                "type": "window",
                "timestamp": window_info["timestamp"],
                "window_title": window_info["title"],
                "process_name": window_info["process_name"],
                "process_path": window_info["process_path"]
            }

            # Send event to event grouper
            if not self._paused.is_set():
                # Use run_coroutine_threadsafe to schedule the async call on the bot's event loop
                if self._bot_loop:
                    asyncio.run_coroutine_threadsafe(
                        self.event_grouper.add_event(event['type'], event_details=event),
                        self._bot_loop
                    )
                else:
                    logging.warning("Bot event loop not available in WindowMonitor.")
            else:
                logging.debug(f"Monitoring paused, not adding window change event: {window_info['title']}")
            
            logging.debug(f"Window changed: {window_info['title']} ({window_info['process_name']})")
            
        except Exception as e:
            logging.error(f"Error handling window change: {e}")
    
    async def _handle_suspicious_window(self, window_info):
        """Handle a suspicious window event.
        
        Args:
            window_info (dict): Information about the suspicious window.
        """
        try:
            # Create suspicious window event
            event = {
                "type": "suspicious_window",
                "timestamp": window_info["timestamp"],
                "title": window_info["title"],
                "process_name": window_info["process_name"],
                "process_path": window_info["process_path"]
            }

            # Send event to event grouper
            if not self._paused.is_set():
                # Use run_coroutine_threadsafe to schedule the async call on the bot's event loop
                if self._bot_loop:
                    asyncio.run_coroutine_threadsafe(
                        self.event_grouper.add_event(event['type'], event_details=event),
                        self._bot_loop
                    )
                else:
                    logging.warning("Bot event loop not available in WindowMonitor.")
            else:
                logging.debug(f"Monitoring paused, not adding suspicious window event: {window_info['title']}")

            logging.warning(f"Suspicious window detected: {window_info['title']} ({window_info['process_name']})")
            
        except Exception as e:
            logging.error(f"Error handling suspicious window: {e}")