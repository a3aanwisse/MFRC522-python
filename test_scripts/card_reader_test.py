#!/usr/bin/env python

import RPi.GPIO as GPIO
import signal
import time
from mfrc522 import MFRC522

# Create an object of the class MFRC522
MIFAREReader = MFRC522()

# This flag will be set to True when the user presses CTRL+C
end_read = False

# This function will be called when the user presses CTRL+C
def end_read_handler(signal, frame):
    global end_read
    print("\nCtrl+C captured, ending read.")
    end_read = True

# Hook the SIGINT
signal.signal(signal.SIGINT, end_read_handler)

print("Hou een kaart voor de lezer...")

# This loop will run until the user presses CTRL+C
while not end_read:
    # Scan for cards
    (status, TagType) = MIFAREReader.MFRC522_Request(MIFAREReader.PICC_REQIDL)

    # If a card is found
    if status == MIFAREReader.MI_OK:
        print("Kaart gedetecteerd!")

    # Get the UID of the card
    (status, uid) = MIFAREReader.MFRC522_Anticoll()

    # If we have the UID, print it
    if status == MIFAREReader.MI_OK:
        card_id = "".join(str(i) for i in uid)
        print("Kaart ID: " + card_id)
        
        # A small delay to prevent multiple reads of the same card
        time.sleep(1)

# Cleanup GPIO
GPIO.cleanup()
