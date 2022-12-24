#!/usr/bin/env python

import sys

from concurrent.futures import ThreadPoolExecutor
from time import sleep
from RPi import GPIO
from gpiozero import Button
from gpiozero import LED
from gpiozero import OutputDevice
from mfrc522 import SimpleMFRC522

print('Press Control + C to exit the program')

# BE AWARE, THESE ARE (G)PIOS, NOT PINS
LED_PIN = 18
RELAY_PIN = 17
REED_CONTACT_1_PIN = 27
REED_CONTACT_2_PIN = 5

led = LED(LED_PIN)
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
        print("Setting relay: ON")
        relay.on()
    else:
        print("Setting relay: OFF")
        relay.off()


def toggle_relay():
    print("Toggling relay")
    relay.toggle()
    sleep(.5)
    relay.toggle()


def flash_light(amount):
    print('Test LED by flashing.')
    for x in range(amount):
        led.on()
        sleep(.25)
        led.off()
        sleep(.25)


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
    while 1:
        tag_id, tag_text = reader.read()
        print(tag_id)
        print(tag_text)


def reed_1_open():
    print('Read contact 1 is open.')


def reed_1_closed():
    print('Read contact 1 is closed.')


def reed_2_open():
    print('Read contact 2 is open.')


def reed_2_closed():
    print('Read contact 2 is closed.')


def test_io():
    while True:
        flash_light(5)
        toggle_relay()


try:
    set_relay(False)
    reed1.when_released = reed_open
    reed1.when_pressed = reed_closed
    initiate_reed_1_state()
    initiate_reed_2_state()
    run_io_tasks_in_parallel([
        lambda: initiate_nfc_reader(),
        lambda: test_io(),
    ])


except KeyboardInterrupt:  # Stops program when "Control + C" is entered
    set_relay(False)
    GPIO.cleanup()
    sys.exit(0)
    raise
