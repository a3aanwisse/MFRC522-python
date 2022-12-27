from flask import Flask, render_template
import threading
import controller

app = Flask(__name__)


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/cards')
def show_card_ids():
    return render_template('cards.html', data=controller.get_allowed_card_ids())


@app.route('/cards/<card_id>', methods=['PUT'])
def add_new_card_id(card_id):
    controller.add_allowed_card_id(card_id)
    return show_card_ids()


@app.route("/test")
def test():
    return render_template('test.html')


@app.route('/relay/toggle', methods=['PUT'])
def toggle_relay():
    controller.toggle_relay()
    return 'ok', 204


@app.route('/reed/closed-door', methods=['PUT'])
def read_reed_closed_door():
    return controller.read_reed_closed_door()


@app.route('/reed/open-door', methods=['PUT'])
def read_reed_open_door():
    return controller.read_reed_open_door()


if __name__ == '__main__':
    try:
        threading.Thread(target=lambda: app.run(host='0.0.0.0', port=5000, debug=True, use_reloader=False)).start()
        controller.setup()
        controller.start_listening()
    except KeyboardInterrupt:
        app.logger.info('Program terminated manually!')
        raise SystemExit

