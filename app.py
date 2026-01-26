import dev_mocks
import sys
import os

# Set up mocks for development if '--dev' flag is present.
IS_DEVELOPMENT = dev_mocks.setup_development_mode()

from flask import Flask, render_template, request, redirect, url_for, flash
from flask_httpauth import HTTPBasicAuth
from werkzeug.security import generate_password_hash, check_password_hash
import threading
import controller
import logging

app = Flask(__name__)
# A secret key is required for flashing messages
app.secret_key = os.urandom(24)
auth = HTTPBasicAuth()
users = {
    'admin': generate_password_hash('Secret')
}

# Suppress Werkzeug development server warning
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
    app.logger.warning('Received update request. Exiting with update code...')
    # We exit the entire process. The launcher script will handle the rest.
    sys.exit(EXIT_CODE_FOR_UPDATE)


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

        controller.setup()

        if not IS_DEVELOPMENT:
            app.logger.info('Starting NFC listener on the Raspberry Pi.')
            app.logger.info('To install production dependencies, run: pip install -r requirements.txt')
            controller.start_listening()
        else:
            app.logger.info('Running in development mode. NFC listener is disabled.')
            app_thread.join()

    except KeyboardInterrupt:
        app.logger.info('Program terminated manually!')
        sys.exit(0) # Clean exit
    except Exception as e:
        app.logger.error(f'An unexpected error occurred: {e}')
        sys.exit(1) # Unclean exit
