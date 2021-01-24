from flask import Flask, render_template
import signal
import controller

app = Flask(__name__)

# Hook the SIGINT
signal.signal(signal.SIGINT, controller.end_read)
controller.setup()


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/status')
def stats():
    return render_template('status.html')


@app.route('/hello/<name>')
def hello(name):
    return render_template('name.html', name=name)


@app.route('/cards')
def showCardIds():
    with open('valid_card_ids.txt', 'r') as file:
        contents = file.readlines()

    allowed = [[8, 155, 225, 64, 50], [7, 155, 107, 64, 183], [54, 175, 183, 66, 108]]
    with open('valid_card_ids2.txt', 'w') as file:
        for uid in allowed:
            file.write(str(uid))
    return render_template('cards.html', data=contents)


@app.route('/cards/<id>')
def addNewCardId(id):
    with open('valid_card_ids.txt', 'a') as file:
        file.write(id + '\n')
    return render_template('newId.html', id=id)


@app.route("/test")
def led():
    return render_template('test.html');


@app.route("/led/<state>", methods=['PUT'])
def switchLed(state):
    if state == 'on':
        controller.switch_led_on()
    elif state == 'off':
        controller.switch_led_off()
    else:
        return 'bad request!', 400
    return 'ok', 204


@app.route("/relay/toggle>", methods=['PUT'])
def toggleRelay():
    controller.toggle_relay()
    return 'ok', 204


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
