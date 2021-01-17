#!/usr/bin/env python

from gpiozero import LED
from gpiozero import OutputDevice
import time
import sys

print('Press Control + C to exit the program')

LED_PIN = 18
RELAY_PIN = 17

led = LED(LED_PIN)
relay = OutputDevice(RELAY_PIN, active_high=False, initial_value=False)


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
        # GPIO.output(ledPin, GPIO.HIGH)
        time.sleep(.25)
        led.off()
        # GPIO.output(ledPin, GPIO.LOW)
        time.sleep(.25)


try:
    set_relay(False)
    while 1:
        flash_light(5)
        toggle_relay()

except KeyboardInterrupt:  # Stops program when "Control + C" is entered
    set_relay(False)
    sys.exit(0)
