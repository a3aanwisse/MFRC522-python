import os
import sys
import argparse

def setup_development_mode():
    """
    Parses command-line arguments to detect a '--dev' flag.

    If the flag is present, this function will mock all Raspberry Pi-specific 
    hardware libraries (RPi.GPIO, spidev, gpiozero) to allow the application 
    to run on a non-Pi machine (like Windows or macOS) for development purposes.

    Returns:
        bool: True if the application is running in development mode, False otherwise.
    """
    parser = argparse.ArgumentParser(
        description='Run the main application with an optional development mode.'
    )
    parser.add_argument(
        '--dev',
        action='store_true',
        help='Run in development mode with mocked hardware libraries.'
    )
    # Use parse_known_args() to prevent conflicts with other libraries' arguments (e.g., Flask)
    args, _ = parser.parse_known_args()

    is_dev_mode = args.dev

    if is_dev_mode:
        print('--- RUNNING IN DEVELOPMENT MODE ---')
        try:
            # 1. Mock RPi.GPIO library using fake-rpi
            print('Mocking RPi.GPIO library...')
            from fake_rpi import RPi
            sys.modules['RPi'] = RPi
            sys.modules['RPi.GPIO'] = RPi.GPIO

            # 2. Mock spidev using our own custom mock file
            print('Using custom spidev_mock.py...')
            import spidev_mock
            sys.modules['spidev'] = spidev_mock

            # 3. Configure gpiozero to use its mock pin factory
            print('Configuring gpiozero to use a mock pin factory...')
            os.environ['GPIOZERO_PIN_FACTORY'] = 'mock'

        except ImportError as e:
            print(f'\nERROR: A required mocking library is not installed: {e}')
            print('Please ensure fake-rpi is installed (`pip install -r requirements.txt`).\n')
            sys.exit(1)
            
    return is_dev_mode
