"""
SmartHub — Vue Dashboard
"""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QFrame, QScrollArea, QTableWidget, QTableWidgetItem,
    QHeaderView, QSizePolicy
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont
from ..theme import *
from ..api import api
from ..widgets import StatCard, SectionTitle, StatusPill, EmptyState


class DashboardView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._workers = []
        self._build_ui()
        self.refresh()
        # auto-refresh toutes les 30s
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.refresh)
        self._timer.start(30_000)

    def _build_ui(self):
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        content = QWidget()
        main = QVBoxLayout(content)
        main.setContentsMargins(28, 24, 28, 24)
        main.setSpacing(24)

        # — Titre —
        hdr = QHBoxLayout()
        t = SectionTitle("Dashboard")
        hdr.addWidget(t)
        hdr.addStretch()
        self.lbl_date = QLabel()
        self.lbl_date.setStyleSheet(f"color:{TXT2};font-size:12px;")
        hdr.addWidget(self.lbl_date)
        main.addLayout(hdr)

        # — Stats aujourd'hui —
        lbl_today = QLabel("Aujourd'hui")
        lbl_today.setStyleSheet(f"color:{TXT2};font-size:12px;font-weight:bold;text-transform:uppercase;letter-spacing:1px;")
        main.addWidget(lbl_today)

        stats_row = QHBoxLayout(); stats_row.setSpacing(12)
        self.card_hours   = StatCard("Heures trackées", "0h00", LBLUE)
        self.card_bill    = StatCard("Facturable", "0.00 €", GREEN)
        self.card_sess    = StatCard("Sessions", "0", TXT2)
        self.card_active  = StatCard("Clients actifs", "0", BLUE)
        for c in [self.card_hours, self.card_bill, self.card_sess, self.card_active]:
            c.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            stats_row.addWidget(c)
        main.addLayout(stats_row)

        # — Alertes —
        lbl_alerts = QLabel("Alertes")
        lbl_alerts.setStyleSheet(f"color:{TXT2};font-size:12px;font-weight:bold;text-transform:uppercase;letter-spacing:1px;")
        main.addWidget(lbl_alerts)

        alerts_row = QHBoxLayout(); alerts_row.setSpacing(12)
        self.card_renewal   = StatCard("Contrats à renouveler", "0", AMBER)
        self.card_waiting   = StatCard("Projets en attente", "0", AMBER)
        self.card_remind    = StatCard("Relances à faire", "0", RED)
        for c in [self.card_renewal, self.card_waiting, self.card_remind]:
            c.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            alerts_row.addWidget(c)
        main.addLayout(alerts_row)

        # — Sessions récentes —
        lbl_recent = QLabel("Sessions récentes")
        lbl_recent.setStyleSheet(f"color:{TXT2};font-size:12px;font-weight:bold;text-transform:uppercase;letter-spacing:1px;")
        main.addWidget(lbl_recent)

        self.tbl = QTableWidget(0, 4)
        self.tbl.setHorizontalHeaderLabels(["Client", "Activité", "Durée", "Montant"])
        self.tbl.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.tbl.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.tbl.setAlternatingRowColors(True)
        self.tbl.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tbl.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tbl.verticalHeader().setVisible(False)
        self.tbl.setMinimumHeight(200)
        main.addWidget(self.tbl)

        main.addStretch()
        scroll.setWidget(content)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(scroll)

    def refresh(self):
        from datetime import datetime
        self.lbl_date.setText(datetime.now().strftime("%A %d %B %Y"))
        w = api("GET", "/dashboard/", on_ok=self._on_dashboard)
        self._workers.append(w)

    def _on_dashboard(self, data):
        today  = data.get("today", {})
        alerts = data.get("alerts", {})
        recent = data.get("recent_sessions", [])

        h = today.get("hours", 0) or 0
        self.card_hours.set_value(f"{int(h)}h{int((h%1)*60):02d}")
        self.card_bill.set_value(f"{today.get('billable', 0) or 0:.2f} €")
        self.card_sess.set_value(today.get("sessions", 0) or 0)
        self.card_active.set_value(alerts.get("active_clients", 0) or 0)
        self.card_renewal.set_value(alerts.get("renewal_alerts", 0) or 0)
        self.card_waiting.set_value(alerts.get("projects_waiting", 0) or 0)
        self.card_remind.set_value(alerts.get("projects_need_reminder", 0) or 0)

        self.tbl.setRowCount(0)
        for s in recent:
            r = self.tbl.rowCount()
            self.tbl.insertRow(r)
            self.tbl.setItem(r, 0, QTableWidgetItem(s.get("client_name", "")))
            self.tbl.setItem(r, 1, QTableWidgetItem(s.get("activity", "")))
            h2 = s.get("duration_hours", 0) or 0
            self.tbl.setItem(r, 2, QTableWidgetItem(f"{int(h2)}h{int((h2%1)*60):02d}"))
            amt = s.get("amount", 0) or 0
            self.tbl.setItem(r, 3, QTableWidgetItem(f"{amt:.2f} €"))
