"""
SmartHub — Vue Clients
"""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QTableWidget, QTableWidgetItem, QHeaderView, QPushButton,
    QLineEdit, QComboBox, QSplitter, QScrollArea, QDialog,
    QDialogButtonBox, QFormLayout, QMessageBox
)
from PyQt6.QtCore import Qt, pyqtSignal
from ..theme import *
from ..api import api
from ..widgets import SectionTitle, StatusPill, EmptyState


class ClientDialog(QDialog):
    """Formulaire création / édition client."""
    def __init__(self, parent=None, data=None):
        super().__init__(parent)
        self.setWindowTitle("Nouveau client" if not data else "Modifier client")
        self.setMinimumWidth(420)
        self.setStyleSheet(f"background:{BG2};")

        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 20, 20, 20)
        lay.setSpacing(16)

        lay.addWidget(QLabel("Informations client"))

        form = QFormLayout(); form.setSpacing(10)

        self.inp_name = QLineEdit(data.get("name","") if data else "")
        self.inp_name.setPlaceholderText("Nom complet")
        form.addRow("Nom *", self.inp_name)

        self.inp_email = QLineEdit(data.get("email","") if data else "")
        self.inp_email.setPlaceholderText("contact@exemple.com")
        form.addRow("Email", self.inp_email)

        self.inp_phone = QLineEdit(data.get("phone","") if data else "")
        self.inp_phone.setPlaceholderText("+32 2 000 00 00")
        form.addRow("Téléphone", self.inp_phone)

        self.inp_vat = QLineEdit(data.get("vat_number","") if data else "")
        self.inp_vat.setPlaceholderText("BE0123456789")
        form.addRow("N° TVA", self.inp_vat)

        self.inp_address = QLineEdit(data.get("address","") if data else "")
        self.inp_address.setPlaceholderText("Rue, Ville")
        form.addRow("Adresse", self.inp_address)

        self.cmb_type = QComboBox()
        self.cmb_type.addItems(["pme","asbl","independant","particulier","interne"])
        if data: self.cmb_type.setCurrentText(data.get("client_type","pme"))
        form.addRow("Type", self.cmb_type)

        self.cmb_status = QComboBox()
        self.cmb_status.addItems(["actif","dormant","inactif","contentieux"])
        if data: self.cmb_status.setCurrentText(data.get("status","actif"))
        form.addRow("Statut", self.cmb_status)

        self.inp_nas = QLineEdit(data.get("nas_path","") if data else "")
        self.inp_nas.setPlaceholderText("/volume1/Smartclick Clients/NomClient")
        form.addRow("Chemin NAS", self.inp_nas)

        self.inp_notes = QLineEdit(data.get("notes","") if data else "")
        self.inp_notes.setPlaceholderText("Notes internes...")
        form.addRow("Notes", self.inp_notes)

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
            "name":        self.inp_name.text().strip(),
            "email":       self.inp_email.text().strip() or None,
            "phone":       self.inp_phone.text().strip() or None,
            "vat_number":  self.inp_vat.text().strip() or None,
            "address":     self.inp_address.text().strip() or None,
            "client_type": self.cmb_type.currentText(),
            "status":      self.cmb_status.currentText(),
            "nas_path":    self.inp_nas.text().strip() or None,
            "notes":       self.inp_notes.text().strip() or None,
        }


class ClientDetail(QScrollArea):
    """Panneau détail d'un client."""
    edit_requested = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self._client = None

        self._content = QWidget()
        self._lay = QVBoxLayout(self._content)
        self._lay.setContentsMargins(20, 20, 20, 20)
        self._lay.setSpacing(16)
        self.setWidget(self._content)

        self._empty = QLabel("← Sélectionnez un client")
        self._empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty.setStyleSheet(f"color:{MUTED};font-size:14px;")
        self._lay.addWidget(self._empty)
        self._lay.addStretch()

    def show_client(self, client):
        self._client = client
        # clear
        while self._lay.count():
            item = self._lay.takeAt(0)
            if item.widget(): item.widget().deleteLater()

        # — Header —
        hdr = QHBoxLayout()
        name = QLabel(client.get("name",""))
        name.setStyleSheet(f"color:{TXT};font-size:20px;font-weight:bold;")
        hdr.addWidget(name)
        hdr.addStretch()
        pill = StatusPill(client.get("status",""))
        hdr.addWidget(pill)
        btn_edit = QPushButton("✏ Modifier")
        btn_edit.setObjectName("btn_secondary")
        btn_edit.clicked.connect(lambda: self.edit_requested.emit(client))
        hdr.addWidget(btn_edit)
        self._lay.addLayout(hdr)

        # — Infos —
        info_frame = QFrame(); info_frame.setObjectName("card")
        info_lay = QFormLayout(info_frame)
        info_lay.setContentsMargins(16,14,16,14)
        info_lay.setSpacing(10)

        def row(label, val):
            if val:
                lbl = QLabel(label); lbl.setStyleSheet(f"color:{TXT2};font-size:12px;")
                val_lbl = QLabel(str(val)); val_lbl.setStyleSheet(f"color:{TXT};")
                val_lbl.setWordWrap(True)
                info_lay.addRow(lbl, val_lbl)

        row("Type",      client.get("client_type","").capitalize())
        row("Email",     client.get("email",""))
        row("Téléphone", client.get("phone",""))
        row("TVA",       client.get("vat_number",""))
        row("Adresse",   client.get("address",""))
        row("NAS",       client.get("nas_path",""))
        row("Notes",     client.get("notes",""))
        self._lay.addWidget(info_frame)

        # — Sites —
        sites = client.get("sites", [])
        if sites:
            lbl_s = QLabel(f"Sites ({len(sites)})")
            lbl_s.setStyleSheet(f"color:{TXT2};font-size:12px;font-weight:bold;")
            self._lay.addWidget(lbl_s)
            for s in sites:
                sf = QFrame(); sf.setObjectName("card")
                sl = QHBoxLayout(sf); sl.setContentsMargins(12,8,12,8)
                sl.addWidget(QLabel(s.get("name","")))
                sl.addStretch()
                if s.get("address"): sl.addWidget(QLabel(s.get("address","")))
                self._lay.addWidget(sf)

        self._lay.addStretch()


class ClientsView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._workers = []
        self._clients = []
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        main = QVBoxLayout(self)
        main.setContentsMargins(0,0,0,0)
        main.setSpacing(0)

        # — Toolbar —
        toolbar = QWidget()
        toolbar.setStyleSheet(f"background:{BG};border-bottom:1px solid {BORDER};")
        tb = QHBoxLayout(toolbar); tb.setContentsMargins(24,12,24,12); tb.setSpacing(10)

        tb.addWidget(SectionTitle("Clients"))
        tb.addStretch()

        self.inp_search = QLineEdit()
        self.inp_search.setPlaceholderText("🔍  Rechercher...")
        self.inp_search.setFixedWidth(220)
        self.inp_search.textChanged.connect(self._filter)
        tb.addWidget(self.inp_search)

        self.cmb_filter = QComboBox()
        self.cmb_filter.addItems(["Tous", "actif", "dormant", "inactif", "contentieux"])
        self.cmb_filter.setFixedWidth(120)
        self.cmb_filter.currentTextChanged.connect(self._filter)
        tb.addWidget(self.cmb_filter)

        btn_new = QPushButton("+ Nouveau client")
        btn_new.setObjectName("btn_primary")
        btn_new.clicked.connect(self._new_client)
        tb.addWidget(btn_new)

        main.addWidget(toolbar)

        # — Splitter liste / détail —
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(1)
        splitter.setStyleSheet(f"QSplitter::handle{{background:{BORDER};}}")

        # Liste
        list_widget = QWidget()
        list_widget.setStyleSheet(f"background:{BG};")
        lw = QVBoxLayout(list_widget); lw.setContentsMargins(0,0,0,0); lw.setSpacing(0)

        self.tbl = QTableWidget(0, 4)
        self.tbl.setHorizontalHeaderLabels(["Nom", "Type", "Statut", "Email"])
        self.tbl.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.tbl.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.tbl.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.tbl.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.tbl.setAlternatingRowColors(True)
        self.tbl.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tbl.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tbl.verticalHeader().setVisible(False)
        self.tbl.setShowGrid(False)
        self.tbl.itemSelectionChanged.connect(self._on_select)
        lw.addWidget(self.tbl)
        splitter.addWidget(list_widget)

        # Détail
        self.detail = ClientDetail()
        self.detail.edit_requested.connect(self._edit_client)
        self.detail.setMinimumWidth(320)
        splitter.addWidget(self.detail)
        splitter.setSizes([500, 380])

        main.addWidget(splitter)

    def refresh(self):
        w = api("GET", "/clients/", on_ok=self._on_clients)
        self._workers.append(w)

    def _on_clients(self, data):
        self._clients = data if isinstance(data, list) else data.get("items", data)
        self._populate(self._clients)

    def _populate(self, clients):
        self.tbl.setRowCount(0)
        for c in clients:
            r = self.tbl.rowCount()
            self.tbl.insertRow(r)
            self.tbl.setItem(r, 0, QTableWidgetItem(c.get("name","")))
            self.tbl.setItem(r, 1, QTableWidgetItem(c.get("client_type","").capitalize()))
            # statut avec couleur
            item_s = QTableWidgetItem(c.get("status","").capitalize())
            status = c.get("status","")
            colors = {"actif": GREEN, "dormant": AMBER, "inactif": MUTED, "contentieux": RED}
            item_s.setForeground(__import__('PyQt6.QtGui', fromlist=['QColor']).QColor(colors.get(status, MUTED)))
            self.tbl.setItem(r, 2, item_s)
            self.tbl.setItem(r, 3, QTableWidgetItem(c.get("email","") or ""))
            self.tbl.item(r, 0).setData(Qt.ItemDataRole.UserRole, c)

    def _filter(self):
        q = self.inp_search.text().lower()
        f = self.cmb_filter.currentText()
        filtered = [c for c in self._clients
                    if (q in c.get("name","").lower() or q in (c.get("email","") or "").lower())
                    and (f == "Tous" or c.get("status") == f)]
        self._populate(filtered)

    def _on_select(self):
        rows = self.tbl.selectedItems()
        if not rows: return
        r = self.tbl.currentRow()
        item = self.tbl.item(r, 0)
        if item:
            client = item.data(Qt.ItemDataRole.UserRole)
            if client: self.detail.show_client(client)

    def _new_client(self):
        dlg = ClientDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            data = dlg.get_data()
            if not data["name"]:
                QMessageBox.warning(self, "Erreur", "Le nom est obligatoire.")
                return
            w = api("POST", "/clients/", data, on_ok=lambda _: self.refresh())
            self._workers.append(w)

    def _edit_client(self, client):
        dlg = ClientDialog(self, client)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            data = dlg.get_data()
            cid = client.get("id")
            w = api("PUT", f"/clients/{cid}", data, on_ok=lambda _: self.refresh())
            self._workers.append(w)
