#!/usr/bin/env python

import RPi.GPIO as GPIO
import time

print('Press Control + C to exit the program')

GPIO.setmode(GPIO.BOARD)  # the pin numbers refer to the board connector not the chip
GPIO.setwarnings(False)

ledPin = 12
relayPin = 11

GPIO.setup(ledPin, GPIO.OUT)
GPIO.setup(relayPin, GPIO.OUT)


def flash_light(amount):
    print('Test LED by flashing.')
    for x in range(amount):
        GPIO.output(ledPin, GPIO.HIGH)
        time.sleep(.5)
        GPIO.output(ledPin, GPIO.LOW)
        time.sleep(.5)


# def switch_relay():
#     print('Test Relay by opening and closing.')
#     GPIO.output(relayPin, GPIO.LOW)
#     time.sleep(.5)
#     GPIO.output(relayPin, GPIO.HIGH)


try:
    while True:
        flash_light(5)
        time.sleep(10)
        # switch_relay()

except KeyboardInterrupt:  # Stops program when "Control + C" is entered
    GPIO.cleanup()  # Turns OFF everything
