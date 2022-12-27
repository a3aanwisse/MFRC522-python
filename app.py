from flask import Flask, render_template
from flask_httpauth import HTTPBasicAuth
from werkzeug.security import generate_password_hash, check_password_hash
import threading
import controller

app = Flask(__name__)
auth = HTTPBasicAuth()
users = {
    "admin": generate_password_hash("Secret")
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


@app.route('/cards')
@auth.login_required
def show_card_ids():
    return render_template('cards.html', data=controller.get_allowed_card_ids())


@app.route('/cards/<card_id>', methods=['PUT'])
@auth.login_required
def add_new_card_id(card_id):
    controller.add_allowed_card_id(card_id)
    return show_card_ids()


@app.route("/test")
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
        appThread = threading.Thread(target=lambda: app.run(host='0.0.0.0', port=5000, debug=True, use_reloader=False))
        appThread.start()
        controller.setup()
        controller.start_listening()
    except KeyboardInterrupt:
        app.logger.info('Program terminated manually!')
        raise SystemExit

