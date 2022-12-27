#!/usr/bin/env python
# -*- coding: utf8 -*-

import time
from concurrent.futures import ThreadPoolExecutor
from gpiozero import OutputDevice
from gpiozero import Button
from mfrc522 import SimpleMFRC522

# BE AWARE, THESE ARE (G)PIOS, NOT PINS
RELAY_PIN = 17
REED_CONTACT_CLOSED_DOOR_PIN = 22
REED_CONTACT_OPEN_DOOR_PIN = 23
VALID_CARD_IDS_FILE = 'valid_card_ids.txt'

continue_reading = True
allowed_card_ids = []
relay: OutputDevice
reed_closed_door: Button
reed_open_door: Button


def setup():
    global relay
    relay = OutputDevice(RELAY_PIN, active_high=True, initial_value=False)
    setup_reed_contacts()
    read_allowed_card_ids()


def run_io_tasks_in_parallel(tasks):
    with ThreadPoolExecutor() as executor:
        running_tasks = [executor.submit(task) for task in tasks]
        for running_task in running_tasks:
            running_task.result()


def read_allowed_card_ids():
    print('Reading allowed card ids from ' + VALID_CARD_IDS_FILE)
    with open(VALID_CARD_IDS_FILE, 'r') as file:
        global allowed_card_ids
        allowed_card_ids = file.read().splitlines()


def get_allowed_card_ids():
    return allowed_card_ids


def add_allowed_card_id(card_id):
    with open(VALID_CARD_IDS_FILE, 'a') as file:
        file.write(str(card_id + '\n'))
    read_allowed_card_ids()


def toggle_relay():
    print('Toggling relay')
    relay.toggle()
    time.sleep(.5)
    relay.toggle()


def setup_reed_contacts():
    print('Setting up reed contacts')
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
    print('Closed door reed contact is open - garage door is opening/open.')


def reed_closed_door_closed():
    print('Closed door reed contact is closed - garage door is closed.')


def reed_open_door_open():
    print('Open door reed is open - garage door is closing/closed.')


def reed_open_door_closed():
    print('Open door reed contact is door is closed - garage door is open.')


def start_listening():
    print('Starting NFC reader')
    reader = SimpleMFRC522()
    while continue_reading:
        (tag_id, tag_text) = reader.read()
        print(allowed_card_ids)
        if tag_id in allowed_card_ids:
            print('ACCESS FOR CARD ' + str(tag_id))
            toggle_relay()
        else:
            print('ACCESS BLOCKED FOR CARD ' + str(tag_id))
