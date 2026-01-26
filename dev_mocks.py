import os
import sys
import argparse

def setup_development_mode():
    """
    Parses command-line arguments for development mode and config file path.

    If '--dev' is present, it mocks hardware libraries.
    '--config' specifies the path to the config.ini file.

    Returns:
        (bool, str): A tuple containing the development mode status (True/False)
                     and the path to the configuration file.
    """
    parser = argparse.ArgumentParser(
        description='Run the main application with optional development mode and config path.'
    )
    parser.add_argument(
        '--dev',
        action='store_true',
        help='Run in development mode with mocked hardware libraries.'
    )
    parser.add_argument(
        '--config',
        type=str,
        default='config.ini',
        help='Path to the configuration file (default: config.ini).'
    )
    
    args, _ = parser.parse_known_args()

    is_dev_mode = args.dev
    config_path = args.config

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
            print('Please ensure fake-rpi is installed (`pip install -r requirements-dev.txt`).\n')
            sys.exit(1)
            
    return is_dev_mode, config_path
