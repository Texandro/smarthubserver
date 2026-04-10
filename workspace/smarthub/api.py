"""
SmartHub — Client API
Thread-safe, basé httpx
"""
import httpx
from PyQt6.QtCore import QThread, pyqtSignal
from .theme import API_BASE


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
        try:
            url = f"{API_BASE}{self.endpoint}"
            with httpx.Client(timeout=8) as c:
                if self.method == "GET":
                    r = c.get(url, params=self.params)
                elif self.method == "POST":
                    r = c.post(url, json=self.payload)
                elif self.method == "PUT":
                    r = c.put(url, json=self.payload)
                elif self.method == "DELETE":
                    r = c.delete(url)
                r.raise_for_status()
                try:
                    self.result.emit(r.json())
                except Exception:
                    self.result.emit({})
        except httpx.HTTPStatusError as e:
            self.error.emit(f"HTTP {e.response.status_code}: {e.response.text[:200]}")
        except Exception as e:
            self.error.emit(str(e))


def api(method, endpoint, payload=None, params=None, on_ok=None, on_err=None):
    """Helper : crée, connecte et démarre un ApiWorker."""
    w = ApiWorker(method, endpoint, payload, params)
    if on_ok:  w.result.connect(on_ok)
    if on_err: w.error.connect(on_err)
    w.start()
    return w  # garder une référence !
