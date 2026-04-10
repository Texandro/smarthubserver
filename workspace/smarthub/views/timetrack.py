"""
SmartHub — Vue Timetrack (historique)
"""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QPushButton, QComboBox, QDateEdit
)
from PyQt6.QtCore import Qt, QDate
from PyQt6.QtGui import QColor
from ..theme import *
from ..api import api
from ..widgets import SectionTitle, StatCard


class TimetracKView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._workers = []
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        main = QVBoxLayout(self)
        main.setContentsMargins(0,0,0,0)
        main.setSpacing(0)

        # Toolbar
        toolbar = QWidget()
        toolbar.setStyleSheet(f"background:{BG};border-bottom:1px solid {BORDER};")
        tb = QHBoxLayout(toolbar); tb.setContentsMargins(24,12,24,12); tb.setSpacing(10)
        tb.addWidget(SectionTitle("Time Tracking"))
        tb.addStretch()

        self.date_from = QDateEdit()
        self.date_from.setCalendarPopup(True)
        self.date_from.setDate(QDate.currentDate().addDays(-30))
        tb.addWidget(QLabel("Du :")); tb.addWidget(self.date_from)

        self.date_to = QDateEdit()
        self.date_to.setCalendarPopup(True)
        self.date_to.setDate(QDate.currentDate())
        tb.addWidget(QLabel("Au :")); tb.addWidget(self.date_to)

        btn_refresh = QPushButton("↺ Rafraîchir")
        btn_refresh.setObjectName("btn_secondary")
        btn_refresh.clicked.connect(self.refresh)
        tb.addWidget(btn_refresh)

        main.addWidget(toolbar)

        # Stats row
        stats = QWidget(); stats.setStyleSheet(f"background:{BG};padding:16px 24px;")
        sr = QHBoxLayout(stats); sr.setContentsMargins(24,16,24,8); sr.setSpacing(12)
        from PyQt6.QtWidgets import QSizePolicy
        self.card_total = StatCard("Total heures", "0h00", LBLUE)
        self.card_bill  = StatCard("Facturable", "0.00 €", GREEN)
        self.card_sess  = StatCard("Sessions", "0", TXT2)
        for c in [self.card_total, self.card_bill, self.card_sess]:
            c.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
            sr.addWidget(c)
        sr.addStretch()
        main.addWidget(stats)

        # Table
        self.tbl = QTableWidget(0, 6)
        self.tbl.setHorizontalHeaderLabels(["Date", "Client", "Activité", "Début", "Fin", "Durée"])
        self.tbl.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.tbl.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.tbl.setAlternatingRowColors(True)
        self.tbl.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tbl.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tbl.verticalHeader().setVisible(False)
        self.tbl.setShowGrid(False)

        container = QWidget(); container.setStyleSheet(f"background:{BG};")
        cl = QVBoxLayout(container); cl.setContentsMargins(24,0,24,24)
        cl.addWidget(self.tbl)
        main.addWidget(container)

    def refresh(self):
        params = {
            "from_date": self.date_from.date().toString("yyyy-MM-dd"),
            "to_date":   self.date_to.date().toString("yyyy-MM-dd"),
        }
        w = api("GET", "/timetrack/history", params=params, on_ok=self._on_data)
        self._workers.append(w)

    def _on_data(self, data):
        sessions = data if isinstance(data, list) else data.get("sessions", [])
        total_h  = sum((s.get("duration_hours") or 0) for s in sessions)
        total_b  = sum((s.get("amount") or 0) for s in sessions)

        self.card_total.set_value(f"{int(total_h)}h{int((total_h%1)*60):02d}")
        self.card_bill.set_value(f"{total_b:.2f} €")
        self.card_sess.set_value(len(sessions))

        self.tbl.setRowCount(0)
        for s in sessions:
            r = self.tbl.rowCount(); self.tbl.insertRow(r)
            started = s.get("started_at","")
            date_str = started[:10] if started else ""
            time_str = started[11:16] if len(started) > 10 else ""
            ended = s.get("ended_at","") or ""
            end_str = ended[11:16] if len(ended) > 10 else "—"
            h = s.get("duration_hours",0) or 0

            self.tbl.setItem(r, 0, QTableWidgetItem(date_str))
            self.tbl.setItem(r, 1, QTableWidgetItem(s.get("client_name","") or ""))
            self.tbl.setItem(r, 2, QTableWidgetItem(s.get("activity","") or ""))
            self.tbl.setItem(r, 3, QTableWidgetItem(time_str))
            self.tbl.setItem(r, 4, QTableWidgetItem(end_str))
            self.tbl.setItem(r, 5, QTableWidgetItem(f"{int(h)}h{int((h%1)*60):02d}"))

            if not s.get("billable"):
                for col in range(6):
                    item = self.tbl.item(r, col)
                    if item: item.setForeground(QColor(MUTED))
