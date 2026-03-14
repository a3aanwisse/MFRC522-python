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

VERSION = "1.9.1"

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

continue_reading = True
allowed_cards = {}
last_used_card_id = None  # We only need to know if a card was used, not the phone number
active_close_token = None # Stores the unique token for the current open session

relay: OutputDevice = None
reed_closed_door: Button = None
reed_open_door: Button = None
door_open_timer: Timer = None
stats_lock = threading.Lock()
stat_listeners = [] # List of queues to notify on updates
hardware_listeners = [] # List of queues for hardware status updates

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


def load_config(config):
    """Loads configuration values from the config object."""
    global VALID_CARDS_FILE, NTFY_TOPIC, STATS_FILE, DOOR_OPEN_TIMEOUT, CAMERA_URL, CAMERA_USER, CAMERA_PASS

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


def setup(config):
    """Sets up the controller with the given configuration."""
    global relay

    if not load_config(config):
        sys.exit(1)

    relay = OutputDevice(RELAY_PIN, active_high=True, initial_value=False)
    setup_reed_contacts()


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
                # The file now only contains card IDs, one per line
                new_allowed_cards[line] = True
        allowed_cards = new_allowed_cards
        logging.info('Allowed cards loaded: %s', list(allowed_cards.keys()))
    except FileNotFoundError:
        logging.error(f'Could not find {VALID_CARDS_FILE}. No cards will be loaded.')
        allowed_cards = {}


def get_allowed_cards():
    # Return a list of keys for display purposes
    return list(allowed_cards.keys())


def add_allowed_card(card_id):
    """Adds a new card ID to the file."""
    card_id_str = str(card_id)
    try:
        with open(VALID_CARDS_FILE, 'a') as file:
            file.write(f'\n{card_id_str}')
        logging.info(f'Writing card id {card_id_str} to file.')
        read_allowed_cards()
        return True
    except Exception as e:
        logging.error(f"Failed to write card ID to file: {e}")
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


def _perform_toggle_relay():
    logging.info('Toggling relay')
    if relay:
        relay.toggle()
        time.sleep(.5)
        relay.toggle()
        time.sleep(1.5)
        broadcast_hardware_update() # Notify UI that toggle is done
    else:
        logging.error("Relay not initialized")

def toggle_relay():
    # Run the actual relay toggle in a separate thread so we don't block the caller
    # (especially important for the web server to avoid queue depth issues)
    threading.Thread(target=_perform_toggle_relay, daemon=True).start()


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
    global last_used_card_id
    logging.info('Closed door reed contact is open - garage door is opening/open.')
    
    # Log the event BEFORE resetting the card ID
    log_stat_event('OPEN', last_used_card_id)
    
    # Reset last used card on any new door opening event to detect manual opens
    last_used_card_id = None
    logging.info('Reset last used card ID due to new door opening event.')
    broadcast_hardware_update()


def reed_closed_door_closed():
    global door_open_timer
    logging.info('Closed door reed contact is closed - garage door is closed.')
    log_stat_event('CLOSE')
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

        if last_used_card_id:
            message += f' Laatst opengemaakt met kaart: {last_used_card_id}.'
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
        except Exception as e:
            logging.error(f"Error in remote command listener: {e}")
            time.sleep(10) # Wait before reconnecting


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

def start_listening():
    global last_used_card_id
    logging.info('Starting NFC reader...')

    # Check if door is already open upon startup (e.g. after a reboot/update)
    if reed_open_door and reed_open_door.is_pressed:
        logging.info("Startup check: Door is detected as open. Resuming notification timer.")
        reed_open_door_closed()

    # Start the remote listener in a background thread
    threading.Thread(target=listen_for_ntfy_commands, daemon=True).start()
    
    reader = MFRC522()
    logging.info('Started NFC reader. Waiting for cards...')
    while continue_reading:
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
                        last_used_card_id = card_id_str
                        logging.info(f'ACCESS FOR CARD {card_id_str}')
                        toggle_relay()
                    else:
                        logging.info(f'ACCESS BLOCKED FOR CARD {card_id_str}')
                    
                    # A small delay to prevent multiple reads of the same card
                    time.sleep(1)

        except Exception as e:
            # This can happen if the reader is interrupted by a shutdown signal
            if continue_reading:
                logging.error(f"Error reading NFC tag: {e}")
                time.sleep(1) # Prevent tight loop on error

def stop_listening():
    """Stops the NFC reader and other listening threads."""
    global continue_reading
    logging.info('Stopping NFC reader and other listening threads...')
    continue_reading = False
