#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Translator Module

This module provides translation functionality for the Windows Anomaly Watcher PRO application.
It loads translation strings from JSON files and provides methods to translate text.
"""

import os
import json
import logging
from pathlib import Path

# Available languages
AVAILABLE_LANGUAGES = ['en', 'ru']
DEFAULT_LANGUAGE = 'en'


class Translator:
    """Handles translation of text based on the selected language."""
    
    def __init__(self, language=DEFAULT_LANGUAGE):
        """Initialize the translator with the specified language.
        
        Args:
            language (str): The language code to use for translations.
                            Must be one of the available languages.
        """
        self.translations = {}
        self.current_language = DEFAULT_LANGUAGE
        
        # Set the language (this will load the translation file)
        self.set_language(language)
    
    def set_language(self, language):
        """Set the current language and load the corresponding translation file.
        
        Args:
            language (str): The language code to use for translations.
                            Must be one of the available languages.
        
        Returns:
            bool: True if the language was set successfully, False otherwise.
        """
        # Validate the language
        if language not in AVAILABLE_LANGUAGES:
            logging.warning(f"Unsupported language: {language}. Falling back to {DEFAULT_LANGUAGE}.")
            language = DEFAULT_LANGUAGE
        
        # Set the current language
        self.current_language = language
        
        # Load the translation file
        return self._load_translations()
    
    def _load_translations(self):
        """Load the translation file for the current language.
        
        Returns:
            bool: True if the translations were loaded successfully, False otherwise.
        """
        try:
            # Construct the path to the translation file
            # Assumes translation files are in the same directory as the translator.py file
            translator_dir = Path(__file__).parent
            translation_file_path = translator_dir / f"{self.current_language}.json"

            # Add logging before opening the file
            logging.debug(f"Translator: Attempting to load translation file: {translation_file_path}")

            # Load the translation file
            with open(translation_file_path, 'r', encoding='utf-8') as f:
                self.translations = json.load(f)

            logging.info(f"Loaded translations for language: {self.current_language}")
            # Add logging to show loaded translations (optional, can be verbose)
            # logging.debug(f"Translator: Loaded translations: {self.translations}")
            return True
        except FileNotFoundError:
            logging.error(f"Translator: Translation file not found for language {self.current_language}: {translation_file_path}")
            # Try to load the default language as a fallback
            if self.current_language != DEFAULT_LANGUAGE:
                logging.warning(f"Translator: Falling back to default language: {DEFAULT_LANGUAGE}")
                self.current_language = DEFAULT_LANGUAGE
                return self._load_translations()
            return False
        except json.JSONDecodeError as e:
            logging.error(f"Translator: Failed to parse JSON translation file for language {self.current_language}: {e}")
            # Try to load the default language as a fallback
            if self.current_language != DEFAULT_LANGUAGE:
                logging.warning(f"Translator: Falling back to default language: {DEFAULT_LANGUAGE}")
                self.current_language = DEFAULT_LANGUAGE
                return self._load_translations()
            return False
        except Exception as e:
            logging.error(f"Translator: An unexpected error occurred while loading translations for language {self.current_language}: {e}")
            # Try to load the default language as a fallback
            if self.current_language != DEFAULT_LANGUAGE:
                logging.warning(f"Translator: Falling back to default language: {DEFAULT_LANGUAGE}")
                self.current_language = DEFAULT_LANGUAGE
                return self._load_translations()
            return False

    def get(self, key, **kwargs):
        """Get translated string for a given key.
        
        Args:
            key (str): The translation key (e.g., 'app.name').
            **kwargs: Optional keyword arguments for string formatting.
            
        Returns:
            str: The translated string, or the key if not found.
        """
        logging.debug(f"Translator: Requesting key '{key}' for language '{self.current_language}'")
        # Add logging to show current translations dictionary state
        logging.debug(f"Translator: Current translations state: {self.translations}")

        # Split the key into parts
        parts = key.split('.')
        
        # Navigate through the translations dictionary
        value = self.translations
        logging.debug(f"Translator: Starting navigation for key '{key}'. Initial value type: {type(value)}")
        for i, part in enumerate(parts):
            logging.debug(f"Translator: Navigating key part {i}: '{part}'. Current value type: {type(value)}")
            if isinstance(value, dict) and part in value:
                value = value[part]
                logging.debug(f"Translator: Found part '{part}'. Current value type: {type(value)}")
            else:
                # Translation not found, return the key
                logging.warning(f"Translator: Key '{key}' not found in translations for language '{self.current_language}'. Returning key.")
                return key
        
        # If the final value is not a string, return the key
        if not isinstance(value, str):
            logging.warning(f"Translator: Value for key '{key}' is not a string (type: {type(value)}). Returning key.")
            return key
        
        # Apply format arguments if provided
        if kwargs:
            logging.debug(f"Translator: Applying format arguments {kwargs} to translated value '{value}'")
            try:
                translated_value = value.format(**kwargs)
                logging.debug(f"Translator: Successfully translated and formatted key '{key}'. Result: '{translated_value}'")
                return translated_value
            except KeyError as e:
                logging.warning(f"Translator: Missing format argument in translation for key '{key}': {e}. Returning unformatted value.")
                return value
            except Exception as e:
                logging.error(f"Translator: Failed to format translation for key '{key}': {e}. Returning unformatted value.")
                return value
        
        logging.debug(f"Translator: Successfully translated key '{key}'. Result: '{value}'")
        return value

    def get_available_languages(self):
        """Get a list of available languages.
        
        Returns:
            list: A list of available language codes.
        """
        return AVAILABLE_LANGUAGES.copy()
    
    def get_language_name(self, language_code):
        """Get the name of a language in its native form.
        
        Args:
            language_code (str): The language code.
        
        Returns:
            str: The name of the language in its native form.
        """
        language_names = {
            'en': 'English',
            'ru': 'Русский'
        }
        return language_names.get(language_code, language_code)