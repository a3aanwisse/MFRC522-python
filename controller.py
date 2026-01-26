#!/usr/bin/env python
# -*- coding: utf8 -*-

import logging
import sys
import re
import subprocess
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
SIGNAL_SENDER_NR = None
DEFAULT_RECIPIENT_NR = None

continue_reading = True
allowed_cards = {}
last_used_phone_number = None

relay: OutputDevice
reed_closed_door: Button
reed_open_door: Button
door_open_timer: Timer = None

logging.basicConfig(level=logging.INFO)

PHONE_NUMBER_REGEX = re.compile(r'^\+[1-9]\d{1,14}$')


def is_valid_phone_number(phone_number):
    """Validates a phone number against the E.164 format."""
    if not phone_number:
        return False
    return PHONE_NUMBER_REGEX.match(phone_number) is not None


def setup(config):
    """Sets up the controller with the given configuration."""
    global relay, VALID_CARDS_FILE, SIGNAL_SENDER_NR, DEFAULT_RECIPIENT_NR
    
    try:
        VALID_CARDS_FILE = config.get('paths', 'valid_cards_file')
        SIGNAL_SENDER_NR = config.get('signal', 'sender_number')
        DEFAULT_RECIPIENT_NR = config.get('signal', 'default_recipient_number')
        logging.info('Successfully loaded paths and signal config.')
    except (configparser.NoSectionError, configparser.NoOptionError) as e:
        logging.error(f'Could not read configuration from config.ini: {e}')
        # Exit if critical configuration is missing
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

                if ',' not in line:
                    logging.error(f'Invalid format on line {i} in {VALID_CARDS_FILE}: Missing comma.')
                    continue

                card_id, phone_number = [part.strip() for part in line.split(',', 1)]

                if not card_id:
                    logging.error(f'Validation failed on line {i}: Card ID is missing. Skipping.')
                    continue
                
                if not is_valid_phone_number(phone_number):
                    logging.error(f"Validation failed on line {i}: Invalid phone number '{phone_number}' for card '{card_id}'. Skipping.")
                    continue

                new_allowed_cards[card_id] = phone_number
        allowed_cards = new_allowed_cards
        logging.info('Allowed cards loaded: %s', str(allowed_cards))
    except FileNotFoundError:
        logging.error(f'Could not find {VALID_CARDS_FILE}. No cards will be loaded.')
        allowed_cards = {}


def get_allowed_cards():
    return allowed_cards


def add_allowed_card(card_id, phone_number):
    """Adds a new card and phone number, validating the number first."""
    if not is_valid_phone_number(phone_number):
        logging.error(f'Attempted to add invalid phone number: {phone_number}')
        return False

    card_id_str = str(card_id)
    with open(VALID_CARDS_FILE, 'a') as file:
        file.write(f'\n{card_id_str},{phone_number}')
    logging.info(f'Writing card id {card_id_str} with phone {phone_number} to file.')
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
    global last_used_phone_number
    logging.info('Closed door reed contact is open - garage door is opening/open.')
    last_used_phone_number = None
    logging.info('Reset last used phone number due to new door opening event.')


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


def send_signal_notification():
    recipient = last_used_phone_number or DEFAULT_RECIPIENT_NR
    
    if not recipient:
        logging.error('No recipient for door open notification; neither last user nor default is set.')
        return

    if reed_open_door.is_pressed:
        logging.info(f'Sending Signal notification to {recipient}.')
        message = 'Warning: Garage door has been open for more than 30 seconds!'
        try:
            subprocess.run([
                'signal-cli', '-u', SIGNAL_SENDER_NR, 'send', '-m', message, recipient
            ], check=True)
            logging.info('Successfully sent Signal message.')
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            logging.error(f'Failed to send Signal message: {e}')
    else:
        logging.warning('Door is no longer open; skipping notification.')


def reed_open_door_closed():
    global door_open_timer
    logging.info('Open door reed contact is closed - garage door is open.')
    if door_open_timer and door_open_timer.is_alive():
        door_open_timer.cancel()
        logging.info('Cancelling previous door open timer.')
    
    logging.info('Starting 30-second timer for door open notification.')
    door_open_timer = Timer(30, send_signal_notification)
    door_open_timer.start()


def start_listening():
    global last_used_phone_number
    logging.info('Starting NFC reader')
    reader = SimpleMFRC522()
    while continue_reading:
        (tag_id, tag_text) = reader.read()
        tag_id_str = str(tag_id)
        if tag_id_str in allowed_cards:
            last_used_phone_number = allowed_cards[tag_id_str]
            logging.info(f'ACCESS FOR CARD {tag_id_str}, user: {last_used_phone_number}')
            toggle_relay()
        else:
            logging.info(f'ACCESS BLOCKED FOR CARD {tag_id_str}')
