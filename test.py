#!/usr/bin/env python

import sys
import time


import RPi.GPIO as GPIO
from mfrc522 import SimpleMFRC522
from gpiozero import Button
from gpiozero import LED
from gpiozero import OutputDevice

print('Press Control + C to exit the program')

LED_PIN = 18
RELAY_PIN = 17
REED_CONTACT_1_PIN = 27

led = LED(LED_PIN)
relay = OutputDevice(RELAY_PIN, active_high=False, initial_value=False)
reed1 = Button(27)


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
    time.sleep(.5)
    relay.toggle()


def flash_light(amount):
    print('Test LED by flashing.')
    for x in range(amount):
        led.on()
        time.sleep(.25)
        led.off()
        time.sleep(.25)


def initiate_reed_state():
    if reed1.is_pressed:
        reed_open()
    else:
        reed_closed()


def initiate_nfc_reader():
    reader = SimpleMFRC522()
    while 1:
        id, text = reader.read()
        print(id)
        print(text)


def reed_open():
    print('Read contact is open.')


def reed_closed():
    print('Read contact is closed.')


try:
    set_relay(False)
    reed1.when_released = reed_open
    reed1.when_pressed = reed_closed
    initiate_reed_state()
    initiate_nfc_reader()
    while 1:
        flash_light(5)
        toggle_relay()


except KeyboardInterrupt:  # Stops program when "Control + C" is entered
    set_relay(False)
    sys.exit(0)
    GPIO.cleanup()
