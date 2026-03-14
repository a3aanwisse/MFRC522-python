import dev_mocks
import sys
import os
import configparser
import json
import logging
import threading
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, Response
from flask_httpauth import HTTPBasicAuth
from werkzeug.security import generate_password_hash, check_password_hash
import controller

# --- Basic Logging Configuration ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Set up mocks and get config path.
IS_DEVELOPMENT, CONFIG_FILE_PATH = dev_mocks.setup_development_mode()

app = Flask(__name__)
app.secret_key = os.urandom(24)
auth = HTTPBasicAuth()

# --- Load Configuration from config file ---
config = configparser.ConfigParser(interpolation=None)
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

# Suppress Werkzeug's default logs
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

EXIT_CODE_FOR_UPDATE = 10

# Global event for graceful shutdown
shutdown_event = threading.Event()


@auth.verify_password
def verify_password(username, password):
    if username in users:
        return check_password_hash(users.get(username), password)
    return False


@app.context_processor
def inject_version():
    return dict(version=controller.VERSION)


@app.route('/')
@auth.login_required
def index():
    nfc_status = controller.get_nfc_status()
    return render_template('index.html', username=auth.username(), ntfy_topic=controller.NTFY_TOPIC, nfc_status=nfc_status)


@app.route('/update', methods=['POST'])
@auth.login_required
def trigger_update():
    logging.warning('Received update request. Initiating graceful shutdown for update...')
    controller.stop_nfc_reader() # Stop NFC reader gracefully
    controller.stop_listening() # Signal controller to stop other loops (like ntfy listener)
    shutdown_event.set() # Signal main thread to exit
    return jsonify({'message': 'Update initiated, application is shutting down.'}), 202 # Return immediately


@app.route('/config/reload', methods=['POST'])
@auth.login_required
def reload_config():
    try:
        logging.info("Reloading configuration...")
        config.read(CONFIG_FILE_PATH)
        
        # Update credentials
        try:
            new_username = config.get('credentials', 'username')
            new_password = config.get('credentials', 'password')
            global users
            users = { new_username: generate_password_hash(new_password) }
        except Exception as e:
            logging.warning(f"Failed to update credentials during reload (keeping old ones): {e}")

        if controller.load_config(config):
            flash('Configuratie succesvol herladen.', 'success')
        else:
            flash('Fout bij herladen configuratie. Check logs.', 'error')
            
    except Exception as e:
        logging.error(f"Error reloading config: {e}")
        flash(f'Error: {e}', 'error')
        
    return redirect(url_for('index'))


@app.route('/cards', methods=['GET', 'POST'])
@auth.login_required
def manage_cards():
    if request.method == 'POST':
        card_id = request.form.get('card_id')
        user_name = request.form.get('user_name', 'Onbekend') # Get user_name, default to 'Onbekend'

        if not card_id:
            flash('Card ID is required.', 'error')
        else:
            # The controller now handles adding the card ID and user name
            if controller.add_allowed_card(card_id, user_name):
                flash(f'Successfully added card {card_id} for user {user_name}.', 'success')
            else:
                flash(f'Failed to add card {card_id}. It might already exist or an error occurred.', 'error')
        
        return redirect(url_for('manage_cards'))

    # On GET request, display the cards
    # controller.get_allowed_cards() now returns a list of card IDs, not a dictionary
    # We need to pass the full allowed_cards dictionary to the template
    cards_with_users = controller.allowed_cards # Access the global dictionary directly
    return render_template('cards.html', cards=cards_with_users)


@app.route('/stats')
@auth.login_required
def stats():
    data = controller.get_stats()
    return render_template('stats.html', stats=data)


@app.route('/api/stats')
@auth.login_required
def api_stats():
    return jsonify(controller.get_stats())


@app.route('/stream/stats')
@auth.login_required
def stream_stats():
    def generate():
        # Register a new listener queue
        q = controller.register_stat_listener()
        try:
            # Send initial data immediately upon connection
            yield f"data: {json.dumps(controller.get_stats())}\n\n"
            while True:
                # Wait for new data (blocks until controller puts something in queue)
                data = q.get()
                yield f"data: {json.dumps(data)}\n\n"
        finally:
            # Clean up when client disconnects
            controller.remove_stat_listener(q)

    return Response(generate(), mimetype='text/event-stream')


@app.route('/stream/hardware')
@auth.login_required
def stream_hardware():
    def generate():
        q = controller.register_hardware_listener()
        try:
            # Send initial state immediately
            initial_state = {
                'relay': 'Verbonden',
                'reed_closed': controller.read_reed_closed_door(),
                'reed_open': controller.read_reed_open_door(),
                'timestamp': 'Nu'
            }
            yield f"data: {json.dumps(initial_state)}\n\n"
            
            while True:
                data = q.get()
                yield f"data: {json.dumps(data)}\n\n"
        finally:
            controller.remove_hardware_listener(q)

    return Response(generate(), mimetype='text/event-stream')


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


@app.route('/notify/test', methods=['POST'])
@auth.login_required
def test_notification():
    # Run in a separate thread to prevent blocking the request (fetching camera image takes time)
    threading.Thread(target=controller.send_ntfy_notification, args=(True,)).start()
    return 'ok', 204

@app.route('/nfc/status', methods=['GET'])
@auth.login_required
def nfc_status():
    return jsonify({'nfc_active': controller.get_nfc_status()})

@app.route('/nfc/start', methods=['POST'])
@auth.login_required
def nfc_start():
    if controller.start_nfc_reader():
        flash('NFC-lezer succesvol gestart.', 'success')
    else:
        flash('NFC-lezer is al actief of kon niet starten.', 'warning')
    return redirect(url_for('index'))

@app.route('/nfc/stop', methods=['POST'])
@auth.login_required
def nfc_stop():
    if controller.stop_nfc_reader():
        flash('NFC-lezer succesvol gestopt.', 'success')
    else:
        flash('NFC-lezer is niet actief of kon niet stoppen.', 'warning')
    return redirect(url_for('index'))


if __name__ == '__main__':
    try:
        controller.setup(config)
        controller.start_nfc_reader() # Start NFC reader by default

        flask_thread = None
        if not IS_DEVELOPMENT:
            logging.info('Starting production server with Waitress...')
            from waitress import serve
            flask_thread = threading.Thread(
                target=lambda: serve(app, host='0.0.0.0', port=5000, threads=6)
            )
        else:
            logging.info('Running in development mode with Flask dev server.')
            flask_thread = threading.Thread(
                target=lambda: app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)
            )
        
        flask_thread.daemon = True # Allow main program to exit even if this thread is still running
        flask_thread.start()

        # Main thread waits for a shutdown signal
        logging.info('Application running. Waiting for shutdown signal...')
        shutdown_event.wait() # This will block until shutdown_event.set() is called

        logging.info('Shutdown signal received. Performing graceful shutdown...')
        # Ensure controller threads are stopped (redundant if trigger_update called it, but safe)
        controller.stop_nfc_reader() # Ensure NFC reader is stopped
        controller.stop_listening() # Stop other listeners (like ntfy)

        logging.info(f'Exiting application with status {EXIT_CODE_FOR_UPDATE}.')
        sys.exit(EXIT_CODE_FOR_UPDATE)

    except KeyboardInterrupt:
        logging.info('Program terminated manually (KeyboardInterrupt)!')
        controller.stop_nfc_reader()
        controller.stop_listening()
        sys.exit(0)
    except Exception as e:
        logging.error(f'An unexpected error occurred: {e}', exc_info=True)
        controller.stop_nfc_reader()
        controller.stop_listening()
        sys.exit(1) # Error exit
