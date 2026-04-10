# -*- coding: utf-8 -*-
"""
SmartHub — Wizard de génération de contrat PDF
Tous types : LM IT, LM Cloud, LM Forensics, LM Dev, CM, Full Inclusive/Exclusive
"""
import os, tempfile
from datetime import date
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QPushButton, QComboBox, QLineEdit, QTextEdit, QFormLayout,
    QTabWidget, QWidget, QScrollArea, QDoubleSpinBox, QSpinBox,
    QCheckBox, QTableWidget, QTableWidgetItem, QHeaderView,
    QMessageBox, QFileDialog, QStackedWidget, QDateEdit,
    QSizePolicy
)
from PyQt6.QtCore import Qt, QDate, pyqtSignal, QThread
from PyQt6.QtGui import QColor, QDesktopServices
from PyQt6.QtCore import QUrl
from ..theme import *
from ..api import api
from ..pdf_generator import generate_lm, generate_maintenance

CONTRACT_TYPES = [
    ("gestion_it",        "📋 Lettre de mission – Gestion IT opérationnelle"),
    ("cloud",             "☁️  Lettre de mission – Infrastructure Cloud & serveurs"),
    ("full_inclusive",    "⭐ Lettre de mission – IT Full Inclusive (forfait)"),
    ("full_exclusive",    "🔄 Lettre de mission – IT Full Exclusive (régie)"),
    ("forensics",         "🔍 Lettre de mission – Forensics informatique"),
    ("dev",               "💻 Lettre de mission – Développement sur mesure"),
    ("recherche_donnees", "🗄️  Lettre de mission – Recherche / récupération données"),
    ("ponctuel",          "📝 Lettre de mission – Mission ponctuelle"),
    ("maintenance",       "🔧 Contrat de maintenance (avec SLA & annexes)"),
]

MISSIONS_DEFAULTS = {
    "gestion_it": [
        "Support et maintenance des postes fixes et portables.",
        "Support logiciels (outils métier) dans le cadre d'une obligation de moyens.",
        "Support messagerie et configuration des boîtes mail lorsque le service est opéré par un tiers.",
        "Gestion des infrastructures physiques : armoires réseau, NAS, périphériques.",
        "Coordination avec fournisseurs/éditeurs (ouverture et suivi de tickets, escalades).",
    ],
    "cloud": [
        "Serveur Docker / VPN (exploitation, supervision, maintenance).",
        "Serveur FreeIPA (identité, administration, politiques et services associés).",
        "Serveur Remote Desktop (administration système, disponibilité et supervision).",
        "Mises à jour planifiées et maintenance courante.",
        "Gestion technique des comptes Microsoft et FreeIPA.",
        "Attribution et retrait des licences Microsoft 365.",
    ],
    "full_inclusive": [
        "Support IT quotidien (logiciels, messagerie, assistance utilisateurs) en heures ouvrées.",
        "Coordination avec fournisseurs/éditeurs.",
        "Gestion des demandes utilisateurs (création/modification) selon procédure e-mail.",
        "Déplacements : visites selon planning incluses (si planifiées et consommées).",
        "Budget matériel : enveloppe budgétaire définie, utilisable pour matériel standard (accord préalable).",
    ],
    "full_exclusive": [
        "Aucun forfait mensuel : facturation au temps réellement presté.",
        "Déplacements facturés uniquement s'ils sont effectués.",
        "Matériel facturé au coût réel.",
        "Support IT selon besoins, sur base horaire.",
    ],
    "forensics": [
        "Analyse technique des supports de stockage des systèmes concernés.",
        "Recherche d'indices d'effacement ou de tentative d'effacement de données.",
        "Analyse des journaux systèmes et des éléments techniques pertinents.",
        "Documentation des constatations techniques effectuées.",
        "Rédaction d'un rapport factuel de forensics informatique.",
    ],
    "dev": [
        "Analyse des besoins et rédaction des spécifications fonctionnelles.",
        "Développement et implémentation de la solution.",
        "Tests et validation.",
        "Documentation technique et formation à l'utilisation.",
        "Support post-livraison (période à convenir).",
    ],
    "maintenance": [
        "Maintenance corrective des équipements listés en Annexe 1.",
        "Maintenance préventive planifiée (selon notices constructeurs).",
        "Service de garde passif en heures ouvrées.",
        "Support téléphonique et téléassistance.",
        "Rapport d'intervention via le système helpdesk.",
    ],
}


class MissionEditor(QWidget):
    """Éditeur de liste de missions avec ajout/suppression."""
    def __init__(self, defaults=None, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0,0,0,0)
        lay.setSpacing(4)

        self._rows = []
        self._lay = QVBoxLayout()
        self._lay.setSpacing(4)
        lay.addLayout(self._lay)

        btn_add = QPushButton("+ Ajouter une mission")
        btn_add.setObjectName("btn_secondary")
        btn_add.clicked.connect(self._add_row)
        lay.addWidget(btn_add)

        for d in (defaults or []):
            self._add_row(d)

    def _add_row(self, text=""):
        row = QHBoxLayout()
        inp = QLineEdit(text)
        inp.setPlaceholderText("Description de la mission...")
        btn_del = QPushButton("✕")
        btn_del.setObjectName("btn_icon")
        btn_del.setFixedWidth(28)
        row.addWidget(inp)
        row.addWidget(btn_del)

        container = QWidget()
        container.setLayout(row)
        self._lay.addWidget(container)
        self._rows.append((container, inp))
        btn_del.clicked.connect(lambda _, c=container, i=inp: self._del_row(c, i))

    def _del_row(self, container, inp):
        self._rows = [(c, i) for c, i in self._rows if c is not container]
        container.deleteLater()

    def get_missions(self):
        return [i.text().strip() for _, i in self._rows if i.text().strip()]


class DeviceTableEditor(QWidget):
    """Table éditable pour les dispositifs du contrat de maintenance."""
    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0,0,0,0)

        self.tbl = QTableWidget(0, 3)
        self.tbl.setHorizontalHeaderLabels(["Dispositif", "Description", "Qté"])
        self.tbl.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.tbl.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.tbl.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        self.tbl.setColumnWidth(2, 50)
        self.tbl.setAlternatingRowColors(True)
        lay.addWidget(self.tbl)

        btn_add = QPushButton("+ Ajouter un dispositif")
        btn_add.setObjectName("btn_secondary")
        btn_add.clicked.connect(self._add_row)
        lay.addWidget(btn_add)

    def _add_row(self):
        r = self.tbl.rowCount()
        self.tbl.insertRow(r)
        self.tbl.setItem(r, 2, QTableWidgetItem("1"))

    def get_devices(self):
        devs = []
        for r in range(self.tbl.rowCount()):
            nom  = (self.tbl.item(r,0) or QTableWidgetItem("")).text().strip()
            desc = (self.tbl.item(r,1) or QTableWidgetItem("")).text().strip()
            qty  = (self.tbl.item(r,2) or QTableWidgetItem("1")).text().strip()
            if nom:
                devs.append({"nom": nom, "description": desc, "quantite": qty})
        return devs


class ContractGeneratorDialog(QDialog):
    """Wizard complet de génération de contrat PDF."""

    def __init__(self, parent=None, clients=None, preselect_client=None):
        super().__init__(parent)
        self.setWindowTitle("Générer un document contractuel")
        self.setMinimumSize(780, 680)
        self.setStyleSheet(f"background:{BG2};")
        self._clients = clients or []
        self._output_path = None
        self._workers = []

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0,0,0,0)
        lay.setSpacing(0)

        # Header
        hdr = QWidget(); hdr.setStyleSheet(f"background:{BLUE};")
        hl = QHBoxLayout(hdr); hl.setContentsMargins(20,14,20,14)
        t = QLabel("📄  Nouveau document contractuel")
        t.setStyleSheet("color:white;font-size:15px;font-weight:bold;")
        hl.addWidget(t)
        lay.addWidget(hdr)

        # Body scroll
        scroll = QScrollArea(); scroll.setWidgetResizable(True); scroll.setFrameShape(QFrame.Shape.NoFrame)
        body = QWidget(); body.setStyleSheet(f"background:{BG2};")
        self._form = QVBoxLayout(body); self._form.setContentsMargins(24,20,24,12); self._form.setSpacing(12)
        scroll.setWidget(body)
        lay.addWidget(scroll, 1)

        self._build_form(preselect_client)

        # Footer
        footer = QWidget(); footer.setStyleSheet(f"background:{BG};border-top:1px solid {BORDER};")
        fl = QHBoxLayout(footer); fl.setContentsMargins(20,12,20,12); fl.setSpacing(10)
        self._lbl_status = QLabel("")
        self._lbl_status.setStyleSheet(f"color:{TXT2};font-size:12px;")
        fl.addWidget(self._lbl_status, 1)
        btn_cancel = QPushButton("Annuler"); btn_cancel.setObjectName("btn_secondary")
        btn_cancel.clicked.connect(self.reject)
        btn_gen = QPushButton("⚡ Générer le PDF"); btn_gen.setObjectName("btn_primary")
        btn_gen.clicked.connect(self._generate)
        fl.addWidget(btn_cancel); fl.addWidget(btn_gen)
        lay.addWidget(footer)

    def _lbl(self, t):
        l = QLabel(t); l.setStyleSheet(f"color:{TXT2};font-size:12px;min-width:160px;")
        return l

    def _section_title(self, t):
        l = QLabel(t); l.setStyleSheet(f"color:{LBLUE};font-size:13px;font-weight:bold;padding-top:8px;")
        return l

    def _build_form(self, preselect_client):
        f = self._form

        # Type de document
        f.addWidget(self._section_title("Type de document"))
        self.cmb_type = QComboBox()
        for key, label in CONTRACT_TYPES:
            self.cmb_type.addItem(label, key)
        self.cmb_type.currentIndexChanged.connect(self._on_type_change)
        f.addWidget(self.cmb_type)

        # Infos générales
        f.addWidget(self._section_title("Informations générales"))
        row_gen = QFormLayout(); row_gen.setSpacing(8)

        self.cmb_client = QComboBox()
        for c in self._clients:
            self.cmb_client.addItem(c["name"], c)
        if preselect_client:
            for i, c in enumerate(self._clients):
                if c.get("id") == preselect_client.get("id"):
                    self.cmb_client.setCurrentIndex(i); break
        row_gen.addRow(self._lbl("Client *"), self.cmb_client)

        self.inp_client_forme = QLineEdit("Besloten Vennootschap")
        row_gen.addRow(self._lbl("Forme juridique"), self.inp_client_forme)
        self.inp_client_vat = QLineEdit()
        self.inp_client_vat.setPlaceholderText("BE0123456789")
        row_gen.addRow(self._lbl("N° TVA client"), self.inp_client_vat)
        self.inp_client_siege = QLineEdit()
        self.inp_client_siege.setPlaceholderText("Rue, Ville")
        row_gen.addRow(self._lbl("Siège social client"), self.inp_client_siege)
        self.inp_client_rep = QLineEdit()
        self.inp_client_rep.setPlaceholderText("Prénom Nom, Fonction")
        row_gen.addRow(self._lbl("Représentant client"), self.inp_client_rep)

        self.inp_ref = QLineEdit()
        self.inp_ref.setPlaceholderText("LM-XXX-2026-001 (laissez vide pour auto)")
        row_gen.addRow(self._lbl("Référence"), self.inp_ref)
        self.inp_lieu = QLineEdit("Sint-Pieters-Leeuw")
        row_gen.addRow(self._lbl("Lieu de signature"), self.inp_lieu)
        self.date_doc = QDateEdit(); self.date_doc.setCalendarPopup(True)
        self.date_doc.setDate(QDate.currentDate())
        row_gen.addRow(self._lbl("Date du document"), self.date_doc)
        f.addLayout(row_gen)

        # Auto-remplir depuis client
        self.cmb_client.currentIndexChanged.connect(self._autofill_client)
        self._autofill_client()

        # Contexte
        f.addWidget(self._section_title("Contexte (exposé des motifs)"))
        self.inp_contexte = QTextEdit()
        self.inp_contexte.setFixedHeight(70)
        self.inp_contexte.setPlaceholderText("Le client souhaite confier au prestataire...")
        f.addWidget(self.inp_contexte)

        # Missions
        f.addWidget(self._section_title("Missions du prestataire"))
        self._mission_editor = MissionEditor(MISSIONS_DEFAULTS.get("gestion_it", []))
        f.addWidget(self._mission_editor)

        # Exclusions spécifiques
        f.addWidget(self._section_title("Exclusions spécifiques (optionnel)"))
        self.inp_exclusions = QTextEdit()
        self.inp_exclusions.setFixedHeight(55)
        self.inp_exclusions.setPlaceholderText("Une exclusion par ligne (laissez vide pour les exclusions par défaut)...")
        f.addWidget(self.inp_exclusions)

        # === Bloc tarifaire ===
        f.addWidget(self._section_title("Tarification"))
        tarif_form = QFormLayout(); tarif_form.setSpacing(8)

        self.spin_tarif = QDoubleSpinBox(); self.spin_tarif.setRange(0,999); self.spin_tarif.setValue(81.25)
        self.spin_tarif.setSuffix(" €/h HTVA"); self.spin_tarif.setDecimals(2)
        tarif_form.addRow(self._lbl("Tarif horaire"), self.spin_tarif)

        self.spin_install_poste = QDoubleSpinBox(); self.spin_install_poste.setRange(0,9999)
        self.spin_install_poste.setValue(150.0); self.spin_install_poste.setSuffix(" € HTVA")
        tarif_form.addRow(self._lbl("Installation poste"), self.spin_install_poste)

        self.spin_creation_user = QDoubleSpinBox(); self.spin_creation_user.setRange(0,9999)
        self.spin_creation_user.setValue(0); self.spin_creation_user.setSuffix(" € HTVA")
        self.spin_creation_user.setToolTip("0 = non affiché")
        tarif_form.addRow(self._lbl("Création utilisateur"), self.spin_creation_user)

        # Full Inclusive specifics
        self._fi_widget = QWidget()
        fi_lay = QFormLayout(self._fi_widget); fi_lay.setSpacing(8)
        self.spin_forfait = QDoubleSpinBox(); self.spin_forfait.setRange(0,99999); self.spin_forfait.setSuffix(" €/mois HTVA")
        fi_lay.addRow(self._lbl("Forfait mensuel"), self.spin_forfait)
        self.spin_budget_mat = QDoubleSpinBox(); self.spin_budget_mat.setRange(0,9999); self.spin_budget_mat.setSuffix(" €/mois HTVA")
        fi_lay.addRow(self._lbl("Budget matériel inclus"), self.spin_budget_mat)
        self.spin_visites = QSpinBox(); self.spin_visites.setRange(0,30); self.spin_visites.setSuffix(" visite(s)/mois/site")
        self.spin_visites.setValue(1)
        fi_lay.addRow(self._lbl("Visites incluses"), self.spin_visites)
        self._fi_widget.setVisible(False)
        tarif_form.addRow(self._fi_widget)

        # Maintenance specifics
        self._maint_tarif_widget = QWidget()
        mt_lay = QFormLayout(self._maint_tarif_widget); mt_lay.setSpacing(8)
        self.spin_garde_57 = QDoubleSpinBox(); self.spin_garde_57.setRange(0,9999); self.spin_garde_57.setValue(55.0); self.spin_garde_57.setSuffix(" €/sem")
        mt_lay.addRow(self._lbl("Garde 5/7 passif"), self.spin_garde_57)
        self.spin_garde_77 = QDoubleSpinBox(); self.spin_garde_77.setRange(0,9999); self.spin_garde_77.setValue(120.0); self.spin_garde_77.setSuffix(" €/sem")
        mt_lay.addRow(self._lbl("Garde 7/7 passif"), self.spin_garde_77)
        self.spin_preventif = QDoubleSpinBox(); self.spin_preventif.setRange(0,9999); self.spin_preventif.setValue(650.0); self.spin_preventif.setSuffix(" €/jour")
        mt_lay.addRow(self._lbl("Maintenance préventive"), self.spin_preventif)
        self.spin_deplacement = QDoubleSpinBox(); self.spin_deplacement.setRange(0,999); self.spin_deplacement.setValue(26.20); self.spin_deplacement.setSuffix(" €/dép.")
        mt_lay.addRow(self._lbl("Déplacement"), self.spin_deplacement)
        self.spin_interventions = QSpinBox(); self.spin_interventions.setRange(0,20); self.spin_interventions.setValue(4)
        mt_lay.addRow(self._lbl("Interventions offertes"), self.spin_interventions)
        self.spin_total_htva = QDoubleSpinBox(); self.spin_total_htva.setRange(0,999999); self.spin_total_htva.setSuffix(" € HTVA")
        mt_lay.addRow(self._lbl("Total annuel HTVA"), self.spin_total_htva)
        self._maint_tarif_widget.setVisible(False)
        tarif_form.addRow(self._maint_tarif_widget)

        f.addLayout(tarif_form)

        # Dispositifs (maintenance seulement)
        self._devices_section = QWidget()
        ds_lay = QVBoxLayout(self._devices_section); ds_lay.setContentsMargins(0,0,0,0)
        ds_lay.addWidget(self._section_title("Dispositifs sous contrat (Annexe 1)"))
        self._device_editor = DeviceTableEditor()
        ds_lay.addWidget(self._device_editor)
        self._devices_section.setVisible(False)
        f.addWidget(self._devices_section)

        # Durée
        f.addWidget(self._section_title("Durée du contrat"))
        dur_row = QHBoxLayout()
        self.cmb_duree = QComboBox()
        self.cmb_duree.addItems(["Durée indéterminée","Mission ponctuelle","Durée déterminée"])
        dur_row.addWidget(self.cmb_duree)
        self.inp_duree_texte = QLineEdit(); self.inp_duree_texte.setPlaceholderText("Ex: 1 an renouvelable")
        self.inp_duree_texte.setVisible(False)
        dur_row.addWidget(self.inp_duree_texte)
        self.cmb_duree.currentTextChanged.connect(
            lambda t: self.inp_duree_texte.setVisible(t == "Durée déterminée"))
        f.addLayout(dur_row)

        # Notes
        f.addWidget(self._section_title("Notes & conditions particulières"))
        self.inp_notes = QTextEdit(); self.inp_notes.setFixedHeight(60)
        self.inp_notes.setPlaceholderText("Conditions spécifiques, remarques...")
        f.addWidget(self.inp_notes)

    def _autofill_client(self):
        client = self.cmb_client.currentData()
        if not client: return
        self.inp_client_vat.setText(client.get("vat_number","") or "")
        self.inp_client_siege.setText(client.get("address","") or "")

    def _on_type_change(self):
        t = self.cmb_type.currentData()
        # Missions par défaut
        # Rebuild mission editor
        old = self._mission_editor
        new = MissionEditor(MISSIONS_DEFAULTS.get(t, []))
        self._form.replaceWidget(old, new)
        old.deleteLater()
        self._mission_editor = new

        # Show/hide blocs spécifiques
        self._fi_widget.setVisible(t == "full_inclusive")
        self._maint_tarif_widget.setVisible(t == "maintenance")
        self._devices_section.setVisible(t == "maintenance")

        # Contexte par défaut
        contexts = {
            "gestion_it":   "Le client souhaite confier au prestataire la gestion IT opérationnelle quotidienne de ses bureaux, incluant le support lié aux logiciels, à la messagerie, au matériel et aux infrastructures physiques.",
            "cloud":        "Le client souhaite disposer d'une infrastructure serveurs Cloud opérée par le prestataire afin de garantir la continuité de ses services IT et d'en assurer l'administration complète.",
            "full_inclusive":"Le client souhaite disposer d'une formule de gestion IT tout compris, afin de maîtriser son budget et de clarifier les modalités d'intervention.",
            "full_exclusive":"Le client souhaite bénéficier des services IT du prestataire sur base d'une facturation au temps réellement presté, sans forfait mensuel.",
            "forensics":    "Le client a constaté des faits laissant supposer une utilisation potentiellement non conforme de systèmes informatiques. Il souhaite procéder à une analyse technique afin d'évaluer l'état des données et d'identifier d'éventuels indices d'usage non conforme.",
            "dev":          "Le client souhaite confier au prestataire le développement d'une solution informatique sur mesure selon les spécifications définies conjointement.",
            "maintenance":  "Le client souhaite confier au prestataire la maintenance de son infrastructure informatique, incluant la maintenance corrective et préventive avec service de garde.",
        }
        if t in contexts and not self.inp_contexte.toPlainText().strip():
            self.inp_contexte.setPlainText(contexts[t])

    def _build_data(self):
        client_obj = self.cmb_client.currentData() or {}
        t = self.cmb_type.currentData()

        # Référence auto
        ref = self.inp_ref.text().strip()
        if not ref:
            type_codes = {"gestion_it":"LM-IT","cloud":"LM-CLD","full_inclusive":"LM-FI",
                          "full_exclusive":"LM-FX","forensics":"LM-FOR","dev":"LM-DEV",
                          "maintenance":"CM","ponctuel":"LM-PON","recherche_donnees":"LM-RD"}
            client_code = "".join(w[0] for w in (client_obj.get("name","XXX")).split()[:3]).upper()
            year = date.today().year
            ref = f"{type_codes.get(t,'LM')}-{client_code}-{year}-001"

        client_data = {
            "nom":          client_obj.get("name",""),
            "forme":        self.inp_client_forme.text().strip(),
            "nentreprise":  self.inp_client_vat.text().strip(),
            "siege":        self.inp_client_siege.text().strip(),
            "representant": self.inp_client_rep.text().strip(),
            "email":        client_obj.get("email","") or "",
        }

        excl_raw = self.inp_exclusions.toPlainText().strip()
        exclusions = [l.strip() for l in excl_raw.splitlines() if l.strip()] if excl_raw else None

        duree_map = {"Durée indéterminée":"indeterminee","Mission ponctuelle":"ponctuelle","Durée déterminée":"determinee"}

        data = {
            "client":        client_data,
            "type":          t,
            "reference":     ref,
            "date_doc":      self.date_doc.date().toString("dd/MM/yyyy"),
            "lieu":          self.inp_lieu.text().strip(),
            "contexte":      self.inp_contexte.toPlainText().strip(),
            "missions":      self._mission_editor.get_missions(),
            "exclusions":    exclusions,
            "tarif_horaire": self.spin_tarif.value(),
            "installation_poste": self.spin_install_poste.value() or None,
            "creation_user_prix": self.spin_creation_user.value() or None,
            "duree":         duree_map.get(self.cmb_duree.currentText(),"indeterminee"),
            "duree_texte":   self.inp_duree_texte.text().strip(),
            "notes":         self.inp_notes.toPlainText().strip() or None,
        }

        if t == "full_inclusive":
            data["forfait_mensuel"]  = self.spin_forfait.value() or None
            data["budget_materiel"]  = self.spin_budget_mat.value() or None
            data["inclus_visites"]   = self.spin_visites.value() or None

        if t == "maintenance":
            data["tarif_garde_5_7"]   = self.spin_garde_57.value()
            data["tarif_garde_7_7"]   = self.spin_garde_77.value()
            data["tarif_preventif"]   = self.spin_preventif.value()
            data["tarif_deplacement"] = self.spin_deplacement.value()
            data["nb_interventions_offertes"] = self.spin_interventions.value()
            data["total_htva"]        = self.spin_total_htva.value()
            data["dispositifs"]       = self._device_editor.get_devices()
            data["duree_ans"]         = 1

        return data

    def _generate(self):
        data = self._build_data()
        if not data["client"]["nom"]:
            QMessageBox.warning(self, "Erreur", "Veuillez sélectionner un client.")
            return

        # Proposer où sauvegarder
        ref = data["reference"]
        default_name = f"{ref}.pdf"
        path, _ = QFileDialog.getSaveFileName(
            self, "Enregistrer le PDF", default_name, "PDF (*.pdf)")
        if not path:
            return

        self._lbl_status.setText("⏳ Génération en cours...")
        try:
            t = data["type"]
            if t == "maintenance":
                generate_maintenance(path, data)
            else:
                generate_lm(path, data)

            self._output_path = path
            self._lbl_status.setText(f"✅ PDF généré : {os.path.basename(path)}")

            reply = QMessageBox.question(
                self, "PDF généré",
                f"Le document a été généré :\n{path}\n\nVoulez-vous l'ouvrir ?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                QDesktopServices.openUrl(QUrl.fromLocalFile(path))

            self.accept()
        except Exception as e:
            self._lbl_status.setText(f"❌ Erreur : {str(e)[:80]}")
            QMessageBox.critical(self, "Erreur de génération", str(e))
