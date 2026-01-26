import dev_mocks

# Set up mocks for development if '--dev' flag is present.
IS_DEVELOPMENT = dev_mocks.setup_development_mode()

from flask import Flask, render_template, request, redirect, url_for, flash
from flask_httpauth import HTTPBasicAuth
from werkzeug.security import generate_password_hash, check_password_hash
import threading
import controller
import os

app = Flask(__name__)
# A secret key is required for flashing messages
app.secret_key = os.urandom(24)
auth = HTTPBasicAuth()
users = {
    'admin': generate_password_hash('Secret')
}


@auth.verify_password
def verify_password(username, password):
    if username in users:
        return check_password_hash(users.get(username), password)
    return False


@app.route('/')
@auth.login_required
def index():
    return render_template('index.html', username=auth.username())


@app.route('/cards', methods=['GET', 'POST'])
@auth.login_required
def manage_cards():
    if request.method == 'POST':
        card_id = request.form.get('card_id')
        phone_number = request.form.get('phone_number')

        if not card_id or not phone_number:
            flash('Card ID and Phone Number are required.', 'error')
        else:
            # Use the new, more accurate function name
            success = controller.add_allowed_card(card_id, phone_number)
            if success:
                flash(f'Successfully added card {card_id}.', 'success')
            else:
                flash(
                    f"Failed to add card. The phone number '{phone_number}' is not a valid E.164 number (e.g., +31612345678).",
                    'error')

        return redirect(url_for('manage_cards'))

    # Use the new, more accurate function name
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
            app.logger.info('To install development dependencies, run: pip install -r requirements-dev.txt')
            app_thread.join()

    except KeyboardInterrupt:
        app.logger.info('Program terminated manually!')
        raise SystemExit
