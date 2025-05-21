#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
USB Monitor Module

This module provides functionality for monitoring USB device activity on Windows systems.
It detects USB device connections and disconnections.
"""

import time
import logging
from datetime import datetime
import pythoncom
import asyncio

# Import required modules
try:
    import win32api
    import win32file
    import win32con
    import wmi
except ImportError:
    logging.error("Failed to import win32 or wmi modules. Make sure they are installed.")

from config.settings import USB_POLL_INTERVAL
from utils.screenshot import take_screenshot


class USBMonitor:
    """Monitors USB device activity on Windows systems."""
    
    def __init__(self, event_grouper, paused_event, bot_loop):
        """Initialize the USB monitor.
        
        Args:
            event_grouper: The event grouper to send events to.
            paused_event (threading.Event): Event to signal pause state.
            bot_loop: The asyncio event loop of the Telegram bot.
        """
        self.event_grouper = event_grouper
        self._paused = paused_event
        self._bot_loop = bot_loop
        self.connected_devices = {}
        self.wmi = None
        self.running = False
        logging.info("USB monitor initialized")
    
    def start(self):
        """Start monitoring USB device activity."""
        self.running = True
        logging.info("USB monitoring started")
        
        async def _async_start():
            # Initialize COM for this thread
            pythoncom.CoInitialize()
            
            try:
                # Initialize WMI within the thread
                self.wmi = wmi.WMI()
                
                # Initialize connected devices
                self._update_connected_devices(initial=True)
                
                while self.running:
                    # Wait if paused
                    if self._paused.is_set():
                        logging.debug("USBMonitor paused.")
                        self._paused.wait() # Block until the event is cleared
                        logging.debug("USBMonitor resumed.")

                    self._update_connected_devices()
                    await asyncio.sleep(USB_POLL_INTERVAL) # Use asyncio.sleep in async context
            except Exception as e:
                logging.error(f"Error in USB monitoring: {e}")
                self.running = False
            finally:
                # Uninitialize COM for this thread
                pythoncom.CoUninitialize()

        asyncio.run(_async_start())
    
    def stop(self):
        """Stop monitoring USB device activity."""
        self.running = False
        logging.info("USB monitoring stopped")
    
    def _update_connected_devices(self, initial=False):
        """Update the list of connected USB devices and detect changes.
        
        Args:
            initial (bool): Whether this is the initial update.
        """
        try:
            if self.wmi is None:
                try:
                    self.wmi = wmi.WMI()
                except Exception as e:
                    logging.error(f"Failed to initialize WMI: {e}")
                    return
            
            # Get current USB devices using Win32_PnPEntity
            current_devices = {}
            # Query for devices where DeviceID contains "USB"
            for device in self.wmi.query("SELECT * FROM Win32_PnPEntity WHERE DeviceID LIKE '%USB%'"):
                 # Use PNPDeviceID as a more stable identifier if available, otherwise use DeviceID
                 device_id = getattr(device, 'PNPDeviceID', device.DeviceID)
                 current_devices[device_id] = {
                     "device_id": device_id,
                     "description": getattr(device, 'Description', 'Unknown'),
                     "name": getattr(device, 'Name', 'Unknown'),
                     "status": getattr(device, 'Status', 'Unknown')
                 }

            # Note: Win32_PnPEntity does not directly provide partition/drive letter info
            # If partition details are crucial, a more complex query or combination with Win32_LogicalDisk might be needed.
            # For now, focusing on basic USB device detection (connect/disconnect).
            
            if not initial:
                # Check for new devices
                for device_id, device_info in current_devices.items():
                    if device_id not in self.connected_devices:
                        self._handle_device_connected(device_id, device_info)
                
                # Check for disconnected devices
                for device_id in list(self.connected_devices.keys()):
                    if device_id not in current_devices:
                        self._handle_device_disconnected(device_id, self.connected_devices[device_id])
            
            # Update connected devices
            self.connected_devices = current_devices
            
        except Exception as e:
            logging.error(f"Error updating connected devices: {e}")
    
    def _handle_device_connected(self, device_id, device_info):
        """Handle a USB device connection.
        
        Args:
            device_id (str): The device ID.
            device_info (dict): Information about the device.
        """
        try:
            # Create device event
            event = {
                "type": "usb_connected",
                "timestamp": datetime.now(),
                "device_id": device_id,
                "device_description": device_info.get("description", "Unknown"),
                "device_name": device_info.get("name", "Unknown"),
                "status": device_info.get("status", "Unknown")
            }
            
            # Add screenshot if needed (currently disabled)
            
            # Send event to event grouper
            if not self._paused.is_set():
                # Use run_coroutine_threadsafe to schedule the async call on the bot's event loop
                if self._bot_loop:
                    asyncio.run_coroutine_threadsafe(
                        self.event_grouper.add_event(event['type'], event_details=event),
                        self._bot_loop
                    )
                else:
                    logging.warning("Bot event loop not available in USBMonitor.")
            else:
                logging.debug(f"Monitoring paused, not adding USB connected event: {device_info.get('description', 'Unknown')}")

            logging.info(f"USB device connected: {device_info.get('description', 'Unknown')} ({device_id})")
            
        except Exception as e:
            logging.error(f"Error handling device connection: {e}")
    
    def _handle_device_disconnected(self, device_id, device_info):
        """Handle a USB device disconnection.
        
        Args:
            device_id (str): The device ID.
            device_info (dict): Information about the device.
        """
        try:
            # Create device event
            event = {
                "type": "usb_disconnected",
                "timestamp": datetime.now(),
                "device_id": device_id,
                "device_description": device_info.get("description", "Unknown"),
                "device_name": device_info.get("name", "Unknown")
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
                    logging.warning("Bot event loop not available in USBMonitor.")
            else:
                logging.debug(f"Monitoring paused, not adding USB disconnected event: {device_info.get('description', 'Unknown')}")

            logging.info(f"USB device disconnected: {device_info.get('description', 'Unknown')} ({device_id})")
            
        except Exception as e:
            logging.error(f"Error handling device disconnection: {e}")