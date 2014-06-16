import os

from flask import Flask
app = Flask(__name__)


@app.route("/")
def hello():
    return "Hello %s World!" % os.environ.get('BLUEGREEN', 'bland')
