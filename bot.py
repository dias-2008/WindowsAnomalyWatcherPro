import logging
import logging
import asyncio
import threading
import telegram
from telegram import Update, InlineKeyboardButton, Bot, InlineKeyboardMarkup, InputFile # Import InputFile
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, CallbackContext, CallbackQueryHandler
import subprocess
import io # Needed for sending bytes as a file
from utils.screenshot import take_screenshot # Import the screenshot function
from datetime import datetime, timedelta # Import datetime and timedelta

class TelegramBot:
    def __init__(self, config, translator, app_instance=None):
        self.config = config
        self.translator = translator
        self.app_instance = app_instance # Reference to the main application instance
        self.application = None
        self._polling_ready_event = threading.Event()
        self._polling_thread = threading.Thread(target=self._run_bot_polling, daemon=True)
        self.token = config.get('telegram_token')
        self.chat_id = config.get('telegram_chat_id')
        self.running = False # Add this line
        self._bot_loop = None # Initialize _bot_loop to None
        self._message_details = {} # Dictionary to store original message details (text, reply_markup)

        # Initialize the Application instance
        if self.token:
            self.application = Application.builder().token(self.token).build()
            self.initialize_handlers()
        else:
            logging.error("Telegram token not configured. Bot will not start.")
            self.application = None

        logging.info(f"TelegramBot initialized with translator language: {self.translator.current_language}")

    async def stop_bot(self):
        """Stop the bot's polling mechanism."""
        logging.info("Stopping Telegram bot polling...")
        self.running = False # Signal the polling loop to stop
        if self.application:
            # Stop the application gracefully
            await self.application.shutdown()
            logging.info("Telegram bot application shutdown called.")

        # Wait for the polling thread to finish
        if self._polling_thread and self._polling_thread.is_alive():
            logging.info("Telegram bot polling stopped.")
            self._polling_thread.join()

    def _run_bot_polling(self):
        """Run the bot's polling mechanism in a separate thread."""
        if not self.application:
            logging.error("Telegram bot application not initialized. Cannot start polling.")
            self.running = False
            return

        try:
            # Create and set a new event loop for this thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            self._bot_loop = loop # Store the event loop

            # Signal that polling is ready
            self._polling_ready_event.set()
            logging.info("Telegram bot polling started.")

            # Start polling
            self.application.run_polling()

        except Exception as e:
            logging.error(f"Error during bot polling: {e}")
        finally:
            # The application.run_polling() should block until stop_polling() is called.
            # The stop_polling() method should handle the loop termination.
            # Explicitly stopping the loop here might interfere.
            pass # Rely on application.stop_polling() to terminate the loop

        logging.info("Telegram bot polling stopped.")
        self.running = False
        self.running = False

    def initialize_handlers(self):
        """Initialize bot handlers."""
        if not self.application:
            logging.warning("Telegram bot application not initialized. Cannot initialize handlers.")
            return

        # Add command handlers
        self.application.add_handler(CommandHandler("start", self.start_command))

        # Add callback query handler
        self.application.add_handler(CallbackQueryHandler(self.button_callback))

        logging.info("Telegram bot handlers initialized.")

    async def start_command(self, update: Update, context: CallbackContext) -> None:
        """Handles the /start command."""
        logging.info("Received /start command")
        await self.send_startup_message()

    async def button_callback(self, update: Update, context: CallbackContext) -> None:
        """Handles button presses."""
        query = update.callback_query
        try:
            await query.answer()
        except telegram.error.TimedOut:
            logging.warning("Telegram API timed out when answering callback query.")
            # Optionally, you could add a retry mechanism or a different notification here
            pass # Continue processing the callback even if answering fails

        data = query.data
        logging.info(f"Received callback query: {data}")

        try:
            if data == 'start_monitoring':
                # Call the start_monitoring method on the main application instance
                if self.app_instance:
                    await query.edit_message_text(text=self.translator.get("telegram.monitoring_started"))
                    self.app_instance.start_monitoring()
                else:
                    await query.edit_message_text(text=self.translator.get("Application instance not available to start monitoring."))
            elif data == 'stop_monitoring':
                 # Start the pause selection process and present pause options
                if self.app_instance:
                    self.app_instance.start_pause_selection() # Immediately set paused state for buffering
                    pause_keyboard = [
                        [InlineKeyboardButton(self.translator.get("telegram.buttons.pause_10"), callback_data='pause_10')],
                        [InlineKeyboardButton(self.translator.get("telegram.buttons.pause_30"), callback_data='pause_30')],
                        [InlineKeyboardButton(self.translator.get("telegram.buttons.pause_60"), callback_data='pause_60')],
                        [InlineKeyboardButton(self.translator.get("telegram.buttons.cancel"), callback_data='cancel')]
                    ]
                    pause_reply_markup = InlineKeyboardMarkup(pause_keyboard)
                    await query.edit_message_text(text=self.translator.get("Choose pause duration:"), reply_markup=pause_reply_markup)
                else:
                    await query.edit_message_text(text=self.translator.get("Application instance not available to pause monitoring."))
            elif data == 'window_change_ack':
                # Start the pause selection process after acknowledging and present pause options
                if self.app_instance:
                    self.app_instance.start_pause_selection() # Immediately set paused state for buffering
                    pause_keyboard = [
                        [InlineKeyboardButton(self.translator.get("telegram.buttons.pause_10"), callback_data='pause_10')],
                        [InlineKeyboardButton(self.translator.get("telegram.buttons.pause_30"), callback_data='pause_30')],
                        [InlineKeyboardButton(self.translator.get("telegram.buttons.pause_60"), callback_data='pause_60')],
                        [InlineKeyboardButton(self.translator.get("telegram.buttons.cancel"), callback_data='cancel')]
                    ]
                    pause_reply_markup = InlineKeyboardMarkup(pause_keyboard)
                    # Use the correct translation key for the acknowledged message
                    await query.edit_message_text(text=self.translator.get("telegram.buttons.yes_its_me"), reply_markup=pause_reply_markup)
                else:
                    await query.edit_message_text(text=self.translator.get("Acknowledged: Yes, it's me. Application instance not available to pause monitoring."))
            elif data.startswith('pause_'):
                try:
                    minutes = int(data.split('_')[1])
                    if self.app_instance:
                        self.app_instance.pause_monitoring(minutes)
                        await query.edit_message_text(text=self.translator.get("Monitoring paused for {minutes} minutes.").format(minutes=minutes))
                    else:
                        await query.edit_message_text(text=self.translator.get("Application instance not available to pause monitoring."))
                except ValueError:
                    logging.error(f"Invalid pause duration: {data}")
                    await query.edit_message_text(text=self.translator.get("Invalid pause command."))
            elif data == 'review_events':
                # Handle review button press
                if self.app_instance and self.app_instance.event_grouper:
                    events = await self.app_instance.event_grouper.get_paused_buffered_events()
                    if events:
                        review_message = self.translator.get("Events during pause:") + "\n\n"
                        for event in events:
                            # Format event for display (adjust as needed based on event structure)
                            event_str = f"Type: {event.get('type', 'N/A')}, Details: {event.get('details', 'N/A')}"
                            review_message += f"- {event_str}\n"
                        await query.edit_message_text(text=review_message)
                    else:
                        await query.edit_message_text(text=self.translator.get("No events occurred during the pause."))
                else:
                    await query.edit_message_text(text=self.translator.get("Event grouper not available."))
            elif data == 'lock_pc':
                # Implement PC locking logic
                try:
                    subprocess.run(["rundll32.exe", "user32.dll,LockWorkStation"], check=True)
                    await query.edit_message_text(text=self.translator.get("PC locked."))
                except Exception as e:
                    logging.error(f"Failed to lock PC: {e}")
                    await query.edit_message_text(text=self.translator.get("Failed to lock PC: {e}").format(e=e))
            
            elif data == 'shutdown_pc':
                # Ask for confirmation before shutting down
                confirmation_keyboard = [
                    [InlineKeyboardButton(self.translator.get("telegram.buttons.yes"), callback_data='confirm_shutdown_yes')],
                    [InlineKeyboardButton(self.translator.get("telegram.buttons.no"), callback_data='confirm_shutdown_no')]
                ]
                confirmation_reply_markup = InlineKeyboardMarkup(confirmation_keyboard)
                await query.edit_message_text(text=self.translator.get("Are you sure you want to shut down the PC?"), reply_markup=confirmation_reply_markup)
            elif data == 'confirm_shutdown_yes':
                # Implement PC shutdown logic (requires appropriate permissions)
                try:
                    # Use subprocess.run with shell=True for shutdown command on Windows
                    subprocess.run(["shutdown", "/s", "/t", "0"], check=True, shell=True)
                    await query.edit_message_text(text=self.translator.get("PC is shutting down."))
                except Exception as e:
                    logging.error(f"Failed to shutdown PC: {e}")
                    await query.edit_message_text(text=self.translator.get("Failed to shutdown PC: {e}").format(e=e))
            elif data == 'confirm_shutdown_no':
                if self.app_instance and self.app_instance.event_grouper:
                    self.app_instance.event_grouper.clear_stopped()
                await query.edit_message_text(text=self.translator.get("Shutdown cancelled."))
            elif data.startswith('show_details_'):
                # Implement showing details logic
                try:
                    event_id = data.split('_', 2)[2] # Split by '_' and get the third part (the ID)
                    if self.app_instance and self.app_instance.event_grouper and event_id in self.app_instance.event_grouper._detailed_event_info:
                        detailed_info = self.app_instance.event_grouper._detailed_event_info[event_id]

                        # Store original message text and reply markup before editing
                        original_message = query.message
                        message_id = original_message.message_id
                        chat_id = original_message.chat_id
                        # Store details using message_id as key
                        self._message_details[message_id] = {
                            'text': original_message.text,
                            'reply_markup': original_message.reply_markup
                        }

                        # Format the detailed info for display
                        if isinstance(detailed_info, list):
                             # Handle buffered events list
                             message_lines = [self.translator.get('telegram.notification.buffered_events.details_title')] # Use a specific title for buffered events details
                             for event in detailed_info:
                                 # Basic formatting for each event in the list
                                 event_type = event.get('type', 'N/A')
                                 # Ensure timestamp_obj is a datetime object
                                 timestamp_obj = event.get('timestamp', datetime.now())
                                 if isinstance(timestamp_obj, str):
                                     try:
                                         # Assuming the string format is compatible with datetime parsing
                                         # You might need to adjust the format string based on how timestamps are stored
                                         timestamp_obj = datetime.fromisoformat(timestamp_obj)
                                     except ValueError:
                                         logging.error(f"Failed to parse timestamp string: {timestamp_obj}")
                                         timestamp_obj = datetime.now() # Fallback to current time on error
                                 elif not isinstance(timestamp_obj, datetime):
                                     logging.error(f"Unexpected timestamp type: {type(timestamp_obj)}. Falling back to current time.")
                                     timestamp_obj = datetime.now() # Fallback for unexpected types

                                 # Now timestamp_obj is guaranteed to be a datetime object
                                 logging.debug(f"Timestamp object type before strftime: {type(timestamp_obj)}, value: {timestamp_obj}") # Add this line
                                 timestamp = timestamp_obj.strftime('%H:%M:%S')
                                 details = event.get('details', 'N/A')
                                 message_lines.append(f"\n<b>Type:</b> {event_type}\n<b>Time:</b> {timestamp}\n<b>Details:</b> {details}")
                             details_text = "\n".join(message_lines)
                        else:
                            # Assume it's a string for single event details (like window change)
                            details_text = detailed_info

                        # Combine original message text with detailed info
                        combined_text = original_message.text + "\n\n" + details_text

                        # Modify the keyboard to replace 'Show details' with 'Hide details'
                        original_keyboard = original_message.reply_markup.inline_keyboard
                        new_keyboard = []
                        for row in original_keyboard:
                            new_row = []
                            for button in row:
                                if button.callback_data == f'show_details_{event_id}':
                                    # Replace 'Show details' with 'Hide details'
                                    new_row.append(InlineKeyboardButton(text=self.translator.get("telegram.buttons.hide_details"), callback_data=f'hide_details_{event_id}'))
                                else:
                                    new_row.append(button)
                            new_keyboard.append(new_row)
                        new_reply_markup = InlineKeyboardMarkup(new_keyboard)

                        # Edit the message to show details and the new keyboard
                        await query.edit_message_text(
                            text=combined_text,
                            reply_markup=new_reply_markup,
                            parse_mode=ParseMode.HTML # Ensure HTML parsing is enabled for bold tags
                        )
                        logging.info(f"Showed details for event ID: {event_id}")
                    else:
                        await query.edit_message_text(text=self.translator.get("Details not found."))
                except Exception as e:
                    logging.error(f"Error showing details for event ID {event_id}: {e}")
                    await query.edit_message_text(text=self.translator.get("Failed to show details: {e}").format(e=e))
            elif data.startswith('show_window_details'): # New handler for individual window details
                # Implement showing details logic for individual window events
                try:
                    # The event ID is not part of the callback data for individual alerts,
                    # so we need to retrieve the details based on the message ID.
                    message_id = query.message.message_id
                    chat_id = query.message.chat_id
                    message_key = f"{chat_id}:{message_id}"

                    if message_key in self._message_details and 'detailed_info' in self._message_details[message_key]:
                        detailed_info = self._message_details[message_key]['detailed_info']

                        # Store original message text and reply markup before editing
                        original_message = query.message
                        # No need to store again, it's already in _message_details

                        # Format the detailed info for display (assuming it's a dictionary for window events)
                        message_lines = [f"<b>{self.translator.get('alerts.window.details_title')}</b>"] # Use the specific title for window details
                        # Add specific window details based on the structure of event_details
                        message_lines.append(f"{self.translator.get('alerts.window.details.application_label')}: {detailed_info.get('process_name', 'N/A')}")
                        message_lines.append(f"{self.translator.get('commands.window.details.title_label')}: {detailed_info.get('window_title', 'N/A')}")
                        message_lines.append(f"{self.translator.get('commands.window.details.path_label')}: {detailed_info.get('process_path', 'N/A')}")
                        # Add more details as needed based on your event structure

                        details_text = "\n".join(message_lines)

                        # Combine original message text with detailed info
                        # Retrieve the original text from storage to avoid issues with previous edits
                        original_text = self._message_details[message_key]['text']
                        combined_text = original_text + "\n\n" + details_text

                        # Modify the keyboard...
                        original_keyboard = original_message.reply_markup.inline_keyboard
                        new_keyboard = []
                        for row in original_keyboard:
                            new_row = []
                            for button in row:
                                if button.callback_data == data: # Check against 'show_window_details'
                                    # Replace 'Show details' with 'Hide details'
                                    new_row.append(InlineKeyboardButton(text=self.translator.get("telegram.buttons.hide_details"), callback_data=f'hide_window_details_{message_id}')) # Use message_id for hide callback
                                else:
                                    new_row.append(button)
                            new_keyboard.append(new_row)
                        new_reply_markup = InlineKeyboardMarkup(new_keyboard)

                        # Edit the message to show details and the new keyboard
                        await query.edit_message_text(
                            text=combined_text,
                            reply_markup=new_reply_markup,
                            parse_mode=ParseMode.HTML # Ensure HTML parsing is enabled for bold tags
                        )
                        logging.info(f"Showed details for window event message ID: {message_id}")
                    else:
                        await query.edit_message_text(text=self.translator.get("Details not available for this message."))
                except Exception as e:
                    logging.error(f"Error showing window details: {e}")
                    await query.edit_message_text(text=self.translator.get("Failed to show details: {e}").format(e=e))
            elif data.startswith('hide_details_'): # Modified to specifically handle grouped details hide
                # Implement hiding details logic for grouped events
                try:
                    event_id = data.split('_', 2)[2] # Split by '_' and get the third part (the ID)
                    message_id = query.message.message_id
                    if message_id in self._message_details:
                        original_details = self._message_details.pop(message_id) # Retrieve and remove original details
                        original_text = original_details['text']
                        original_reply_markup = original_details['reply_markup']

                        # Edit the message back to its original state
                        await query.edit_message_text(
                            text=original_text,
                            reply_markup=original_reply_markup,
                            parse_mode=ParseMode.HTML # Ensure HTML parsing is enabled
                        )
                        logging.info(f"Hid details for grouped event ID: {event_id}")
                    else:
                        await query.edit_message_text(text=self.translator.get("Details are already hidden or not present.")) # Use a more appropriate message
                except Exception as e:
                    logging.error(f"Error hiding grouped details: {e}")
                    await query.edit_message_text(text=self.translator.get("Failed to hide details: {e}").format(e=e))
            elif data.startswith('hide_window_details_'): # New handler for individual window details hide
                # Implement hiding details logic for individual window events
                try:
                    message_id = int(data.split('_', 3)[3]) # Split by '_' and get the fourth part (the message ID)
                    chat_id = query.message.chat_id
                    message_key = f"{chat_id}:{message_id}"

                    if message_key in self._message_details:
                        original_details = self._message_details.pop(message_key) # Retrieve and remove original details
                        original_text = original_details['text']
                        original_reply_markup = original_details['reply_markup']

                        # Edit the message back to its original state
                        await query.edit_message_text(
                            text=original_text,
                            reply_markup=original_reply_markup,
                            parse_mode=ParseMode.HTML # Ensure HTML parsing is enabled
                        )
                        logging.info(f"Hid details for window event message ID: {message_id}")
                    else:
                        await query.edit_message_text(text=self.translator.get("Details are already hidden or not present.")) # Use a more appropriate message
                except Exception as e:
                    logging.error(f"Error hiding window details: {e}")
                    await query.edit_message_text(text=self.translator.get("Failed to hide details: {e}").format(e=e))
            elif data == 'take_screenshot':
                # Implement take screenshot logic
                try:
                    screenshot_result = take_screenshot() # Call the screenshot function
                    if screenshot_result and len(screenshot_result) > 1:
                        screenshot_bytes = screenshot_result[1] # Extract the bytes from the tuple
                        if screenshot_bytes:
                            # Send the screenshot as a photo
                            chat_id = query.message.chat_id
                            await context.bot.send_photo(chat_id=chat_id, photo=InputFile(io.BytesIO(screenshot_bytes), filename='screenshot.png'))
                            await query.edit_message_text(text=self.translator.get("Screenshot taken.")) # Acknowledge the action
                            logging.info("Screenshot sent successfully.")
                        else:
                            await query.edit_message_text(text=self.translator.get("Failed to take screenshot."))
                            logging.error("Failed to take screenshot: screenshot_bytes is None.")
                except Exception as e:
                    logging.error(f"Error taking or sending screenshot: {e}")
                    await query.edit_message_text(text=self.translator.get("Error handling screenshot callback: {e}").format(e=e))
            elif data == 'cancel':
                await query.edit_message_text(text=self.translator.get("Operation cancelled."))
        except Exception as e:
            logging.error(f"Error handling callback query: {e}")
            # Add more specific error handling or logging here if needed
            try:
                # Attempt to send a generic error message back to the user via the callback query
                # Avoid sending sensitive exception details directly to the user
                error_message = self.translator.get("An error occurred while processing your request.")
                await query.edit_message_text(text=error_message)
            except Exception as edit_error:
                logging.error(f"Failed to edit message with error notification: {edit_error}")

    async def stop(self):
        """Stop the Telegram bot."""
        if self.application and self.running:
            logging.info("Stopping Telegram bot polling...")
            # Stop the polling application
            await self.application.stop()
            self.running = False
            logging.info("Telegram bot polling stopped.")

            logging.info("Telegram bot stopped")

    async def send_startup_message(self):
        """Send a startup message to the configured chat ID."""
        message = self.translator.get("Application started successfully.")
        keyboard = [
            [InlineKeyboardButton(self.translator.get("telegram.buttons.start_monitoring"), callback_data='start_monitoring')],
            [InlineKeyboardButton(self.translator.get("telegram.buttons.stop_monitoring"), callback_data='stop_monitoring')],
            [InlineKeyboardButton(self.translator.get("telegram.buttons.pause_10"), callback_data='pause_10'),
             InlineKeyboardButton(self.translator.get("telegram.buttons.pause_30"), callback_data='pause_30'),
             InlineKeyboardButton(self.translator.get("telegram.buttons.pause_60"), callback_data='pause_60')],
            [InlineKeyboardButton(self.translator.get("telegram.buttons.lock_pc"), callback_data='lock_pc'),
             InlineKeyboardButton(self.translator.get("telegram.buttons.shutdown_pc"), callback_data='shutdown_pc')],
            [InlineKeyboardButton(self.translator.get("telegram.buttons.show_details"), callback_data='show_details'),
             InlineKeyboardButton(self.translator.get("telegram.buttons.take_screenshot"), callback_data='take_screenshot')],
            [InlineKeyboardButton(self.translator.get("telegram.buttons.cancel"), callback_data='cancel')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await self.send_message(message, reply_markup=reply_markup)

    async def send_resume_notification(self):
        """Send a notification when monitoring resumes."""
        message = self.translator.get("Monitoring resumed.")
        review_keyboard = [
            [InlineKeyboardButton(self.translator.get("telegram.buttons.review"), callback_data='review_events')]
        ]
        review_reply_markup = InlineKeyboardMarkup(review_keyboard)
        await self.send_message(message, reply_markup=review_reply_markup)

    async def send_message(self, message, parse_mode=ParseMode.HTML, reply_markup=None, detailed_info=None):
        """Send a message to the configured chat ID."""
        logging.debug("send_message called.")
        token = self.config.get('telegram_token')
        chat_id = self.config.get('telegram_chat_id')

        if not token or not chat_id:
            logging.warning("Cannot send message: token or chat ID not configured")
            return
        try:
            logging.debug(f"Attempting to send message to chat ID: {chat_id}")
            # Add a small delay to allow the loop to be fully ready
            await asyncio.sleep(0.01) # Small delay

            if self.application and self.application.bot: # Ensure application and bot instances are ready
                 logging.debug("Telegram application and bot instances are ready. Attempting to send via API.")
                 sent_message = await self.application.bot.send_message(chat_id=chat_id, text=message, parse_mode=parse_mode, reply_markup=reply_markup)
                 logging.debug(f"Telegram API send_message call successful. Message ID: {sent_message.message_id}")
                 # Store original message text and reply_markup, and detailed_info using message_id as key
                 message_id = sent_message.message_id
                 self._message_details[message_id] = {
                     'text': message,
                     'reply_markup': reply_markup,
                     'detailed_info': detailed_info # Store detailed info if provided
                 }
                 logging.debug(f"Stored original message details for message {message_id}")
                 logging.debug(f"Stored details: {self._message_details[message_id]}") # Add this line to log stored content

            else:
                 logging.warning("Telegram bot application or bot instance not initialized. Cannot send message.")
        except Exception as e:
            logging.error(f"Failed to send message: {e}")



    async def test_telegram_connection(self, token=None, chat_id=None):
        """Test the connection to the Telegram bot by sending a test message."""
        test_token = token if token is not None else self.config.get('telegram_token')
        test_chat_id = chat_id if chat_id is not None else self.config.get('telegram_chat_id')

        if not test_token or not test_chat_id:
            logging.warning("Cannot test connection: token or chat ID not configured")
            return (False, "Token or chat ID not configured")
        try:
            # Create a temporary bot instance for testing
            bot = Bot(token=test_token)
            await bot.get_me()
            logging.info("Telegram connection test successful")
            return (True, "Connection successful!")
        except Exception as e: # Catch specific telegram.error.TelegramError for better handling
            logging.error(f"Failed to test Telegram connection: {e}")
            return (False, self.translator.get("Failed to test Telegram connection: {e}").format(e=e))

    def test_connection_async(self, token=None, chat_id=None):
        """Thread-safe method to test the Telegram connection."""
        # This method is primarily used during setup, where the bot might not be fully running.
        # This method is primarily used during setup, where the bot might not be fully running.
        # We can run the test directly using asyncio.run() for simplicity, as it's a short-lived operation.
        try:
            result = asyncio.run(self.test_telegram_connection(token, chat_id))
            return result
        except Exception as e:
            logging.error(f"Error in test_connection_async: {e}")
            return (False, self.translator.get("Error in test_connection_async: {e}").format(e=e))

    def start(self):
        """Start the Telegram bot polling thread."""
        if not self.running and self.application:
            logging.info("Starting Telegram bot polling thread.")
            self.running = True
            self._polling_thread.start()
        elif not self.application:
            logging.warning("Telegram bot application not initialized. Cannot start polling thread.")
        else:
            logging.info("Telegram bot polling thread is already running.")

    def shutdown(self):
        """Synchronously shuts down the Telegram bot application."""
        logging.info("Attempting to shut down Telegram bot application.")
        try:
            # The Application's shutdown method is synchronous and handles stopping the updater and closing the loop.
            self.application.shutdown()
            logging.info("Telegram bot application shut down successfully.")
        except Exception as e:
            logging.error(f"Error during Telegram bot application shutdown: {e}")
