#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Installer Module

This module provides installation utilities for the Windows Anomaly Watcher PRO application.
It handles tasks like creating shortcuts and registry entries.
"""

import os
import sys
import logging
import shutil
from pathlib import Path

# Import Windows-specific modules
try:
    import winreg as reg
    import win32com.client
except ImportError:
    logging.error("Failed to import Windows-specific modules. Make sure pywin32 is installed.")

from config.settings import APP_NAME
from utils.system_utils import add_to_startup, remove_from_startup


def create_desktop_shortcut(target_path=None, shortcut_name=None):
    """Create a desktop shortcut for the application.
    
    Args:
        target_path (str, optional): The path to the target executable.
                                     If None, sys.executable is used.
        shortcut_name (str, optional): The name of the shortcut.
                                      If None, APP_NAME is used.
    
    Returns:
        bool: True if the shortcut was created successfully, False otherwise.
    """
    try:
        # Get the target path
        if target_path is None:
            if getattr(sys, 'frozen', False):
                # Running as compiled executable
                target_path = sys.executable
            else:
                # Running as script
                target_path = str(Path(__file__).parent.parent / "main.py")
        
        # Get the shortcut name
        if shortcut_name is None:
            shortcut_name = APP_NAME
        
        # Get the desktop path
        desktop_path = os.path.join(os.path.expanduser("~"), "Desktop")
        
        # Create the shortcut
        shortcut_path = os.path.join(desktop_path, f"{shortcut_name}.lnk")
        
        # Create a shortcut using the Windows Script Host
        shell = win32com.client.Dispatch("WScript.Shell")
        shortcut = shell.CreateShortCut(shortcut_path)
        shortcut.Targetpath = target_path
        shortcut.WorkingDirectory = os.path.dirname(target_path)
        shortcut.IconLocation = target_path
        shortcut.save()
        
        logging.info(f"Created desktop shortcut: {shortcut_path}")
        return True
    except Exception as e:
        logging.error(f"Failed to create desktop shortcut: {e}")
        return False


def create_start_menu_shortcut(target_path=None, shortcut_name=None):
    """Create a start menu shortcut for the application.
    
    Args:
        target_path (str, optional): The path to the target executable.
                                     If None, sys.executable is used.
        shortcut_name (str, optional): The name of the shortcut.
                                      If None, APP_NAME is used.
    
    Returns:
        bool: True if the shortcut was created successfully, False otherwise.
    """
    try:
        # Get the target path
        if target_path is None:
            if getattr(sys, 'frozen', False):
                # Running as compiled executable
                target_path = sys.executable
            else:
                # Running as script
                target_path = str(Path(__file__).parent.parent / "main.py")
        
        # Get the shortcut name
        if shortcut_name is None:
            shortcut_name = APP_NAME
        
        # Get the start menu path
        start_menu_path = os.path.join(
            os.path.expanduser("~"),
            "AppData",
            "Roaming",
            "Microsoft",
            "Windows",
            "Start Menu",
            "Programs"
        )
        
        # Create the shortcut
        shortcut_path = os.path.join(start_menu_path, f"{shortcut_name}.lnk")
        
        # Create a shortcut using the Windows Script Host
        shell = win32com.client.Dispatch("WScript.Shell")
        shortcut = shell.CreateShortCut(shortcut_path)
        shortcut.Targetpath = target_path
        shortcut.WorkingDirectory = os.path.dirname(target_path)
        shortcut.IconLocation = target_path
        shortcut.save()
        
        logging.info(f"Created start menu shortcut: {shortcut_path}")
        return True
    except Exception as e:
        logging.error(f"Failed to create start menu shortcut: {e}")
        return False


def install_application():
    """Install the application.
    
    This function performs the following tasks:
    - Adds the application to startup
    - Creates desktop and start menu shortcuts
    
    Returns:
        bool: True if the installation was successful, False otherwise.
    """
    try:
        # Add the application to startup
        add_to_startup()
        
        # Create desktop and start menu shortcuts
        create_desktop_shortcut()
        create_start_menu_shortcut()
        
        logging.info("Application installed successfully")
        return True
    except Exception as e:
        logging.error(f"Failed to install application: {e}")
        return False


def uninstall_application():
    """Uninstall the application.
    
    This function performs the following tasks:
    - Removes the application from startup
    - Removes desktop and start menu shortcuts
    
    Returns:
        bool: True if the uninstallation was successful, False otherwise.
    """
    try:
        # Remove the application from startup
        remove_from_startup()
        
        # Remove desktop shortcut
        desktop_path = os.path.join(os.path.expanduser("~"), "Desktop")
        shortcut_path = os.path.join(desktop_path, f"{APP_NAME}.lnk")
        if os.path.exists(shortcut_path):
            os.remove(shortcut_path)
        
        # Remove start menu shortcut
        start_menu_path = os.path.join(
            os.path.expanduser("~"),
            "AppData",
            "Roaming",
            "Microsoft",
            "Windows",
            "Start Menu",
            "Programs"
        )
        shortcut_path = os.path.join(start_menu_path, f"{APP_NAME}.lnk")
        if os.path.exists(shortcut_path):
            os.remove(shortcut_path)
        
        logging.info("Application uninstalled successfully")
        return True
    except Exception as e:
        logging.error(f"Failed to uninstall application: {e}")
        return False