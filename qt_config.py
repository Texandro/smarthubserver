"""
SmartHub Qt — Configuration persistante
Clé API et URL serveur stockées dans QSettings (registre Windows / fichier Linux).
"""
from PyQt6.QtCore import QSettings

APP_NAME = "SmartHub"
ORG_NAME = "Smartclick"

# URL par défaut — IP du NUC
DEFAULT_API_BASE = "http://10.0.2.202:8080/api/v1"


def _settings() -> QSettings:
    return QSettings(ORG_NAME, APP_NAME)


def get_api_base() -> str:
    s = _settings()
    return s.value("api/base_url", DEFAULT_API_BASE)


def set_api_base(url: str):
    s = _settings()
    s.setValue("api/base_url", url.rstrip("/"))


def get_api_key() -> str:
    s = _settings()
    return s.value("api/key", "")


def set_api_key(key: str):
    s = _settings()
    s.setValue("api/key", key.strip())


def is_configured() -> bool:
    """True si une clé API est configurée."""
    return bool(get_api_key())
