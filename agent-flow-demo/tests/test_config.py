"""Una variable presente pero vacia en el .env tenia que caer al default.
Sin esto, `DEMO_API_URL=` (una linea que quedo a medio llenar) dejaba la URL
en cadena vacia y el flujo moria con un MissingSchema de requests."""
import importlib

from agent_flow import config


def test_una_variable_vacia_cae_al_default(monkeypatch):
    monkeypatch.setenv("VARIABLE_DE_PRUEBA", "")
    assert config._env("VARIABLE_DE_PRUEBA", "default") == "default"


def test_una_variable_con_valor_manda_sobre_el_default(monkeypatch):
    monkeypatch.setenv("VARIABLE_DE_PRUEBA", "http://x")
    assert config._env("VARIABLE_DE_PRUEBA", "default") == "http://x"


def test_demo_api_url_vacia_cae_al_despliegue(monkeypatch):
    monkeypatch.setenv("DEMO_API_URL", "")
    try:
        recargado = importlib.reload(config)
        assert recargado.DEMO_API_URL == "https://roxygt.lat/demo-api"
    finally:
        monkeypatch.undo()
        importlib.reload(config)
