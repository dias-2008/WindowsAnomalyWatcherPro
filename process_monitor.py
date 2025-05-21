#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Process Monitor Module

This module provides functionality for monitoring process activity on Windows systems.
It detects process creation and termination events.
"""

import time
import logging
from datetime import datetime

# Import required modules
try:
    import psutil
    import win32process
    import win32api
except ImportError:
    logging.error("Failed to import psutil or win32 modules. Make sure they are installed.")

from config.settings import PROCESS_POLL_INTERVAL
from utils.screenshot import take_screenshot
import asyncio
import threading

class ProcessMonitor:
    """Monitors process activity on Windows systems."""

    def __init__(self, event_grouper, paused_event: threading.Event, bot_loop: asyncio.AbstractEventLoop):
        """Initialize the process monitor.

        Args:
            event_grouper: The event grouper to send events to.
            paused_event (threading.Event): Event to signal pause state.
            bot_loop (asyncio.AbstractEventLoop): The event loop of the Telegram bot.
        """
        self.event_grouper = event_grouper
        self._paused = paused_event
        self._bot_loop = bot_loop
        self.running_processes = {}
        self.suspicious_processes = [
            "cmd.exe", "powershell.exe", "psexec.exe", "netcat", "nc.exe",
            "mimikatz", "putty.exe", "regsvr32.exe", "schtasks.exe", "wmic.exe",
            "vssadmin.exe", "taskkill.exe", "net.exe", "net1.exe", "reg.exe"
        ]
        self.running = False
        logging.info("Process monitor initialized")

    def _is_system_process(self, process_info):
        """Check if the process is a system process that should be ignored based on general system criteria.

        Args:
            process_info (dict): Information about the process.

        Returns:
            bool: True if the process should be ignored, False otherwise.
        """
        process_name = (process_info.get('name') or '').lower()
        process_path = (process_info.get('exe') or '').lower()
        username = (process_info.get('username') or '').lower()

        # Ignore processes running as system users
        system_users = [r'nt authority\system', r'nt authority\local service', r'nt authority\network service']
        if username in system_users:
            return True

        # Ignore processes in common system directories
        system_dirs = [
            r'c:\windows\system32',
            r'c:\windows\syswow64',
            r'c:\windows\servicing',
            r'c:\windows\winsxs',
            r'c:\program files\windowsapps'
        ]
        for sys_dir in system_dirs:
            if process_path.startswith(sys_dir):
                return True

        # Ignore specific known system processes that might not be in system dirs but are background tasks
        known_system_processes = [
            'svchost.exe',
            'explorer.exe', # Often user-related, but can be noisy with background tasks
            'runtimebroker.exe',
            'shellexperiencehost.exe',
            'searchindexer.exe',
            'searchprotocolhost.exe',
            'searchfilterhost.exe',
            'ctfmon.exe',
            'msrdc.exe', # Remote Desktop Connection
            'dwm.exe', # Desktop Window Manager
            'spoolsv.exe', # Print Spooler
            'services.exe',
            'lsass.exe',
            'winlogon.exe',
            'csrss.exe',
            'smss.exe',
            'system',
            'idle'
        ]
        if process_name in known_system_processes:
             return True

        # Ignore specific processes like conhost.exe and cmd.exe if they are in System32
        if process_name in ['conhost.exe', 'cmd.exe'] and process_path.startswith(r'c:\windows\system32'):
            return True

        # Ignore processes running from common temporary directories
        temp_dirs = [
            r'c:\\users', # Need to handle variable username
            r'c:\\windows\\temp'
        ]
        for temp_dir in temp_dirs:
            if temp_dir in process_path:
                # Further check for AppData\Local\Temp specifically for user temp dirs
                if temp_dir == r'c:\\users' and r'appdata\local\temp' in process_path: # This check seems redundant with the new _should_ignore_process_event logic for temp dirs, will review later.
                    return True
                elif temp_dir == r'c:\\windows\\temp':
                    return True

        return False

    def _should_ignore_process_event(self, process_info, event_type):
        """Check if a process event should be ignored based on specific suppression criteria."""
        process_name = (process_info.get('name') or '').lower()
        process_path = (process_info.get('exe') or '').lower()
        create_time = process_info.get('create_time')

        # Ignore specific processes with short runtime on termination
        if event_type == 'terminated' and process_name in ['cmd.exe', 'conhost.exe', 'powershell.exe']:
            if create_time is not None:
                runtime = datetime.now().timestamp() - create_time
                if runtime < 3:
                    return True

        # Ignore specific processes on termination
        if event_type == 'terminated':
            # Ignore cmd.exe and browser.exe termination
            if process_name in ['cmd.exe', 'browser.exe']:
                return True
            # Ignore processes inside Yandex Browser directory
            if process_path and r'appdata\local\yandex\yandexbrowser' in process_path.lower():
                return True

        # Ignore browser.exe specifically if it's from the Yandex Browser path
        if process_name == 'browser.exe' and process_path and r'appdata\local\yandex\yandexbrowser' in process_path.lower():
            return True

        return False

    def start(self):
        """Start monitoring process activity."""
        self.running = True
        logging.info("Process monitoring started")

        # Initialize running processes
        asyncio.run_coroutine_threadsafe(self._update_running_processes(initial=True), self._bot_loop)

        try:
            while self.running:
                # Wait if paused
                if self._paused.is_set():
                    logging.debug("ProcessMonitor paused.")
                    self._paused.wait() # Block until the event is cleared
                    logging.debug("ProcessMonitor resumed.")

                # Schedule the async update on the bot's event loop
                asyncio.run_coroutine_threadsafe(self._update_running_processes(), self._bot_loop)
                time.sleep(PROCESS_POLL_INTERVAL)
        except Exception as e:
            logging.error(f"Error in process monitoring: {e}")
            self.running = False

    def stop(self):
        """Stop monitoring process activity."""
        self.running = False
        logging.info("Process monitoring stopped")
    
    async def _update_running_processes(self, initial=False):
        """Update the list of running processes and detect changes.
        
        Args:
            initial (bool): Whether this is the initial update.
        """
        try:
            # Get current processes
            current_processes = {}
            for proc in psutil.process_iter(['pid', 'name', 'exe', 'cmdline', 'username', 'create_time']):
                try:
                    process_info = proc.info
                    pid = process_info['pid']
                    
                    # Skip system processes with very low PIDs
                    if pid < 10:
                        continue
                    
                    current_processes[pid] = {
                        'pid': pid,
                        'name': process_info['name'],
                        'exe': process_info['exe'],
                        'cmdline': process_info['cmdline'],
                        'username': process_info['username'],
                        'create_time': process_info['create_time']
                    }
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    pass
            
            if not initial:
                # Check for new processes
                for pid, proc_info in current_processes.items():
                    if pid not in self.running_processes:
                        await self._handle_process_created(pid, proc_info)
                
                # Check for terminated processes
                for pid in list(self.running_processes.keys()):
                    if pid not in current_processes:
                        await self._handle_process_terminated(pid, self.running_processes[pid])
            
            # Update running processes
            self.running_processes = current_processes
            
        except Exception as e:
            logging.error(f"Error updating running processes: {e}")
    
    def _is_suspicious_process(self, process_info):
        """Check if the process is suspicious based on name or command line.
        
        Args:
            process_info (dict): Information about the process.
        
        Returns:
            bool: True if the process is suspicious, False otherwise.
        """
        process_name = process_info.get('name', '').lower()
        process_path = process_info.get('exe') # Retrieve process_path here
        cmdline_list = process_info.get('cmdline', [])
        # Ensure cmdline_list is iterable before joining
        cmdline = ' '.join(cmdline_list).lower() if isinstance(cmdline_list, list) else str(cmdline_list).lower()
        
        # Check for suspicious process names
        for suspicious in self.suspicious_processes:
            if suspicious.lower() in process_name:
                return True
        
        # Check for suspicious command line arguments
        suspicious_args = [
            '-encodedcommand', 'iex', 'invoke-expression', 'downloadstring',
            'bypass', 'hidden', 'webclient', 'shellcode', 'base64'
        ]
        
        for arg in suspicious_args:
            if arg in cmdline:
                return True
        
        # Ignore processes running from common temporary directories
        temp_dirs = [
            'c:\\users', # Need to handle variable username
            'c:\\windows\\temp'
        ]
        for temp_dir in temp_dirs:
            if process_path and temp_dir in process_path.lower():
                return True

        return False
    
    async def _handle_process_created(self, pid, process_info):
        """Handle a process creation event.

        Args:
            pid (int): The process ID.
            process_info (dict): Information about the process.
        """
        try:
            process_name = process_info.get('name')
            process_path = process_info.get('exe')

            # Check if it's a system process and should be ignored based on general criteria
            if self._is_system_process(process_info):
                logging.debug(f"Ignoring system process creation event based on general system rules: {process_name or 'Unknown'} (PID: {pid})")
                return

            # Check if the process event should be ignored based on specific suppression rules
            if self._should_ignore_process_event(process_info, 'created'):
                 logging.debug(f"Ignoring process creation event based on specific suppression rules: {process_info.get('name', 'Unknown')} (PID: {pid})")
                 return

            # Check if the process is suspicious
            is_suspicious = self._is_suspicious_process(process_info)

            # Create process event
            event = {
                "type": "process_created",
                "timestamp": datetime.now(),
                "pid": pid,
                "process_name": process_name or 'Unknown',
                "process_path": process_path or 'Unknown',
                "cmdline": process_info.get('cmdline', []),
                "username": process_info.get('username', 'Unknown'),
                "suspicious": is_suspicious
            }
            
            # Mark as suspicious if needed
            if is_suspicious:
                event["type"] = "suspicious_process"
                logging.warning(f"Suspicious process detected: {process_info.get('name', 'Unknown')} (PID: {pid})")
            else:
                logging.debug(f"Process created: {process_info.get('name', 'Unknown')} (PID: {pid})")
             
            # Send event to event grouper
            if not self._paused.is_set():
                asyncio.run_coroutine_threadsafe(
                    self.event_grouper.add_event(event["type"], event_details=event),
                    self._bot_loop
                )
        except Exception as e:
            logging.error(f"Error handling process creation: {e}")

    async def _handle_process_terminated(self, pid, process_info):
        """Handle a process termination event.

        Args:
            pid (int): The process ID.
            process_info (dict): Information about the process.
        """
        if not isinstance(process_info, dict) or 'name' not in process_info or 'exe' not in process_info:
            logging.warning(f"Invalid process_info received for PID {pid}: {process_info}")
            return

        try:
            process_name = process_info.get('name')
            process_path = process_info.get('exe')

            # Check if it's a system process and should be ignored based on general criteria
            if self._is_system_process(process_info):
                logging.debug(f"Ignoring system process termination event based on general system rules: {process_name or 'Unknown'} (PID: {pid})")
                return

            # Check if the process event should be ignored based on specific suppression rules
            if self._should_ignore_process_event(process_info, 'terminated'):
                 logging.debug(f"Ignoring process termination event based on specific suppression rules: {process_info.get('name', 'Unknown')} (PID: {pid})")
                 return

            # Create process event
            event = {
                "type": "process_terminated",
                "timestamp": datetime.now(),
                "pid": pid,
                "process_name": process_name or 'Unknown',
                "process_path": process_path or 'Unknown',
            }
            
            # Send event to event grouper
            if not self._paused.is_set():
                asyncio.run_coroutine_threadsafe(
                    self.event_grouper.add_event(event["type"], event_details=event),
                    self._bot_loop
                )
            else:
                logging.debug(f"Monitoring paused, not adding process terminated event: {process_info.get('name', 'Unknown')}")

            logging.debug(f"Process terminated: {process_info.get('name', 'Unknown')} (PID: {pid})")

        except Exception as e:
            logging.error(f"Error handling process termination: {e}")