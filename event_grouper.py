import logging
import asyncio
import uuid
import re
from datetime import datetime, timedelta
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
import threading
from collections import defaultdict

class EventGrouper:
    """Groups similar events and sends consolidated notifications."""

    def __init__(self, telegram_bot, translator, paused_event: threading.Event):
        """Initialize the EventGrouper.

        Args:
            telegram_bot: The Telegram bot instance.
            translator: The translator instance.
            paused_event: A threading.Event to signal if monitoring is paused.
        """
        logging.debug("EventGrouper __init__ called.")
        self.telegram_bot = telegram_bot
        self.translator = translator
        self._paused = paused_event
        self._event_buffer = {}
        self._buffer_lock = threading.Lock()
        self._detailed_event_info = {}
        self._processing_task = None
        self._processing_interval = 10 # seconds
        self._running = False
        
        # System file alert grouping settings
        self._system_file_alerts = defaultdict(list)
        self._last_alert_times = {}
        # Use settings from config file
        from config.settings import SYSTEM_FILE_ALERT_THRESHOLD, SYSTEM_FILE_ALERT_WINDOW
        self._system_alert_threshold = SYSTEM_FILE_ALERT_THRESHOLD
        self._system_alert_window = SYSTEM_FILE_ALERT_WINDOW
        
        logging.info("EventGrouper initialized.")
        logging.info("Event grouper cleared stopped state.")



    async def add_event(self, event_type, event_details):
        """Add an event to the buffer or send immediately for certain types."""
        logging.debug(f"Adding event: {event_type}.")

        try:
            # Special handling for suspicious file modifications to reduce alert frequency
            if event_type == 'suspicious_file_modified':
                file_path = event_details.get('file_path', '')
                # Get a simplified path for grouping similar system file alerts
                simplified_path = self._simplify_system_path(file_path)
                current_time = datetime.now()
            
                # Check if we should group this alert
                with self._buffer_lock:
                    # Add to the system file alerts collection
                    self._system_file_alerts[simplified_path].append(event_details)
                    
                    # Check if we've sent an alert for this path recently
                    last_alert_time = self._last_alert_times.get(simplified_path)
                    alert_count = len(self._system_file_alerts[simplified_path])
                    
                    # Only send if:
                    # 1. We haven't sent an alert for this path recently, or
                    # 2. We've accumulated enough alerts to justify sending another one
                    should_send = False
                    
                    if not last_alert_time or (current_time - last_alert_time) > timedelta(seconds=self._system_alert_window):
                        # It's been long enough since the last alert
                        should_send = True
                    elif alert_count >= self._system_alert_threshold:
                        # We've accumulated enough alerts to justify sending another one
                        should_send = True
                        
                    if should_send:
                        # Create a copy of the event details and add the grouped count
                        grouped_details = event_details.copy()
                        grouped_count = len(self._system_file_alerts[simplified_path]) - 1
                        if grouped_count > 0:
                            grouped_details['grouped_count'] = grouped_count
                        
                        # Update the last alert time
                        self._last_alert_times[simplified_path] = current_time
                        
                        # Clear the buffer for this path
                        self._system_file_alerts[simplified_path] = []
                        
                        # Send the alert
                        logging.debug(f"Sending grouped suspicious file alert for {simplified_path} with {grouped_count} additional alerts")
                        await self._send_individual_alert(event_type, grouped_details)
                    else:
                        logging.debug(f"Buffering suspicious file alert for {simplified_path}, current count: {alert_count}")
            
            # Buffer file and folder events for grouping
            elif event_type in ['file_created', 'file_modified', 'file_deleted', 'file_moved']:
                with self._buffer_lock:
                    if event_type not in self._event_buffer:
                        self._event_buffer[event_type] = []
                    self._event_buffer[event_type].append(event_details)
                logging.debug(f"Buffered {event_type} event.")
            # Handle window events immediately as they are the trigger for grouping file/folder activity
            elif event_type == 'window':
                logging.debug("Received window event. Processing immediately.")
                await self._process_window_event(event_details)
            # Send other event types immediately
            else:
                await self._send_individual_alert(event_type, event_details)
        except Exception as e:
            logging.error(f"Error adding event: {e}")
    async def _process_window_event(self, window_details):
        """Process a window event and group buffered file/folder events."""
        logging.debug("_process_window_event called.")
        buffered_events = {}
        with self._buffer_lock:
            # Copy buffered events and clear the buffer
            buffered_events = self._event_buffer.copy()
            self._event_buffer.clear()
    
        # Only send a grouped alert if there are buffered file/folder events
        if buffered_events:
            logging.debug(f"Processing window event with buffered events: {buffered_events.keys()}")
            try:
                await self._send_grouped_file_activity_alert(window_details, buffered_events)
            except Exception as e:
                logging.error(f"Error processing window event and sending grouped alert: {e}")
                # Optionally, send a simplified error message to Telegram
                try:
                    error_message = self.translator.get("An error occurred while processing window activity.")
                    # await self.telegram_bot.send_message(error_message)
                    logging.error(f"Error processing window event and sending grouped alert: {e}") # Log the error details
                except Exception as send_error:
                    logging.error(f"Failed to send error message to Telegram: {send_error}")
        else:
            logging.debug("No buffered file/folder events to group with window event. Sending individual window alert.")
            # If no file/folder events were buffered, send the window event as an individual alert
            try:
                await self._send_individual_alert('window', window_details)
            except Exception as e:
                logging.error(f"Error sending individual window alert: {e}")
                # Optionally, send a simplified error message to Telegram
                try:
                    error_message = self.translator.get("An error occurred while sending a window activity alert.")
                    # await self.telegram_bot.send_message(error_message)
                    logging.error(f"Error sending individual window alert: {e}") # Log the error details
                except Exception as send_error:
                    logging.error(f"Failed to send error message to Telegram: {send_error}")

    async def _send_grouped_file_activity_alert(self, window_details, grouped_events):
        """Send a consolidated alert for grouped file/folder activity."""
        logging.debug("_send_grouped_file_activity_alert called.")
        try:
            timestamp_now = datetime.now().strftime('%H:%M:%S')

            # Use the new grouped alert title
            title = self.translator.get('alerts.grouped_file_activity.title')

            message_lines = []
            message_lines.append(f"<b>⚠️ {title}</b>")
            message_lines.append(f"⏰ {timestamp_now}")

            # Add window activity details
            process_name = window_details.get('process_name', 'N/A')
            activity_detected = self.translator.get('alerts.window.activity_detected')
            message_lines.append(f"{process_name}")
            message_lines.append(f"{activity_detected}")

            # Generate a unique ID for this grouped event
            event_id = str(uuid.uuid4())
            # Store the detailed info with the unique ID
            self._detailed_event_info[event_id] = {
                "window_details": window_details,
                "grouped_events": grouped_events
            }

            # Add a button to show details
            keyboard = [
                [InlineKeyboardButton(text=self.translator.get("telegram.buttons.yes_its_me"), callback_data='window_change_ack'),
                 InlineKeyboardButton(text=self.translator.get("telegram.buttons.show_details"), callback_data=f'show_grouped_details_{event_id}')],
                [InlineKeyboardButton(text=self.translator.get("telegram.buttons.lock_pc"), callback_data='lock_pc'),
                 InlineKeyboardButton(text=self.translator.get("telegram.buttons.shutdown_pc"), callback_data='shutdown_pc')],
                [InlineKeyboardButton(text=self.translator.get("telegram.buttons.take_screenshot"), callback_data='take_screenshot')]
            ]

            reply_markup = InlineKeyboardMarkup(keyboard)
            consolidated_message = "\n".join(message_lines)

            # Send the grouped message
            logging.debug("Calling send_async_message for grouped alert.")
            await self.telegram_bot.send_message(consolidated_message, reply_markup=reply_markup, parse_mode=ParseMode.HTML)
            logging.info("Sent grouped file activity alert.")

        except Exception as e:
            logging.error(f"Error sending grouped file activity alert: {e}")

    async def handle_callback_query(self, callback_query):
        """Handle incoming callback queries from inline keyboard buttons."""
        logging.debug(f"Received callback query: {callback_query.data}")
        try:
            data = callback_query.data
            chat_id = callback_query.message.chat.id
            message_id = callback_query.message.message_id

            if data == 'window_change_ack':
                await self.telegram_bot.answer_callback_query(callback_query.id, text=self.translator.get("telegram.buttons.acknowledge"))
                # Optionally delete the message or edit it to show acknowledgement
                # await self.telegram_bot.delete_message(chat_id, message_id)

            elif data == 'show_window_details':
                # This callback is for individual window events, which are now sent only if no file/folder events are buffered.
                # The window details are already in the original message, so we can just acknowledge.
                await self.telegram_bot.answer_callback_query(callback_query.id, text=self.translator.get("telegram.buttons.show_details"))

            elif data.startswith('show_individual_details_'):
                event_id = data.replace('show_individual_details_', '')
                details = self._detailed_event_info.get(event_id)
                if details:
                    detail_message = self._format_individual_details(details)
                    await self.telegram_bot.send_message(chat_id, detail_message, parse_mode=ParseMode.HTML)
                    await self.telegram_bot.answer_callback_query(callback_query.id)
                else:
                    await self.telegram_bot.answer_callback_query(callback_query.id, text="Details not found.")

            elif data.startswith('show_grouped_details_'):
                event_id = data.replace('show_grouped_details_', '')
                details = self._detailed_event_info.get(event_id)
                if details:
                    detail_message = self._format_grouped_details(details)
                    await self.telegram_bot.send_message(chat_id, detail_message, parse_mode=ParseMode.HTML)
                    await self.telegram_bot.answer_callback_query(callback_query.id)
                else:
                    await self.telegram_bot.answer_callback_query(callback_query.id, text="Details not found.")

            elif data == 'lock_pc':
                # Implement PC locking logic here
                await self.telegram_bot.answer_callback_query(callback_query.id, text=self.translator.get("telegram.buttons.lock_pc"))

            elif data == 'shutdown_pc':
                # Implement PC shutdown logic here
                await self.telegram_bot.answer_callback_query(callback_query.id, text=self.translator.get("telegram.buttons.shutdown_pc"))

            elif data == 'take_screenshot':
                # Implement screenshot logic here
                await self.telegram_bot.answer_callback_query(callback_query.id, text=self.translator.get("telegram.buttons.take_screenshot"))

            # Clean up old detailed info to prevent memory issues
            self._cleanup_old_details()

        except Exception as e:
            logging.error(f"Error handling callback query: {e}")

    def _format_individual_details(self, details):
        """Format details for an individual event."""
        message_lines = []
        message_lines.append("<b>Event Details:</b>")
        for key, value in details.items():
            message_lines.append(f"<b>{key.replace('_', ' ').title()}:</b> {value}")
        return "\n".join(message_lines)

    def _format_grouped_details(self, details):
        """Format details for a grouped event."""
        message_lines = []
        message_lines.append("<b>Grouped Event Details:</b>")

        window_details = details.get("window_details", {})
        message_lines.append("\n<b>Window Activity:</b>")
        for key, value in window_details.items():
             if key != 'timestamp': # Avoid showing timestamp again
                message_lines.append(f"  <b>{key.replace('_', ' ').title()}:</b> {value}")

        grouped_events = details.get("grouped_events", {})
        for event_type, events in grouped_events.items():
            message_lines.append(f"\n<b>{event_type.replace('_', ' ').title()}:</b>")
            for event in events:
                for key, value in event.items():
                    if key != 'timestamp': # Avoid showing timestamp again
                        message_lines.append(f"  <b>{key.replace('_', ' ').title()}:</b> {value}")
                message_lines.append("----") # Separator for multiple events of the same type

        return "\n".join(message_lines)

    def _cleanup_old_details(self):
        """Clean up old detailed event info from the dictionary."""
        # Implement a cleanup strategy, e.g., remove entries older than a certain time
        pass # Placeholder for cleanup logic

    def _simplify_system_path(self, file_path):
        """Simplify a system file path to group similar alerts."""
        if not file_path:
            return "unknown"
            
        # Convert to lowercase and normalize path separators
        normalized_path = file_path.lower().replace('\\', '/')
        
        # Extract directory patterns for grouping
        if 'c:/windows/system32/' in normalized_path:
            return 'system32_files'
        elif 'c:/windows/syswow64/' in normalized_path:
            return 'syswow64_files'
        elif 'c:/windows/' in normalized_path:
            return 'windows_files'
        elif 'c:/program files/' in normalized_path:
            return 'program_files'
        elif 'c:/program files (x86)/' in normalized_path:
            return 'program_files_x86'
        else:
            # Return the first two directory levels
            parts = normalized_path.split('/')
            if len(parts) >= 3:
                return f"{parts[0]}/{parts[1]}/{parts[2]}"
            return normalized_path
            
    async def _send_individual_alert(self, event_type, event_details):
        """Send an individual notification for a specific event type."""
        logging.debug(f"_send_individual_alert called for event type: {event_type}.")
        try:
            timestamp_now = datetime.now().strftime('%H:%M:%S')

            # Determine title key based on event type
            title_key = f'alerts.{event_type}.title'
            title = self.translator.get(title_key)

            message_lines = []
            message_lines.append(f"<b>⚠️ {title}</b>")
            message_lines.append(f"⏰ {timestamp_now}")

            # Add specific details based on event type
            if event_type == 'window':
                process_name = event_details.get('process_name', 'N/A')
                activity_detected = self.translator.get('alerts.window.activity_detected')
                message_lines.append(f"{process_name}")
                message_lines.append(f"{activity_detected}")

                # Window specific buttons
                keyboard = [
                    [InlineKeyboardButton(text=self.translator.get("telegram.buttons.yes_its_me"), callback_data='window_change_ack'),
                     InlineKeyboardButton(text=self.translator.get("telegram.buttons.show_details"), callback_data='show_window_details')],
                    [InlineKeyboardButton(text=self.translator.get("telegram.buttons.lock_pc"), callback_data='lock_pc'),
                     InlineKeyboardButton(text=self.translator.get("telegram.buttons.shutdown_pc"), callback_data='shutdown_pc')],
                    [InlineKeyboardButton(text=self.translator.get("telegram.buttons.take_screenshot"), callback_data='take_screenshot')]
                ]

            elif event_type in ['file_modified', 'file_deleted', 'file_created', 'suspicious_file_modified']:
                file_path = event_details.get('file_path', 'N/A')
                
                # Check if this is a grouped system file alert
                grouped_count = event_details.get('grouped_count', 0)
                if grouped_count > 0:
                    message_lines.append(f"<b>+{grouped_count} similar alerts grouped</b>")
                    
                message_lines.append(f"File: {file_path}")

                # File specific buttons (Show Details)
                # Generate a unique ID for this event
                event_id = str(uuid.uuid4())
                # Store the detailed info with the unique ID
                self._detailed_event_info[event_id] = event_details

                keyboard = [
                    [InlineKeyboardButton(text=self.translator.get("telegram.buttons.show_details"), callback_data=f'show_individual_details_{event_id}')]
                ]

            elif event_type == 'file_moved':
                old_path = event_details.get('old_path', 'N/A')
                new_path = event_details.get('new_path', 'N/A')
                message_lines.append(f"Old Path: {old_path}")
                message_lines.append(f"New Path: {new_path}")

                # File move specific buttons (Show Details)
                # Generate a unique ID for this event
                event_id = str(uuid.uuid4())
                # Store the detailed info with the unique ID
                self._detailed_event_info[event_id] = event_details

                keyboard = [
                    [InlineKeyboardButton(text=self.translator.get("telegram.buttons.show_details"), callback_data=f'show_individual_details_{event_id}')]
                ]

            elif event_type in ['suspicious_process', 'process_created', 'process_terminated']:
                process_name = event_details.get('process_name', 'N/A')
                process_path = event_details.get('process_path', 'N/A')
                message_lines.append(f"Process Name: {process_name}")
                message_lines.append(f"Process Path: {process_path}")

                # Process specific buttons (Show Details)
                # Generate a unique ID for this event
                event_id = str(uuid.uuid4())
                # Store the detailed info with the unique ID
                self._detailed_event_info[event_id] = event_details

                keyboard = [
                    [InlineKeyboardButton(text=self.translator.get("telegram.buttons.show_details"), callback_data=f'show_individual_details_{event_id}')]
                ]

            else:
                # Default case for other individual alert types if any
                pass # Explicitly pass if no default action needed

            reply_markup = InlineKeyboardMarkup(keyboard)
            consolidated_message = "\n".join(message_lines)

            # Send the individual message
            logging.debug("Calling send_async_message for individual alert.")
            await self.telegram_bot.send_message(consolidated_message, reply_markup=reply_markup, parse_mode=ParseMode.HTML)
            logging.info(f"Sent individual alert for {event_type}.")

        except Exception as e:
            logging.error(f"Error sending individual alert for {event_type}: {e}")
            # Optionally, send a simplified error message to Telegram if possible
            try:
                error_message = self.translator.get("An error occurred while processing an alert.")
                # Avoid sending the full exception details to Telegram for security/verbosity reasons
                # await self.telegram_bot.send_message(error_message)
                logging.error(f"Error sending individual alert for {event_type}: {e}") # Log the error details
            except Exception as send_error:
                logging.error(f"Failed to send error message to Telegram: {send_error}")

    def clear_paused_buffered_events(self):
        """Clear the event buffer when pausing to avoid sending old events on resume."""
        logging.debug("Clearing paused buffered events.")
        # Clear both the regular event buffer and the system file alerts buffer
        with self._buffer_lock:
            self._event_buffer.clear()
            self._system_file_alerts.clear()
            self._last_alert_times.clear()
        logging.debug("Paused buffered events and system file alerts cleared.")
        logging.info("Retrieved 0 buffered events.")
