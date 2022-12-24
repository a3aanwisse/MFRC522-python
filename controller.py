#!/usr/bin/env python
# -*- coding: utf8 -*-

import time
from gpiozero import LED
from gpiozero import OutputDevice
from gpiozero import Button

LED_PIN = 18
RELAY_PIN = 17
REED_CONTACT_1_PIN = 27

continue_reading = True
led: LED
relay: OutputDevice
reed1: Button


def setup():
    global led, relay
    led = LED(LED_PIN)
    relay = OutputDevice(RELAY_PIN, active_high=False, initial_value=False)
    setup_reed_contacts()
    # start_listening()


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
    global reed1
    reed1 = Button(REED_CONTACT_1_PIN)
    reed1.when_released = reed_open
    reed1.when_pressed = reed_closed


def read_reed_1():
    if reed1.value == 0:
        return "open"
    else:
        return "closed"


def reed_open():
    print('Read contact is open.')


def reed_closed():
    print('Read contact is closed.')


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
