"""
SmartHub — Vue Projets / Kanban
"""
from datetime import date
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QPushButton, QScrollArea, QDialog, QFormLayout,
    QLineEdit, QComboBox, QTextEdit, QDialogButtonBox,
    QDateEdit, QDoubleSpinBox, QMessageBox, QSizePolicy
)
from PyQt6.QtCore import Qt, QDate, pyqtSignal
from PyQt6.QtGui import QColor
from ..theme import *
from ..api import api
from ..widgets import SectionTitle, StatusPill


COLUMNS = [
    ("en_cours",      "En cours",         BLUE),
    ("en_attente",    "En attente tiers",  AMBER),
    ("a_relancer",    "À relancer",        RED),
    ("a_facturer",    "À facturer",        GREEN),
    ("termine",       "Terminé",           MUTED),
]


class ProjectCard(QFrame):
    clicked = pyqtSignal(dict)

    def __init__(self, project, parent=None):
        super().__init__(parent)
        self._project = project
        self.setObjectName("card")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedWidth(220)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(6)

        # Titre
        title = QLabel(project.get("name",""))
        title.setStyleSheet(f"color:{TXT};font-weight:bold;font-size:13px;")
        title.setWordWrap(True)
        lay.addWidget(title)

        # Client
        client = QLabel(project.get("client_name",""))
        client.setStyleSheet(f"color:{TXT2};font-size:11px;")
        lay.addWidget(client)

        # Waiting for
        wf = project.get("waiting_for")
        if wf:
            wf_lbl = QLabel(f"⏳ {wf}")
            wf_lbl.setStyleSheet(f"color:{AMBER};font-size:11px;")
            wf_lbl.setWordWrap(True)
            lay.addWidget(wf_lbl)

        # Jours en attente
        days = project.get("days_waiting", 0) or 0
        if days > 0:
            col = RED if days > 7 else AMBER
            d_lbl = QLabel(f"{'⚠ ' if days > 7 else ''}{days}j en attente")
            d_lbl.setStyleSheet(f"color:{col};font-size:11px;font-weight:bold;")
            lay.addWidget(d_lbl)

        # Priorité
        prio = project.get("priority","")
        prio_colors = {"critique":RED,"haute":AMBER,"normale":TXT2,"basse":MUTED}
        if prio and prio != "normale":
            p_lbl = QLabel(f"● {prio.capitalize()}")
            p_lbl.setStyleSheet(f"color:{prio_colors.get(prio,TXT2)};font-size:11px;")
            lay.addWidget(p_lbl)

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self._project)


class KanbanColumn(QFrame):
    card_clicked = pyqtSignal(dict)

    def __init__(self, key, label, color, parent=None):
        super().__init__(parent)
        self._key = key
        self.setObjectName("card")
        self.setFixedWidth(244)
        self.setMinimumHeight(400)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0,0,0,0)
        lay.setSpacing(0)

        # Header colonne
        hdr = QWidget()
        hdr.setStyleSheet(f"background:{BG2};border-radius:8px 8px 0 0;")
        hl = QHBoxLayout(hdr); hl.setContentsMargins(12,10,12,10)
        lbl = QLabel(label)
        lbl.setStyleSheet(f"color:{color};font-weight:bold;font-size:13px;")
        hl.addWidget(lbl)
        hl.addStretch()
        self._count = QLabel("0")
        self._count.setStyleSheet(f"color:{MUTED};font-size:12px;")
        hl.addWidget(self._count)
        lay.addWidget(hdr)

        # Zone scrollable
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._cards_widget = QWidget()
        self._cards_widget.setStyleSheet(f"background:{BG};")
        self._cards_lay = QVBoxLayout(self._cards_widget)
        self._cards_lay.setContentsMargins(8,8,8,8)
        self._cards_lay.setSpacing(8)
        self._cards_lay.addStretch()
        scroll.setWidget(self._cards_widget)
        lay.addWidget(scroll)

    def set_projects(self, projects):
        # Clear existing cards (keep stretch)
        while self._cards_lay.count() > 1:
            item = self._cards_lay.takeAt(0)
            if item.widget(): item.widget().deleteLater()

        self._count.setText(str(len(projects)))
        for p in projects:
            card = ProjectCard(p)
            card.clicked.connect(self.card_clicked)
            self._cards_lay.insertWidget(self._cards_lay.count()-1, card)


class ProjectDialog(QDialog):
    def __init__(self, parent=None, data=None, clients=None):
        super().__init__(parent)
        self.setWindowTitle("Nouveau projet" if not data else "Modifier projet")
        self.setMinimumWidth(460)
        self.setStyleSheet(f"background:{BG2};")
        self._clients = clients or []

        lay = QVBoxLayout(self)
        lay.setContentsMargins(20,20,20,20)
        lay.setSpacing(14)

        form = QFormLayout(); form.setSpacing(10)
        def lbl(t): l=QLabel(t);l.setStyleSheet(f"color:{TXT2};");return l

        self.inp_name = QLineEdit(data.get("name","") if data else "")
        self.inp_name.setPlaceholderText("Nom du projet")
        form.addRow(lbl("Nom *"), self.inp_name)

        self.cmb_client = QComboBox()
        for c in self._clients:
            self.cmb_client.addItem(c["name"], c["id"])
        if data and data.get("client_id"):
            idx = self.cmb_client.findData(data["client_id"])
            if idx >= 0: self.cmb_client.setCurrentIndex(idx)
        form.addRow(lbl("Client"), self.cmb_client)

        self.inp_desc = QTextEdit()
        self.inp_desc.setFixedHeight(70)
        self.inp_desc.setPlaceholderText("Description...")
        if data: self.inp_desc.setPlainText(data.get("description","") or "")
        form.addRow(lbl("Description"), self.inp_desc)

        self.cmb_status = QComboBox()
        self.cmb_status.addItems(["en_cours","en_attente","a_relancer","a_facturer","termine"])
        if data: self.cmb_status.setCurrentText(data.get("status","en_cours"))
        form.addRow(lbl("Statut"), self.cmb_status)

        self.cmb_prio = QComboBox()
        self.cmb_prio.addItems(["basse","normale","haute","critique"])
        if data: self.cmb_prio.setCurrentText(data.get("priority","normale"))
        else: self.cmb_prio.setCurrentText("normale")
        form.addRow(lbl("Priorité"), self.cmb_prio)

        self.inp_waiting = QLineEdit(data.get("waiting_for","") if data else "")
        self.inp_waiting.setPlaceholderText("En attente de qui / quoi ?")
        form.addRow(lbl("En attente de"), self.inp_waiting)

        self.spin_hours = QDoubleSpinBox()
        self.spin_hours.setRange(0,9999); self.spin_hours.setSuffix(" h")
        self.spin_hours.setValue(float(data.get("estimated_hours",0) or 0) if data else 0)
        form.addRow(lbl("Heures estimées"), self.spin_hours)

        lay.addLayout(form)

        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.button(QDialogButtonBox.StandardButton.Ok).setText("Enregistrer")
        btns.button(QDialogButtonBox.StandardButton.Ok).setObjectName("btn_primary")
        btns.button(QDialogButtonBox.StandardButton.Cancel).setObjectName("btn_secondary")
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        lay.addWidget(btns)

    def get_data(self):
        return {
            "name":            self.inp_name.text().strip(),
            "client_id":       self.cmb_client.currentData(),
            "description":     self.inp_desc.toPlainText().strip() or None,
            "status":          self.cmb_status.currentText(),
            "priority":        self.cmb_prio.currentText(),
            "waiting_for":     self.inp_waiting.text().strip() or None,
            "estimated_hours": self.spin_hours.value() or None,
        }


class ProjectsView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._workers = []
        self._projects = []
        self._clients = []
        self._columns = {}
        self._build_ui()
        self._load_clients()
        self.refresh()

    def _build_ui(self):
        main = QVBoxLayout(self)
        main.setContentsMargins(0,0,0,0)
        main.setSpacing(0)

        # Toolbar
        toolbar = QWidget()
        toolbar.setStyleSheet(f"background:{BG};border-bottom:1px solid {BORDER};")
        tb = QHBoxLayout(toolbar); tb.setContentsMargins(24,12,24,12); tb.setSpacing(10)
        tb.addWidget(SectionTitle("Projets"))
        tb.addStretch()
        btn_new = QPushButton("+ Nouveau projet")
        btn_new.setObjectName("btn_primary")
        btn_new.clicked.connect(self._new_project)
        tb.addWidget(btn_new)
        main.addWidget(toolbar)

        # Kanban horizontal scrollable
        outer = QScrollArea()
        outer.setWidgetResizable(True)
        outer.setFrameShape(QFrame.Shape.NoFrame)
        outer.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        board = QWidget(); board.setStyleSheet(f"background:{BG};")
        board_lay = QHBoxLayout(board)
        board_lay.setContentsMargins(20,16,20,16)
        board_lay.setSpacing(12)

        for key, label, color in COLUMNS:
            col = KanbanColumn(key, label, color)
            col.card_clicked.connect(self._on_card_click)
            self._columns[key] = col
            board_lay.addWidget(col)

        board_lay.addStretch()
        outer.setWidget(board)
        main.addWidget(outer)

    def _load_clients(self):
        w = api("GET", "/clients/summary", on_ok=lambda d: setattr(self, "_clients", d))
        self._workers.append(w)

    def refresh(self):
        w = api("GET", "/projects/", on_ok=self._on_projects)
        self._workers.append(w)

    def _on_projects(self, data):
        self._projects = data if isinstance(data, list) else data.get("items", [])
        # Distribuer par colonne
        by_status = {k: [] for k, *_ in COLUMNS}
        for p in self._projects:
            s = p.get("status","en_cours")
            if s in by_status: by_status[s].append(p)
        for key, col in self._columns.items():
            col.set_projects(by_status.get(key, []))

    def _on_card_click(self, project):
        dlg = ProjectDialog(self, data=project, clients=self._clients)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            data = dlg.get_data()
            pid = project.get("id")
            w = api("PUT", f"/projects/{pid}", data, on_ok=lambda _: self.refresh())
            self._workers.append(w)

    def _new_project(self):
        dlg = ProjectDialog(self, clients=self._clients)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            data = dlg.get_data()
            if not data["name"]:
                QMessageBox.warning(self, "Erreur", "Le nom est obligatoire.")
                return
            w = api("POST", "/projects/", data, on_ok=lambda _: self.refresh())
            self._workers.append(w)
