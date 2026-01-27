#!/usr/bin/env python
# -*- coding: utf8 -*-

import logging
import sys

import requests
import time
import configparser
from concurrent.futures import ThreadPoolExecutor
from threading import Timer

from gpiozero import Button
from gpiozero import OutputDevice
from mfrc522 import SimpleMFRC522

# BE AWARE, THESE ARE (G)PIOS, NOT PINS
RELAY_PIN = 17
REED_CONTACT_CLOSED_DOOR_PIN = 22
REED_CONTACT_OPEN_DOOR_PIN = 23

# These will be set by the setup function from the config file
VALID_CARDS_FILE = None
NTFY_TOPIC = None

continue_reading = True
allowed_cards = {}
last_used_card_id = None # We only need to know if a card was used, not the phone number

relay: OutputDevice
reed_closed_door: Button
reed_open_door: Button
door_open_timer: Timer = None

logging.basicConfig(level=logging.INFO)

def setup(config):
    """Sets up the controller with the given configuration."""
    global relay, VALID_CARDS_FILE, NTFY_TOPIC
    
    try:
        VALID_CARDS_FILE = config.get('paths', 'valid_cards_file')
        NTFY_TOPIC = config.get('ntfy', 'topic')
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
    with open(VALID_CARDS_FILE, 'a') as file:
        file.write(f'\n{card_id_str}')
    logging.info(f'Writing card id {card_id_str} to file.')
    read_allowed_cards()
    return True


def toggle_relay():
    logging.info('Toggling relay')
    relay.toggle()
    time.sleep(.5)
    relay.toggle()
    time.sleep(1.5)


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
    if reed_closed_door.value == 0:
        return 'garage door is opening / open'
    else:
        return 'garage door is closed'


def read_reed_open_door():
    if reed_open_door.value == 0:
        return 'garage door is closing / closed'
    else:
        return 'garage door is fully open'


def reed_closed_door_open():
    global last_used_card_id
    logging.info('Closed door reed contact is open - garage door is opening/open.')
    # Reset last used card on any new door opening event to detect manual opens
    last_used_card_id = None
    logging.info('Reset last used card ID due to new door opening event.')


def reed_closed_door_closed():
    global door_open_timer
    logging.info('Closed door reed contact is closed - garage door is closed.')
    if door_open_timer and door_open_timer.is_alive():
        door_open_timer.cancel()
        logging.info('Cancelled door open timer as door is now closed.')


def reed_open_door_open():
    global door_open_timer
    logging.info('Open door reed is open - garage door is closing/closed.')
    if door_open_timer and door_open_timer.is_alive():
        door_open_timer.cancel()
        logging.info('Cancelled door open timer.')


def send_ntfy_notification():
    if not NTFY_TOPIC or NTFY_TOPIC == 'your_ntfy_topic_here':
        logging.error('ntfy topic is not configured in config.ini. Cannot send notification.')
        return

    if reed_open_door.is_pressed:
        title = 'Garage Door Alert'
        message = 'The garage door has been open for more than 30 seconds!'

        if last_used_card_id:
            message += f' Last opened by card: {last_used_card_id}.'
        else:
            message += ' Last opened manually (user unknown).'

        logging.info(f'Sending notification to ntfy topic: {NTFY_TOPIC}')
        try:
            requests.post(
                f'https://ntfy.sh/{NTFY_TOPIC}',
                data=message.encode(encoding='utf-8'),
                headers={'Title': title}
            )
            logging.info('Successfully sent ntfy notification.')
        except Exception as e:
            logging.error(f'Failed to send ntfy notification: {e}')
    else:
        logging.warning('Door is no longer open; skipping notification.')


def reed_open_door_closed():
    global door_open_timer
    logging.info('Open door reed contact is closed - garage door is open.')
    if door_open_timer and door_open_timer.is_alive():
        door_open_timer.cancel()
        logging.info('Cancelling previous door open timer.')
    
    logging.info('Starting 30-second timer for door open notification.')
    door_open_timer = Timer(30, send_ntfy_notification)
    door_open_timer.start()


def start_listening():
    global last_used_card_id
    logging.info('Starting NFC reader...')
    reader = SimpleMFRC522()
    logging.info('Started NFC reader')
    while continue_reading:
        (tag_id, tag_text) = reader.read()
        tag_id_str = str(tag_id)
        if tag_id_str in allowed_cards:
            last_used_card_id = tag_id_str
            logging.info(f'ACCESS FOR CARD {tag_id_str}')
            toggle_relay()
        else:
            logging.info(f'ACCESS BLOCKED FOR CARD {tag_id_str}')

