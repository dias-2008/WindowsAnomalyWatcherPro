#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Logger Module

This module provides logging functionality for the Windows Anomaly Watcher PRO application.
"""

import os
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from config.settings import LOG_FILE, LOG_LEVEL, LOG_FORMAT, LOG_MAX_SIZE, LOG_BACKUP_COUNT


def setup_logger():
    """Set up the application logger.
    
    This function configures the logging system for the application.
    It sets up a file handler for logging to a file and a console handler
    for logging to the console.
    
    Returns:
        logging.Logger: The configured logger.
    """
    # Create the logs directory if it doesn't exist
    log_dir = Path(LOG_FILE).parent
    log_dir.mkdir(parents=True, exist_ok=True)
    
    # Configure the root logger
    logger = logging.getLogger()
    logger.setLevel(getattr(logging, LOG_LEVEL))
    
    # Remove existing handlers to avoid duplicates
    for handler in logger.handlers[:]:  # Make a copy of the list
        logger.removeHandler(handler)
    
    # Create a file handler for logging to a file
    file_handler = RotatingFileHandler(
        LOG_FILE,
        maxBytes=LOG_MAX_SIZE,
        backupCount=LOG_BACKUP_COUNT,
        encoding='utf-8'
    )
    file_handler.setLevel(getattr(logging, LOG_LEVEL))
    file_handler.setFormatter(logging.Formatter(LOG_FORMAT))
    logger.addHandler(file_handler)
    
    # Create a file handler for logging errors to a separate file
    error_file = Path(LOG_FILE).parent / "error.log"
    error_handler = RotatingFileHandler(
        error_file,
        maxBytes=LOG_MAX_SIZE,
        backupCount=LOG_BACKUP_COUNT,
        encoding='utf-8'
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(logging.Formatter(LOG_FORMAT))
    logger.addHandler(error_handler)
    
    # Create a console handler for logging to the console (during development)
    if os.environ.get('ANOMALY_WATCHER_DEBUG', '0') == '1':
        console_handler = logging.StreamHandler()
        console_handler.setLevel(getattr(logging, LOG_LEVEL))
        console_handler.setFormatter(logging.Formatter(LOG_FORMAT))
        logger.addHandler(console_handler)
    
    # Log that the logger has been set up
    logger.info("Logger initialized")
    
    return logger


def get_logger(name):
    """Get a logger with the specified name.
    
    Args:
        name (str): The name of the logger.
    
    Returns:
        logging.Logger: The logger with the specified name.
    """
    return logging.getLogger(name)