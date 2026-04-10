# -*- coding: utf-8 -*-
"""
SmartHub — Vue Atelier
Fiches d'intervention + Rapports Data Shredding
"""
import os
from datetime import date
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QTableWidget, QTableWidgetItem, QHeaderView, QPushButton,
    QDialog, QFormLayout, QLineEdit, QComboBox, QTextEdit,
    QDialogButtonBox, QDoubleSpinBox, QTabWidget, QMessageBox,
    QFileDialog, QSizePolicy, QScrollArea
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QDesktopServices
from PyQt6.QtCore import QUrl
from ..theme import *
from ..api import api
from ..widgets import SectionTitle, StatusPill
from ..pdf_generator import generate_fiche_intervention, generate_shredding_report


# ── Fiche d'intervention Dialog ────────────────────────────────────────────────
class FicheInterventionDialog(QDialog):
    def __init__(self, parent=None, clients=None, data=None):
        super().__init__(parent)
        self.setWindowTitle("Fiche d'intervention" if not data else "Modifier la fiche")
        self.setMinimumSize(680, 700)
        self.setStyleSheet(f"background:{BG2};")
        self._clients = clients or []

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0,0,0,0)

        hdr = QWidget(); hdr.setStyleSheet(f"background:{BLUE};")
        hl = QHBoxLayout(hdr); hl.setContentsMargins(20,12,20,12)
        t = QLabel("🔧  Fiche d'intervention atelier"); t.setStyleSheet("color:white;font-size:14px;font-weight:bold;")
        hl.addWidget(t)
        lay.addWidget(hdr)

        scroll = QScrollArea(); scroll.setWidgetResizable(True); scroll.setFrameShape(QFrame.Shape.NoFrame)
        body = QWidget(); body.setStyleSheet(f"background:{BG2};")
        form = QFormLayout(body); form.setContentsMargins(20,16,20,16); form.setSpacing(10)

        def lbl(t): l=QLabel(t);l.setStyleSheet(f"color:{TXT2};");return l

        self.cmb_client = QComboBox()
        for c in self._clients:
            self.cmb_client.addItem(c["name"], c["id"])
        form.addRow(lbl("Client *"), self.cmb_client)

        self.inp_machine_type = QComboBox()
        self.inp_machine_type.addItems(["Laptop","Desktop","Serveur","NAS","Switch","Imprimante","Tablette","Téléphone","Autre"])
        form.addRow(lbl("Type appareil"), self.inp_machine_type)

        row_machine = QHBoxLayout()
        self.inp_marque = QLineEdit(); self.inp_marque.setPlaceholderText("Marque")
        self.inp_modele = QLineEdit(); self.inp_modele.setPlaceholderText("Modèle")
        self.inp_serie  = QLineEdit(); self.inp_serie.setPlaceholderText("N° série")
        row_machine.addWidget(self.inp_marque); row_machine.addWidget(self.inp_modele); row_machine.addWidget(self.inp_serie)
        form.addRow(lbl("Marque / Modèle / Série"), row_machine)

        self.inp_symptomes = QTextEdit(); self.inp_symptomes.setFixedHeight(60)
        self.inp_symptomes.setPlaceholderText("Description du problème rapporté par le client...")
        form.addRow(lbl("Symptômes *"), self.inp_symptomes)

        self.inp_diagnostic = QTextEdit(); self.inp_diagnostic.setFixedHeight(60)
        self.inp_diagnostic.setPlaceholderText("Diagnostic technique établi...")
        form.addRow(lbl("Diagnostic"), self.inp_diagnostic)

        self.inp_travaux = QTextEdit(); self.inp_travaux.setFixedHeight(80)
        self.inp_travaux.setPlaceholderText("Un travail par ligne...")
        form.addRow(lbl("Travaux effectués"), self.inp_travaux)

        self.inp_pieces = QTextEdit(); self.inp_pieces.setFixedHeight(70)
        self.inp_pieces.setPlaceholderText("Format : Désignation | Référence | Prix\nEx: SSD Samsung 870 EVO 512GB | MZ-77E512B | 89.00")
        form.addRow(lbl("Pièces utilisées"), self.inp_pieces)

        self.spin_heures = QDoubleSpinBox(); self.spin_heures.setRange(0,99); self.spin_heures.setSuffix(" h"); self.spin_heures.setSingleStep(0.25)
        form.addRow(lbl("Temps main d'œuvre"), self.spin_heures)

        self.spin_tarif = QDoubleSpinBox(); self.spin_tarif.setRange(0,999); self.spin_tarif.setValue(81.25); self.spin_tarif.setSuffix(" €/h")
        form.addRow(lbl("Tarif horaire"), self.spin_tarif)

        self.cmb_statut = QComboBox()
        self.cmb_statut.addItems(["En diagnostic","En cours","En attente pièces","Terminé","Rendu client","Irréparable"])
        form.addRow(lbl("Statut"), self.cmb_statut)

        self.inp_notes = QTextEdit(); self.inp_notes.setFixedHeight(50)
        self.inp_notes.setPlaceholderText("Notes internes...")
        form.addRow(lbl("Notes"), self.inp_notes)

        # Préremplir si édition
        if data:
            m = data.get("machine",{})
            self.inp_marque.setText(m.get("marque",""))
            self.inp_modele.setText(m.get("modele",""))
            self.inp_serie.setText(m.get("serie",""))
            self.inp_symptomes.setPlainText(data.get("symptomes",""))
            self.inp_diagnostic.setPlainText(data.get("diagnostic",""))
            self.inp_travaux.setPlainText("\n".join(data.get("travaux",[])))
            self.spin_heures.setValue(data.get("temps_main_oeuvre",0))
            self.cmb_statut.setCurrentText(data.get("statut","En cours"))
            self.inp_notes.setPlainText(data.get("notes",""))

        scroll.setWidget(body)
        lay.addWidget(scroll, 1)

        footer = QWidget(); footer.setStyleSheet(f"background:{BG};border-top:1px solid {BORDER};")
        fl = QHBoxLayout(footer); fl.setContentsMargins(16,10,16,10); fl.setSpacing(8)
        btn_pdf = QPushButton("⬇ Générer PDF fiche"); btn_pdf.setObjectName("btn_secondary")
        btn_pdf.clicked.connect(self._gen_pdf)
        fl.addWidget(btn_pdf); fl.addStretch()
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.button(QDialogButtonBox.StandardButton.Ok).setText("Enregistrer")
        btns.button(QDialogButtonBox.StandardButton.Ok).setObjectName("btn_primary")
        btns.button(QDialogButtonBox.StandardButton.Cancel).setObjectName("btn_secondary")
        btns.accepted.connect(self.accept); btns.rejected.connect(self.reject)
        fl.addWidget(btns)
        lay.addWidget(footer)

    def get_data(self):
        pieces = []
        for line in self.inp_pieces.toPlainText().splitlines():
            parts = [p.strip() for p in line.split("|")]
            if len(parts) >= 1 and parts[0]:
                pieces.append({
                    "designation": parts[0],
                    "ref":         parts[1] if len(parts) > 1 else "",
                    "prix":        float(parts[2]) if len(parts) > 2 else 0.0,
                })
        client = self.cmb_client.currentData()
        return {
            "client_id":          client,
            "client_name":        self.cmb_client.currentText(),
            "machine": {
                "marque": self.inp_marque.text().strip(),
                "modele": self.inp_modele.text().strip(),
                "serie":  self.inp_serie.text().strip(),
                "type":   self.inp_machine_type.currentText(),
            },
            "symptomes":          self.inp_symptomes.toPlainText().strip(),
            "diagnostic":         self.inp_diagnostic.toPlainText().strip(),
            "travaux":            [l.strip() for l in self.inp_travaux.toPlainText().splitlines() if l.strip()],
            "pieces":             pieces,
            "temps_main_oeuvre":  self.spin_heures.value(),
            "tarif_horaire":      self.spin_tarif.value(),
            "statut":             self.cmb_statut.currentText(),
            "notes":              self.inp_notes.toPlainText().strip(),
        }

    def _gen_pdf(self):
        data = self.get_data()
        ref = f"FI-{date.today().strftime('%Y%m%d')}-001"
        data["reference"] = ref
        data["date_reception"] = date.today().strftime("%d/%m/%Y")
        data["technicien"] = "Mathieu Pleitinx"
        data["client"] = {"nom": self.cmb_client.currentText()}

        path, _ = QFileDialog.getSaveFileName(self, "Enregistrer la fiche", f"{ref}.pdf", "PDF (*.pdf)")
        if not path: return
        try:
            generate_fiche_intervention(path, data)
            QDesktopServices.openUrl(QUrl.fromLocalFile(path))
        except Exception as e:
            QMessageBox.critical(self, "Erreur", str(e))


# ── Data Shredding Dialog ──────────────────────────────────────────────────────
class ShreddingDialog(QDialog):
    def __init__(self, parent=None, clients=None):
        super().__init__(parent)
        self.setWindowTitle("Rapport d'effacement sécurisé")
        self.setMinimumSize(700, 600)
        self.setStyleSheet(f"background:{BG2};")
        self._clients = clients or []

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0,0,0,0)

        hdr = QWidget(); hdr.setStyleSheet(f"background:{BLUE};")
        hl = QHBoxLayout(hdr); hl.setContentsMargins(20,12,20,12)
        t = QLabel("🗑️  Rapport Data Shredding certifié"); t.setStyleSheet("color:white;font-size:14px;font-weight:bold;")
        hl.addWidget(t)
        lay.addWidget(hdr)

        scroll = QScrollArea(); scroll.setWidgetResizable(True); scroll.setFrameShape(QFrame.Shape.NoFrame)
        body = QWidget(); body.setStyleSheet(f"background:{BG2};")
        form = QFormLayout(body); form.setContentsMargins(20,16,20,16); form.setSpacing(10)

        def lbl(t): l=QLabel(t);l.setStyleSheet(f"color:{TXT2};");return l

        self.cmb_client = QComboBox()
        for c in self._clients:
            self.cmb_client.addItem(c["name"], c["id"])
        form.addRow(lbl("Client *"), self.cmb_client)

        self.inp_date = QLineEdit(date.today().strftime("%d/%m/%Y"))
        form.addRow(lbl("Date opération"), self.inp_date)

        self.cmb_methode = QComboBox()
        self.cmb_methode.addItems(["DoD 5220.22-M (3 passes)","NIST 800-88 (Purge)","Gutmann (35 passes)","Single Pass Overwrite","Secure Erase (ATA)"])
        form.addRow(lbl("Méthode"), self.cmb_methode)

        self.chk_onsite = QComboBox()
        self.chk_onsite.addItems(["Non – En atelier", "Oui – Sur site client"])
        form.addRow(lbl("Lieu"), self.chk_onsite)

        # Tableau supports
        lbl_sup = QLabel("Supports à effacer"); lbl_sup.setStyleSheet(f"color:{LBLUE};font-weight:bold;")
        form.addRow(lbl_sup)

        self.tbl_sup = QTableWidget(0, 6)
        self.tbl_sup.setHorizontalHeaderLabels(["Type","Marque / Modèle","N° Série","Capacité","Passes","Hash SHA-256"])
        self.tbl_sup.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.tbl_sup.setAlternatingRowColors(True)
        self.tbl_sup.setMinimumHeight(180)
        form.addRow(self.tbl_sup)

        btn_add_sup = QPushButton("+ Ajouter un support"); btn_add_sup.setObjectName("btn_secondary")
        btn_add_sup.clicked.connect(self._add_support)
        form.addRow(btn_add_sup)

        self.inp_notes = QTextEdit(); self.inp_notes.setFixedHeight(50)
        self.inp_notes.setPlaceholderText("Observations, conditions particulières...")
        form.addRow(lbl("Notes"), self.inp_notes)

        scroll.setWidget(body)
        lay.addWidget(scroll, 1)

        footer = QWidget(); footer.setStyleSheet(f"background:{BG};border-top:1px solid {BORDER};")
        fl = QHBoxLayout(footer); fl.setContentsMargins(16,10,16,10)
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.button(QDialogButtonBox.StandardButton.Ok).setText("⬇ Générer le rapport PDF")
        btns.button(QDialogButtonBox.StandardButton.Ok).setObjectName("btn_primary")
        btns.button(QDialogButtonBox.StandardButton.Cancel).setObjectName("btn_secondary")
        btns.accepted.connect(self._generate); btns.rejected.connect(self.reject)
        fl.addWidget(btns)
        lay.addWidget(footer)

        # Ajouter ligne par défaut
        self._add_support()

    def _add_support(self):
        r = self.tbl_sup.rowCount(); self.tbl_sup.insertRow(r)
        type_combo = QComboBox()
        type_combo.addItems(["HDD","SSD","USB","SD Card","NVMe","Server/NAS"])
        self.tbl_sup.setCellWidget(r, 0, type_combo)
        for col in range(1,6):
            defaults = ["","","","3",""]
            item = QTableWidgetItem(defaults[col-1])
            self.tbl_sup.setItem(r, col, item)

    def _generate(self):
        ref = f"DS-{date.today().strftime('%Y%m%d')}-001"
        supports = []
        for r in range(self.tbl_sup.rowCount()):
            type_w = self.tbl_sup.cellWidget(r, 0)
            s_type = type_w.currentText() if type_w else ""
            def cell(c): return (self.tbl_sup.item(r,c) or QTableWidgetItem("")).text().strip()
            if cell(1) or s_type:
                mm_parts = cell(1).split("/",1)
                supports.append({
                    "type":          s_type,
                    "marque":        mm_parts[0].strip() if mm_parts else "",
                    "modele":        mm_parts[1].strip() if len(mm_parts)>1 else "",
                    "marque_modele": cell(1),
                    "serie":         cell(2),
                    "capacite":      cell(3),
                    "passes":        cell(4) or "3",
                    "resultat":      "OK",
                    "hash":          cell(5),
                })

        if not supports:
            QMessageBox.warning(self, "Erreur", "Ajoutez au moins un support.")
            return

        data = {
            "client":         {"nom": self.cmb_client.currentText()},
            "reference":      ref,
            "date_operation": self.inp_date.text(),
            "technicien":     "Mathieu Pleitinx",
            "methode":        self.cmb_methode.currentText(),
            "on_site":        self.chk_onsite.currentIndex() == 1,
            "supports":       supports,
            "notes":          self.inp_notes.toPlainText().strip() or None,
        }

        path, _ = QFileDialog.getSaveFileName(self, "Enregistrer le rapport", f"{ref}.pdf", "PDF (*.pdf)")
        if not path: return
        try:
            generate_shredding_report(path, data)
            QDesktopServices.openUrl(QUrl.fromLocalFile(path))
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Erreur", str(e))


# ── Vue Atelier principale ─────────────────────────────────────────────────────
class AtelierView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._workers = []
        self._fiches = []
        self._clients = []
        self._build_ui()
        self._load_clients()

    def _build_ui(self):
        main = QVBoxLayout(self)
        main.setContentsMargins(0,0,0,0)
        main.setSpacing(0)

        # Toolbar
        toolbar = QWidget(); toolbar.setStyleSheet(f"background:{BG};border-bottom:1px solid {BORDER};")
        tb = QHBoxLayout(toolbar); tb.setContentsMargins(24,12,24,12); tb.setSpacing(10)
        tb.addWidget(SectionTitle("Atelier"))
        tb.addStretch()

        btn_fi = QPushButton("🔧 Nouvelle fiche intervention")
        btn_fi.setObjectName("btn_primary")
        btn_fi.clicked.connect(self._new_fiche)
        tb.addWidget(btn_fi)

        btn_ds = QPushButton("🗑️ Data Shredding")
        btn_ds.setObjectName("btn_secondary")
        btn_ds.clicked.connect(self._new_shredding)
        tb.addWidget(btn_ds)

        main.addWidget(toolbar)

        # Tabs
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet(f"QTabWidget::pane{{border:none;background:{BG};}}")

        # Tab Interventions
        inter_w = QWidget(); inter_w.setStyleSheet(f"background:{BG};")
        il = QVBoxLayout(inter_w); il.setContentsMargins(20,16,20,16)

        # Stats rapides
        stats_row = QHBoxLayout(); stats_row.setSpacing(12)
        self._stat_labels = {}
        for key, label, color in [("en_cours","En cours",LBLUE),("en_attente","En attente pièces",AMBER),("termine","Terminés",GREEN)]:
            f = QFrame(); f.setObjectName("card"); f.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            fl = QVBoxLayout(f); fl.setContentsMargins(14,10,14,10); fl.setSpacing(2)
            v = QLabel("0"); v.setStyleSheet(f"color:{color};font-size:22px;font-weight:bold;")
            l = QLabel(label); l.setStyleSheet(f"color:{TXT2};font-size:11px;")
            fl.addWidget(v); fl.addWidget(l)
            self._stat_labels[key] = v
            stats_row.addWidget(f)
        il.addLayout(stats_row)
        il.addWidget(QLabel(""))  # spacer

        self.tbl_inter = QTableWidget(0, 6)
        self.tbl_inter.setHorizontalHeaderLabels(["Réf.", "Client", "Appareil", "Statut", "Heures", "Total"])
        self.tbl_inter.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.tbl_inter.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.tbl_inter.setAlternatingRowColors(True)
        self.tbl_inter.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tbl_inter.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tbl_inter.verticalHeader().setVisible(False)
        self.tbl_inter.setShowGrid(False)
        self.tbl_inter.doubleClicked.connect(self._edit_fiche)
        il.addWidget(self.tbl_inter)

        self.tabs.addTab(inter_w, "🔧  Interventions")

        # Tab Data Shredding (historique)
        shred_w = QWidget(); shred_w.setStyleSheet(f"background:{BG};")
        sl = QVBoxLayout(shred_w); sl.setContentsMargins(20,16,20,16)

        info = QLabel("📋  Les rapports Data Shredding sont générés en PDF et archivés localement.\nCliquez sur 'Data Shredding' dans la barre pour créer un nouveau rapport certifié.")
        info.setStyleSheet(f"color:{TXT2};font-size:13px;padding:20px;")
        info.setWordWrap(True)
        sl.addWidget(info)

        # Grille tarifaire shredding
        grille = QFrame(); grille.setObjectName("card")
        gl = QVBoxLayout(grille); gl.setContentsMargins(16,12,16,12)
        gl.addWidget(QLabel("Grille tarifaire Data Shredding"))
        tarifs = [
            ("HDD / SSD (standard) – jusqu'à 1 TB",  "35,00 € HTVA / drive"),
            ("HDD / SSD (large) – plus de 1 TB",      "45,00 € HTVA / drive"),
            ("USB Stick / Carte SD (toute taille)",    "15,00 € HTVA / device"),
            ("Serveur / NAS (jusqu'à 4 baies)",        "90,00 € HTVA / système"),
            ("Rapport d'effacement certifié PDF",      "Offert"),
            ("Option déplacement on-site",             "85,00 € HTVA + tarif drive"),
        ]
        tbl_tarif = QTableWidget(len(tarifs), 2)
        tbl_tarif.setHorizontalHeaderLabels(["Prestation", "Prix HTVA"])
        tbl_tarif.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        tbl_tarif.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        tbl_tarif.verticalHeader().setVisible(False)
        tbl_tarif.setShowGrid(False)
        tbl_tarif.setAlternatingRowColors(True)
        for r, (label, prix) in enumerate(tarifs):
            tbl_tarif.setItem(r, 0, QTableWidgetItem(label))
            item_p = QTableWidgetItem(prix)
            item_p.setForeground(QColor(GREEN))
            tbl_tarif.setItem(r, 1, item_p)
        tbl_tarif.setFixedHeight(len(tarifs)*36 + 32)
        gl.addWidget(tbl_tarif)
        sl.addWidget(grille)
        sl.addStretch()

        self.tabs.addTab(shred_w, "🗑️  Data Shredding")
        main.addWidget(self.tabs)

    def _load_clients(self):
        w = api("GET", "/clients/summary", on_ok=lambda d: setattr(self, "_clients", d))
        self._workers.append(w)

    def _populate_table(self):
        self.tbl_inter.setRowCount(0)
        counts = {"en_cours": 0, "en_attente": 0, "termine": 0}
        for fi in self._fiches:
            statut = fi.get("statut","")
            if "attente" in statut.lower(): counts["en_attente"] += 1
            elif statut in ("Terminé","Rendu client"): counts["termine"] += 1
            else: counts["en_cours"] += 1

            r = self.tbl_inter.rowCount(); self.tbl_inter.insertRow(r)
            self.tbl_inter.setItem(r, 0, QTableWidgetItem(fi.get("reference","")))
            self.tbl_inter.setItem(r, 1, QTableWidgetItem(fi.get("client_name","")))
            m = fi.get("machine",{})
            self.tbl_inter.setItem(r, 2, QTableWidgetItem(f"{m.get('marque','')} {m.get('modele','')}".strip()))

            stat_item = QTableWidgetItem(statut)
            stat_colors = {"Terminé":GREEN,"Rendu client":GREEN,"En cours":LBLUE,
                           "En attente pièces":AMBER,"En diagnostic":TXT2,"Irréparable":RED}
            stat_item.setForeground(QColor(stat_colors.get(statut, TXT2)))
            self.tbl_inter.setItem(r, 3, stat_item)

            h = fi.get("temps_main_oeuvre", 0)
            self.tbl_inter.setItem(r, 4, QTableWidgetItem(f"{h:.1f}h"))
            mo = h * fi.get("tarif_horaire", 81.25)
            tp = sum(p.get("prix",0) for p in fi.get("pieces",[]))
            self.tbl_inter.setItem(r, 5, QTableWidgetItem(f"{(mo+tp):.2f} €"))
            self.tbl_inter.item(r, 0).setData(Qt.ItemDataRole.UserRole, fi)

        for key, lbl in self._stat_labels.items():
            lbl.setText(str(counts.get(key, 0)))

    def _new_fiche(self):
        dlg = FicheInterventionDialog(self, clients=self._clients)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            data = dlg.get_data()
            import random
            data["reference"] = f"FI-{date.today().strftime('%Y%m%d')}-{random.randint(100,999)}"
            self._fiches.append(data)
            self._populate_table()

    def _edit_fiche(self):
        r = self.tbl_inter.currentRow()
        if r < 0: return
        item = self.tbl_inter.item(r, 0)
        if not item: return
        fi = item.data(Qt.ItemDataRole.UserRole)
        if not fi: return
        dlg = FicheInterventionDialog(self, clients=self._clients, data=fi)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            data = dlg.get_data()
            data["reference"] = fi.get("reference","")
            idx = next((i for i, f in enumerate(self._fiches) if f.get("reference") == fi.get("reference")), -1)
            if idx >= 0: self._fiches[idx] = data
            self._populate_table()

    def _new_shredding(self):
        dlg = ShreddingDialog(self, clients=self._clients)
        dlg.exec()
