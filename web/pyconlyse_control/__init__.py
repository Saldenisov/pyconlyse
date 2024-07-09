from flask import Flask


def create_app():
    app = Flask(__name__, static_folder='../static', template_folder='templates')
    app.config.from_object('config.Config')

    with app.app_context():
        from . import routes
        return app

