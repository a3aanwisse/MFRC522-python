import dev_mocks
import sys
import os
import configparser
import logging

# --- Basic Logging Configuration ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Set up mocks and get config path. This must be done before other imports.
IS_DEVELOPMENT, CONFIG_FILE_PATH = dev_mocks.setup_development_mode()

from flask import Flask, render_template, request, redirect, url_for, flash
from flask_httpauth import HTTPBasicAuth
from werkzeug.security import generate_password_hash, check_password_hash
import threading
import controller

app = Flask(__name__)
# A secret key is required for flashing messages
app.secret_key = os.urandom(24)
auth = HTTPBasicAuth()

# --- Load Configuration from config file ---
config = configparser.ConfigParser()
users = {}
try:
    if not os.path.exists(CONFIG_FILE_PATH):
        raise FileNotFoundError(f"Config file not found at '{CONFIG_FILE_PATH}'")
        
    config.read(CONFIG_FILE_PATH)
    username = config.get('credentials', 'username')
    password = config.get('credentials', 'password')
    users = {
        username: generate_password_hash(password)
    }
    logging.info(f"Successfully loaded credentials from {CONFIG_FILE_PATH}")
except (configparser.NoSectionError, configparser.NoOptionError, FileNotFoundError) as e:
    logging.error(f"Could not load configuration from '{CONFIG_FILE_PATH}': {e}")
    logging.error("Please provide a valid config file using the --config argument.")
    sys.exit(1)


# Suppress Werkzeug's default INFO and WARNING logs
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

# Special exit code to signal the launcher script to update and restart
EXIT_CODE_FOR_UPDATE = 10


@auth.verify_password
def verify_password(username, password):
    if username in users:
        return check_password_hash(users.get(username), password)
    return False


@app.route('/')
@auth.login_required
def index():
    return render_template('index.html', username=auth.username())


@app.route('/update', methods=['POST'])
@auth.login_required
def trigger_update():
    """
    Shuts down the application with a special exit code.
    The launcher.sh script will detect this code, pull from git, and restart.
    """
    logging.warning('Received update request. Exiting with update code...')
    os._exit(EXIT_CODE_FOR_UPDATE)


@app.route('/cards', methods=['GET', 'POST'])
@auth.login_required
def manage_cards():
    if request.method == 'POST':
        card_id = request.form.get('card_id')
        phone_number = request.form.get('phone_number')

        if not card_id or not phone_number:
            flash('Card ID and Phone Number are required.', 'error')
        else:
            success = controller.add_allowed_card(card_id, phone_number)
            if success:
                flash(f'Successfully added card {card_id}.', 'success')
            else:
                flash(
                    f"Failed to add card. The phone number '{phone_number}' is not a valid E.164 number (e.g., +31612345678).",
                    'error')

        return redirect(url_for('manage_cards'))

    cards = controller.get_allowed_cards()
    return render_template('cards.html', cards=cards)


@app.route('/test')
@auth.login_required
def test():
    return render_template('test.html')


@app.route('/relay/toggle', methods=['PUT'])
@auth.login_required
def toggle_relay():
    controller.toggle_relay()
    return 'ok', 204


@app.route('/reed/closed-door', methods=['PUT'])
@auth.login_required
def read_reed_closed_door():
    return controller.read_reed_closed_door()


@app.route('/reed/open-door', methods=['PUT'])
@auth.login_required
def read_reed_open_door():
    return controller.read_reed_open_door()


if __name__ == '__main__':
    try:
        app_thread = threading.Thread(
            target=lambda: app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False))
        app_thread.daemon = True
        app_thread.start()

        # Pass the loaded config object to the controller
        controller.setup(config)

        if not IS_DEVELOPMENT:
            logging.info('Starting NFC listener on the Raspberry Pi.')
            logging.info('To install production dependencies, run: pip install -r requirements.txt')
            controller.start_listening()
        else:
            logging.info('Running in development mode. NFC listener is disabled.')
            logging.info('To install development dependencies, run: pip install -r requirements-dev.txt')
            app_thread.join()

    except KeyboardInterrupt:
        logging.info('Program terminated manually!')
        sys.exit(0) # Clean exit
    except Exception as e:
        logging.error(f'An unexpected error occurred: {e}', exc_info=True)
        sys.exit(1) # Unclean exit
