"""
SmartHub — Thème Smartclick
Palette, styles Qt réutilisables
"""

# ── Palette ───────────────────────────────────────────────────────────────────
BG        = "#080b10"
BG2       = "#0d1220"
BG3       = "#111827"
BORDER    = "#1a2540"
BLUE      = "#1565ff"
LBLUE     = "#4d8aff"
BLUE_DIM  = "#0d3a99"
RED       = "#ff4d6d"
AMBER     = "#f59e0b"
GREEN     = "#22c55e"
TXT       = "#e8edf8"
TXT2      = "#8899bb"
MUTED     = "#4a5a7a"

API_BASE  = "http://10.0.2.202:8080/api/v1"

# ── Stylesheet global ─────────────────────────────────────────────────────────
STYLE = f"""
* {{
    font-family: 'Segoe UI', 'Ubuntu', 'Helvetica Neue', sans-serif;
    font-size: 13px;
    color: {TXT};
}}
QMainWindow, QWidget {{
    background-color: {BG};
}}
QLabel {{
    background: transparent;
}}
/* ── Sidebar ── */
QWidget#sidebar {{
    background-color: {BG2};
    border-right: 1px solid {BORDER};
}}
QPushButton#nav_btn {{
    background-color: transparent;
    color: {TXT2};
    border: none;
    border-radius: 6px;
    text-align: left;
    padding: 10px 16px;
    font-size: 13px;
}}
QPushButton#nav_btn:hover {{
    background-color: {BORDER};
    color: {TXT};
}}
QPushButton#nav_btn_active {{
    background-color: {BLUE_DIM};
    color: {LBLUE};
    border: none;
    border-radius: 6px;
    text-align: left;
    padding: 10px 16px;
    font-size: 13px;
    font-weight: bold;
}}
/* ── Cards ── */
QFrame#card {{
    background-color: {BG2};
    border: 1px solid {BORDER};
    border-radius: 8px;
}}
QFrame#card_blue {{
    background-color: {BLUE_DIM};
    border: 1px solid {BLUE}55;
    border-radius: 8px;
}}
/* ── Inputs ── */
QLineEdit, QTextEdit, QComboBox, QSpinBox, QDoubleSpinBox {{
    background-color: {BG2};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 6px 10px;
    color: {TXT};
    min-height: 32px;
    selection-background-color: {BLUE}66;
}}
QLineEdit:focus, QTextEdit:focus, QComboBox:focus {{
    border: 1px solid {BLUE}99;
}}
QComboBox::drop-down {{ border: none; width: 24px; }}
QComboBox QAbstractItemView {{
    background-color: {BG2};
    border: 1px solid {BORDER};
    color: {TXT};
    selection-background-color: {BLUE}44;
    outline: none;
}}
QDateEdit {{
    background-color: {BG2};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 6px 10px;
    color: {TXT};
    min-height: 32px;
}}
QDateEdit:focus {{ border: 1px solid {BLUE}99; }}
QDateEdit::drop-down {{ border: none; width: 24px; }}
QCalendarWidget {{
    background-color: {BG2};
    color: {TXT};
}}
/* ── Boutons ── */
QPushButton#btn_primary {{
    background-color: {BLUE};
    color: #fff;
    border: none;
    border-radius: 6px;
    padding: 8px 20px;
    font-weight: bold;
    min-height: 34px;
}}
QPushButton#btn_primary:hover {{ background-color: {LBLUE}; }}
QPushButton#btn_primary:disabled {{ background-color: {BORDER}; color: {MUTED}; }}
QPushButton#btn_secondary {{
    background-color: transparent;
    color: {TXT2};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 8px 20px;
    min-height: 34px;
}}
QPushButton#btn_secondary:hover {{ color: {TXT}; border-color: {TXT2}; }}
QPushButton#btn_danger {{
    background-color: {RED}22;
    color: {RED};
    border: 1px solid {RED}44;
    border-radius: 6px;
    padding: 8px 20px;
    min-height: 34px;
}}
QPushButton#btn_danger:hover {{ background-color: {RED}44; }}
QPushButton#btn_icon {{
    background-color: transparent;
    border: none;
    color: {TXT2};
    padding: 4px;
    border-radius: 4px;
}}
QPushButton#btn_icon:hover {{ background-color: {BORDER}; color: {TXT}; }}
/* ── Tables ── */
QTableWidget {{
    background-color: {BG};
    border: 1px solid {BORDER};
    border-radius: 8px;
    gridline-color: {BORDER};
    outline: none;
}}
QTableWidget::item {{
    padding: 8px 12px;
    border: none;
    color: {TXT};
}}
QTableWidget::item:selected {{
    background-color: {BLUE}33;
    color: {TXT};
}}
QHeaderView::section {{
    background-color: {BG2};
    color: {TXT2};
    border: none;
    border-bottom: 1px solid {BORDER};
    padding: 8px 12px;
    font-weight: bold;
    font-size: 12px;
    text-transform: uppercase;
    letter-spacing: 1px;
}}
QTableWidget::item:alternate {{ background-color: {BG2}; }}
/* ── Scrollbars ── */
QScrollBar:vertical {{
    background: {BG};
    width: 6px;
    border-radius: 3px;
}}
QScrollBar::handle:vertical {{
    background: {BORDER};
    border-radius: 3px;
    min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{ background: {MUTED}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar:horizontal {{
    background: {BG};
    height: 6px;
    border-radius: 3px;
}}
QScrollBar::handle:horizontal {{
    background: {BORDER};
    border-radius: 3px;
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}
/* ── Tabs ── */
QTabWidget::pane {{
    border: 1px solid {BORDER};
    border-radius: 8px;
    background: {BG};
    top: -1px;
}}
QTabBar::tab {{
    background: transparent;
    color: {TXT2};
    padding: 8px 20px;
    border: none;
    border-bottom: 2px solid transparent;
    margin-right: 4px;
}}
QTabBar::tab:selected {{
    color: {LBLUE};
    border-bottom: 2px solid {BLUE};
}}
QTabBar::tab:hover {{ color: {TXT}; }}
/* ── Séparateurs ── */
QFrame[frameShape="4"], QFrame[frameShape="5"] {{
    color: {BORDER};
}}
/* ── Tooltips ── */
QToolTip {{
    background-color: {BG2};
    color: {TXT};
    border: 1px solid {BORDER};
    padding: 4px 8px;
    border-radius: 4px;
}}
/* ── MessageBox ── */
QMessageBox {{
    background-color: {BG2};
}}
QMessageBox QPushButton {{
    background-color: {BLUE};
    color: #fff;
    border: none;
    border-radius: 6px;
    padding: 6px 16px;
    min-width: 80px;
}}
"""
