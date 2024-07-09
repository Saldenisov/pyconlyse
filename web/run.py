from pyconlyse_control import create_app


if __name__ == '__main__':
    app = create_app()
    app.run(host='129.175.100.128', port=5000, debug=True)


