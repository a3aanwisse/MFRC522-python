#!/usr/bin/env python
# -*- coding: utf8 -*-

import logging
import sys
import time
import json
import os
from datetime import datetime
import uuid
import threading
import configparser
from concurrent.futures import ThreadPoolExecutor
from threading import Timer

import requests
from gpiozero import Button, OutputDevice
from mfrc522 import SimpleMFRC522

VERSION = "1.2.0"

# BE AWARE, THESE ARE (G)PIOS, NOT PINS
RELAY_PIN = 17
REED_CONTACT_CLOSED_DOOR_PIN = 22
REED_CONTACT_OPEN_DOOR_PIN = 23

# These will be set by the setup function from the config file
VALID_CARDS_FILE = None
NTFY_TOPIC = None
STATS_FILE = None

continue_reading = True
allowed_cards = {}
last_used_card_id = None  # We only need to know if a card was used, not the phone number
active_close_token = None # Stores the unique token for the current open session

relay: OutputDevice = None
reed_closed_door: Button = None
reed_open_door: Button = None
door_open_timer: Timer = None
stats_lock = threading.Lock()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


def setup(config):
    """Sets up the controller with the given configuration."""
    global relay, VALID_CARDS_FILE, NTFY_TOPIC, STATS_FILE

    try:
        VALID_CARDS_FILE = config.get('paths', 'valid_cards_file')
        NTFY_TOPIC = config.get('ntfy', 'topic')
        STATS_FILE = config.get('paths', 'stats_file', fallback='garage_stats.json')
        logging.info('Successfully loaded paths and ntfy config.')
    except (configparser.NoSectionError, configparser.NoOptionError) as e:
        logging.error(f'Could not read configuration from config.ini: {e}')
        sys.exit(1)

    relay = OutputDevice(RELAY_PIN, active_high=True, initial_value=False)
    setup_reed_contacts()
    read_allowed_cards()


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


def toggle_relay():
    logging.info('Toggling relay')
    if relay:
        relay.toggle()
        time.sleep(.5)
        relay.toggle()
        time.sleep(1.5)
    else:
        logging.error("Relay not initialized")


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


def reed_closed_door_closed():
    global door_open_timer
    logging.info('Closed door reed contact is closed - garage door is closed.')
    log_stat_event('CLOSE')
    if door_open_timer and door_open_timer.is_alive():
        door_open_timer.cancel()
        logging.info('Cancelled door open timer as door is now closed.')


def reed_open_door_open():
    global door_open_timer
    logging.info('Open door reed contact is open - garage door is closing/closed.')
    if door_open_timer and door_open_timer.is_alive():
        door_open_timer.cancel()
        logging.info('Cancelled door open timer.')


def reed_open_door_closed():
    global door_open_timer
    logging.info('Open door reed contact is closed - garage door is open.')
    if door_open_timer and door_open_timer.is_alive():
        door_open_timer.cancel()
        logging.info('Cancelling previous door open timer.')

    logging.info('Starting 60-second timer for door open notification.')
    door_open_timer = Timer(120, send_ntfy_notification)
    door_open_timer.start()


def send_ntfy_notification():
    global active_close_token
    if not NTFY_TOPIC or NTFY_TOPIC == 'your_ntfy_topic_here':
        logging.error('ntfy topic is not configured in config.ini. Cannot send notification.')
        return

    if reed_open_door and reed_open_door.is_pressed:
        title = 'Garagedeur alarm!'
        message = 'De garagedeur is meer dan 2 minuten open!'
        log_stat_event('LONG_OPEN_WARNING')

        if last_used_card_id:
            message += f' Laatst opengemaakt met kaart: {last_used_card_id}.'
        else:
            message += ' Laatst handmatig geopend (gebruiker onbekend).'

        # Generate a unique token for this specific notification
        token = str(uuid.uuid4())
        active_close_token = token

        # Add an action button to the notification
        headers = {
            'Title': title,
            'Actions': f'http, Sluiten, https://ntfy.sh/{NTFY_TOPIC}, body=CLOSE_TOKEN_{token}, method=POST'
        }

        logging.info(f'Sending notification to ntfy topic: {NTFY_TOPIC}')
        try:
            requests.post(
                f'https://ntfy.sh/{NTFY_TOPIC}',
                data=message.encode(encoding='utf-8'),
                headers=headers
            )
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

    logging.info(f"Starting remote command listener on topic: {NTFY_TOPIC}")
    while True:
        try:
            # Listen to the stream for JSON data
            resp = requests.get(f'https://ntfy.sh/{NTFY_TOPIC}/json', stream=True, timeout=60)
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


def start_listening():
    global last_used_card_id
    logging.info('Starting NFC reader...')

    # Check if door is already open upon startup (e.g. after a reboot/update)
    if reed_open_door and reed_open_door.is_pressed:
        logging.info("Startup check: Door is detected as open. Resuming notification timer.")
        reed_open_door_closed()

    # Start the remote listener in a background thread
    threading.Thread(target=listen_for_ntfy_commands, daemon=True).start()
    
    reader = SimpleMFRC522()
    logging.info('Started NFC reader')
    while continue_reading:
        try:
            (tag_id, tag_text) = reader.read()
            tag_id_str = str(tag_id)
            if tag_id_str in allowed_cards:
                last_used_card_id = tag_id_str
                logging.info(f'ACCESS FOR CARD {tag_id_str}')
                toggle_relay()
            else:
                logging.info(f'ACCESS BLOCKED FOR CARD {tag_id_str}')
        except Exception as e:
            logging.error(f"Error reading NFC tag: {e}")
            time.sleep(1) # Prevent tight loop on error
