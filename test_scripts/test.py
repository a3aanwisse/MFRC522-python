#!/usr/bin/env python

import sys
import logging
from concurrent.futures import ThreadPoolExecutor
from time import sleep

from gpiozero import Button
from gpiozero import OutputDevice
from mfrc522 import SimpleMFRC522

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

try:
    from RPi import GPIO
except ImportError:
    logging.warning("RPi.GPIO not found, using fake_rpi")
    from fake_rpi.RPi import GPIO

logging.info('Press Control + C to exit the program')

# BE AWARE, THESE ARE (G)PIOS, NOT PINS
RELAY_PIN = 17
REED_CONTACT_1_PIN = 22
REED_CONTACT_2_PIN = 23

relay = OutputDevice(RELAY_PIN, active_high=False, initial_value=False)
reed1 = Button(REED_CONTACT_1_PIN)
reed2 = Button(REED_CONTACT_2_PIN)


def run_io_tasks_in_parallel(tasks):
    with ThreadPoolExecutor() as executor:
        running_tasks = [executor.submit(task) for task in tasks]
        for running_task in running_tasks:
            running_task.result()


def set_relay(status):
    if status:
        logging.info("Setting relay: ON")
        relay.on()
    else:
        logging.info("Setting relay: OFF")
        relay.off()


def toggle_relay():
    logging.info("Toggling relay")
    relay.toggle()
    sleep(.5)
    relay.toggle()


def initiate_reed_1_state():
    if reed1.is_pressed:
        reed_1_open()
    else:
        reed_1_closed()


def initiate_reed_2_state():
    if reed2.is_pressed:
        reed_2_open()
    else:
        reed_2_closed()


def initiate_nfc_reader():
    reader = SimpleMFRC522()
    while True:
        tag_id, tag_text = reader.read()
        logging.info(f"Tag ID: {tag_id}")
        logging.info(f"Tag Text: {tag_text}")


def reed_1_open():
    logging.info('Read contact 1 is open.')


def reed_1_closed():
    logging.info('Read contact 1 is closed.')


def reed_2_open():
    logging.info('Read contact 2 is open.')


def reed_2_closed():
    logging.info('Read contact 2 is closed.')


def test_io():
    while True:
        toggle_relay()


if __name__ == "__main__":
    try:
        set_relay(False)
        reed1.when_released = reed_1_open
        reed1.when_pressed = reed_1_closed
        initiate_reed_1_state()
        reed2.when_released = reed_2_open
        reed2.when_pressed = reed_2_closed
        initiate_reed_2_state()
        run_io_tasks_in_parallel([
            lambda: initiate_nfc_reader(),
            lambda: test_io(),
        ])

    except KeyboardInterrupt:  # Stops program when "Control + C" is entered
        set_relay(False)
        # GPIO.cleanup() # gpiozero handles cleanup automatically usually, but if RPi.GPIO is used directly it might be needed.
        # However, since we use gpiozero objects, explicit cleanup of RPi.GPIO might conflict or be redundant.
        # If fake_rpi is used, it might not have cleanup.
        logging.info("Program terminated manually")
        sys.exit(0)
