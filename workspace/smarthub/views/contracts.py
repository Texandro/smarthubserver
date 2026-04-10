"""
SmartHub — Vue Contrats
Module prioritaire : liste, création, rentabilité
"""
from datetime import date, datetime, timedelta
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QTableWidget, QTableWidgetItem, QHeaderView, QPushButton,
    QLineEdit, QComboBox, QDialog, QDialogButtonBox,
    QFormLayout, QMessageBox, QDoubleSpinBox, QSpinBox,
    QDateEdit, QTabWidget, QSplitter, QScrollArea,
    QTextEdit, QCheckBox, QProgressBar
)
from PyQt6.QtCore import Qt, QDate, pyqtSignal
from PyQt6.QtGui import QColor
from ..theme import *
from ..api import api
from ..widgets import SectionTitle, StatusPill, StatCard, EmptyState


class ContractDialog(QDialog):
    """Formulaire création / édition contrat."""

    def __init__(self, parent=None, data=None, clients=None):
        super().__init__(parent)
        self.setWindowTitle("Nouveau contrat" if not data else "Modifier contrat")
        self.setMinimumWidth(500)
        self.setMinimumHeight(600)
        self.setStyleSheet(f"background:{BG2};")
        self._clients = clients or []

        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 20)
        lay.setSpacing(16)

        title = QLabel("Nouveau contrat" if not data else "Modifier le contrat")
        title.setStyleSheet(f"font-size:16px;font-weight:bold;color:{TXT};")
        lay.addWidget(title)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll_content = QWidget()
        form = QFormLayout(scroll_content)
        form.setSpacing(12)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        def label(t):
            l = QLabel(t); l.setStyleSheet(f"color:{TXT2};")
            return l

        # Client
        self.cmb_client = QComboBox()
        for c in self._clients:
            self.cmb_client.addItem(c["name"], c["id"])
        if data and data.get("client_id"):
            idx = self.cmb_client.findData(data["client_id"])
            if idx >= 0: self.cmb_client.setCurrentIndex(idx)
        form.addRow(label("Client *"), self.cmb_client)

        # Type de contrat
        self.cmb_type = QComboBox()
        self.cmb_type.addItems([
            "maintenance",
            "forfait",
            "regie",
            "projet",
            "forensics",
            "ponctuel",
        ])
        if data: self.cmb_type.setCurrentText(data.get("contract_type","maintenance"))
        form.addRow(label("Type *"), self.cmb_type)

        # Titre
        self.inp_title = QLineEdit(data.get("title","") if data else "")
        self.inp_title.setPlaceholderText("Ex: Contrat maintenance annuel 2026")
        form.addRow(label("Titre *"), self.inp_title)

        # Description
        self.inp_desc = QTextEdit()
        self.inp_desc.setPlaceholderText("Description des prestations incluses...")
        self.inp_desc.setFixedHeight(80)
        if data: self.inp_desc.setPlainText(data.get("description","") or "")
        form.addRow(label("Description"), self.inp_desc)

        # Dates
        self.date_start = QDateEdit()
        self.date_start.setCalendarPopup(True)
        self.date_start.setDate(QDate.currentDate() if not data else
                                QDate.fromString(data.get("start_date",""), "yyyy-MM-dd"))
        form.addRow(label("Date début *"), self.date_start)

        self.date_end = QDateEdit()
        self.date_end.setCalendarPopup(True)
        default_end = QDate.currentDate().addYears(1)
        self.date_end.setDate(default_end if not data else
                              QDate.fromString(data.get("end_date",""), "yyyy-MM-dd"))
        form.addRow(label("Date fin *"), self.date_end)

        # Montant & heures
        self.spin_amount = QDoubleSpinBox()
        self.spin_amount.setRange(0, 999999)
        self.spin_amount.setDecimals(2)
        self.spin_amount.setSuffix(" €")
        self.spin_amount.setValue(float(data.get("amount",0) or 0) if data else 0)
        form.addRow(label("Montant HT *"), self.spin_amount)

        self.spin_hours = QDoubleSpinBox()
        self.spin_hours.setRange(0, 9999)
        self.spin_hours.setDecimals(1)
        self.spin_hours.setSuffix(" h")
        self.spin_hours.setValue(float(data.get("included_hours",0) or 0) if data else 0)
        form.addRow(label("Heures incluses"), self.spin_hours)

        self.spin_rate = QDoubleSpinBox()
        self.spin_rate.setRange(0, 999)
        self.spin_rate.setDecimals(2)
        self.spin_rate.setSuffix(" €/h")
        self.spin_rate.setValue(float(data.get("hourly_rate",0) or 0) if data else 95.0)
        form.addRow(label("Tarif horaire"), self.spin_rate)

        # Renouvellement
        self.chk_auto_renew = QCheckBox("Renouvellement automatique")
        self.chk_auto_renew.setChecked(bool(data.get("auto_renew", True)) if data else True)
        form.addRow(label(""), self.chk_auto_renew)

        self.spin_renew_days = QSpinBox()
        self.spin_renew_days.setRange(7, 180)
        self.spin_renew_days.setSuffix(" jours avant")
        self.spin_renew_days.setValue(int(data.get("renewal_reminder_days", 60)) if data else 60)
        form.addRow(label("Rappel renouvellement"), self.spin_renew_days)

        # Statut
        self.cmb_status = QComboBox()
        self.cmb_status.addItems(["draft","active","expired","cancelled"])
        if data: self.cmb_status.setCurrentText(data.get("status","draft"))
        form.addRow(label("Statut"), self.cmb_status)

        # Notes
        self.inp_notes = QTextEdit()
        self.inp_notes.setPlaceholderText("Notes internes, conditions particulières...")
        self.inp_notes.setFixedHeight(60)
        if data: self.inp_notes.setPlainText(data.get("notes","") or "")
        form.addRow(label("Notes"), self.inp_notes)

        scroll.setWidget(scroll_content)
        lay.addWidget(scroll)

        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.button(QDialogButtonBox.StandardButton.Ok).setText("Enregistrer")
        btns.button(QDialogButtonBox.StandardButton.Ok).setObjectName("btn_primary")
        btns.button(QDialogButtonBox.StandardButton.Cancel).setObjectName("btn_secondary")
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        lay.addWidget(btns)

    def get_data(self):
        return {
            "client_id":             self.cmb_client.currentData(),
            "contract_type":         self.cmb_type.currentText(),
            "title":                 self.inp_title.text().strip(),
            "description":           self.inp_desc.toPlainText().strip() or None,
            "start_date":            self.date_start.date().toString("yyyy-MM-dd"),
            "end_date":              self.date_end.date().toString("yyyy-MM-dd"),
            "amount":                self.spin_amount.value(),
            "included_hours":        self.spin_hours.value() or None,
            "hourly_rate":           self.spin_rate.value() or None,
            "auto_renew":            self.chk_auto_renew.isChecked(),
            "renewal_reminder_days": self.spin_renew_days.value(),
            "status":                self.cmb_status.currentText(),
            "notes":                 self.inp_notes.toPlainText().strip() or None,
        }


class ContractDetail(QScrollArea):
    """Panneau détail + rentabilité d'un contrat."""
    edit_requested = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self._contract = None
        self._workers = []

        self._content = QWidget()
        self._lay = QVBoxLayout(self._content)
        self._lay.setContentsMargins(20, 20, 20, 20)
        self._lay.setSpacing(16)

        empty = QLabel("← Sélectionnez un contrat")
        empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty.setStyleSheet(f"color:{MUTED};font-size:14px;")
        self._lay.addWidget(empty)
        self._lay.addStretch()
        self.setWidget(self._content)

    def show_contract(self, contract):
        self._contract = contract
        while self._lay.count():
            item = self._lay.takeAt(0)
            if item.widget(): item.widget().deleteLater()

        # — Header —
        hdr = QHBoxLayout()
        t = QLabel(contract.get("title",""))
        t.setStyleSheet(f"color:{TXT};font-size:17px;font-weight:bold;")
        t.setWordWrap(True)
        hdr.addWidget(t, 1)
        pill = StatusPill(contract.get("status",""))
        hdr.addWidget(pill)
        btn_edit = QPushButton("✏ Modifier")
        btn_edit.setObjectName("btn_secondary")
        btn_edit.clicked.connect(lambda: self.edit_requested.emit(contract))
        hdr.addWidget(btn_edit)
        self._lay.addLayout(hdr)

        # — Infos générales —
        info = QFrame(); info.setObjectName("card")
        fl = QFormLayout(info); fl.setContentsMargins(16,14,16,14); fl.setSpacing(10)

        def row(label, val, color=None):
            if val is not None:
                l = QLabel(label); l.setStyleSheet(f"color:{TXT2};font-size:12px;")
                v = QLabel(str(val))
                if color: v.setStyleSheet(f"color:{color};font-weight:bold;")
                fl.addRow(l, v)

        row("Client",    contract.get("client_name",""))
        row("Type",      contract.get("contract_type","").capitalize())
        row("Référence", contract.get("reference",""))
        row("Début",     contract.get("start_date",""))
        row("Fin",       contract.get("end_date",""))
        amt = contract.get("amount", 0) or 0
        row("Montant HT", f"{amt:.2f} €", LBLUE)
        h = contract.get("included_hours")
        if h: row("Heures incluses", f"{h}h")
        rate = contract.get("hourly_rate")
        if rate: row("Tarif horaire", f"{rate:.2f} €/h")
        if contract.get("auto_renew"):
            row("Renouvellement", f"Auto — rappel {contract.get('renewal_reminder_days',60)}j avant", GREEN)
        if contract.get("notes"):
            row("Notes", contract.get("notes"))

        self._lay.addWidget(info)

        # — Rentabilité —
        self._lay.addWidget(QLabel("Rentabilité"))
        self._load_profitability(contract.get("id"))

        self._lay.addStretch()

    def _load_profitability(self, cid):
        placeholder = QFrame(); placeholder.setObjectName("card")
        pl = QVBoxLayout(placeholder); pl.setContentsMargins(16,14,16,14)
        lbl = QLabel("Chargement..."); lbl.setStyleSheet(f"color:{MUTED};")
        pl.addWidget(lbl)
        self._lay.addWidget(placeholder)
        self._profit_frame = placeholder

        w = api("GET", f"/contracts/{cid}/profitability", on_ok=self._on_profit)
        self._workers.append(w)

    def _on_profit(self, data):
        # Remplace le placeholder
        idx = self._lay.indexOf(self._profit_frame)
        self._profit_frame.deleteLater()

        frame = QFrame(); frame.setObjectName("card")
        lay = QVBoxLayout(frame); lay.setContentsMargins(16,14,16,14); lay.setSpacing(12)

        # Stats rentabilité
        row1 = QHBoxLayout(); row1.setSpacing(12)
        h_used  = data.get("hours_used", 0) or 0
        h_incl  = data.get("hours_included", 0) or 0
        h_extra = data.get("hours_extra", 0) or 0
        revenue = data.get("revenue", 0) or 0
        cost    = data.get("cost_hours", 0) or 0
        margin  = data.get("margin", 0) or 0

        def mini_stat(label, val, color=TXT):
            w = QFrame(); w.setStyleSheet(f"background:{BG3};border-radius:6px;")
            wl = QVBoxLayout(w); wl.setContentsMargins(12,8,12,8); wl.setSpacing(2)
            v = QLabel(str(val)); v.setStyleSheet(f"color:{color};font-size:18px;font-weight:bold;")
            l = QLabel(label); l.setStyleSheet(f"color:{TXT2};font-size:11px;")
            wl.addWidget(v); wl.addWidget(l)
            return w

        row1.addWidget(mini_stat("Heures utilisées", f"{h_used:.1f}h", LBLUE))
        row1.addWidget(mini_stat("Heures incluses", f"{h_incl:.1f}h", TXT2))
        row1.addWidget(mini_stat("Dépassement", f"{h_extra:.1f}h", RED if h_extra > 0 else TXT2))
        lay.addLayout(row1)

        row2 = QHBoxLayout(); row2.setSpacing(12)
        margin_color = GREEN if margin >= 0 else RED
        row2.addWidget(mini_stat("Revenus", f"{revenue:.2f}€", GREEN))
        row2.addWidget(mini_stat("Coût heures", f"{cost:.2f}€", AMBER))
        row2.addWidget(mini_stat("Marge", f"{margin:.2f}€", margin_color))
        lay.addLayout(row2)

        # Barre progression heures
        if h_incl > 0:
            pct = min(100, int((h_used / h_incl) * 100))
            bar_lbl = QLabel(f"Consommation heures : {pct}%")
            bar_lbl.setStyleSheet(f"color:{TXT2};font-size:12px;")
            lay.addWidget(bar_lbl)

            bar = QProgressBar()
            bar.setValue(pct)
            bar.setFixedHeight(8)
            bar.setTextVisible(False)
            color = GREEN if pct < 80 else (AMBER if pct < 100 else RED)
            bar.setStyleSheet(f"""
                QProgressBar {{ background:{BG3}; border-radius:4px; border:none; }}
                QProgressBar::chunk {{ background:{color}; border-radius:4px; }}
            """)
            lay.addWidget(bar)

        self._lay.insertWidget(idx, frame)
        self._profit_frame = frame


class ContractsView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._workers = []
        self._contracts = []
        self._clients = []
        self._build_ui()
        self._load_clients()
        self.refresh()

    def _build_ui(self):
        main = QVBoxLayout(self)
        main.setContentsMargins(0,0,0,0)
        main.setSpacing(0)

        # — Toolbar —
        toolbar = QWidget()
        toolbar.setStyleSheet(f"background:{BG};border-bottom:1px solid {BORDER};")
        tb = QHBoxLayout(toolbar); tb.setContentsMargins(24,12,24,12); tb.setSpacing(10)

        tb.addWidget(SectionTitle("Contrats"))
        tb.addStretch()

        self.inp_search = QLineEdit()
        self.inp_search.setPlaceholderText("🔍  Rechercher...")
        self.inp_search.setFixedWidth(200)
        self.inp_search.textChanged.connect(self._filter)
        tb.addWidget(self.inp_search)

        self.cmb_filter = QComboBox()
        self.cmb_filter.addItems(["Tous", "active", "draft", "expired", "cancelled"])
        self.cmb_filter.setFixedWidth(120)
        self.cmb_filter.currentTextChanged.connect(self._filter)
        tb.addWidget(self.cmb_filter)

        btn_gen = QPushButton("📄 Générer PDF")
        btn_gen.setObjectName("btn_secondary")
        btn_gen.clicked.connect(self._open_wizard)
        tb.addWidget(btn_gen)

        btn_new = QPushButton("+ Nouveau contrat")
        btn_new.setObjectName("btn_primary")
        btn_new.clicked.connect(self._new_contract)
        tb.addWidget(btn_new)

        main.addWidget(toolbar)

        # — Splitter —
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(1)
        splitter.setStyleSheet(f"QSplitter::handle{{background:{BORDER};}}")

        # Liste
        list_w = QWidget(); list_w.setStyleSheet(f"background:{BG};")
        lw = QVBoxLayout(list_w); lw.setContentsMargins(0,0,0,0)

        self.tbl = QTableWidget(0, 5)
        self.tbl.setHorizontalHeaderLabels(["Client", "Titre", "Type", "Fin", "Montant"])
        self.tbl.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.tbl.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.tbl.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.tbl.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.tbl.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.tbl.setAlternatingRowColors(True)
        self.tbl.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tbl.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tbl.verticalHeader().setVisible(False)
        self.tbl.setShowGrid(False)
        self.tbl.itemSelectionChanged.connect(self._on_select)
        lw.addWidget(self.tbl)
        splitter.addWidget(list_w)

        # Détail
        self.detail = ContractDetail()
        self.detail.edit_requested.connect(self._edit_contract)
        self.detail.setMinimumWidth(360)
        splitter.addWidget(self.detail)
        splitter.setSizes([520, 400])

        main.addWidget(splitter)

    def _load_clients(self):
        w = api("GET", "/clients/summary", on_ok=lambda d: setattr(self, "_clients", d))
        self._workers.append(w)

    def refresh(self):
        w = api("GET", "/contracts/", on_ok=self._on_contracts)
        self._workers.append(w)

    def _on_contracts(self, data):
        self._contracts = data if isinstance(data, list) else data.get("items", [])
        self._populate(self._contracts)

    def _populate(self, contracts):
        self.tbl.setRowCount(0)
        today = date.today()
        for c in contracts:
            r = self.tbl.rowCount()
            self.tbl.insertRow(r)
            self.tbl.setItem(r, 0, QTableWidgetItem(c.get("client_name","") or ""))
            self.tbl.setItem(r, 1, QTableWidgetItem(c.get("title","") or ""))
            self.tbl.setItem(r, 2, QTableWidgetItem(c.get("contract_type","").capitalize()))

            # Date fin avec alerte couleur
            end_str = c.get("end_date","") or ""
            item_end = QTableWidgetItem(end_str)
            try:
                end_d = date.fromisoformat(end_str)
                days_left = (end_d - today).days
                if days_left < 0:
                    item_end.setForeground(QColor(RED))
                elif days_left < 60:
                    item_end.setForeground(QColor(AMBER))
                else:
                    item_end.setForeground(QColor(GREEN))
            except: pass
            self.tbl.setItem(r, 3, item_end)

            amt = c.get("amount", 0) or 0
            self.tbl.setItem(r, 4, QTableWidgetItem(f"{amt:.2f} €"))
            self.tbl.item(r, 0).setData(Qt.ItemDataRole.UserRole, c)

    def _filter(self):
        q = self.inp_search.text().lower()
        f = self.cmb_filter.currentText()
        filtered = [c for c in self._contracts
                    if (q in (c.get("title","") or "").lower()
                        or q in (c.get("client_name","") or "").lower())
                    and (f == "Tous" or c.get("status") == f)]
        self._populate(filtered)

    def _on_select(self):
        r = self.tbl.currentRow()
        if r < 0: return
        item = self.tbl.item(r, 0)
        if item:
            c = item.data(Qt.ItemDataRole.UserRole)
            if c: self.detail.show_contract(c)

    def _new_contract(self):
        dlg = ContractDialog(self, clients=self._clients)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            data = dlg.get_data()
            if not data["title"] or not data["client_id"]:
                QMessageBox.warning(self, "Erreur", "Client et titre sont obligatoires.")
                return
            w = api("POST", "/contracts/", data, on_ok=lambda _: self.refresh())
            self._workers.append(w)

    def _edit_contract(self, contract):
        dlg = ContractDialog(self, data=contract, clients=self._clients)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            data = dlg.get_data()
            cid = contract.get("id")
            w = api("PUT", f"/contracts/{cid}", data, on_ok=lambda _: self.refresh())
            self._workers.append(w)

    def _open_wizard(self):
        from .contract_wizard import ContractGeneratorDialog
        # Passer le client sélectionné si disponible
        preselect = None
        r = self.tbl.currentRow()
        if r >= 0:
            item = self.tbl.item(r, 0)
            if item:
                c = item.data(Qt.ItemDataRole.UserRole)
                if c:
                    preselect = {"id": c.get("client_id"), "name": c.get("client_name","")}
        dlg = ContractGeneratorDialog(self, clients=self._clients, preselect_client=preselect)
        dlg.exec()
