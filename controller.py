#!/usr/bin/env python
# -*- coding: utf8 -*-

import logging
import sys
import time
import json
import queue
import os
from datetime import datetime
import uuid
import threading
import configparser
from concurrent.futures import ThreadPoolExecutor
from threading import Timer

import requests
from requests.auth import HTTPDigestAuth
from gpiozero import Button, OutputDevice
from mfrc522 import MFRC522

VERSION = "1.13.0" # Minor version incremented for ntfy listener independence

# BE AWARE, THESE ARE (G)PIOS, NOT PINS
RELAY_PIN = 17
REED_CONTACT_CLOSED_DOOR_PIN = 22
REED_CONTACT_OPEN_DOOR_PIN = 23

# These will be set by the setup function from the config file
VALID_CARDS_FILE = None
NTFY_TOPIC = None
STATS_FILE = None
DOOR_OPEN_TIMEOUT = 120 # Default value in seconds
CAMERA_URL = None
CAMERA_USER = None
CAMERA_PASS = None

# Global control for NFC reader thread and ntfy listener thread
continue_reading = True # Overall application listening state
nfc_reader_should_run = False # Specific control for NFC reader thread
nfc_reader_thread = None
nfc_reader_active = False # Tracks if the NFC reader thread is currently running
ntfy_listener_thread = None # Tracks the ntfy listener thread

allowed_cards = {} # Now stores {"CARD_ID": "Gebruikersnaam"}
last_used_card_user = None  # Stores the username of the last card used
active_close_token = None # Stores the unique token for the current open session

relay: OutputDevice = None
reed_closed_door: Button = None
reed_open_door: Button = None
door_open_timer: Timer = None
stats_lock = threading.Lock()
stat_listeners = [] # List of queues to notify on updates
hardware_listeners = [] # List of queues for hardware status updates

# Global variable to store the actual config file path
_CONTROLLER_CONFIG_FILE_PATH = None

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def _get_config_parser():
    """Helper to get a ConfigParser instance with the current config."""
    if not _CONTROLLER_CONFIG_FILE_PATH:
        logging.error("Config file path not set in controller. Call setup() first.")
        raise RuntimeError("Config file path not initialized.")
    
    # Disable interpolation to prevent issues with '%' characters in config values
    config = configparser.ConfigParser(interpolation=None)
    config.read(_CONTROLLER_CONFIG_FILE_PATH)
    return config

def load_config(config_parser_instance=None):
    """Loads configuration values from the config object."""
    global VALID_CARDS_FILE, NTFY_TOPIC, STATS_FILE, DOOR_OPEN_TIMEOUT, CAMERA_URL, CAMERA_USER, CAMERA_PASS

    config = config_parser_instance if config_parser_instance else _get_config_parser()

    try:
        VALID_CARDS_FILE = config.get('paths', 'valid_cards_file')
        NTFY_TOPIC = config.get('ntfy', 'topic')
        DOOR_OPEN_TIMEOUT = config.getint('ntfy', 'door_open_timeout', fallback=120)
        STATS_FILE = config.get('paths', 'stats_file', fallback='stats.json')
        CAMERA_URL = config.get('camera', 'url', fallback=None)
        CAMERA_USER = config.get('camera', 'username', fallback=None)
        CAMERA_PASS = config.get('camera', 'password', fallback=None)
        logging.info('Successfully loaded paths and ntfy config.')
        
        read_allowed_cards()
        return True
    except (configparser.NoSectionError, configparser.NoOptionError) as e:
        logging.error(f'Could not read configuration from config.ini: {e}')
        return False


def setup(config_parser_instance, config_file_path):
    """Sets up the controller with the given configuration."""
    global relay, _CONTROLLER_CONFIG_FILE_PATH, ntfy_listener_thread, continue_reading
    _CONTROLLER_CONFIG_FILE_PATH = config_file_path # Store the path

    if not load_config(config_parser_instance):
        sys.exit(1)

    relay = OutputDevice(RELAY_PIN, active_high=True, initial_value=False)
    setup_reed_contacts()

    # Start the remote listener in a background thread if not already running
    # This should always be running regardless of NFC reader status
    if not ntfy_listener_thread or not ntfy_listener_thread.is_alive():
        logging.info("Starting ntfy command listener thread during setup.")
        ntfy_listener_thread = threading.Thread(target=listen_for_ntfy_commands, daemon=True)
        ntfy_listener_thread.start()
    else:
        logging.info("ntfy command listener thread is already running.")

    # Ensure continue_reading is True when setup completes, as it controls all listeners
    continue_reading = True


def run_io_tasks_in_parallel(tasks):
    with ThreadPoolExecutor() as executor:
        running_tasks = [executor.submit(task) for task in tasks]
        for running_task in running_tasks:
            running_task.result()


def read_allowed_cards():
    if not VALID_CARDS_FILE:
        logging.error('VALID_CARDS_FILE path is not set. Cannot read allowed cards.')
        return

    logging.info(f'Reading allowed cards from {VALID_CARDS_FILE}')
    global allowed_cards
    new_allowed_cards = {}
    try:
        with open(VALID_CARDS_FILE, 'r') as file:
            for i, line in enumerate(file, 1):
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                
                parts = line.split(',', 1) # Split only on the first comma
                if len(parts) == 2:
                    card_id, user_name = parts[0].strip(), parts[1].strip()
                    new_allowed_cards[card_id] = user_name
                else:
                    logging.warning(f"Invalid line format in {VALID_CARDS_FILE} at line {i}: '{line}'. Expected 'card_id,user_name'.")
                    # For backward compatibility, if only card ID is present, use it with a generic name
                    new_allowed_cards[line] = "Onbekend"

        allowed_cards = new_allowed_cards
        logging.info('Allowed cards loaded: %s', allowed_cards)
    except FileNotFoundError:
        logging.error(f'Could not find {VALID_CARDS_FILE}. No cards will be loaded.')
        allowed_cards = {}


def get_allowed_cards():
    # Return a list of card IDs for display purposes
    return list(allowed_cards.keys())


def add_allowed_card(card_id, user_name="Onbekend"):
    """Adds a new card ID and user name to the file."""
    card_id_str = str(card_id)
    try:
        # Check if the card_id already exists to avoid duplicates
        if card_id_str in allowed_cards:
            logging.warning(f"Card ID {card_id_str} already exists. Not adding.")
            return False

        with open(VALID_CARDS_FILE, 'a') as file:
            file.write(f'\n{card_id_str},{user_name}')
        logging.info(f'Writing card id {card_id_str} with user {user_name} to file.')
        read_allowed_cards() # Reload all cards to update in-memory dictionary
        return True
    except Exception as e:
        logging.error(f"Failed to write card ID and user name to file: {e}")
        return False


def log_stat_event(action, user=None):
    """Logs an event to the stats file."""
    event = {
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'action': action,
        'user': user if user else 'Handmatig/Onbekend'
    }
    
    with stats_lock:
        data = {'total_opens': 0, 'long_open_events': 0, 'history': []}
        
        # Load existing
        if os.path.exists(STATS_FILE):
            try:
                with open(STATS_FILE, 'r') as f:
                    data = json.load(f)
            except Exception as e:
                logging.error(f"Error reading stats file: {e}")

        # Update stats
        if action == 'OPEN':
            data['total_opens'] = data.get('total_opens', 0) + 1
        elif action == 'LONG_OPEN_WARNING':
            data['long_open_events'] = data.get('long_open_events', 0) + 1
        elif action == 'TOGGLE_RELAY': # Log manual toggle events
            # For manual toggles, we don't increment total_opens here,
            # as the reed switch will trigger the 'OPEN' event.
            pass
            
        # Add to history (keep last 100 events)
        data.setdefault('history', []).insert(0, event)
        data['history'] = data['history'][:100]

        with open(STATS_FILE, 'w') as f:
            json.dump(data, f, indent=4)
            
    # Notify all active listeners (SSE streams)
    # We send the full data object so the frontend is always in sync
    dead_listeners = []
    for q in stat_listeners:
        try:
            q.put(data)
        except:
            dead_listeners.append(q)
            
    # Cleanup dead listeners if any (though usually handled by remove_listener)
    for d in dead_listeners:
        if d in stat_listeners:
            stat_listeners.remove(d)


def broadcast_hardware_update():
    """Sends the current hardware status to all connected listeners."""
    status = {
        'relay': 'Klaar voor actie', # Relay is stateless mostly, but we send update to confirm connectivity
        'reed_closed': read_reed_closed_door(),
        'reed_open': read_reed_open_door(),
        'timestamp': datetime.now().strftime('%H:%M:%S')
    }
    
    dead_listeners = []
    for q in hardware_listeners:
        try:
            q.put(status)
        except:
            dead_listeners.append(q)
    
    for d in dead_listeners:
        if d in hardware_listeners:
            hardware_listeners.remove(d)


def _perform_toggle_relay(user=None):
    logging.info(f'Toggling relay by user: {user if user else "NFC Card"}')
    if relay:
        relay.toggle()
        time.sleep(.5)
        relay.toggle()
        time.sleep(1.5)
        broadcast_hardware_update() # Notify UI that toggle is done
        # Log the manual toggle event here
        if user:
            log_stat_event('TOGGLE_RELAY', user=user)
    else:
        logging.error("Relay not initialized")

def toggle_relay(user=None):
    # Run the actual relay toggle in a separate thread so we don't block the caller
    # (especially important for the web server to avoid queue depth issues)
    threading.Thread(target=_perform_toggle_relay, args=(user,), daemon=True).start()


def setup_reed_contacts():
    logging.info('Setting up reed contacts')
    global reed_closed_door, reed_open_door
    reed_closed_door = Button(REED_CONTACT_CLOSED_DOOR_PIN)
    reed_closed_door.when_released = reed_closed_door_open
    reed_closed_door.when_pressed = reed_closed_door_closed
    reed_open_door = Button(REED_CONTACT_OPEN_DOOR_PIN)
    reed_open_door.when_released = reed_open_door_open
    reed_open_door.when_pressed = reed_open_door_closed


def read_reed_closed_door():
    if reed_closed_door and reed_closed_door.value == 0:
        return 'garage door is opening / open'
    else:
        return 'garage door is closed'


def read_reed_open_door():
    if reed_open_door and reed_open_door.value == 0:
        return 'garage door is closing / closed'
    else:
        return 'garage door is fully open'


def reed_closed_door_open():
    global last_used_card_user
    logging.info('Closed door reed contact is open - garage door is opening/open.')
    
    # Log the event. last_used_card_user is set when a card is scanned.
    log_stat_event('OPEN', last_used_card_user)
    
    # Do NOT reset last_used_card_user here. It will be used for the 'CLOSE' event.
    logging.info('Last used card user retained for CLOSE event.')
    broadcast_hardware_update()


def reed_closed_door_closed():
    global door_open_timer, last_used_card_user
    logging.info('Closed door reed contact is closed - garage door is closed.')
    
    # Log the CLOSE event with the user who opened it
    log_stat_event('CLOSE', last_used_card_user)
    
    # Reset last_used_card_user AFTER logging the close event
    last_used_card_user = None
    logging.info('Reset last used card user after CLOSE event.')

    if door_open_timer and door_open_timer.is_alive():
        door_open_timer.cancel()
        logging.info('Cancelled door open timer as door is now closed.')
    broadcast_hardware_update()


def reed_open_door_open():
    global door_open_timer
    logging.info('Open door reed contact is open - garage door is closing/closed.')
    if door_open_timer and door_open_timer.is_alive():
        door_open_timer.cancel()
        logging.info('Cancelled door open timer.')
    broadcast_hardware_update()


def reed_open_door_closed():
    global door_open_timer
    logging.info('Open door reed contact is closed - garage door is open.')
    if door_open_timer and door_open_timer.is_alive():
        door_open_timer.cancel()
        logging.info('Cancelling previous door open timer.')

    logging.info(f'Starting {DOOR_OPEN_TIMEOUT}-second timer for door open notification.')
    door_open_timer = Timer(DOOR_OPEN_TIMEOUT, send_ntfy_notification)
    door_open_timer.start()
    broadcast_hardware_update()


def send_ntfy_notification(is_test=False):
    global active_close_token
    if not NTFY_TOPIC or NTFY_TOPIC == 'your_ntfy_topic_here':
        logging.error('ntfy topic is not configured in config.ini. Cannot send notification.')
        return

    if is_test or (reed_open_door and reed_open_door.is_pressed):
        title = 'Garagedeur alarm!'
        if is_test:
            title = 'Test: Garagedeur Melding'
        
        # Create a friendly time string (e.g., "2 minuten" or "90 seconden")
        time_str = f"{int(DOOR_OPEN_TIMEOUT / 60)} minuten" if DOOR_OPEN_TIMEOUT % 60 == 0 else f"{DOOR_OPEN_TIMEOUT} seconden"
        
        message = f'De garagedeur is meer dan {time_str} open!'
        if is_test:
            message = f'Dit is een testbericht. De ingestelde timeout is {time_str}.'
        else:
            log_stat_event('LONG_OPEN_WARNING')

        if last_used_card_user:
            message += f' Laatst opengemaakt door: {last_used_card_user}.'
        elif not is_test:
            message += ' Laatst handmatig geopend (gebruiker onbekend).'

        # Generate a unique token for this specific notification
        token = str(uuid.uuid4())
        active_close_token = token

        # Use a separate control topic for commands so they don't clutter the user's feed
        control_topic = f"{NTFY_TOPIC}_control"

        # Add an action button to the notification
        headers = {
            'Title': title,
            'Priority': 'high',
            'Actions': f'http, Sluiten, https://ntfy.sh/{control_topic}, body=CLOSE_TOKEN_{token}, method=POST'
        }

        # Try to fetch camera snapshot
        image_data = None
        if CAMERA_URL:
            try:
                logging.info(f"Fetching snapshot from {CAMERA_URL} for user {CAMERA_USER}...")
                auth = None
                if CAMERA_USER and CAMERA_PASS:
                    auth = HTTPDigestAuth(CAMERA_USER, CAMERA_PASS)
                
                # Timeout is short to not block the main thread too long
                resp = requests.get(CAMERA_URL, auth=auth, timeout=4)
                if resp.status_code == 200:
                    image_data = resp.content
                    logging.info(f"Snapshot fetched successfully ({len(image_data)} bytes).")
                else:
                    logging.warning(f"Failed to fetch snapshot. Status code: {resp.status_code}")
            except Exception as e:
                logging.error(f"Error fetching snapshot: {e}")

        logging.info(f'Sending notification to ntfy topic: {NTFY_TOPIC}')
        try:
            if image_data:
                # Send image as body, message moves to header
                headers['Message'] = message
                headers['Filename'] = 'snapshot.jpg'
                requests.post(f'https://ntfy.sh/{NTFY_TOPIC}', data=image_data, headers=headers)
            else:
                # Send text only
                requests.post(f'https://ntfy.sh/{NTFY_TOPIC}', data=message.encode('utf-8'), headers=headers)
                
            logging.info('Successfully sent ntfy notification.')
        except Exception as e:
            logging.error(f'Failed to send ntfy notification: {e}')
    else:
        logging.warning('Door is no longer open; skipping notification.')


def listen_for_ntfy_commands():
    """Listens to the ntfy topic for remote commands."""
    global active_close_token
    if not NTFY_TOPIC:
        return

    # Listen on a separate topic to keep the main topic clean
    control_topic = f"{NTFY_TOPIC}_control"
    logging.info(f"Starting remote command listener on topic: {control_topic}")
    while continue_reading: # Added continue_reading check here as well
        try:
            # Listen to the stream for JSON data
            resp = requests.get(f'https://ntfy.sh/{control_topic}/json', stream=True, timeout=60)
            for line in resp.iter_lines():
                if not continue_reading: # Check again in case continue_reading changed during iter_lines
                    break
                if line:
                    data = json.loads(line)
                    event_type = data.get('event')
                    message = data.get('message', '')

                    # Check if this is a message event and contains a token command
                    if event_type == 'message' and message.startswith('CLOSE_TOKEN_'):
                        received_token = message.replace('CLOSE_TOKEN_', '')
                        
                        if received_token != active_close_token:
                            logging.warning("Remote command ignored: Invalid or expired token.")
                            continue

                        logging.info("Valid remote close token received!")
                        
                        # Invalidate token immediately so it cannot be used again
                        active_close_token = None

                        # SAFETY CHECK: Only toggle if the door is NOT closed (reed switch not pressed)
                        if reed_closed_door and not reed_closed_door.is_pressed:
                            logging.info("Safety check passed: Door is open. Closing now.")
                            toggle_relay()
                        else:
                            logging.warning("Remote command ignored: Door is already closed.")
        except requests.exceptions.Timeout:
            logging.debug("ntfy listener timeout, reconnecting...")
        except Exception as e:
            logging.error(f"Error in remote command listener: {e}")
            time.sleep(10) # Wait before reconnecting
    
    logging.info('ntfy command listener stopped.')


def get_stats():
    """Returns the current statistics."""
    if os.path.exists(STATS_FILE):
        try:
            with open(STATS_FILE, 'r') as f:
                return json.load(f)
        except:
            pass
    return {'total_opens': 0, 'long_open_events': 0, 'history': []}


def register_stat_listener():
    """Creates a queue for a new listener and returns it."""
    q = queue.Queue()
    stat_listeners.append(q)
    return q

def remove_stat_listener(q):
    """Removes a listener queue."""
    if q in stat_listeners:
        stat_listeners.remove(q)

def register_hardware_listener():
    """Creates a queue for a new hardware listener."""
    q = queue.Queue()
    hardware_listeners.append(q)
    return q

def remove_hardware_listener(q):
    """Removes a hardware listener queue."""
    if q in hardware_listeners:
        hardware_listeners.remove(q)

def _nfc_listening_loop():
    """The main loop for the NFC reader, run in a separate thread."""
    global last_used_card_user, nfc_reader_should_run, nfc_reader_active, continue_reading
    logging.info('Starting NFC reader loop...')

    # Check if door is already open upon startup (e.g. after a reboot/update)
    if reed_open_door and reed_open_door.is_pressed:
        logging.info("Startup check: Door is detected as open. Resuming notification timer.")
        reed_open_door_closed()
    
    reader = MFRC522()
    logging.info('Started NFC reader. Waiting for cards...')
    nfc_reader_active = True
    while nfc_reader_should_run and continue_reading: # Use both flags
        try:
            # Scan for cards
            (status, TagType) = reader.MFRC522_Request(reader.PICC_REQIDL)

            # If a card is found
            if status == reader.MI_OK:
                # Get the UID of the card
                (status, uid) = reader.MFRC522_Anticoll()

                if status == reader.MI_OK:
                    # Convert UID bytes to a hexadecimal string
                    card_id_str = "".join([f"{i:02X}" for i in uid])
                    
                    if card_id_str in allowed_cards:
                        user_name = allowed_cards[card_id_str]
                        last_used_card_user = user_name
                        logging.info(f'ACCESS GRANTED for card {card_id_str} (User: {user_name})')
                        toggle_relay()
                    else:
                        logging.info(f'ACCESS BLOCKED for card {card_id_str}')
                    
                    # A small delay to prevent multiple reads of the same card
                    time.sleep(1) # Keep this delay after a successful read
            else:
                # If no card is found, introduce a small delay to reduce CPU usage
                time.sleep(0.5) # Small delay to prevent busy-waiting

        except Exception as e:
            # This can happen if the reader is interrupted by a shutdown signal
            if nfc_reader_should_run and continue_reading: # Only log if we intended to continue reading
                logging.error(f"Error reading NFC tag: {e}")
                time.sleep(1) # Prevent tight loop on error
    
    logging.info('NFC reader loop stopped.')
    nfc_reader_active = False


def start_nfc_reader():
    """Starts the NFC reader in a separate thread."""
    global nfc_reader_thread, nfc_reader_active, nfc_reader_should_run, continue_reading
    if nfc_reader_thread and nfc_reader_thread.is_alive():
        logging.warning("NFC reader is already running.")
        return False
    
    if not continue_reading:
        logging.warning("Cannot start NFC reader: overall listening is stopped.")
        return False

    logging.info('Starting NFC reader thread...')
    nfc_reader_should_run = True # Set the flag to allow NFC loop to run
    nfc_reader_thread = threading.Thread(target=_nfc_listening_loop, daemon=True)
    nfc_reader_thread.start()
    return True

def stop_nfc_reader():
    """Stops the NFC reader thread."""
    global nfc_reader_thread, nfc_reader_active, nfc_reader_should_run
    if not nfc_reader_thread or not nfc_reader_thread.is_alive():
        logging.warning("NFC reader is not running.")
        return False
    
    logging.info('Stopping NFC reader thread...')
    nfc_reader_should_run = False # Signal the NFC loop to stop
    nfc_reader_thread.join(timeout=2) # Give the thread a chance to finish
    if nfc_reader_thread.is_alive():
        logging.warning("NFC reader thread did not terminate gracefully.")
    nfc_reader_active = False
    return True

def stop_listening():
    """Signals all continuous listening loops (NFC, ntfy) to stop."""
    global continue_reading, nfc_reader_thread, ntfy_listener_thread, nfc_reader_should_run
    logging.info("Signaling all listening loops to stop...")
    continue_reading = False # This will stop both NFC and ntfy loops

    # Also explicitly stop the NFC reader flag
    nfc_reader_should_run = False

    # Wait for NFC reader thread to finish
    if nfc_reader_thread and nfc_reader_thread.is_alive():
        logging.info("Waiting for NFC reader thread to terminate...")
        nfc_reader_thread.join(timeout=2)
        if nfc_reader_thread.is_alive():
            logging.warning("NFC reader thread did not terminate gracefully.")
    
    # Wait for ntfy listener thread to finish
    if ntfy_listener_thread and ntfy_listener_thread.is_alive():
        logging.info("Waiting for ntfy listener thread to terminate...")
        ntfy_listener_thread.join(timeout=2)
        if ntfy_listener_thread.is_alive():
            logging.warning("ntfy listener thread did not terminate gracefully.")
    
    logging.info("All listening loops signaled to stop.")


def get_nfc_status():
    """Returns the current status of the NFC reader (True if running, False otherwise)."""
    global nfc_reader_active
    return nfc_reader_active

def get_all_config_items():
    """
    Reads the config.ini file and returns all configuration items as a dictionary,
    excluding sensitive fields like usernames and passwords.
    """
    config = _get_config_parser()
    all_config = {}
    sensitive_fields = {
        'credentials': ['username', 'password'],
        'camera': ['username', 'password']
    }

    for section in config.sections():
        all_config[section] = {}
        for key, value in config.items(section):
            if section in sensitive_fields and key in sensitive_fields[section]:
                all_config[section][key] = '********' # Mask sensitive info
            else:
                all_config[section][key] = value
    return all_config

def update_config_items(updates):
    """
    Updates the config.ini file with the provided dictionary of updates.
    Sensitive fields (usernames, passwords) cannot be updated via this function.
    """
    config = _get_config_parser()
    sensitive_fields = {
        'credentials.username', 'credentials.password',
        'camera.username', 'camera.password'
    }
    
    updated_any = False
    for key_path, new_value in updates.items():
        if key_path in sensitive_fields:
            logging.warning(f"Attempted to update sensitive field '{key_path}'. Operation blocked.")
            continue

        section, key = key_path.split('.', 1)
        if not config.has_section(section):
            config.add_section(section)
        
        current_value = config.get(section, key, fallback=None)
        if current_value != new_value:
            config.set(section, key, new_value)
            updated_any = True
            logging.info(f"Config updated: [{section}]{key} = {new_value}")

    if updated_any:
        try:
            with open(_CONTROLLER_CONFIG_FILE_PATH, 'w') as configfile:
                config.write(configfile)
            logging.info("config.ini file successfully updated on disk.")
            # Reload the in-memory config to reflect changes
            load_config(config)
            return True
        except Exception as e:
            logging.error(f"Failed to write config.ini file: {e}")
            return False
    else:
        logging.info("No changes detected for config.ini.")
        return False
