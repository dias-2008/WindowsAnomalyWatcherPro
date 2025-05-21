#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Log Viewer Script

This script reads and displays the contents of the application log file.
"""

import os

LOG_FILE_PATH = "data/logs/app.log"

def view_logs():
    """Reads and prints the content of the log file."""
    log_file_absolute_path = os.path.join(os.path.dirname(__file__), '..', LOG_FILE_PATH)
    
    if not os.path.exists(log_file_absolute_path):
        print(f"Error: Log file not found at {log_file_absolute_path}")
        return

    try:
        with open(log_file_absolute_path, 'r', encoding='utf-8') as f:
            # Read all lines
            lines = f.readlines()
            
            # Print the last 100 lines (or fewer if the file is smaller)
            print("\n--- Application Logs (Last 100 Lines) ---\n")
            for line in lines[-100:]:
                print(line.strip())
            print("\n-----------------------------------------\n")

    except Exception as e:
        print(f"Error reading log file: {e}")

if __name__ == "__main__":
    view_logs()