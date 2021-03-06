#!/usr/bin/env python
# -*- coding: utf8 -*-
#
#    Copyright 2014,2018 Mario Gomez <mario.gomez@teubi.co>
#
#    This file is part of MFRC522-Python
#    MFRC522-Python is a simple Python implementation for
#    the MFRC522 NFC Card Reader for the Raspberry Pi.
#
#    MFRC522-Python is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Lesser General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    MFRC522-Python is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Lesser General Public License for more details.
#
#    You should have received a copy of the GNU Lesser General Public License
#    along with MFRC522-Python.  If not, see <http://www.gnu.org/licenses/>.
#

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
