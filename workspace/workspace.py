"""
SmartHub Workspace — Application principale
Cross-platform (Windows / Linux / macOS)
Requires: pip install PyQt6 httpx
"""
import sys
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QHBoxLayout,
    QVBoxLayout, QLabel, QPushButton, QFrame, QStackedWidget,
    QSizePolicy
)
from PyQt6.QtCore import Qt, QTimer, QSize, QSettings
from PyQt6.QtGui import QFont, QIcon, QColor

from smarthub.theme import *
from smarthub.api import api
from smarthub.views import (
    DashboardView, ClientsView, ContractsView,
    ProjectsView, TimetracKView, AtelierView
)


NAV_ITEMS = [
    ("dashboard",  "📊", "Dashboard"),
    ("clients",    "👥", "Clients"),
    ("contracts",  "📄", "Contrats"),
    ("projects",   "📋", "Projets"),
    ("atelier",    "🔧", "Atelier"),
    ("timetrack",  "⏱", "Timetrack"),
]


class NavButton(QPushButton):
    def __init__(self, icon, label, parent=None):
        super().__init__(f"  {icon}  {label}", parent)
        self.setObjectName("nav_btn")
        self.setCheckable(False)
        self.setFixedHeight(44)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._active = False

    def set_active(self, active: bool):
        self._active = active
        self.setObjectName("nav_btn_active" if active else "nav_btn")
        # Force style refresh
        self.style().unpolish(self)
        self.style().polish(self)


class SessionBanner(QFrame):
    """Bannière session active en haut du workspace."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("card_blue")
        self.setFixedHeight(36)
        self.hide()

        lay = QHBoxLayout(self)
        lay.setContentsMargins(16, 0, 16, 0)
        lay.setSpacing(12)

        self._dot = QLabel("●")
        self._dot.setStyleSheet(f"color:{GREEN};font-size:10px;")
        lay.addWidget(self._dot)

        self._lbl = QLabel("Aucune session")
        self._lbl.setStyleSheet(f"color:{TXT};font-size:12px;")
        lay.addWidget(self._lbl)

        self._timer_lbl = QLabel("00:00:00")
        self._timer_lbl.setStyleSheet(f"color:{LBLUE};font-size:12px;font-weight:bold;font-family:monospace;")
        lay.addWidget(self._timer_lbl)

        lay.addStretch()

        self._elapsed = 0
        self._tick = QTimer(); self._tick.timeout.connect(self._on_tick)

    def set_session(self, session):
        if session and session.get("id"):
            client = session.get("client_name","")
            activity = session.get("activity","")
            self._lbl.setText(f"◉  {client}  —  {activity}")
            from datetime import datetime
            started = datetime.fromisoformat(session["started_at"])
            self._elapsed = int((datetime.now() - started).total_seconds())
            self._tick.start(1000)
            self.show()
        else:
            self._tick.stop()
            self.hide()

    def _on_tick(self):
        self._elapsed += 1
        h, m, s = self._elapsed//3600, (self._elapsed%3600)//60, self._elapsed%60
        self._timer_lbl.setText(f"{h:02d}:{m:02d}:{s:02d}")


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SmartHub — Smartclick")
        self.setMinimumSize(1100, 680)
        self._workers = []
        self._nav_btns = {}
        self._current = None

        self._restore_geometry()
        self._build_ui()
        self._navigate("dashboard")

        # Poll session active
        self._poll = QTimer(self)
        self._poll.timeout.connect(self._check_session)
        self._poll.start(10_000)
        self._check_session()

    # ── UI ────────────────────────────────────────────────────────────────────
    def _build_ui(self):
        self.setStyleSheet(STYLE)
        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(0,0,0,0)
        root.setSpacing(0)

        # — Sidebar —
        sidebar = QWidget(); sidebar.setObjectName("sidebar"); sidebar.setFixedWidth(200)
        sb = QVBoxLayout(sidebar); sb.setContentsMargins(8,16,8,16); sb.setSpacing(2)

        # Logo
        logo_frame = QWidget()
        lf = QHBoxLayout(logo_frame); lf.setContentsMargins(12,0,12,12)
        logo = QLabel("SmartHub")
        logo.setStyleSheet(f"color:{BLUE};font-size:18px;font-weight:bold;letter-spacing:1px;")
        lf.addWidget(logo)
        sb.addWidget(logo_frame)

        # Nav items
        for key, icon, label in NAV_ITEMS:
            btn = NavButton(icon, label)
            btn.clicked.connect(lambda _, k=key: self._navigate(k))
            self._nav_btns[key] = btn
            sb.addWidget(btn)

        sb.addStretch()

        # Version
        ver = QLabel("v1.0")
        ver.setStyleSheet(f"color:{MUTED};font-size:11px;padding:4px 12px;")
        sb.addWidget(ver)

        root.addWidget(sidebar)

        # — Main area —
        right = QWidget(); right.setStyleSheet(f"background:{BG};")
        rl = QVBoxLayout(right); rl.setContentsMargins(0,0,0,0); rl.setSpacing(0)

        # Session banner
        self.banner = SessionBanner()
        rl.addWidget(self.banner)

        # Page stack
        self.stack = QStackedWidget()
        self._views = {
            "dashboard": DashboardView(),
            "clients":   ClientsView(),
            "contracts": ContractsView(),
            "projects":  ProjectsView(),
            "atelier":   AtelierView(),
            "timetrack": TimetracKView(),
        }
        for v in self._views.values():
            self.stack.addWidget(v)

        rl.addWidget(self.stack)
        root.addWidget(right)

    # ── Navigation ────────────────────────────────────────────────────────────
    def _navigate(self, key):
        if self._current == key:
            return
        self._current = key

        for k, btn in self._nav_btns.items():
            btn.set_active(k == key)

        view = self._views.get(key)
        if view:
            self.stack.setCurrentWidget(view)
            if hasattr(view, "refresh"):
                view.refresh()

    # ── Session active ─────────────────────────────────────────────────────────
    def _check_session(self):
        w = api("GET", "/timetrack/active", on_ok=self.banner.set_session)
        self._workers.append(w)

    # ── Geometry persistence ──────────────────────────────────────────────────
    def _restore_geometry(self):
        s = QSettings("Smartclick", "SmartHubWorkspace")
        geo = s.value("geometry")
        if geo: self.restoreGeometry(geo)
        else:
            screen = QApplication.primaryScreen().geometry()
            self.resize(1200, 760)
            self.move((screen.width()-1200)//2, (screen.height()-760)//2)

    def closeEvent(self, e):
        QSettings("Smartclick","SmartHubWorkspace").setValue("geometry", self.saveGeometry())
        super().closeEvent(e)


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setApplicationName("SmartHub")
    app.setOrganizationName("Smartclick")
    app.setStyle("Fusion")  # base propre cross-platform
    w = MainWindow()
    w.show()
    sys.exit(app.exec())
