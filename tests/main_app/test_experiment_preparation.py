from main_app.ui.experiment_preparation import build_preparation_url


def test_build_preparation_url_defaults_to_local_web_server(monkeypatch):
    monkeypatch.delenv("PYCONLYSE_WEB_URL", raising=False)

    assert build_preparation_url("v0") == (
        "http://127.0.0.1:5000/experiment-preparation?experiment=V0&autostart=1"
    )


def test_build_preparation_url_supports_vd2_and_configured_server(monkeypatch):
    monkeypatch.setenv("PYCONLYSE_WEB_URL", "http://pyconlyse.local:3000/")

    assert build_preparation_url("VD2", autostart=False) == (
        "http://pyconlyse.local:3000/experiment-preparation?experiment=VD2"
    )
