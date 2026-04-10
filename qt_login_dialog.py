"""
SmartHub Qt — Dialog de connexion / configuration API key
Affiché au premier démarrage ou si la clé est invalide.
"""
import httpx
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFrame, QFormLayout, QMessageBox
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from .config import get_api_base, set_api_base, get_api_key, set_api_key
from .theme  import BG, BG2, BLUE, LBLUE, TXT, TXT2, BORDER, GREEN, RED


class LoginDialog(QDialog):
    """
    Dialog de connexion affiché si aucune clé API n'est configurée.
    L'utilisateur colle sa clé API (générée par deploy.sh sur le serveur).
    """

    def __init__(self, parent=None, message: str = ""):
        super().__init__(parent)
        self.setWindowTitle("SmartHub — Connexion")
        self.setFixedSize(480, 340)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.MSWindowsFixedSizeDialogHint)
        self.setStyleSheet(f"background:{BG};color:{TXT};")
        self._build_ui(message)

    def _build_ui(self, message: str):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        # Header bleu
        hdr = QWidget()
        hdr.setStyleSheet(f"background:{BLUE};")
        hl = QHBoxLayout(hdr); hl.setContentsMargins(24, 18, 24, 18)
        t = QLabel("🔐  SmartHub — Connexion")
        t.setStyleSheet("color:white;font-size:16px;font-weight:bold;")
        hl.addWidget(t)
        lay.addWidget(hdr)

        # Corps
        body = QFrame(); body.setStyleSheet(f"background:{BG2};")
        bl = QVBoxLayout(body); bl.setContentsMargins(28, 24, 28, 24); bl.setSpacing(14)

        if message:
            err = QLabel(message)
            err.setStyleSheet(f"color:{RED};font-size:11px;background:{BG};padding:8px;border-radius:4px;")
            err.setWordWrap(True)
            bl.addWidget(err)

        info = QLabel(
            "Collez votre clé API ci-dessous.\n"
            "La clé a été générée par le script deploy.sh sur le serveur."
        )
        info.setStyleSheet(f"color:{TXT2};font-size:11px;")
        info.setWordWrap(True)
        bl.addWidget(info)

        form = QFormLayout(); form.setSpacing(10)

        def lbl(t):
            l = QLabel(t); l.setStyleSheet(f"color:{TXT2};font-size:11px;")
            return l

        self.inp_url = QLineEdit(get_api_base())
        self.inp_url.setStyleSheet(
            f"background:{BG};color:{TXT};border:1px solid {BORDER};"
            f"border-radius:4px;padding:6px 10px;font-size:12px;"
        )
        self.inp_url.setPlaceholderText("http://10.0.2.202:8080/api/v1")
        form.addRow(lbl("URL serveur :"), self.inp_url)

        self.inp_key = QLineEdit(get_api_key())
        self.inp_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.inp_key.setStyleSheet(
            f"background:{BG};color:{TXT};border:1px solid {BORDER};"
            f"border-radius:4px;padding:6px 10px;font-size:12px;"
        )
        self.inp_key.setPlaceholderText("smh_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx")
        form.addRow(lbl("Clé API :"), self.inp_key)

        bl.addLayout(form)

        # Boutons
        btn_row = QHBoxLayout(); btn_row.setSpacing(8)
        btn_row.addStretch()

        self.btn_show = QPushButton("👁 Afficher")
        self.btn_show.setCheckable(True)
        self.btn_show.setStyleSheet(
            f"background:{BG};color:{TXT2};border:1px solid {BORDER};"
            f"border-radius:4px;padding:5px 12px;font-size:11px;"
        )
        self.btn_show.toggled.connect(self._toggle_visibility)
        btn_row.addWidget(self.btn_show)

        self.btn_test = QPushButton("🔗 Tester")
        self.btn_test.setStyleSheet(
            f"background:{BG};color:{LBLUE};border:1px solid {LBLUE};"
            f"border-radius:4px;padding:5px 14px;font-size:11px;"
        )
        self.btn_test.clicked.connect(self._test_connection)
        btn_row.addWidget(self.btn_test)

        self.btn_connect = QPushButton("✅  Se connecter")
        self.btn_connect.setStyleSheet(
            f"background:{BLUE};color:white;font-weight:bold;"
            f"border:none;border-radius:4px;padding:7px 20px;font-size:12px;"
        )
        self.btn_connect.clicked.connect(self._connect)
        btn_row.addWidget(self.btn_connect)

        bl.addLayout(btn_row)
        lay.addWidget(body, 1)

    def _toggle_visibility(self, checked):
        mode = QLineEdit.EchoMode.Normal if checked else QLineEdit.EchoMode.Password
        self.inp_key.setEchoMode(mode)

    def _test_connection(self):
        url  = self.inp_url.text().strip().rstrip("/")
        key  = self.inp_key.text().strip()
        try:
            r = httpx.get(
                f"{url}/auth/me",
                headers={"X-API-Key": key},
                timeout=5,
            )
            if r.status_code == 200:
                data = r.json()
                QMessageBox.information(
                    self, "Connexion OK",
                    f"✅ Connecté en tant que {data.get('name')} ({data.get('role')})"
                )
            elif r.status_code == 401:
                QMessageBox.warning(self, "Erreur", "❌ Clé API invalide.")
            else:
                QMessageBox.warning(self, "Erreur", f"HTTP {r.status_code}: {r.text[:200]}")
        except Exception as e:
            QMessageBox.critical(self, "Erreur connexion", f"❌ {e}")

    def _connect(self):
        url = self.inp_url.text().strip().rstrip("/")
        key = self.inp_key.text().strip()
        if not key:
            QMessageBox.warning(self, "Erreur", "La clé API est obligatoire.")
            return
        set_api_base(url)
        set_api_key(key)
        self.accept()


# Import nécessaire pour le QWidget dans le header
from PyQt6.QtWidgets import QWidget
