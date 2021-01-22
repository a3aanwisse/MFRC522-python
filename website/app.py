from flask import Flask, render_template
from gpiozero import LED

app = Flask(__name__)

LED_PIN = 18
led = LED(LED_PIN)


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
    return render_template('cards.html', data=contents)


@app.route('/cards/<id>')
def addNewCardId(id):
    with open('valid_card_ids.txt', 'a') as file:
        file.write(id + '\n')
    return render_template('newId.html', id=id)


@app.route("/light")
def light():
    return render_template('light.html');


@app.route("/light/<state>", methods=['PUT'])
def turnLightOn(state):
    if state == 'on':
        led.on()
    elif state == 'off':
        led.off()
    else:
        return 'bad request!', 400
    return 'ok', 204


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')
