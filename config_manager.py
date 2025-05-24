#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Configuration Manager Module

This module provides functionality for loading, saving, and validating application configuration.
"""

import os
import json
import logging
from pathlib import Path

from config.settings import CONFIG_FILE, DEFAULT_SETTINGS
from utils.crypto import encrypt_data, decrypt_data


class ConfigManager:
    """Manages application configuration."""

    def __init__(self, config_file=None):
        """Initialize the configuration manager.

        Args:
            config_file (str, optional): Path to the configuration file.
                                         If None, the default path from settings is used.
        """
        self.config_file = Path(config_file) if config_file else Path(CONFIG_FILE)
        self.config = {}
        logging.debug(f"ConfigManager initialized with config file path: {self.config_file}") # Added logging
        self.load()

    def load(self):
        """Load configuration from file.

        Returns:
            dict: The loaded configuration.
        """
        logging.info(f"Attempting to load configuration from: {self.config_file}")
        # Create directory if it doesn't exist
        self.config_file.parent.mkdir(exist_ok=True)

        # If config file exists, load it
        if self.config_file.exists():
            logging.debug(f"Config file found at: {self.config_file}") # Added logging
            try:
                logging.debug(f"Opening config file for loading: {self.config_file}")
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config_data = json.load(f)

                logging.debug(f"Loaded raw config data: {config_data}")
                # Decrypt sensitive data, handle potential decryption failures
                decrypted_token = decrypt_data(config_data.get('telegram_token'))
                decrypted_chat_id = decrypt_data(config_data.get('telegram_chat_id'))

                # Use decrypted data if successful, otherwise use None or default
                config_data['telegram_token'] = decrypted_token if decrypted_token is not None else '' # Use empty string on failure
                config_data['telegram_chat_id'] = decrypted_chat_id if decrypted_chat_id is not None else '' # Use empty string on failure

                self.config = config_data
                logging.info("Configuration loaded successfully")
                logging.debug(f"Loaded configuration: {self.config}")
            except Exception as e:
                logging.error(f"Failed to load configuration from {self.config_file}: {e}") # Modified logging
                self.config = DEFAULT_SETTINGS.copy()
                logging.info("Using default configuration due to load failure") # Added logging
        else:
            # Use default settings if config file doesn't exist
            logging.warning(f"Config file not found at: {self.config_file}. Using default configuration.") # Modified logging
            self.config = DEFAULT_SETTINGS.copy()
            logging.info("Using default configuration")

        return self.config

    def save(self):
        """Save configuration to file.

        Returns:
            bool: True if the configuration was saved successfully, False otherwise.
        """
        logging.info(f"Attempting to save configuration to: {self.config_file}")
        try:
            # Create directory if it doesn't exist
            self.config_file.parent.mkdir(exist_ok=True)

            # Create a copy of the config to avoid modifying the original
            config_data = self.config.copy()

            # Encrypt sensitive data
            logging.debug("Attempting to encrypt sensitive data before saving.")
            if 'telegram_token' in config_data:
                try:
                    config_data['telegram_token'] = encrypt_data(config_data['telegram_token'])
                    logging.debug("Telegram token encrypted successfully.")
                except Exception as e:
                    logging.error(f"Failed to encrypt telegram token: {e}")
                    # Decide how to handle encryption failure - maybe don't save or save unencrypted?
                    # For now, let's proceed with potentially unencrypted data or previous encrypted data
                    pass # Or set to None/empty string depending on desired behavior

            if 'telegram_chat_id' in config_data:
                try:
                    config_data['telegram_chat_id'] = encrypt_data(config_data['telegram_chat_id'])
                    logging.debug("Telegram chat ID encrypted successfully.")
                except Exception as e:
                    logging.error(f"Failed to encrypt telegram chat ID: {e}")
                    pass # Or set to None/empty string

            logging.debug("Sensitive data encryption attempt completed.")

            # Save the config to file
            logging.debug(f"Saving raw config data to {self.config_file}: {config_data}")
            try:
                with open(self.config_file, 'w', encoding='utf-8') as f:
                    json.dump(config_data, f, indent=4)
                logging.info("Configuration saved successfully")
            except Exception as e:
                logging.error(f"Failed to write configuration file {self.config_file}: {e}")
                return False

            logging.debug("Configuration file writing completed.")
            logging.debug(f"Config saved to: {self.config_file}")
            logging.debug(f"Saved configuration: {self.config}")
            return True
        except Exception as e:
            logging.error(f"Failed to save configuration to {self.config_file}: {e}") # Modified logging
            return False

    def get(self, key, default=None):
        """Get a configuration value.

        Args:
            key (str): The configuration key.
            default: The default value to return if the key is not found.
        
        Returns:
            The configuration value, or the default value if the key is not found.
        """
        return self.config.get(key, default)

    def set(self, key, value):
        """Set a configuration value.

        Args:
            key (str): The configuration key.
            value: The configuration value.
        
        Returns:
            bool: True if the configuration was saved successfully, False otherwise.
        """
        self.config[key] = value
        return self.save()

    def is_configured(self):
        """Check if the application is configured.

        Returns:
            bool: True if the application is configured, False otherwise.
        """
        # Check if the required configuration values are set
        is_configured = (
            self.config.get('telegram_token') and
            self.config.get('telegram_chat_id')
        )
        
        # Ensure monitored_folders is set even if not configured
        if 'monitored_folders' not in self.config or not self.config['monitored_folders']:
            self.config['monitored_folders'] = DEFAULT_SETTINGS['monitored_folders']
            self.save()
            
        return is_configured

    def reset(self):
        """Reset the configuration to default values.

        Returns:
            bool: True if the configuration was reset successfully, False otherwise.
        """
        self.config = DEFAULT_SETTINGS.copy()
        return self.save()