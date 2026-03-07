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
    return render_template('index.html', username=auth.username(), ntfy_topic=controller.NTFY_TOPIC)


@app.route('/update', methods=['POST'])
@auth.login_required
def trigger_update():
    logging.warning('Received update request. Exiting with update code...')
    os._exit(EXIT_CODE_FOR_UPDATE)


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

        if not card_id:
            flash('Card ID is required.', 'error')
        else:
            # The controller now handles adding the card ID to the list
            if controller.add_allowed_card(card_id):
                flash(f'Successfully added card {card_id}.', 'success')
            else:
                flash(f'Failed to add card {card_id}. Check logs.', 'error')
        
        return redirect(url_for('manage_cards'))

    # On GET request, display the cards
    cards = controller.get_allowed_cards()
    return render_template('cards.html', cards=cards)


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


if __name__ == '__main__':
    try:
        # Pass the loaded config object to the controller
        controller.setup(config)

        if not IS_DEVELOPMENT:
            logging.info('Starting production server with Waitress...')
            from waitress import serve
            
            # Run waitress in a separate thread so we can also run the NFC listener
            server_thread = threading.Thread(
                target=lambda: serve(app, host='0.0.0.0', port=5000, threads=4)
            )
            server_thread.daemon = True
            server_thread.start()

            logging.info('Starting NFC listener on the Raspberry Pi.')
            logging.info('To install production dependencies, run: pip install -r requirements.txt')
        else:
            logging.info('Running in development mode with Flask dev server.')
            logging.info('To install development dependencies, run: pip install -r requirements-dev.txt')
            
            app_thread = threading.Thread(
                target=lambda: app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False))
            app_thread.daemon = True
            app_thread.start()

            app_thread.join()

        controller.start_listening()

    except KeyboardInterrupt:
        logging.info('Program terminated manually!')
        sys.exit(0)
    except Exception as e:
        logging.error(f'An unexpected error occurred: {e}', exc_info=True)
        sys.exit(1)
