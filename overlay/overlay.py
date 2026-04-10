"""
SmartHub Overlay — Time Tracker
Always-on-top, cross-platform (Windows / Linux / macOS)
Requires: pip install PyQt6 httpx
"""

import sys
import httpx
from datetime import datetime
from PyQt6.QtWidgets import (
    QApplication, QWidget, QHBoxLayout, QVBoxLayout,
    QLabel, QPushButton, QComboBox, QLineEdit,
    QTextEdit, QFrame
)
from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal, QSettings
from PyQt6.QtGui import QFont

# ── Config ────────────────────────────────────────────────────────────────────
API_BASE       = "http://10.0.2.202:8080/api/v1"
POLL_INTERVAL  = 5000   # ms
WIDTH          = 420
HEIGHT_IDLE    = 110
HEIGHT_REPORT  = 300

# ── Palette Smartclick ────────────────────────────────────────────────────────
BG      = "#080b10"
PANEL   = "#0d1220"
BORDER  = "#1a2540"
BLUE    = "#1565ff"
LBLUE   = "#4d8aff"
RED     = "#ff4d6d"
TXT     = "#e8edf8"
MUTED   = "#4a5a7a"

STYLE = f"""
QWidget {{
    background-color: {BG};
    color: {TXT};
    font-family: 'Consolas', 'Courier New', monospace;
    font-size: 12px;
}}
QComboBox {{
    background-color: {PANEL};
    border: 1px solid {BORDER};
    border-radius: 4px;
    padding: 4px 8px;
    color: {TXT};
    min-height: 26px;
}}
QComboBox::drop-down {{ border: none; width: 20px; }}
QComboBox QAbstractItemView {{
    background-color: {PANEL};
    border: 1px solid {BORDER};
    color: {TXT};
    selection-background-color: {BLUE}44;
}}
QLineEdit {{
    background-color: {PANEL};
    border: 1px solid {BORDER};
    border-radius: 4px;
    padding: 4px 8px;
    color: {TXT};
    min-height: 26px;
}}
QLineEdit:focus {{ border: 1px solid {BLUE}99; }}
QTextEdit {{
    background-color: {PANEL};
    border: 1px solid {BORDER};
    border-radius: 4px;
    padding: 4px 8px;
    color: {TXT};
}}
QTextEdit:focus {{ border: 1px solid {BLUE}99; }}
QPushButton {{
    border-radius: 4px;
    font-weight: bold;
    font-size: 12px;
    padding: 4px 10px;
    min-height: 26px;
    border: none;
}}
QPushButton#btn_start {{
    background-color: {BLUE};
    color: #fff;
    min-width: 38px;
    font-size: 14px;
}}
QPushButton#btn_start:hover  {{ background-color: {LBLUE}; }}
QPushButton#btn_start:disabled {{ background-color: {BORDER}; color: {MUTED}; }}
QPushButton#btn_stop  {{ background-color: {RED}; color: #fff; min-width: 80px; }}
QPushButton#btn_stop:hover  {{ background-color: #ff6680; }}
QPushButton#btn_confirm {{ background-color: {BLUE}; color: #fff; }}
QPushButton#btn_confirm:hover {{ background-color: {LBLUE}; }}
QPushButton#btn_cancel  {{ background-color: transparent; color: {MUTED}; border: 1px solid {BORDER}; }}
QPushButton#btn_cancel:hover  {{ color: {TXT}; }}
QPushButton#btn_wm {{
    background-color: transparent;
    color: {MUTED};
    border: none;
    font-size: 15px;
    padding: 0 6px;
    min-height: 22px;
    min-width: 22px;
}}
QPushButton#btn_wm:hover {{ color: {TXT}; }}
QPushButton#btn_wm_close:hover {{ color: {RED}; }}
QFrame#topbar {{ background-color: {PANEL}; border-bottom: 1px solid {BORDER}; }}
"""


# ── API Worker ────────────────────────────────────────────────────────────────
class ApiWorker(QThread):
    result = pyqtSignal(object)
    error  = pyqtSignal(str)

    def __init__(self, method, endpoint, payload=None):
        super().__init__()
        self.method, self.endpoint, self.payload = method, endpoint, payload

    def run(self):
        try:
            url = f"{API_BASE}{self.endpoint}"
            with httpx.Client(timeout=5) as c:
                r = c.get(url) if self.method == "GET" else c.post(url, json=self.payload)
                r.raise_for_status()
                self.result.emit(r.json())
        except Exception as e:
            self.error.emit(str(e))


# ── Overlay ───────────────────────────────────────────────────────────────────
class SmartHubOverlay(QWidget):

    def __init__(self):
        super().__init__()
        self.setWindowTitle("SmartHub")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setStyleSheet(STYLE)
        self.setFixedWidth(WIDTH)

        self._drag_pos     = None
        self._session      = None
        self._elapsed      = 0
        self._workers      = []
        self._report_mode  = False

        self._build_ui()
        self._restore_pos()

        # timers
        self._tick = QTimer(self); self._tick.timeout.connect(self._on_tick); self._tick.start(1000)
        self._poll = QTimer(self); self._poll.timeout.connect(self._do_poll); self._poll.start(POLL_INTERVAL)

        self._load_clients()
        self._load_active()
        self._load_today()

    # ── Build UI ──────────────────────────────────────────────────────────────
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # — topbar —
        topbar = QFrame(); topbar.setObjectName("topbar"); topbar.setFixedHeight(30)
        tb = QHBoxLayout(topbar); tb.setContentsMargins(10, 0, 4, 0); tb.setSpacing(2)

        lbl = QLabel("SMARTHUB"); lbl.setStyleSheet(f"color:{BLUE};font-weight:bold;font-size:11px;letter-spacing:2px;")
        tb.addWidget(lbl)

        self.dot = QLabel("●"); self.dot.setStyleSheet(f"color:{RED};font-size:8px;"); tb.addWidget(self.dot)
        tb.addStretch()

        self.lbl_today = QLabel("0h00 | 0.00€"); self.lbl_today.setStyleSheet(f"color:{MUTED};font-size:11px;")
        tb.addWidget(self.lbl_today)

        for txt, obj, extra in [("−","btn_wm",""), ("×","btn_wm_close","")]:
            b = QPushButton(txt); b.setObjectName("btn_wm")
            if obj == "btn_wm_close":
                b.setStyleSheet(f"QPushButton{{background:transparent;color:{MUTED};border:none;font-size:15px;padding:0 6px;min-height:22px;min-width:22px;}} QPushButton:hover{{color:{RED};}}")
                b.clicked.connect(self._close)
            else:
                b.setStyleSheet(f"QPushButton{{background:transparent;color:{MUTED};border:none;font-size:15px;padding:0 6px;min-height:22px;min-width:22px;}} QPushButton:hover{{color:{TXT};}}")
                b.clicked.connect(self.showMinimized)
            tb.addWidget(b)

        root.addWidget(topbar)

        # — body —
        body = QWidget(); body.setStyleSheet(f"background:{BG};")
        self._body_layout = QVBoxLayout(body)
        self._body_layout.setContentsMargins(10, 8, 10, 10)
        self._body_layout.setSpacing(6)

        # idle row
        self._idle = QWidget()
        row = QHBoxLayout(self._idle); row.setContentsMargins(0,0,0,0); row.setSpacing(6)

        self.combo = QComboBox()
        self.combo.setPlaceholderText("Client...")
        self.combo.setSizePolicy(self.combo.sizePolicy().horizontalPolicy(), self.combo.sizePolicy().verticalPolicy())
        row.addWidget(self.combo, 3)

        self.inp_act = QLineEdit(); self.inp_act.setPlaceholderText("Activité...")
        self.inp_act.returnPressed.connect(self._start)
        row.addWidget(self.inp_act, 4)

        self.btn_start = QPushButton("▶"); self.btn_start.setObjectName("btn_start")
        self.btn_start.setFixedSize(38, 30); self.btn_start.clicked.connect(self._start)
        row.addWidget(self.btn_start)

        self._body_layout.addWidget(self._idle)

        # active view
        self._active = QWidget(); self._active.hide()
        ar = QHBoxLayout(self._active); ar.setContentsMargins(0,0,0,0); ar.setSpacing(8)

        col = QVBoxLayout(); col.setSpacing(2)
        self.lbl_timer = QLabel("00:00:00")
        self.lbl_timer.setStyleSheet(f"color:{LBLUE};font-size:20px;font-weight:bold;")
        col.addWidget(self.lbl_timer)
        self.lbl_info = QLabel("")
        self.lbl_info.setStyleSheet(f"color:{MUTED};font-size:11px;")
        col.addWidget(self.lbl_info)
        ar.addLayout(col, 1)

        self.btn_stop = QPushButton("■ Stop"); self.btn_stop.setObjectName("btn_stop")
        self.btn_stop.setFixedHeight(40); self.btn_stop.clicked.connect(self._show_report)
        ar.addWidget(self.btn_stop)
        self._body_layout.addWidget(self._active)

        # report view
        self._report = QWidget(); self._report.hide()
        rl = QVBoxLayout(self._report); rl.setContentsMargins(0,0,0,0); rl.setSpacing(6)

        self.inp_done = QTextEdit(); self.inp_done.setPlaceholderText("Ce qui a été fait...")
        self.inp_done.setFixedHeight(65); rl.addWidget(self.inp_done)

        self.inp_wait = QTextEdit(); self.inp_wait.setPlaceholderText("En attente de... (optionnel)")
        self.inp_wait.setFixedHeight(50); rl.addWidget(self.inp_wait)

        btns = QHBoxLayout(); btns.setSpacing(6)
        bc = QPushButton("Annuler"); bc.setObjectName("btn_cancel"); bc.clicked.connect(self._show_active)
        bf = QPushButton("✓ Confirmer"); bf.setObjectName("btn_confirm"); bf.clicked.connect(self._confirm)
        btns.addWidget(bc); btns.addWidget(bf)
        rl.addLayout(btns)
        self._body_layout.addWidget(self._report)

        root.addWidget(body)
        self.setFixedHeight(HEIGHT_IDLE)

    # ── Drag ──────────────────────────────────────────────────────────────────
    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = e.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, e):
        if self._drag_pos and e.buttons() == Qt.MouseButton.LeftButton:
            self.move(e.globalPosition().toPoint() - self._drag_pos)

    def mouseReleaseEvent(self, e):
        self._drag_pos = None; self._save_pos()

    # ── Position ──────────────────────────────────────────────────────────────
    def _save_pos(self):
        QSettings("Smartclick","SmartHubOverlay").setValue("pos", self.pos())

    def _restore_pos(self):
        pos = QSettings("Smartclick","SmartHubOverlay").value("pos")
        if pos: self.move(pos)
        else:
            s = QApplication.primaryScreen().geometry()
            self.move(s.width() - WIDTH - 20, 20)

    def _close(self):
        self._save_pos(); QApplication.quit()

    # ── API ───────────────────────────────────────────────────────────────────
    def _api(self, method, endpoint, payload=None, on_ok=None, on_err=None):
        w = ApiWorker(method, endpoint, payload)
        if on_ok:  w.result.connect(on_ok)
        if on_err: w.error.connect(on_err)
        w.error.connect(lambda e: self.dot.setStyleSheet(f"color:{RED};font-size:8px;"))
        w.start(); self._workers.append(w)

    def _load_clients(self):
        self._api("GET", "/clients/summary", on_ok=self._on_clients)

    def _on_clients(self, data):
        self.dot.setStyleSheet(f"color:{LBLUE};font-size:8px;")
        self.combo.clear()
        for c in data:
            self.combo.addItem(c["name"], c["id"])

    def _load_active(self):
        self._api("GET", "/timetrack/active", on_ok=self._on_active)

    def _on_active(self, data):
        if data and data.get("id"):
            self._session = data
            started = datetime.fromisoformat(data["started_at"])
            self._elapsed = int((datetime.now() - started).total_seconds())
            self._show_active()
        else:
            self._session = None
            if not self._report_mode: self._show_idle()

    def _load_today(self):
        self._api("GET", "/timetrack/today", on_ok=self._on_today)

    def _on_today(self, data):
        h = data.get("total_hours", 0) or 0
        b = data.get("billable_amount", 0) or 0
        self.lbl_today.setText(f"{int(h)}h{int((h%1)*60):02d} | {b:.2f}€")

    # ── Start / Stop ──────────────────────────────────────────────────────────
    def _start(self):
        if self.combo.currentIndex() < 0: return
        act = self.inp_act.text().strip()
        if not act: self.inp_act.setPlaceholderText("⚠ requis"); return
        self.btn_start.setEnabled(False)
        self._api("POST", "/timetrack/start",
                  {"client_id": self.combo.currentData(), "activity": act, "billable": True},
                  on_ok=self._on_started,
                  on_err=lambda e: self.btn_start.setEnabled(True))

    def _on_started(self, data):
        self._session = data; self._elapsed = 0; self._show_active()

    def _confirm(self):
        if not self._session: return
        sid = self._session["id"]
        self._api("POST", f"/timetrack/{sid}/stop",
                  {"work_done": self.inp_done.toPlainText().strip(),
                   "waiting_for": self.inp_wait.toPlainText().strip() or None},
                  on_ok=self._on_stopped)

    def _on_stopped(self, _):
        self._session = None; self._elapsed = 0
        self.inp_done.clear(); self.inp_wait.clear(); self.inp_act.clear()
        self._show_idle(); self._load_today()

    # ── Views ─────────────────────────────────────────────────────────────────
    def _show_idle(self):
        self._report_mode = False
        self._idle.show(); self._active.hide(); self._report.hide()
        self.btn_start.setEnabled(True)
        self.setFixedHeight(HEIGHT_IDLE)

    def _show_active(self):
        self._report_mode = False
        cn = self._session.get("client_name","") if self._session else ""
        ac = self._session.get("activity","") if self._session else ""
        self.lbl_info.setText(f"◉  {cn}  —  {ac}")
        self._idle.hide(); self._active.show(); self._report.hide()
        self.setFixedHeight(HEIGHT_IDLE)

    def _show_report(self):
        self._report_mode = True
        self._idle.hide(); self._active.hide(); self._report.show()
        self.setFixedHeight(HEIGHT_REPORT)

    # ── Tick / Poll ───────────────────────────────────────────────────────────
    def _on_tick(self):
        if self._session and not self._report_mode:
            self._elapsed += 1
            h,m,s = self._elapsed//3600, (self._elapsed%3600)//60, self._elapsed%60
            self.lbl_timer.setText(f"{h:02d}:{m:02d}:{s:02d}")

    def _do_poll(self):
        self._load_active(); self._load_today()


# ── Main ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setApplicationName("SmartHub")
    app.setOrganizationName("Smartclick")
    w = SmartHubOverlay()
    w.show()
    sys.exit(app.exec())
