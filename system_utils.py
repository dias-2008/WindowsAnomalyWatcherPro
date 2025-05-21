#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
System Utilities Module

This module provides system-related utilities for the Windows Anomaly Watcher PRO application.
"""

import os
import sys
import ctypes
import socket
import logging
import winreg as reg
from pathlib import Path

# Import Windows-specific modules
try:
    import win32api
    import win32con
    import win32gui
    import win32process
    from win32com.client import Dispatch
except ImportError:
    logging.error("Failed to import win32 modules. Make sure pywin32 is installed.")


def hide_console_window():
    """Hide the console window.
    
    This function hides the console window when the application is running.
    It is typically called when the application is running in production mode.
    
    Returns:
        bool: True if the console window was hidden successfully, False otherwise.
    """
    try:
        # Get the console window handle
        console_window = ctypes.windll.kernel32.GetConsoleWindow()
        
        # Hide the console window
        if console_window:
            ctypes.windll.user32.ShowWindow(console_window, 0)  # SW_HIDE = 0
            return True
        return False
    except Exception as e:
        logging.error(f"Failed to hide console window: {e}")
        return False


def add_to_startup(app_name=None, executable_path=None):
    """Add the application to Windows startup.
    
    This function adds the application to Windows startup so that it runs
    automatically when Windows starts.
    
    Args:
        app_name (str, optional): The name of the application in the registry.
                                  If None, the name is derived from the executable path.
        executable_path (str, optional): The path to the executable.
                                        If None, sys.executable is used.
    
    Returns:
        bool: True if the application was added to startup successfully, False otherwise.
    """
    try:
        # Get the executable path
        if executable_path is None:
            if getattr(sys, 'frozen', False):
                # Running as compiled executable
                executable_path = sys.executable
            else:
                # Running as script
                executable_path = str(Path(__file__).resolve())
        
            app_name = Path(executable_path).stem
        
        # Open the registry key for startup programs
        key = reg.OpenKey(
            reg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0,
            reg.KEY_SET_VALUE
        )
        
        # Add the application to startup
        reg.SetValueEx(key, app_name, 0, reg.REG_SZ, executable_path)
        reg.CloseKey(key)
        
        logging.info(f"Added application to startup: {app_name}")
        return True
    except Exception as e:
        logging.error(f"Failed to add application to startup: {e}")
        return False


def remove_from_startup(app_name=None):
    """Remove the application from Windows startup.
    
    This function removes the application from Windows startup.
    
    Args:
        app_name (str, optional): The name of the application in the registry.
                                  If None, the name is derived from the executable path.
    
    Returns:
        bool: True if the application was removed from startup successfully, False otherwise.
    """
    try:
        # Get the application name
        if app_name is None:
            app_name = Path(sys.executable).stem
        
        # Open the registry key for startup programs
        key = reg.OpenKey(
            reg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0,
            reg.KEY_SET_VALUE
        )
        
        # Remove the application from startup
        reg.DeleteValue(key, app_name)
        reg.CloseKey(key)
        
        logging.info(f"Removed application from startup: {app_name}")
        return True
    except Exception as e:
        logging.error(f"Failed to remove application from startup: {e}")
        return False


def get_computer_name():
    """Get the computer name.
    
    Returns:
        str: The computer name.
    """
    try:
        return socket.gethostname()
    except Exception as e:
        logging.error(f"Failed to get computer name: {e}")
        return "Unknown"


def get_ip_address():
    """Get the IP address of the computer.
    
    Returns:
        str: The IP address.
    """
    try:
        # Get the hostname
        hostname = socket.gethostname()
        
        # Get the IP address
        ip_address = socket.gethostbyname(hostname)
        
        return ip_address
    except Exception as e:
        logging.error(f"Failed to get IP address: {e}")
        return "Unknown"


def lock_workstation():
    """Lock the workstation.
    
    Returns:
        bool: True if the workstation was locked successfully, False otherwise.
    """
    try:
        ctypes.windll.user32.LockWorkStation()
        return True
    except Exception as e:
        logging.error(f"Failed to lock workstation: {e}")
        return False


def shutdown_computer(timeout=30):
    """Shutdown the computer.
    
    Args:
        timeout (int, optional): The timeout in seconds before shutdown.
                                Default is 30 seconds.
    
    Returns:
        bool: True if the shutdown was initiated successfully, False otherwise.
    """
    try:
        os.system(f'shutdown /s /t {timeout}')
        return True
    except Exception as e:
        logging.error(f"Failed to shutdown computer: {e}")
        return False


def cancel_shutdown():
    """Cancel a pending shutdown.
    
    Returns:
        bool: True if the shutdown was cancelled successfully, False otherwise.
    """
    try:
        os.system('shutdown /a')
        return True
    except Exception as e:
        logging.error(f"Failed to cancel shutdown: {e}")
        return False