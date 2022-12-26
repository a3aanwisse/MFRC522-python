#!/usr/bin/env python
# -*- coding: utf8 -*-

import time
from concurrent.futures import ThreadPoolExecutor
from gpiozero import LED
from gpiozero import OutputDevice
from gpiozero import Button
from mfrc522 import SimpleMFRC522

# BE AWARE, THESE ARE (G)PIOS, NOT PINS
LED_PIN = 18
RELAY_PIN = 17
REED_CONTACT_1_PIN = 22
REED_CONTACT_2_PIN = 23

continue_reading = True
allowed_card_ids = []
led: LED
relay: OutputDevice
reed1: Button
reed2: Button


def setup():
    global led, relay
    led = LED(LED_PIN)
    relay = OutputDevice(RELAY_PIN, active_high=False, initial_value=False)
    setup_reed_contacts()
    read_allowed_card_ids()


def run_io_tasks_in_parallel(tasks):
    with ThreadPoolExecutor() as executor:
        running_tasks = [executor.submit(task) for task in tasks]
        for running_task in running_tasks:
            running_task.result()


def read_allowed_card_ids():
    print("Reading allowed card ids")
    global allowed_card_ids
    allowed_card_ids = [864127531329]


def switch_led_on():
    print("LED turning on.")
    led.on()


def switch_led_off():
    print("LED turning off.")
    led.off()


def toggle_relay():
    print("Toggling relay")
    relay.toggle()
    time.sleep(.5)
    relay.toggle()


def setup_reed_contacts():
    print("Setting up reed contacts")
    global reed1, reed2
    reed1 = Button(REED_CONTACT_1_PIN)
    reed1.when_released = reed_1_open
    reed1.when_pressed = reed_1_closed
    reed2 = Button(REED_CONTACT_2_PIN)
    reed2.when_released = reed_2_open
    reed2.when_pressed = reed_2_closed


def read_reed_1():
    if reed1.value == 0:
        return "open"
    else:
        return "closed"


def read_reed_2():
    if reed2.value == 0:
        return "open"
    else:
        return "closed"


def reed_1_open():
    print('Reed contact 1 is open.')


def reed_1_closed():
    print('Reed contact 1 is closed.')


def reed_2_open():
    print('Reed contact 2 is open.')


def reed_2_closed():
    print('Reed contact 2 is closed.')


def start_listening():
    print("Starting NFC reader")
    reader = SimpleMFRC522()
    while continue_reading:
        (tag_id, tag_text) = reader.read()
        print(tag_id)
        print(tag_text)

        if tag_id in allowed_card_ids:
            switch_led_on()
            toggle_relay()
            time.sleep(10)
            switch_led_off()

            print("ENTRANCE!")
        else:
            print("BLOCKED!")
#
# def start_listening():
#     # This loop keeps checking for chips. If one is near it will get the UID and authenticate
#     while continue_reading:
#
#         # Scan for cards
#         (status, TagType) = MIFAREReader.MFRC522_Request(MIFAREReader.PICC_REQIDL)
#
#         # If a card is found
#         if status == MIFAREReader.MI_OK:
#             print("Card detected")
#
#         # Get the UID of the card
#         (status, uid) = MIFAREReader.MFRC522_Anticoll()
#
#         # If we have the UID, continue
#         if status == MIFAREReader.MI_OK:
#
#             # Print UID
#             print("Card read UID:")
#             print(uid)
#
#             # This is the default key for authentication
#             key = [0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF]
#
#             # Select the scanned tag
#             MIFAREReader.MFRC522_SelectTag(uid)
#
#             # Authenticate
#             status = MIFAREReader.MFRC522_Auth(MIFAREReader.PICC_AUTHENT1A, 8, key, uid)
#
#             # Check if authenticated
#             if status == MIFAREReader.MI_OK:
#                 MIFAREReader.MFRC522_Read(8)
#                 MIFAREReader.MFRC522_StopCrypto1()
#
#                 if uid in allowed:
#                     switch_led_on()
#                     toggle_relay()
#                     time.sleep(10)
#                     switch_led_off()
#
#                     print("ENTRANCE!")
#                 else:
#                     print("BLOCKED!")
#             else:
#                 print("Authentication error")
