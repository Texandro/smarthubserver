"""
SmartHub — Widgets réutilisables
"""
from PyQt6.QtWidgets import (
    QWidget, QLabel, QFrame, QHBoxLayout, QVBoxLayout,
    QPushButton, QSizePolicy
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont
from .theme import *


class StatCard(QFrame):
    """Carte stat : valeur + label + couleur accent."""
    def __init__(self, label, value="—", accent=BLUE, parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        self.setMinimumWidth(140)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.setSpacing(4)

        self._val = QLabel(value)
        self._val.setStyleSheet(f"color:{accent};font-size:26px;font-weight:bold;")
        lay.addWidget(self._val)

        lbl = QLabel(label)
        lbl.setStyleSheet(f"color:{TXT2};font-size:12px;")
        lay.addWidget(lbl)

    def set_value(self, v):
        self._val.setText(str(v))


class AlertBadge(QLabel):
    """Badge rouge/amber avec compteur."""
    def __init__(self, count=0, color=RED, parent=None):
        super().__init__(parent)
        self._color = color
        self.set_count(count)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setFixedSize(22, 22)

    def set_count(self, n):
        self.setText(str(n))
        visible = n > 0
        color = self._color if visible else MUTED
        self.setStyleSheet(
            f"background:{color}22;color:{color};border:1px solid {color}55;"
            f"border-radius:11px;font-size:11px;font-weight:bold;"
        )


class SectionTitle(QLabel):
    """Titre de section avec style uniforme."""
    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        self.setStyleSheet(
            f"color:{TXT};font-size:16px;font-weight:bold;"
            f"padding-bottom:4px;"
        )


class StatusPill(QLabel):
    """Pill coloré pour les statuts."""
    COLORS = {
        "actif":      (GREEN,  "#052e16"),
        "inactif":    (MUTED,  BG2),
        "dormant":    (AMBER,  "#451a03"),
        "contentieux":(RED,    "#2d0a14"),
        "pending":    (AMBER,  "#451a03"),
        "accepted":   (GREEN,  "#052e16"),
        "rejected":   (RED,    "#2d0a14"),
        "active":     (GREEN,  "#052e16"),
        "expired":    (RED,    "#2d0a14"),
        "draft":      (MUTED,  BG2),
        "signed":     (BLUE,   "#0c1a4d"),
    }

    def __init__(self, status, parent=None):
        super().__init__(parent)
        self.set_status(status)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)

    def set_status(self, status):
        s = (status or "").lower()
        fg, bg = self.COLORS.get(s, (MUTED, BG2))
        self.setText(s.capitalize())
        self.setStyleSheet(
            f"color:{fg};background:{bg};border:1px solid {fg}55;"
            f"border-radius:10px;padding:2px 10px;font-size:11px;font-weight:bold;"
        )


class EmptyState(QWidget):
    """État vide avec icône et message."""
    action_clicked = pyqtSignal()

    def __init__(self, icon="📭", title="Aucun élément", subtitle="", btn_label="", parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.setSpacing(12)

        ico = QLabel(icon)
        ico.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ico.setStyleSheet("font-size:48px;background:transparent;")
        lay.addWidget(ico)

        t = QLabel(title)
        t.setAlignment(Qt.AlignmentFlag.AlignCenter)
        t.setStyleSheet(f"color:{TXT};font-size:15px;font-weight:bold;background:transparent;")
        lay.addWidget(t)

        if subtitle:
            s = QLabel(subtitle)
            s.setAlignment(Qt.AlignmentFlag.AlignCenter)
            s.setStyleSheet(f"color:{TXT2};font-size:12px;background:transparent;")
            s.setWordWrap(True)
            lay.addWidget(s)

        if btn_label:
            btn = QPushButton(btn_label)
            btn.setObjectName("btn_primary")
            btn.setFixedWidth(180)
            btn.clicked.connect(self.action_clicked)
            lay.addWidget(btn, alignment=Qt.AlignmentFlag.AlignCenter)


class Separator(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.HLine)
        self.setStyleSheet(f"color:{BORDER};background:{BORDER};max-height:1px;")
