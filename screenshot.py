#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Screenshot Module

This module provides screenshot functionality for the Windows Anomaly Watcher PRO application.
"""

import os
import time
import logging
from datetime import datetime
from pathlib import Path

import pyautogui
from PIL import Image

from config.settings import DATA_DIR, SCREENSHOT_RATE_LIMIT_SECONDS

last_screenshot_time = 0

def take_screenshot(save_to_file=True, filename=None):
    """Take a screenshot of the current desktop.
    
    Args:
        save_to_file (bool, optional): Whether to save the screenshot to a file.
                                       Default is True.
        filename (str, optional): The filename to save the screenshot to.
                                 If None, a filename is generated based on the current time.
    
    Returns:
        tuple: (screenshot_path, screenshot_bytes) where screenshot_path is the path to the
               saved screenshot file (or None if save_to_file is False) and screenshot_bytes
               is the screenshot image as bytes (for sending via Telegram).
    """
    try:
        # Take the screenshot
        screenshot = pyautogui.screenshot()

        # Generate a filename if not provided
        if save_to_file:
            if filename is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"screenshot_{timestamp}.png"
            
            # Create the screenshots directory if it doesn't exist
            screenshots_dir = DATA_DIR / "screenshots"
            screenshots_dir.mkdir(exist_ok=True)
            
            # Save the screenshot to file
            screenshot_path = screenshots_dir / filename
            screenshot.save(screenshot_path)
            logging.info(f"Screenshot saved to {screenshot_path}")
        else:
            screenshot_path = None
        
        # Convert the screenshot to bytes for sending via Telegram
        import io
        img_byte_arr = io.BytesIO()
        screenshot.save(img_byte_arr, format='PNG')
        screenshot_bytes = img_byte_arr.getvalue()
        
        return screenshot_path, screenshot_bytes, 'success'
    except Exception as e:
        logging.error(f"Failed to take screenshot: {e}")
        return None, None, 'failed'


def get_screenshot_timestamp(screenshot_path):
    """Get the timestamp of a screenshot from its filename.
    
    Args:
        screenshot_path (str): The path to the screenshot file.
    
    Returns:
        datetime: The timestamp of the screenshot, or None if the filename
                 doesn't match the expected format.
    """
    try:
        # Extract the timestamp from the filename
        filename = Path(screenshot_path).stem
        if filename.startswith("screenshot_"):
            timestamp_str = filename.replace("screenshot_", "")
            return datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S")
        return None
    except Exception as e:
        logging.error(f"Failed to get screenshot timestamp: {e}")
        return None


def take_screenshot_on_button_press():
    """Take a screenshot when the screenshot button is pressed."""
    # This function should be linked to the screenshot button in the GUI
    screenshot_path, screenshot_bytes = take_screenshot()
    if screenshot_path:
        logging.info(f"Screenshot taken and saved to {screenshot_path}")
    else:
        logging.error("Failed to take screenshot")