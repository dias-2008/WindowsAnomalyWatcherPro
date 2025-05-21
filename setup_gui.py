#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Setup GUI Module

This module provides a GUI for first-run setup of the Windows Anomaly Watcher PRO application.
It collects necessary information such as Telegram bot token and chat ID.
"""

import os
import sys
import logging
from pathlib import Path
from threading import Thread
import asyncio
from tkinter import filedialog, messagebox

# Add project root to path to ensure imports work correctly
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Try to import customtkinter, fall back to tkinter if not available
try:
    import customtkinter as ctk
    CTK_AVAILABLE = True
except ImportError:
    import tkinter as tk
    from tkinter import ttk
    CTK_AVAILABLE = False
    logging.warning("CustomTkinter not available, falling back to standard Tkinter")

from config.config_manager import ConfigManager
from config.settings import APP_NAME, VERSION
from i18n.translator import Translator, AVAILABLE_LANGUAGES
from telegram_bot.bot import TelegramBot


def show_setup_gui(config_manager):
    """Show the setup GUI to collect necessary information.
    
    Returns:
        bool: True if setup was completed successfully, False otherwise.
    """
    # Initialize translator with default language
    translator = Translator()
    
    # Use the provided config manager instance
    
    # Flag to indicate if setup was successful
    setup_completed_successfully = False
    
    # Create the setup window
    if CTK_AVAILABLE:
        # Use CustomTkinter for a modern look
        ctk.set_appearance_mode("System")  # Use system theme
        ctk.set_default_color_theme("blue")
        
        root = ctk.CTk()
        root.title(translator.get("setup.title"))
        root.geometry("600x650")
        root.resizable(False, False)
        
        # Set window icon if available
        try:
            icon_path = project_root / "data" / "icon.ico"
            if icon_path.exists():
                root.iconbitmap(str(icon_path))
        except Exception as e:
            logging.warning(f"Failed to set window icon: {e}")
        
        # Create the main frame
        main_frame = ctk.CTkFrame(root)
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        # Welcome label
        welcome_label = ctk.CTkLabel(
            main_frame,
            text=translator.get("setup.welcome"),
            font=ctk.CTkFont(size=20, weight="bold")
        )
        welcome_label.pack(pady=(0, 10))
        
        # Instructions label
        instructions_label = ctk.CTkLabel(
            main_frame,
            text=translator.get("setup.instructions"),
            font=ctk.CTkFont(size=14)
        )
        instructions_label.pack(pady=(0, 20))
        
        # Telegram Bot Token
        token_label = ctk.CTkLabel(
            main_frame,
            text=translator.get("setup.telegram_token"),
            font=ctk.CTkFont(size=14, weight="bold")
        )
        token_label.pack(anchor="w", padx=10)
        
        token_help_label = ctk.CTkLabel(
            main_frame,
            text=translator.get("setup.telegram_token_help"),
            font=ctk.CTkFont(size=12),
            text_color="gray"
        )
        token_help_label.pack(anchor="w", padx=10)
        
        token_entry = ctk.CTkEntry(main_frame, width=560, placeholder_text="1234567890:ABCDEFGHIJKLMNOPQRSTUVWXYZ")
        token_entry.pack(fill="x", padx=10, pady=(5, 15))
        token_entry.insert(0, config_manager.get("telegram_token", ""))
        
        # Telegram Chat ID
        chat_id_label = ctk.CTkLabel(
            main_frame,
            text=translator.get("setup.telegram_chat_id"),
            font=ctk.CTkFont(size=14, weight="bold")
        )
        chat_id_label.pack(anchor="w", padx=10)
        
        chat_id_help_label = ctk.CTkLabel(
            main_frame,
            text=translator.get("setup.telegram_chat_id_help"),
            font=ctk.CTkFont(size=12),
            text_color="gray"
        )
        chat_id_help_label.pack(anchor="w", padx=10)
        
        chat_id_entry = ctk.CTkEntry(main_frame, width=560, placeholder_text="123456789")
        chat_id_entry.pack(fill="x", padx=10, pady=(5, 15))
        chat_id_entry.insert(0, config_manager.get("telegram_chat_id", ""))
        
        # Language selection
        language_label = ctk.CTkLabel(
            main_frame,
            text=translator.get("setup.language"),
            font=ctk.CTkFont(size=14, weight="bold")
        )
        language_label.pack(anchor="w", padx=10)
        
        language_var = ctk.StringVar(value=config_manager.get("language", "en"))
        language_frame = ctk.CTkFrame(main_frame)
        language_frame.pack(fill="x", padx=10, pady=(5, 15))
        
        for i, lang_code in enumerate(AVAILABLE_LANGUAGES):
            lang_name = translator.get_language_name(lang_code)
            lang_radio = ctk.CTkRadioButton(
                language_frame,
                text=lang_name,
                variable=language_var,
                value=lang_code
            )
            lang_radio.pack(side="left", padx=10)
        
        # Start with Windows checkbox
        startup_var = ctk.BooleanVar(value=config_manager.get("start_with_windows", True))
        startup_checkbox = ctk.CTkCheckBox(
            main_frame,
            text=translator.get("setup.start_with_windows"),
            variable=startup_var
        )
        startup_checkbox.pack(anchor="w", padx=10, pady=(5, 15))
        
        # Monitored folders
        folders_label = ctk.CTkLabel(
            main_frame,
            text=translator.get("setup.monitored_folders"),
            font=ctk.CTkFont(size=14, weight="bold")
        )
        folders_label.pack(anchor="w", padx=10)
        
        # Frame for folders list and buttons
        folders_frame = ctk.CTkFrame(main_frame)
        folders_frame.pack(fill="x", padx=10, pady=(5, 15))
        
        # Listbox for folders
        folders_listbox = ctk.CTkTextbox(folders_frame, height=100)
        folders_listbox.pack(fill="x", side="top", padx=5, pady=5)
        
        # Add the current monitored folders to the listbox
        monitored_folders = config_manager.get("monitored_folders", [])
        folders_listbox.delete("1.0", "end")
        for folder in monitored_folders:
            folders_listbox.insert("end", f"{folder}\n")
        
        # Buttons frame
        buttons_frame = ctk.CTkFrame(folders_frame)
        buttons_frame.pack(fill="x", side="bottom", padx=5, pady=5)
        
        def add_folder():
            folder = filedialog.askdirectory()
            if folder:
                folders_listbox.insert("end", f"{folder}\n")
        
        def remove_folder():
            try:
                # Get the current line
                current_line = folders_listbox.index("insert")
                line_start = f"{int(float(current_line))}.0"
                line_end = f"{int(float(current_line)) + 1}.0"
                folders_listbox.delete(line_start, line_end)
            except Exception as e:
                logging.error(f"Failed to remove folder: {e}")
        
        add_button = ctk.CTkButton(
            buttons_frame,
            text=translator.get("setup.add_folder"),
            command=add_folder
        )
        add_button.pack(side="left", padx=5)
        
        remove_button = ctk.CTkButton(
            buttons_frame,
            text=translator.get("setup.remove_folder"),
            command=remove_folder
        )
        remove_button.pack(side="left", padx=5)
        
        # Test connection button
        def test_connection():
            token = token_entry.get().strip()
            chat_id = chat_id_entry.get().strip()

            if not token or not chat_id:
                messagebox.showerror(
                    "Error",
                    "Please enter both Telegram bot token and chat ID."
                )
                return

            # Disable the button during testing
            test_button.configure(state="disabled", text="Testing...")
            root.update()

            # Test the connection in a separate thread to avoid freezing the UI
            def test_thread(config_manager, translator):
                try:
                    # Instantiate TelegramBot and call the test method
                    telegram_bot_instance = TelegramBot(config_manager, translator)
                    # Use asyncio.run to execute the async method
                    success, message = asyncio.run(telegram_bot_instance.test_telegram_connection(token, chat_id))

                    # Re-enable the button and show result in the main thread
                    root.after(0, lambda: test_button.configure(state="normal", text=translator.get("setup.test_connection")))
                    if success:
                        root.after(0, lambda: messagebox.showinfo("Success", translator.get("setup.connection_success")))
                    else:
                        root.after(0, lambda: messagebox.showerror("Error", f"{translator.get('setup.connection_failed')}\n{message}"))
                except Exception as e:
                    logging.error(f"Error during connection test thread: {e}")
                    root.after(0, lambda: test_button.configure(state="normal", text=translator.get("setup.test_connection")))
                    root.after(0, lambda: messagebox.showerror("Error", f"An unexpected error occurred during the test: {e}"))

            # Start the test thread
            thread = Thread(target=test_thread, args=(config_manager, translator))
            thread.start()

        test_button = ctk.CTkButton(
            main_frame,
            text=translator.get("setup.test_connection"),
            command=test_connection
        )
        test_button.pack(pady=(10, 20))
        
        # Buttons frame for save and cancel
        action_buttons_frame = ctk.CTkFrame(main_frame)
        action_buttons_frame.pack(fill="x", side="bottom", padx=10, pady=10)
        
        def save_settings():
            # Get values from the form
            token = token_entry.get().strip()
            chat_id = chat_id_entry.get().strip()
            language = language_var.get()
            start_with_windows = startup_var.get()
            
            # Get monitored folders from the listbox
            folders_text = folders_listbox.get("1.0", "end").strip()
            monitored_folders = [folder for folder in folders_text.split("\n") if folder]
            
            # Validate required fields
            if not token or not chat_id:
                messagebox.showerror(
                    "Error",
                    "Please enter both Telegram bot token and chat ID."
                )
                return
            
            # Set the settings in the config manager instance
            config_manager.config["telegram_token"] = token
            config_manager.config["telegram_chat_id"] = chat_id
            config_manager.config["language"] = language
            config_manager.config["start_with_windows"] = start_with_windows
            config_manager.config["monitored_folders"] = monitored_folders
            
            # Save the settings to file and check for success
            if config_manager.save():
                # Set the flag to True
                nonlocal setup_completed_successfully
                setup_completed_successfully = True
                
                # Show success message
                messagebox.showinfo("Success", translator.get("setup.setup_complete"))
                
                # Close the window
                root.quit()
                root.destroy()
            else:
                # Show error message if saving failed
                messagebox.showerror(
                    "Error",
                    translator.get("setup.save_failed")
                )

        def cancel():
            if messagebox.askyesno("Cancel", "Are you sure you want to cancel setup? The application will not run without configuration."):
                root.quit()
                root.destroy()
        
        # Save and Start button
        save_button = ctk.CTkButton(
            main_frame,
            text=translator.get("setup.save"), # This already uses the translation key
            command=save_settings
        )
        save_button.pack(pady=20)

        cancel_button = ctk.CTkButton(
            action_buttons_frame,
            text=translator.get("setup.cancel"),
            command=cancel
        )
        cancel_button.pack(side="right", padx=5)
        
    else:
        # Fall back to standard Tkinter
        root = tk.Tk()
        root.title(translator.get("setup.title"))
        root.geometry("600x650")
        root.resizable(False, False)
        
        # Set window icon if available
        try:
            icon_path = project_root / "data" / "icon.ico"
            if icon_path.exists():
                root.iconbitmap(str(icon_path))
        except Exception as e:
            logging.warning(f"Failed to set window icon: {e}")
        
        # Create the main frame
        main_frame = ttk.Frame(root, padding=20)
        main_frame.pack(fill="both", expand=True)
        
        # Welcome label
        welcome_label = ttk.Label(
            main_frame,
            text=translator.get("setup.welcome"),
            font=("TkDefaultFont", 16, "bold")
        )
        welcome_label.pack(pady=(0, 10))
        
        # Instructions label
        instructions_label = ttk.Label(
            main_frame,
            text=translator.get("setup.instructions"),
            font=("TkDefaultFont", 12)
        )
        instructions_label.pack(pady=(0, 20))
        
        # Telegram Bot Token
        token_label = ttk.Label(
            main_frame,
            text=translator.get("setup.telegram_token"),
            font=("TkDefaultFont", 12, "bold")
        )
        token_label.pack(anchor="w", padx=10)
        
        token_help_label = ttk.Label(
            main_frame,
            text=translator.get("setup.telegram_token_help"),
            font=("TkDefaultFont", 10),
            foreground="gray"
        )
        token_help_label.pack(anchor="w", padx=10)
        
        token_entry = ttk.Entry(main_frame, width=60)
        token_entry.pack(fill="x", padx=10, pady=(5, 15))
        token_entry.insert(0, config_manager.get("telegram_token", ""))
        
        # Telegram Chat ID
        chat_id_label = ttk.Label(
            main_frame,
            text=translator.get("setup.telegram_chat_id"),
            font=("TkDefaultFont", 12, "bold")
        )
        chat_id_label.pack(anchor="w", padx=10)
        
        chat_id_help_label = ttk.Label(
            main_frame,
            text=translator.get("setup.telegram_chat_id_help"),
            font=("TkDefaultFont", 10),
            foreground="gray"
        )
        chat_id_help_label.pack(anchor="w", padx=10)
        
        chat_id_entry = ttk.Entry(main_frame, width=60)
        chat_id_entry.pack(fill="x", padx=10, pady=(5, 15))
        chat_id_entry.insert(0, config_manager.get("telegram_chat_id", ""))
        
        # Language selection
        language_label = ttk.Label(
            main_frame,
            text=translator.get("setup.language"),
            font=("TkDefaultFont", 12, "bold")
        )
        language_label.pack(anchor="w", padx=10)
        
        language_var = tk.StringVar(value=config_manager.get("language", "en"))
        language_frame = ttk.Frame(main_frame)
        language_frame.pack(fill="x", padx=10, pady=(5, 15))
        
        for i, lang_code in enumerate(AVAILABLE_LANGUAGES):
            lang_name = translator.get_language_name(lang_code)
            lang_radio = ttk.Radiobutton(
                language_frame,
                text=lang_name,
                variable=language_var,
                value=lang_code
            )
            lang_radio.pack(side="left", padx=10)
        
        # Start with Windows checkbox
        startup_var = tk.BooleanVar(value=config_manager.get("start_with_windows", True))
        startup_checkbox = ttk.Checkbutton(
            main_frame,
            text=translator.get("setup.start_with_windows"),
            variable=startup_var
        )
        startup_checkbox.pack(anchor="w", padx=10, pady=(5, 15))
        
        # Monitored folders
        folders_label = ttk.Label(
            main_frame,
            text=translator.get("setup.monitored_folders"),
            font=("TkDefaultFont", 12, "bold")
        )
        folders_label.pack(anchor="w", padx=10)
        
        # Frame for folders list and buttons
        folders_frame = ttk.Frame(main_frame)
        folders_frame.pack(fill="x", padx=10, pady=(5, 15))
        
        # Listbox for folders
        folders_listbox = tk.Text(folders_frame, height=6, width=60)
        folders_listbox.pack(fill="x", side="top", padx=5, pady=5)
        
        # Add the current monitored folders to the listbox
        monitored_folders = config_manager.get("monitored_folders", [])
        folders_listbox.delete("1.0", "end")
        for folder in monitored_folders:
            folders_listbox.insert("end", f"{folder}\n")
        
        # Buttons frame
        buttons_frame = ttk.Frame(folders_frame)
        buttons_frame.pack(fill="x", side="bottom", padx=5, pady=5)
        
        def add_folder():
            folder = filedialog.askdirectory()
            if folder:
                folders_listbox.insert("end", f"{folder}\n")
        
        def remove_folder():
            try:
                # Get the current line
                current_line = folders_listbox.index("insert")
                line_start = f"{int(float(current_line))}.0"
                line_end = f"{int(float(current_line)) + 1}.0"
                folders_listbox.delete(line_start, line_end)
            except Exception as e:
                logging.error(f"Failed to remove folder: {e}")
        
        add_button = ttk.Button(
            buttons_frame,
            text=translator.get("setup.add_folder"),
            command=add_folder
        )
        add_button.pack(side="left", padx=5)
        
        remove_button = ttk.Button(
            buttons_frame,
            text=translator.get("setup.remove_folder"),
            command=remove_folder
        )
        remove_button.pack(side="left", padx=5)
        
        # Test connection button
        def test_connection():
            token = token_entry.get().strip()
            chat_id = chat_id_entry.get().strip()
            
            if not token or not chat_id:
                messagebox.showerror(
                    "Error",
                    "Please enter both Telegram bot token and chat ID."
                )
                return
            
            # Disable the button during testing
            test_button.configure(state="disabled")
            test_button.configure(text="Testing...")
            root.update()
            
            # Test the connection in a separate thread to avoid freezing the UI
            def test_thread():
                success, message = test_telegram_connection(token, chat_id)
                
                # Re-enable the button
                test_button.configure(state="normal")
                test_button.configure(text=translator.get("setup.test_connection"))
                
                if success:
                    messagebox.showinfo("Success", translator.get("setup.connection_success"))
                else:
                    messagebox.showerror("Error", f"{translator.get('setup.connection_failed')}\n\nDetails: {message}")
            
            Thread(target=test_thread, args=(config_manager, translator)).start()
        
        test_button = ttk.Button(
            main_frame,
            text=translator.get("setup.test_connection"),
            command=test_connection
        )
        test_button.pack(pady=(10, 20))
        
        # Buttons frame for save and cancel
        action_buttons_frame = ttk.Frame(main_frame)
        action_buttons_frame.pack(fill="x", side="bottom", padx=10, pady=10)
        
        def save_settings():
            # Get values from the form
            token = token_entry.get().strip()
            chat_id = chat_id_entry.get().strip()
            language = language_var.get()
            start_with_windows = startup_var.get()
            
            # Get monitored folders from the listbox
            folders_text = folders_listbox.get("1.0", "end").strip()
            monitored_folders = [folder for folder in folders_text.split("\n") if folder]
            
            # Validate required fields
            if not token or not chat_id:
                messagebox.showerror(
                    "Error",
                    "Please enter both Telegram bot token and chat ID."
                )
                return
            
            # Save the settings
            config_manager.set("telegram_token", token)
            config_manager.set("telegram_chat_id", chat_id)
            config_manager.set("language", language)
            config_manager.set("start_with_windows", start_with_windows)
            config_manager.set("monitored_folders", monitored_folders)
            
            # Show success message
            messagebox.showinfo("Success", translator.get("setup.setup_complete"))
            
            # Close the window
            root.quit()
            root.destroy()
        
        def cancel():
            if messagebox.askyesno("Cancel", "Are you sure you want to cancel setup? The application will not run without configuration."):
                root.quit()
                root.destroy()
        
        save_button = ttk.Button(
            action_buttons_frame,
            text=translator.get("setup.save"),
            command=save_settings
        )
        save_button.pack(side="right", padx=5)
        
        cancel_button = ttk.Button(
            action_buttons_frame,
            text=translator.get("setup.cancel"),
            command=cancel
        )
        cancel_button.pack(side="right", padx=5)
    
    # Center the window on the screen
    root.update_idletasks()
    width = root.winfo_width()
    height = root.winfo_height()
    x = (root.winfo_screenwidth() // 2) - (width // 2)
    y = (root.winfo_screenheight() // 2) - (height // 2)
    root.geometry(f"{width}x{height}+{x}+{y}")
    
    # Run the main loop
    root.mainloop()
    
    # Check if the configuration is complete
    return config_manager.is_configured()


if __name__ == "__main__":
    # This is a test call for the GUI
    # In the actual application, show_setup_gui is called from main.py
    # with a ConfigManager instance.
    # Create a dummy config manager for testing
    class DummyConfigManager:
        def __init__(self):
            self.config = {}

        def get(self, key, default=None):
            return self.config.get(key, default)

        def set(self, key, value):
            self.config[key] = value

        def save(self):
            print("Dummy config saved:", self.config)
            return True # Simulate successful save

    dummy_config_manager = DummyConfigManager()

    # Show the GUI
    show_setup_gui(dummy_config_manager)