"""
SmartHub Qt — Client API
Thread-safe, basé httpx. Authentification X-API-Key.
"""
import httpx
from PyQt6.QtCore import QThread, pyqtSignal
from .config import get_api_key, get_api_base


class ApiWorker(QThread):
    result = pyqtSignal(object)
    error  = pyqtSignal(str)

    def __init__(self, method, endpoint, payload=None, params=None):
        super().__init__()
        self.method   = method
        self.endpoint = endpoint
        self.payload  = payload
        self.params   = params

    def run(self):
        api_base = get_api_base()
        api_key  = get_api_key()

        headers = {"X-API-Key": api_key} if api_key else {}

        try:
            url = f"{api_base}{self.endpoint}"
            with httpx.Client(timeout=10, headers=headers) as c:
                if self.method == "GET":
                    r = c.get(url, params=self.params)
                elif self.method == "POST":
                    r = c.post(url, json=self.payload)
                elif self.method == "PUT":
                    r = c.put(url, json=self.payload)
                elif self.method == "PATCH":
                    r = c.patch(url, json=self.payload)
                elif self.method == "DELETE":
                    r = c.delete(url)
                else:
                    self.error.emit(f"Méthode HTTP inconnue : {self.method}")
                    return

                if r.status_code == 401:
                    self.error.emit("❌ Clé API invalide ou manquante. Vérifiez Paramètres → Clé API.")
                    return
                if r.status_code == 403:
                    self.error.emit("⛔ Accès refusé (droits insuffisants).")
                    return

                r.raise_for_status()
                try:
                    self.result.emit(r.json())
                except Exception:
                    self.result.emit({})

        except httpx.ConnectError:
            self.error.emit(f"❌ Impossible de joindre le serveur ({api_base}). Vérifiez la connexion.")
        except httpx.TimeoutException:
            self.error.emit("⏱ Timeout — le serveur met trop de temps à répondre.")
        except httpx.HTTPStatusError as e:
            self.error.emit(f"HTTP {e.response.status_code}: {e.response.text[:300]}")
        except Exception as e:
            self.error.emit(str(e))


def api(method, endpoint, payload=None, params=None, on_ok=None, on_err=None):
    """Helper : crée, connecte et démarre un ApiWorker."""
    w = ApiWorker(method, endpoint, payload, params)
    if on_ok:  w.result.connect(on_ok)
    if on_err: w.error.connect(on_err)
    w.start()
    return w  # garder une référence !
