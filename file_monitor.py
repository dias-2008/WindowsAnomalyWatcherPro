#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
File Monitor Module

This module provides functionality for monitoring file system changes on Windows systems.
It detects file creation, modification, and deletion events in specified directories.
"""

import os
import time
import logging
from datetime import datetime
from pathlib import Path
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from config.settings import FILE_POLL_INTERVAL
from utils.screenshot import take_screenshot
import asyncio
import threading


class FileEventHandler(FileSystemEventHandler):
    """Handles file system events."""

    def __init__(self, file_monitor: "FileMonitor"):
        """Initialize the file event handler.

        Args:
            file_monitor: The file monitor that created this handler.
        """
        self.file_monitor = file_monitor

    def on_created(self, event):
        """Handle file creation events.

        Args:
            event: The file system event.
        """
        if not event.is_directory:
            # Use run_coroutine_threadsafe to schedule the async handler on the bot's event loop
            asyncio.run_coroutine_threadsafe(
                self.file_monitor._handle_file_created(event.src_path),
                self.file_monitor._bot_loop
            )

    def on_modified(self, event):
        """Handle file modification events.

        Args:
            event: The file system event.
        """
        if not event.is_directory:
            # Use run_coroutine_threadsafe to schedule the async handler on the bot's event loop
            asyncio.run_coroutine_threadsafe(
                self.file_monitor._handle_file_modified(event.src_path),
                self.file_monitor._bot_loop
            )

    def on_deleted(self, event):
        """Handle file deletion events.

        Args:
            event: The file system event.
        """
        if not event.is_directory:
            # Use run_coroutine_threadsafe to schedule the async handler on the bot's event loop
            asyncio.run_coroutine_threadsafe(
                self.file_monitor._handle_file_deleted(event.src_path),
                self.file_monitor._bot_loop
            )

    def on_moved(self, event):
        """Handle file move events.

        Args:
            event: The file system event.
        """
        if not event.is_directory:
            # Use run_coroutine_threadsafe to schedule the async handler on the bot's event loop
            asyncio.run_coroutine_threadsafe(
                self.file_monitor._handle_file_moved(event.src_path, event.dest_path),
                self.file_monitor._bot_loop
            )


class FileMonitor:
    """Monitors file system changes on Windows systems."""

    def __init__(self, event_grouper, monitored_folders=None, paused_event=None, bot_loop=None):
        """Initialize the file monitor.

        Args:
            event_grouper: The event grouper to send events to.
            monitored_folders (list, optional): List of folders to monitor.
                                               If None, no folders are monitored.
            paused_event (threading.Event, optional): Event to signal pause state.
            bot_loop (asyncio.AbstractEventLoop, optional): The event loop of the Telegram bot.
        """
        self.event_grouper = event_grouper
        self.monitored_folders = monitored_folders or []
        self._paused = paused_event
        self._bot_loop = bot_loop
        self.observers = []
        self.suspicious_extensions = [
            ".exe", ".bat", ".cmd", ".ps1", ".vbs", ".js", ".wsf", ".hta",
            ".scr", ".pif", ".reg", ".dll", ".com", ".msi", ".msp", ".msc"
        ]
        self.running = False
        logging.info("File monitor initialized")

    def _should_ignore_file_event(self, file_path):
        """Check if a file event should be ignored based on specified criteria."""
        file_path_lower = file_path.lower()
        file_name_lower = os.path.basename(file_path).lower()
        file_ext_lower = os.path.splitext(file_path)[1].lower()

        # Ignore specific directories
        # Normalize path separators for consistent comparison
        normalized_file_path = file_path.replace('\\', '/').lower()

        # Aggressively filter Windows system directories that generate excessive alerts
        if normalized_file_path.startswith('c:/windows/') or normalized_file_path.startswith('c:/windows\\'):
            # Allow only specific high-risk Windows directories
            allowed_windows_dirs = [
                'c:/windows/system32/config/',
                'c:/windows/system32/winevt/'
            ]
            # Check if the file is in an allowed directory
            is_allowed = False
            for allowed_dir in allowed_windows_dirs:
                if normalized_file_path.startswith(allowed_dir):
                    is_allowed = True
                    break
            # If not in allowed directories, ignore it
            if not is_allowed:
                return True

        # Ignore specific directories and patterns that generate excessive alerts
        ignore_patterns = [
            'c:/windows/inf/',
            'c:/windows/system32/drivers/',
            'c:/windows/system32/spool/',
            'c:/windows/system32/wbem/',
            'c:/windows/syswow64/',
            'c:/windows/systemapps/',
            'appdata/local/microsoft/windows/powershell/',
            'appdata/local/temp/',
            'appdata/roaming/trae/network/',
            'c:/windows/temp/',
            'c:/programdata/',
            'c:/users/default/appdata/',
            'c:/users/public/appdata/',
            'appdata/locallow/microsoft/cryptneturlcache/',
            'appdata/roaming/.vscode/',
            'appdata/roaming/code/crashpad/',
            'appdata/roaming/microsoft/protect/',
            'c:/windows/winsxs/manifests/',
            'appdata/local/microsoft/windows/safety/',
            'appdata/local/packages/', # Ignore UWP app data
            'c:/program files/', # Ignore Program Files directory
            'c:/program files (x86)/', # Ignore Program Files (x86) directory
            'appdata/local/microsoft/windows/inetcache/',
            'appdata/local/microsoft/windows/temporary internet files/',
            'appdata/local/microsoft/windows/webcache/',
            'appdata/local/microsoft/windows/history/',
            'appdata/local/microsoft/windows/caches/',
            'appdata/local/microsoft/windows/iecompatcache/',
            'appdata/local/microsoft/windows/iedownloadhistory/',
            'appdata/local/microsoft/windows/ienetcookies/'
        ]

        for pattern in ignore_patterns:
            if pattern in normalized_file_path:
                return True

        # Add more specific temporary file patterns
        if '.tmp' in file_name_lower or file_name_lower.endswith('.temp'):
            return True

        # Ignore specific file patterns and extensions that generate noise
        ignore_extensions = ['.pnf', '.mui', '.ps1', '.psm1', '.etl', '.log', '.dat', '.blf', '.regtrans-ms', 
                             '.cat', '.db', '.cache', '.tlb', '.nls', '.clb', '.bin', '.dll', '.sys']
        if file_ext_lower in ignore_extensions:
            return True
            
        if file_name_lower.startswith('_psscriptpolicytest') or 'psscriptpolicytest' in file_path_lower:
            return True

        # Ignore events from the activitywatch directory
        if "activitywatch" in file_path_lower:
            return True

        return False

    def start(self):
        """Start monitoring file system changes."""
        self.running = True
        logging.info("File monitoring started")
        
        try:
            # Create an observer for each monitored folder
            for folder in self.monitored_folders:
                if os.path.exists(folder) and os.path.isdir(folder):
                    observer = Observer()
                    event_handler = FileEventHandler(self)
                    observer.schedule(event_handler, folder, recursive=True)
                    observer.start()
                    self.observers.append(observer)
                    logging.info(f"Monitoring folder: {folder}")
                else:
                    logging.warning(f"Folder does not exist or is not a directory: {folder}")
            
            # Keep the thread alive while running
            while self.running:
                # Wait if paused
                if self._paused and self._paused.is_set():
                    logging.debug("FileMonitor paused.")
                    self._paused.wait() # Block until the event is cleared
                    logging.debug("FileMonitor resumed.")

                time.sleep(FILE_POLL_INTERVAL)
        except Exception as e:
            logging.error(f"Error in file monitoring: {e}")
            self.running = False
        finally:
            self.stop()
    
    def stop(self):
        """Stop monitoring file system changes."""
        if not self.running:
            return # Already stopped

        self.running = False
        logging.info("Stopping file monitoring")

        # Stop all observers
        for observer in self.observers:
            try:
                observer.stop()
            except Exception as e:
                logging.error(f"Error stopping observer: {e}")

        # Wait for all observer threads to join
        for observer in self.observers:
            try:
                observer.join(timeout=5.0) # Wait up to 5 seconds for thread to join
            except Exception as e:
                logging.error(f"Error joining observer thread: {e}")

        self.observers = []
        logging.info("File monitoring stopped")
    
    def _is_suspicious_file(self, file_path):
        """Check if the file is suspicious based on extension or name.
        
        Args:
            file_path (str): The path to the file.
        
        Returns:
            bool: True if the file is suspicious, False otherwise.
        """
        file_ext = os.path.splitext(file_path)[1].lower()
        file_name = os.path.basename(file_path).lower()
        
        # Check for suspicious extensions
        if file_ext in self.suspicious_extensions:
            # Exclude temporary files created by PowerShell or in common temp directories
            if "AppData\\Local\\Temp" in file_path or "C:\\Windows\\Temp" in file_path:
                return False
            # Exclude PowerShell startup profile data
            if "AppData\\Local\\Microsoft\\Windows\\PowerShellStartupProfileData-NonInteractive" in file_path:
                return False
            # Exclude files in AppData\Roaming\Microsoft\Protect
            if r"AppData\Roaming\Microsoft\Protect" in file_path:
                return False
            # Exclude Temporary Internet Files
            if r"AppData\Local\Microsoft\Windows\INetCache" in file_path:
                return False
            # Exclude common browser cache locations
            if r"AppData\Local\Google\Chrome\User Data" in file_path or r"AppData\Local\Mozilla\Firefox\Profiles" in file_path:
                return False
            # Add exclusions for common log and temporary file extensions
            if file_ext in ['.log', '.tmp', '.temp', '.dat', '.cache', '.swp', '.bak']:
                return False

            # Add exclusions for common system and application directories
            if "C:\\Program Files" in file_path or "C:\\Program Files (x86)" in file_path or "C:\\Windows" in file_path or "C:\\ProgramData" in file_path:
                 return False

            return True
        
        # Check for suspicious file names
        suspicious_names = ["hack", "crack", "keylogger", "spy", "trojan", "malware", "virus"]
        for name in suspicious_names:
            if name in file_name:
                return True
        
        return False
    
    async def _handle_file_created(self, file_path):
        """Handle a file creation event.

        Args:
            file_path (str): The path to the created file.
        """
        try:
            # Check if the event should be ignored
            if self._should_ignore_file_event(file_path):
                logging.debug(f"Ignoring file creation event based on suppression rules: {file_path}")
                return

            # Create file event
            is_suspicious = self._is_suspicious_file(file_path)
            event = {
                "type": "file_created",
                "timestamp": datetime.now(),
                "file_path": file_path,
                "is_suspicious": is_suspicious
            }
            
            # Mark as suspicious if needed
            if is_suspicious:
                event["type"] = "suspicious_file_created"
                logging.warning(f"Suspicious file created: {file_path}")
            else:
                logging.debug(f"File created: {file_path}")

            # Send event to event grouper
            if not self._paused.is_set():
                asyncio.run_coroutine_threadsafe(
                    self.event_grouper.add_event(event['type'], event_details=event),
                    self._bot_loop
                )
            else:
                logging.debug(f"Monitoring paused, not adding file created event: {file_path}")

        except Exception as e:
            logging.error(f"Error handling file creation: {e}")
    
    async def _handle_file_modified(self, file_path):
        """Handle a file modification event.

        Args:
            file_path (str): The path to the modified file.
        """
        try:
            # Check if the event should be ignored
            if self._should_ignore_file_event(file_path):
                logging.debug(f"Ignoring file modification event based on suppression rules: {file_path}")
                return

            # Check if the file is suspicious
            is_suspicious = self._is_suspicious_file(file_path)
            
            # Create file event
            event = {
                "type": "file_modified",
                "timestamp": datetime.now(),
                "file_path": file_path,
                "is_suspicious": is_suspicious
            }
            
            # Mark as suspicious if needed
            if is_suspicious:
                event["type"] = "suspicious_file_modified"
                logging.warning(f"Suspicious file modified: {file_path}")
            else:
                logging.debug(f"File modified: {file_path}")

            # Send event to event grouper
            if not self._paused.is_set():
                asyncio.run_coroutine_threadsafe(
                    self.event_grouper.add_event(event['type'], event_details=event),
                    self._bot_loop
                )
            else:
                logging.debug(f"Monitoring paused, not adding file modified event: {file_path}")

        except Exception as e:
            logging.error(f"Error handling file modification: {e}")
    
    async def _handle_file_deleted(self, file_path):
        """Handle a file deletion event.

        Args:
            file_path (str): The path to the deleted file.
        """
        try:
            # Check if the event should be ignored
            if self._should_ignore_file_event(file_path):
                logging.debug(f"Ignoring file deletion event based on suppression rules: {file_path}")
                return

            # Check if the file is suspicious (needed for the event dictionary)
            is_suspicious = self._is_suspicious_file(file_path)

            # Create file event
            event = {
                "type": "file_deleted",
                "timestamp": datetime.now(),
                "file_path": file_path,
                "is_suspicious": is_suspicious
            }

            # Send event to event grouper
            if not self._paused.is_set():
                asyncio.run_coroutine_threadsafe(
                    self.event_grouper.add_event(event['type'], event_details=event),
                    self._bot_loop
                )
            else:
                logging.debug(f"Monitoring paused, not adding file deleted event: {file_path}")

            logging.debug(f"File deleted: {file_path}")

        except Exception as e:
            logging.error(f"Error handling file deletion: {e}")
    
    async def _handle_file_moved(self, src_path, dest_path):
        """Handle a file move event.

        Args:
            src_path (str): The path to the source file.
            dest_path (str): The path to the destination file.
        """
        try:
            # Check if the event should be ignored for either path
            if self._should_ignore_file_event(src_path) or self._should_ignore_file_event(dest_path):
                logging.debug(f"Ignoring file move event based on suppression rules: {src_path} -> {dest_path}")
                return

            # Check if the files are suspicious
            is_suspicious_src = self._is_suspicious_file(src_path)
            is_suspicious_dest = self._is_suspicious_file(dest_path)
            is_suspicious = is_suspicious_src or is_suspicious_dest

            # Create file move event
            event = {
                "type": "file_moved",
                "timestamp": datetime.now(),
                "old_path": src_path,
                "new_path": dest_path,
                "is_suspicious": is_suspicious
            }

            # Mark as suspicious if needed
            if is_suspicious:
                event["type"] = "suspicious_file_moved"
                logging.warning(f"Suspicious file moved: {src_path} -> {dest_path}")
            else:
                logging.debug(f"File moved: {src_path} -> {dest_path}")

            # Send event to event grouper
            if not self._paused.is_set():
                asyncio.run_coroutine_threadsafe(
                    self.event_grouper.add_event(event["type"], event_details=event),
                    self._bot_loop
                )
            else:
                logging.debug(f"Monitoring paused, not adding file moved event: {src_path} -> {dest_path}")

        except Exception as e:
            logging.error(f"Error handling file move: {e}")