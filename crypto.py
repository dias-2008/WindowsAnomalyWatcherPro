import base64
import os
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import logging
from pathlib import Path

# Define the path for the encryption key file
KEY_FILE_PATH = Path(__file__).parent.parent / "data" / "key.key"

def load_or_generate_key():
    """Loads the encryption key from a file or generates a new one if it doesn't exist."""
    if KEY_FILE_PATH.exists():
        logging.debug(f"Loading encryption key from: {KEY_FILE_PATH}")
        try:
            with open(KEY_FILE_PATH, 'rb') as key_file:
                key = key_file.read()
            logging.debug("Encryption key loaded successfully.")
            return key
        except Exception as e:
            logging.error(f"Failed to load encryption key from {KEY_FILE_PATH}: {e}")
            # Fallback to generating a new key if loading fails
            logging.warning("Generating a new encryption key due to loading failure.")
            return generate_and_save_key()
    else:
        logging.info("Encryption key file not found. Generating a new key.")
        return generate_and_save_key()

def generate_and_save_key():
    """Generates a new encryption key and saves it to a file."""
    key = Fernet.generate_key()
    try:
        # Ensure the data directory exists
        KEY_FILE_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(KEY_FILE_PATH, 'wb') as key_file:
            key_file.write(key)
        logging.info(f"New encryption key generated and saved to: {KEY_FILE_PATH}")
        return key
    except Exception as e:
        logging.error(f"Failed to generate and save encryption key to {KEY_FILE_PATH}: {e}")
        # Return the generated key even if saving fails, though persistence is lost
        return key

# Load or generate the key when the module is imported
ENCRYPTION_KEY = load_or_generate_key()
FERNET = Fernet(ENCRYPTION_KEY)

def encrypt_data(data):
    """Encrypts data using the persistent encryption key."""
    if not isinstance(data, bytes):
        data = str(data).encode()
    try:
        encrypted_data = FERNET.encrypt(data)
        logging.debug("Data encrypted successfully.")
        return encrypted_data.decode() # Return as string for JSON
    except Exception as e:
        logging.error(f"Failed to encrypt data: {e}")
        return None # Or handle error appropriately

def decrypt_data(data):
    """Decrypts data using the persistent encryption key."""
    if not isinstance(data, bytes):
        data = str(data).encode()
    try:
        decrypted_data = FERNET.decrypt(data)
        logging.debug("Data decrypted successfully.")
        return decrypted_data.decode()
    except Exception as e:
        logging.error(f"Failed to decrypt data: {e}")
        # This is where the 'Incorrect padding' or 'Invalid base64' errors occur
        # If decryption fails, return None or the original data depending on desired behavior
        # Returning None might cause issues if the application expects a string
        # Let's return None and handle it in ConfigManager
        return None