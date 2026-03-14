#!/usr/bin/env python

import RPi.GPIO as GPIO
from mfrc522 import SimpleMFRC522

reader = SimpleMFRC522()

print("Hou een kaart voor de lezer...")

try:
    while True:
        id, text = reader.read()
        print("Kaart gedetecteerd!")
        print("ID: %s" % (id))
        print("Text: %s" % (text))
finally:
    print("Programma wordt afgesloten.")
    GPIO.cleanup()
