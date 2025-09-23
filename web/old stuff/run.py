from web.backend.pyconlyse_control import create_app
from web.backend.pyconlyse_control.routes import routes  # Import Blueprint


if __name__ == '__main__':
    app = create_app()
    app.debug = True
    app.register_blueprint(routes, url_prefix="/")
    #app.run(host='129.175.100.209', port=5000, debug=True)
    app.run(host='0.0.0.0', port=5000, debug=True)


