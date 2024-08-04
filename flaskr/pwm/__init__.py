import os
from flask import Flask
from . import db, pwm


def create_app(test_config=None):
    # create and configure the app
    app = Flask(__name__)
    app.config.from_mapping(
        SECRET_KEY='dev',
        DB_HOST='localhost',
        DB_USER='root',
        DB_PASSWORD='mysqlpwm',
        DB_DATABASE='pwm'
    )

    db.init_app(app)
    app.register_blueprint(pwm.bp)

    if test_config is None:
        # load the instance config, if it exists, when not testing
        app.config.from_pyfile('config.py', silent=True)
    else:
        # load the test config if passed in
        app.config.from_mapping(test_config)

    # ensure the instance folder exists
    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass

    return app

app = create_app(None)

