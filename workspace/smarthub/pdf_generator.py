# -*- coding: utf-8 -*-
"""
SmartHub - Generateur PDF contrats & lettres de mission
ReportLab - Logo Smartclick - Tous types de documents
"""
import os
from datetime import date
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, PageBreak, KeepTogether
)
from reportlab.platypus.flowables import Flowable
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# Palette Smartclick
SC_BLUE   = colors.HexColor("#1565ff")
SC_LBLUE  = colors.HexColor("#4d8aff")
SC_DARK   = colors.HexColor("#080b10")
SC_GREY   = colors.HexColor("#4a5a7a")
SC_LGREY  = colors.HexColor("#e8edf8")
SC_WHITE  = colors.white
SC_BLACK  = colors.HexColor("#1a1a2e")

W, H = A4  # 595.27 x 841.89 pt

# ── Smartclick info ────────────────────────────────────────────────────────────
PRESTATAIRE = {
    "nom":       "Smartclick S.R.L.",
    "forme":     "Société à Responsabilité Limitée",
    "nentreprise": "0746.385.009",
    "siege":     "Brugstraat 22 – 1601 Sint-Pieters-Leeuw",
    "email":     "mathieu.pleitinx@smartclick.be",
    "tel":       "+32 475 43 10 01",
    "representant": "Mathieu Pleitinx",
    "titre":     "Gérant",
}

# ── Styles ─────────────────────────────────────────────────────────────────────
def make_styles():
    s = getSampleStyleSheet()
    base = dict(fontName="Helvetica", fontSize=9, leading=13,
                textColor=SC_BLACK, spaceAfter=4)

    def st(name, **kw):
        d = {**base, **kw}
        return ParagraphStyle(name, **d)

    return {
        "title_doc":   st("title_doc",   fontName="Helvetica-Bold", fontSize=22,
                          textColor=SC_BLUE, spaceAfter=2, leading=26),
        "subtitle":    st("subtitle",    fontName="Helvetica-Bold", fontSize=13,
                          textColor=SC_BLACK, spaceAfter=2),
        "subtitle2":   st("subtitle2",   fontName="Helvetica", fontSize=11,
                          textColor=SC_GREY, spaceAfter=12),
        "section":     st("section",     fontName="Helvetica-Bold", fontSize=11,
                          textColor=SC_BLUE, spaceBefore=10, spaceAfter=4),
        "subsection":  st("subsection",  fontName="Helvetica-Bold", fontSize=9.5,
                          textColor=SC_BLACK, spaceBefore=6, spaceAfter=3),
        "body":        st("body",        alignment=TA_JUSTIFY, leading=14),
        "body_bold":   st("body_bold",   fontName="Helvetica-Bold"),
        "bullet":      st("bullet",      leftIndent=14, firstLineIndent=-8,
                          spaceAfter=3),
        "small":       st("small",       fontSize=8, textColor=SC_GREY),
        "sign_label":  st("sign_label",  fontName="Helvetica-Bold", fontSize=9),
        "sign_name":   st("sign_name",   fontSize=9, textColor=SC_GREY),
        "header_label":st("header_label",fontSize=8, textColor=SC_GREY),
        "header_val":  st("header_val",  fontSize=9, fontName="Helvetica-Bold"),
        "annex_title": st("annex_title", fontName="Helvetica-Bold", fontSize=11,
                          textColor=SC_WHITE),
        "center":      st("center",      alignment=TA_CENTER, fontName="Helvetica-Bold"),
        "right":       st("right",       alignment=TA_RIGHT, fontSize=8, textColor=SC_GREY),
    }

STYLES = make_styles()


# ── Helpers ────────────────────────────────────────────────────────────────────
def hr(color=SC_BLUE, thickness=0.8, space_before=6, space_after=6):
    return HRFlowable(width="100%", thickness=thickness, color=color,
                      spaceAfter=space_after, spaceBefore=space_before)

def sp(h=4):
    return Spacer(1, h)

def para(text, style="body"):
    return Paragraph(text, STYLES[style])

def bullet_item(text):
    return Paragraph(f"• &nbsp; {text}", STYLES["bullet"])

def section(num, title):
    return para(f"{num}. {title}", "section")

def subsection(title):
    return para(title, "subsection")

def parties_block(prestataire, client):
    """Tableau parties contractantes."""
    def party_cell(p, label):
        lines = [
            f"<b>{p['nom']}</b>",
            p.get('forme', ''),
            f"N° d'entreprise : {p.get('nentreprise','')}",
            f"Siège social : {p.get('siege','')}",
        ]
        if p.get('representant'):
            lines.append(f"Représentée par : {p['representant']}")
        if p.get('email'):
            lines.append(p['email'])
        content = "<br/>".join(l for l in lines if l.strip())
        return [
            Paragraph(f"<b>{label}</b>", STYLES["small"]),
            sp(3),
            Paragraph(content, STYLES["body"]),
        ]

    data = [[
        party_cell(prestataire, "LE PRESTATAIRE"),
        party_cell(client, "LE CLIENT"),
    ]]
    t = Table(data, colWidths=[W*0.44, W*0.44])
    t.setStyle(TableStyle([
        ("VALIGN", (0,0), (-1,-1), "TOP"),
        ("LEFTPADDING",  (0,0), (-1,-1), 10),
        ("RIGHTPADDING", (0,0), (-1,-1), 10),
        ("TOPPADDING",   (0,0), (-1,-1), 8),
        ("BOTTOMPADDING",(0,0), (-1,-1), 8),
        ("BOX", (0,0), (0,0), 0.5, SC_LBLUE),
        ("BOX", (1,0), (1,0), 0.5, SC_LBLUE),
        ("BACKGROUND", (0,0), (0,0), colors.HexColor("#f0f4ff")),
        ("BACKGROUND", (1,0), (1,0), colors.HexColor("#f8f8ff")),
        ("ROUNDEDCORNERS", [4]),
    ]))
    return t

def sign_block(lieu="", date_str="", client_nom="", client_fn=""):
    """Bloc signatures."""
    d = date_str or date.today().strftime("%d/%m/%Y")
    l = lieu or "________________"
    data = [
        [para(f"Fait à {l}, le {d}", "small"), ""],
        [
            [para("Pour le client", "sign_label"), sp(2),
             para(client_fn or "Nom, fonction", "sign_name"), sp(20),
             para("Signature :", "small")],
            [para("Pour le prestataire", "sign_label"), sp(2),
             para("Mathieu Pleitinx – Gérant", "sign_name"), sp(20),
             para("Signature :", "small")],
        ]
    ]
    t = Table(data, colWidths=[W*0.44, W*0.44])
    t.setStyle(TableStyle([
        ("SPAN", (0,0), (1,0)),
        ("VALIGN", (0,0), (-1,-1), "TOP"),
        ("LEFTPADDING",  (0,0), (-1,-1), 8),
        ("RIGHTPADDING", (0,0), (-1,-1), 8),
        ("TOPPADDING",   (1,0), (-1,-1), 12),
        ("LINEABOVE", (0,1), (0,1), 0.5, SC_LGREY),
        ("LINEABOVE", (1,1), (1,1), 0.5, SC_LGREY),
    ]))
    return t

def price_table(rows, title=None):
    """Tableau tarifaire standard."""
    header = [para(c, "body_bold") for c in ["Prestation", "Prix HTVA"]]
    data = [header] + [[para(r[0]), para(r[1], "right")] for r in rows]
    t = Table(data, colWidths=[W*0.65, W*0.22])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), SC_BLUE),
        ("TEXTCOLOR",  (0,0), (-1,0), SC_WHITE),
        ("FONTNAME",   (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTSIZE",   (0,0), (-1,-1), 8.5),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, colors.HexColor("#f5f7ff")]),
        ("GRID", (0,0), (-1,-1), 0.3, colors.HexColor("#d0d8e8")),
        ("LEFTPADDING",  (0,0), (-1,-1), 8),
        ("RIGHTPADDING", (0,0), (-1,-1), 8),
        ("TOPPADDING",   (0,0), (-1,-1), 5),
        ("BOTTOMPADDING",(0,0), (-1,-1), 5),
        ("ALIGN", (1,0), (1,-1), "RIGHT"),
    ]))
    elems = []
    if title:
        elems.append(para(title, "subsection"))
    elems.append(t)
    return elems

def annex_banner(title):
    data = [[para(f"ANNEXE – {title}", "annex_title")]]
    t = Table(data, colWidths=[W*0.88])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,-1), SC_BLUE),
        ("LEFTPADDING",  (0,0), (-1,-1), 12),
        ("TOPPADDING",   (0,0), (-1,-1), 8),
        ("BOTTOMPADDING",(0,0), (-1,-1), 8),
        ("ROUNDEDCORNERS", [4]),
    ]))
    return t


# ── Header / Footer callback ───────────────────────────────────────────────────
def make_page_callbacks(doc_title, ref=""):
    margin_l = 20*mm

    def on_first_page(canvas, doc):
        _draw_header(canvas, doc_title, ref, first=True)
        _draw_footer(canvas, doc)

    def on_later_pages(canvas, doc):
        _draw_header(canvas, doc_title, ref, first=False)
        _draw_footer(canvas, doc)

    return on_first_page, on_later_pages

def _draw_header(canvas, title, ref, first):
    canvas.saveState()
    # Barre bleue en haut
    canvas.setFillColor(SC_BLUE)
    canvas.rect(0, H - 14*mm, W, 14*mm, fill=1, stroke=0)

    # Logo text (si pas d'image logo disponible)
    canvas.setFillColor(SC_WHITE)
    canvas.setFont("Helvetica-Bold", 11)
    canvas.drawString(20*mm, H - 9*mm, "smartclick")

    if not first:
        canvas.setFont("Helvetica", 8)
        canvas.drawRightString(W - 20*mm, H - 9*mm, title[:60])

    # Ref
    if ref:
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(colors.HexColor("#aabbdd"))
        canvas.drawRightString(W - 20*mm, H - 9*mm, ref)

    canvas.restoreState()

def _draw_footer(canvas, doc):
    canvas.saveState()
    canvas.setFillColor(SC_LGREY)
    canvas.rect(0, 0, W, 10*mm, fill=1, stroke=0)
    canvas.setFillColor(SC_GREY)
    canvas.setFont("Helvetica", 7)
    canvas.drawString(20*mm, 3.5*mm,
        "Smartclick S.R.L. – Brugstraat 22 – 1601 Sint-Pieters-Leeuw – BE 0746.385.009 – mathieu.pleitinx@smartclick.be")
    canvas.drawRightString(W - 20*mm, 3.5*mm, f"Page {doc.page}")
    canvas.restoreState()


# ══════════════════════════════════════════════════════════════════════════════
# GENERATEURS PAR TYPE
# ══════════════════════════════════════════════════════════════════════════════

def _base_doc(path, title, ref=""):
    doc = SimpleDocTemplate(
        path,
        pagesize=A4,
        leftMargin=20*mm, rightMargin=20*mm,
        topMargin=20*mm, bottomMargin=16*mm,
        title=title,
        author="Smartclick S.R.L.",
    )
    fp, lp = make_page_callbacks(title, ref)
    return doc, fp, lp

def _common_clauses(extra_exclusions=None):
    """Clauses communes obligations / responsabilité / confidentialité / durée."""
    excl = extra_exclusions or []
    elems = []
    elems += [section(8, "Obligations du prestataire"),
              para("Le prestataire est tenu à une obligation de moyens. Il ne peut garantir un résultat particulier, l'exécution dépendant notamment de l'état des systèmes, des contraintes techniques et des dépendances fournisseurs.", "body")]

    elems += [section(9, "Responsabilité"),
              para("Le prestataire ne pourra être tenu responsable des dommages indirects, pertes de données, interruptions d'activité ou conséquences juridiques découlant de l'exécution ou de l'interprétation des livrables. Sa responsabilité est limitée au montant des honoraires facturés sur la période concernée.", "body")]

    elems += [section(10, "Confidentialité"),
              para("Le prestataire est tenu à une obligation de confidentialité renforcée concernant l'ensemble des informations, données et documents auxquels il a accès dans le cadre de la présente mission. Cette obligation s'applique également à toute personne intervenant pour son compte.", "body")]

    elems += [section(13, "Droit applicable et juridiction compétente"),
              para("La présente convention est soumise au droit belge. En cas de litige, les parties s'engagent à recourir préalablement à la médiation. À défaut d'accord, les tribunaux de l'arrondissement judiciaire de Bruxelles seront seuls compétents.", "body")]
    return elems


# ── 1. LETTRE DE MISSION GENERIQUE ────────────────────────────────────────────
def generate_lm(path, data):
    """
    data: {
      client: {nom, forme, nentreprise, siege, representant, email},
      type: 'gestion_it' | 'cloud' | 'full_inclusive' | 'full_exclusive' | 'forensics' | 'dev' | 'ponctuel',
      reference: str,
      date_doc: str,
      lieu: str,
      contexte: str,       # paragraphe exposé des motifs
      missions: [str],     # liste missions
      exclusions: [str],   # liste exclusions spécifiques
      tarif_horaire: float,
      forfait_mensuel: float | None,   # Full Inclusive
      budget_materiel: float | None,
      inclus_visites: int | None,
      creation_user_prix: float | None,
      installation_poste: float | None,
      duree: str,          # 'indeterminee' | 'determinee' | 'ponctuelle'
      notes: str,
      formule: str | None, # 'full_inclusive' | 'full_exclusive' | None
      # Forensics specific
      supports_analyses: str | None,
      nb_machines: int | None,
    }
    """
    TYPE_TITLES = {
        "gestion_it":      ("Gestion IT opérationnelle & parc informatique", "Lettre de mission – Contrat de services"),
        "cloud":           ("Infrastructure serveurs Cloud", "Location, exploitation & administration"),
        "full_inclusive":  ("IT at your service – Full Inclusive", "Forfait mensuel tout compris"),
        "full_exclusive":  ("IT at your service – Full Exclusive", "Facturation à la consommation"),
        "forensics":       ("Mission de forensics informatique", "Lettre de mission – Expertise technique"),
        "dev":             ("Mission de développement informatique", "Lettre de mission – Développement sur mesure"),
        "ponctuel":        ("Mission ponctuelle", "Lettre de mission – Prestation de services"),
        "recherche_donnees":("Mission de recherche de données", "Lettre de mission – Migration / Récupération"),
        "maintenance":     ("Gestion & maintenance IT", "Lettre de mission – Services managés"),
    }
    t = data.get("type", "ponctuel")
    title1, title2 = TYPE_TITLES.get(t, ("Lettre de Mission", "Contrat de services"))
    ref = data.get("reference", "")

    doc, fp, lp = _base_doc(path, title1, ref)
    story = []

    # ── Couverture ──
    story.append(sp(18))
    story.append(para("LETTRE DE MISSION", "title_doc"))
    story.append(para(title1, "subtitle"))
    story.append(para(title2, "subtitle2"))
    story.append(hr(thickness=2, space_before=4, space_after=16))

    # ── Parties ──
    story.append(para("Entre les soussignés :", "body"))
    story.append(sp(6))
    story.append(parties_block(PRESTATAIRE, data["client"]))
    story.append(sp(8))

    # ── Exposé ──
    story.append(hr(color=SC_LGREY, thickness=0.5))
    story.append(para("IL A PRÉALABLEMENT ÉTÉ EXPOSÉ CE QUI SUIT", "body_bold"))
    story.append(sp(4))
    story.append(para(data.get("contexte", "Le client souhaite confier au prestataire les prestations décrites ci-après."), "body"))
    story.append(sp(6))
    story.append(hr(color=SC_LGREY, thickness=0.5))
    story.append(para("IL A ENSUITE ÉTÉ CONVENU CE QUI SUIT", "body_bold"))
    story.append(sp(6))

    # ── 1. Objet ──
    story.append(section(1, "Objet de la convention"))
    story.append(para("Le présent contrat a pour objet la fourniture, par le prestataire, des prestations de services informatiques décrites ci-après, au bénéfice du client, dans le cadre d'une obligation de moyens.", "body"))

    # ── 2. Missions ──
    story.append(section(2, "Missions du prestataire"))
    story.append(para("Les missions confiées au prestataire comprennent notamment :", "body"))
    for m in data.get("missions", []):
        story.append(bullet_item(m))

    # Forensics spécifique
    if t == "forensics":
        story.append(sp(4))
        story.append(section(3, "Nature de l'intervention – Forensics"))
        story.append(para("Le prestataire agit exclusivement en qualité d'expert technique indépendant. Il ne procède à aucune qualification juridique, disciplinaire ou pénale des faits observés. Les constatations consignées dans le rapport sont strictement techniques et factuelles.", "body"))
        story.append(section(4, "Préservation des données et intégrité"))
        story.append(para("Le prestataire s'engage à respecter les bonnes pratiques de préservation des données numériques. Lorsque cela est pertinent, il procède à la réalisation d'images forensiques des supports, constituant les éléments techniques de référence pour l'analyse.", "body"))
        story.append(section(5, "Conservation des supports"))
        story.append(para("Le prestataire n'a pas vocation à conserver le matériel analysé. La conservation des supports physiques relève de la responsabilité du client. Les éléments techniques produits (images, hashes, documentation) sont conservés pendant la durée strictement nécessaire.", "body"))
        story.append(section(6, "Rapport et utilisation"))
        story.append(para("Le prestataire remet au client un rapport de forensics informatique reprenant les constatations techniques effectuées. Ce rapport est destiné au client et pourra, sous sa responsabilité exclusive, être transmis à ses conseils juridiques ou aux autorités compétentes.", "body"))

    # Formule Full Inclusive
    if t == "full_inclusive" and data.get("forfait_mensuel"):
        story.append(section(3, "Formule Full Inclusive – Détail du forfait"))
        story.append(para(f"Forfait mensuel : <b>{data['forfait_mensuel']:.2f} € HTVA / mois</b>", "body"))
        if data.get("inclus_visites"):
            story.append(para(f"Visites incluses : {data['inclus_visites']} visite(s) par mois et par site (si planifiée et consommée).", "body"))
        if data.get("budget_materiel"):
            story.append(para(f"Budget matériel inclus : {data['budget_materiel']:.2f} € HTVA (utilisable pour matériel standard, accord préalable requis).", "body"))

    # ── 3/4/5. Exclusions ──
    excl_num = 7 if t == "forensics" else 3
    story.append(section(excl_num, "Prestations exclues"))
    default_excl = ["Forensics (lettre de mission spécifique).",
                    "Projets/migrations majeurs non expressément convenus (devis préalable).",
                    "Interventions d'urgence hors heures ouvrées sans accord préalable."]
    if t in ("gestion_it",):
        default_excl = ["Administration des serveurs Cloud (contrat séparé).", "Forensics (lettre de mission spécifique).",
                        "Projets/migrations majeurs non convenus (devis)."]
    elif t == "cloud":
        default_excl = ["Support utilisateur final (Office/Outlook/Teams, usage applicatif).",
                        "Installation et maintenance des postes de travail (contrat séparé).",
                        "Forensics et effacement sécurisé (contrats spécifiques).",
                        "Projets/migrations non expressément convenus (devis/bon de commande)."]
    elif t == "forensics":
        default_excl = ["Toute qualification juridique, disciplinaire ou pénale des faits observés.",
                        "Récupération garantie de données (dépend de l'état des supports).",
                        "Conservation des supports physiques au-delà de la mission."]

    for e in (data.get("exclusions") or default_excl):
        story.append(bullet_item(e))

    # ── Tarification ──
    story.append(section(excl_num + 1, "Honoraires et frais"))
    tarif = data.get("tarif_horaire", 81.25)
    story.append(para(f"Les prestations sont facturées sur base d'un tarif horaire de <b>{tarif:.2f} € HTVA</b>. La facturation est réalisée sur base du temps réellement presté, sauf forfaits expressément convenus.", "body"))
    if data.get("installation_poste"):
        story.append(para(f"Installation d'un nouveau poste : <b>{data['installation_poste']:.2f} € HTVA</b>.", "body"))
    if data.get("creation_user_prix"):
        story.append(para(f"Création d'un nouvel utilisateur (périmètre complet) : <b>{data['creation_user_prix']:.2f} € HTVA</b>.", "body"))

    # ── Durée ──
    story.append(section(excl_num + 2, "Durée du contrat"))
    duree = data.get("duree", "indeterminee")
    if duree == "indeterminee":
        story.append(para("Le présent contrat est conclu pour une durée indéterminée. Il peut être résilié par l'une ou l'autre des parties moyennant un préavis raisonnable d'un (1) mois, sans préjudice des prestations déjà réalisées.", "body"))
    elif duree == "ponctuelle":
        story.append(para("La présente mission est un ordre de mission ponctuel. Le contrat prend fin à la remise du livrable convenu (rapport, livraison, etc.).", "body"))
    else:
        story.append(para(f"Le présent contrat est conclu pour une durée déterminée : {data.get('duree_texte','à convenir')}.", "body"))

    # ── Clauses communes ──
    story += _common_clauses()

    # ── Notes ──
    if data.get("notes"):
        story.append(section("N", "Notes et conditions particulières"))
        story.append(para(data["notes"], "body"))

    # ── Signatures ──
    story.append(sp(10))
    story.append(hr(color=SC_LGREY))
    story.append(sign_block(
        lieu=data.get("lieu", ""),
        date_str=data.get("date_doc", ""),
        client_nom=data["client"]["nom"],
        client_fn=data["client"].get("representant", "")
    ))

    # ── ANNEXE TARIFS ──
    story.append(PageBreak())
    story.append(annex_banner("Grille tarifaire"))
    story.append(sp(8))

    rows = [("Tarif horaire", f"{tarif:.2f} € HTVA / heure")]
    if data.get("installation_poste"):
        rows.append(("Installation nouvelle machine (poste/portable)", f"{data['installation_poste']:.2f} € HTVA"))
    if data.get("creation_user_prix"):
        rows.append(("Création utilisateur complet (Microsoft + FreeIPA + M365)", f"{data['creation_user_prix']:.2f} € HTVA"))
    if data.get("forfait_mensuel"):
        rows.append((f"Forfait mensuel – Full Inclusive", f"{data['forfait_mensuel']:.2f} € HTVA / mois"))
    if data.get("budget_materiel"):
        rows.append(("Budget matériel inclus (mensuel)", f"{data['budget_materiel']:.2f} € HTVA / mois"))

    story += price_table(rows, "Tarification des prestations")

    # Data shredding table
    story.append(sp(10))
    story.append(subsection("Data Shredding – Effacement sécurisé certifié"))
    shred_rows = [
        ("HDD / SSD (standard) – jusqu'à 1 TB",         "35,00 € HTVA / drive"),
        ("HDD / SSD (large) – plus de 1 TB",             "45,00 € HTVA / drive"),
        ("USB Stick / Carte SD (toute taille)",           "15,00 € HTVA / device"),
        ("Serveur / NAS (jusqu'à 4 baies)",               "90,00 € HTVA / système"),
        ("Rapport d'effacement certifié PDF",             "Offert"),
        ("Option déplacement on-site",                    "85,00 € HTVA + tarif drive"),
    ]
    story += price_table(shred_rows)
    story.append(para("Référence : https://www.smartclick.be/data-shredding/", "small"))

    doc.build(story, onFirstPage=fp, onLaterPages=lp)
    return path


# ── 2. CONTRAT DE MAINTENANCE ──────────────────────────────────────────────────
def generate_maintenance(path, data):
    """
    data: {
      client: {...},
      reference: str,
      date_doc: str,
      lieu: str,
      contexte: str,
      dispositifs: [{nom, description, quantite}],
      services: [str],           # services inclus
      exclusions: [str],
      tarif_garde_5_7: float,    # redevance hebdo 5/7
      tarif_garde_7_7: float,    # redevance hebdo 7/7
      tarif_preventif: float,    # par journée
      tarif_horaire_curateur: float,
      tarif_deplacement: float,
      nb_interventions_offertes: int,
      total_htva: float,
      duree_ans: int,
      auto_renew: bool,
      sla: [{criticite, reaction, analyse, resolution}],
      notes: str,
    }
    """
    ref = data.get("reference", "")
    doc, fp, lp = _base_doc(path, "Contrat de maintenance", ref)
    story = []

    story.append(sp(18))
    story.append(para("CONTRAT DE MAINTENANCE", "title_doc"))
    story.append(para("Maintenance corrective & préventive", "subtitle"))
    story.append(para("Service de garde – SLA garanti", "subtitle2"))
    story.append(hr(thickness=2, space_before=4, space_after=16))

    story.append(para("Entre les soussignés :", "body"))
    story.append(sp(6))
    story.append(parties_block(PRESTATAIRE, data["client"]))
    story.append(sp(8))
    story.append(hr(color=SC_LGREY, thickness=0.5))
    story.append(para("IL A PRÉALABLEMENT ÉTÉ EXPOSÉ CE QUI SUIT", "body_bold"))
    story.append(sp(4))
    story.append(para(data.get("contexte", "Le client souhaite confier au prestataire la maintenance de son infrastructure."), "body"))
    story.append(sp(6))
    story.append(hr(color=SC_LGREY, thickness=0.5))
    story.append(para("IL A ENSUITE ÉTÉ CONVENU CE QUI SUIT", "body_bold"))
    story.append(sp(6))

    story.append(section(1, "Objet du contrat"))
    story.append(para("Le présent contrat a pour objet de définir les conditions et le contenu des prestations de maintenance délivrées par le prestataire. Le périmètre couvert est spécifié en Annexe 1.", "body"))

    story.append(section(2, "Services couverts"))
    for s in (data.get("services") or ["Maintenance corrective des équipements listés en Annexe 1.",
                                        "Maintenance préventive planifiée.",
                                        "Service de garde passif en heures ouvrées.",
                                        "Support téléphonique et téléassistance."]):
        story.append(bullet_item(s))

    story.append(section(3, "Maintenance corrective"))
    story.append(para("La maintenance corrective couvre la prise en charge et la résolution de tout incident résultant d'un comportement erroné documenté et provoqué par une anomalie. Dès la survenance d'un incident, le client notifiera sans délai le problème via le helpdesk (www.support.smartclick.be).", "body"))
    story.append(subsection("Niveaux de criticité"))
    criticites = [
        ("Critique",  "Empêche l'utilisation dans son ensemble ou bloque l'activité du client."),
        ("Élevée",    "Empêche un sous-ensemble vital, perturbant fortement l'activité."),
        ("Moyenne",   "Bloque un sous-ensemble non vital, la majorité des activités peut continuer."),
        ("Basse",     "N'empêche pas l'utilisation ou est de nature cosmétique."),
    ]
    for c, d_c in criticites:
        story.append(para(f"<b>{c}</b> : {d_c}", "bullet"))

    story.append(section(4, "Maintenance préventive"))
    story.append(para("La maintenance préventive consiste en une série de tâches planifiées destinées à prolonger la durée de vie des appareils. Les interventions sont planifiées à l'avance avec le client et documentées dans le système helpdesk.", "body"))

    story.append(section(5, "Exclusions"))
    for e in (data.get("exclusions") or [
        "Interventions liées à une mauvaise utilisation, configuration non autorisée ou modification par un tiers.",
        "Défaillances d'infrastructure propre au client.",
        "Pièces de rechange et consommables (feront l'objet d'un devis séparé).",
        "Projets/migrations non expressément convenus.",
    ]):
        story.append(bullet_item(e))

    story.append(section(6, "Durée"))
    nb_ans = data.get("duree_ans", 1)
    story.append(para(f"Le contrat est conclu pour une durée déterminée de {nb_ans} an(s), renouvelable par tacite reconduction sauf préavis d'un (1) mois avant l'échéance.", "body"))

    story.append(section(7, "Conditions financières"))
    story.append(para("La redevance est facturée avant le début de chaque période. Ce montant est irréductible et forfaitaire. Les interventions curatives du mois sont facturées avec la redevance mensuelle.", "body"))
    total = data.get("total_htva", 0)
    if total:
        story.append(para(f"<b>Total annuel HTVA : {total:.2f} €</b>", "body_bold"))

    story += _common_clauses()

    if data.get("notes"):
        story.append(section("N", "Notes et conditions particulières"))
        story.append(para(data["notes"], "body"))

    story.append(sp(10))
    story.append(hr(color=SC_LGREY))
    story.append(sign_block(data.get("lieu",""), data.get("date_doc",""),
                            data["client"]["nom"], data["client"].get("representant","")))

    # ── ANNEXE 1 – Dispositifs ──
    if data.get("dispositifs"):
        story.append(PageBreak())
        story.append(annex_banner("Annexe 1 – Dispositifs sous contrat de maintenance"))
        story.append(sp(8))
        dev_header = [para(h, "body_bold") for h in ["Dispositif", "Description", "Quantité"]]
        dev_rows = [dev_header]
        for d_item in data["dispositifs"]:
            dev_rows.append([
                para(d_item.get("nom","")),
                para(d_item.get("description","")),
                para(str(d_item.get("quantite","1")), "center"),
            ])
        t = Table(dev_rows, colWidths=[W*0.35, W*0.40, W*0.12])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,0), SC_BLUE),
            ("TEXTCOLOR",  (0,0), (-1,0), SC_WHITE),
            ("FONTNAME",   (0,0), (-1,0), "Helvetica-Bold"),
            ("FONTSIZE",   (0,0), (-1,-1), 8.5),
            ("ROWBACKGROUNDS", (0,1), (-1,-1), [SC_WHITE, colors.HexColor("#f5f7ff")]),
            ("GRID", (0,0), (-1,-1), 0.3, colors.HexColor("#d0d8e8")),
            ("LEFTPADDING",  (0,0), (-1,-1), 8),
            ("RIGHTPADDING", (0,0), (-1,-1), 8),
            ("TOPPADDING",   (0,0), (-1,-1), 5),
            ("BOTTOMPADDING",(0,0), (-1,-1), 5),
            ("ALIGN", (2,0), (2,-1), "CENTER"),
        ]))
        story.append(t)

    # ── ANNEXE 2 – Tarification ──
    story.append(PageBreak())
    story.append(annex_banner("Annexe 2 – Tarification"))
    story.append(sp(8))

    annual_rows = []
    if data.get("tarif_garde_5_7"):
        annual_rows.append(("Redevance de garde – 5/7 passif en semaine (lu-ve)", f"{data['tarif_garde_5_7']:.2f} € HTVA / semaine"))
    if data.get("tarif_garde_7_7"):
        annual_rows.append(("Redevance de garde – 7/7 passif (vacances scolaires / avril-novembre)", f"{data['tarif_garde_7_7']:.2f} € HTVA / semaine"))
    if data.get("tarif_preventif"):
        annual_rows.append(("Maintenance préventive technique (par journée)", f"{data['tarif_preventif']:.2f} € HTVA / jour"))
    if data.get("nb_interventions_offertes"):
        annual_rows.append((f"Interventions offertes dans le contrat", f"{data['nb_interventions_offertes']} interventions"))
    if annual_rows:
        story += price_table(annual_rows, "Tarification annuelle")

    story.append(sp(6))
    curatif_rows = []
    if data.get("tarif_horaire_curateur"):
        th = data["tarif_horaire_curateur"]
        curatif_rows += [
            ("Intervention curative à distance – semaine /h",       f"{th:.2f} € HTVA"),
            ("Intervention curative sur site – semaine /h",         f"{th:.2f} € HTVA"),
            ("*Intervention curative à distance – weekend /h",      f"{th*1.17:.2f} € HTVA"),
            ("*Intervention curative sur site – weekend /h",        f"{th*1.41:.2f} € HTVA"),
        ]
    if data.get("tarif_deplacement"):
        curatif_rows.append(("Déplacement en semaine / déplacement",  f"{data['tarif_deplacement']:.2f} € HTVA"))
    if curatif_rows:
        story += price_table(curatif_rows, "Grille tarifaire interventions curatives")

    # ── ANNEXE 3 – SLA ──
    story.append(PageBreak())
    story.append(annex_banner("Annexe 3 – Service Level Agreement (SLA)"))
    story.append(sp(8))
    sla_data = data.get("sla") or [
        {"criticite": "Critique",  "reaction": "4 heures",          "analyse": "1 jour ouvrable",  "resolution": "1 jour ouvrable *"},
        {"criticite": "Élevée",    "reaction": "4 heures ouvrables","analyse": "1 jour ouvrable",  "resolution": "3 jours ouvrables *"},
        {"criticite": "Moyenne",   "reaction": "1 jour ouvrable",   "analyse": "3 jours ouvrables","resolution": "7 jours ouvrables *"},
        {"criticite": "Basse",     "reaction": "1 jour ouvrable",   "analyse": "5 jours ouvrables","resolution": "7 jours ouvrables *"},
    ]
    sla_header = [para(h, "body_bold") for h in ["Priorité", "Criticité", "Délai réaction", "Délai analyse", "Délai résolution"]]
    sla_rows = [sla_header]
    for i, row in enumerate(sla_data, 1):
        sla_rows.append([
            para(str(i), "center"),
            para(f"<b>{row['criticite']}</b>"),
            para(row["reaction"]),
            para(row["analyse"]),
            para(row["resolution"]),
        ])
    t = Table(sla_rows, colWidths=[W*0.07, W*0.13, W*0.22, W*0.22, W*0.22])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), SC_BLUE),
        ("TEXTCOLOR",  (0,0), (-1,0), SC_WHITE),
        ("FONTNAME",   (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTSIZE",   (0,0), (-1,-1), 8.5),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [SC_WHITE, colors.HexColor("#f5f7ff")]),
        ("GRID", (0,0), (-1,-1), 0.3, colors.HexColor("#d0d8e8")),
        ("ALIGN", (0,0), (0,-1), "CENTER"),
        ("LEFTPADDING",  (0,0), (-1,-1), 6),
        ("RIGHTPADDING", (0,0), (-1,-1), 6),
        ("TOPPADDING",   (0,0), (-1,-1), 5),
        ("BOTTOMPADDING",(0,0), (-1,-1), 5),
    ]))
    story.append(t)
    story.append(sp(6))
    story.append(para("(*) Le délai de résolution sera communiqué sur base de l'analyse réalisée par l'équipe de support. Le client peut contacter le prestataire en cas de panne critique afin de trouver un consensus sur le moment d'intervention.", "small"))

    doc.build(story, onFirstPage=fp, onLaterPages=lp)
    return path


# ── 3. FICHE INTERVENTION ATELIER ─────────────────────────────────────────────
def generate_fiche_intervention(path, data):
    """
    data: {
      client: {nom, ...},
      reference: str,
      date_reception: str,
      date_restitution_prev: str,
      technicien: str,
      machine: {marque, modele, serie, type},
      symptomes: str,
      diagnostic: str,
      travaux: [str],
      pieces: [{designation, ref, prix}],
      temps_main_oeuvre: float,
      tarif_horaire: float,
      statut: str,
      notes: str,
    }
    """
    ref = data.get("reference", "FI-" + date.today().strftime("%Y%m%d"))
    doc, fp, lp = _base_doc(path, f"Fiche d'intervention – {ref}", ref)
    story = []

    story.append(sp(14))
    story.append(para("FICHE D'INTERVENTION", "title_doc"))
    story.append(para("Atelier de réparation informatique", "subtitle2"))
    story.append(hr(thickness=2))

    # Bloc infos
    machine = data.get("machine", {})
    client  = data.get("client", {})
    info_rows = [
        ["Référence", ref,              "Client",        client.get("nom","")],
        ["Date réception", data.get("date_reception",""),  "Date prévue restitution", data.get("date_restitution_prev","")],
        ["Technicien", data.get("technicien","Mathieu Pleitinx"), "Statut", data.get("statut","En cours")],
        ["Marque / Modèle", f"{machine.get('marque','')} {machine.get('modele','')}", "N° Série", machine.get("serie","")],
        ["Type appareil", machine.get("type",""), "", ""],
    ]
    t = Table(info_rows, colWidths=[W*0.18, W*0.28, W*0.18, W*0.28])
    t.setStyle(TableStyle([
        ("FONTNAME",   (0,0), (0,-1), "Helvetica-Bold"),
        ("FONTNAME",   (2,0), (2,-1), "Helvetica-Bold"),
        ("FONTSIZE",   (0,0), (-1,-1), 8.5),
        ("BACKGROUND", (0,0), (0,-1), colors.HexColor("#f0f4ff")),
        ("BACKGROUND", (2,0), (2,-1), colors.HexColor("#f0f4ff")),
        ("GRID",       (0,0), (-1,-1), 0.4, colors.HexColor("#d0d8e8")),
        ("LEFTPADDING",  (0,0), (-1,-1), 6),
        ("RIGHTPADDING", (0,0), (-1,-1), 6),
        ("TOPPADDING",   (0,0), (-1,-1), 4),
        ("BOTTOMPADDING",(0,0), (-1,-1), 4),
        ("TEXTCOLOR", (0,0), (-1,-1), SC_BLACK),
    ]))
    story.append(t)
    story.append(sp(8))

    # Symptômes
    story.append(subsection("Symptômes / Problème rapporté"))
    story.append(para(data.get("symptomes", "—"), "body"))
    story.append(sp(6))

    # Diagnostic
    story.append(subsection("Diagnostic technique"))
    story.append(para(data.get("diagnostic", "—"), "body"))
    story.append(sp(6))

    # Travaux effectués
    story.append(subsection("Travaux effectués"))
    for w in (data.get("travaux") or ["—"]):
        story.append(bullet_item(w))
    story.append(sp(6))

    # Pièces
    pieces = data.get("pieces", [])
    if pieces:
        story.append(subsection("Pièces utilisées"))
        pieces_header = [para(h, "body_bold") for h in ["Désignation", "Référence", "Prix HTVA"]]
        pieces_data = [pieces_header]
        total_pieces = 0
        for p in pieces:
            pieces_data.append([
                para(p.get("designation","")),
                para(p.get("ref","")),
                para(f"{p.get('prix',0):.2f} €", "right"),
            ])
            total_pieces += p.get("prix", 0)
        pieces_data.append([para(""), para("<b>Total pièces</b>", "right"), para(f"<b>{total_pieces:.2f} €</b>", "right")])
        t = Table(pieces_data, colWidths=[W*0.45, W*0.25, W*0.18])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,0), SC_BLUE),
            ("TEXTCOLOR",  (0,0), (-1,0), SC_WHITE),
            ("FONTSIZE",   (0,0), (-1,-1), 8.5),
            ("ROWBACKGROUNDS", (0,1), (-1,-2), [SC_WHITE, colors.HexColor("#f5f7ff")]),
            ("BACKGROUND", (0,-1), (-1,-1), colors.HexColor("#e8f0ff")),
            ("GRID", (0,0), (-1,-1), 0.3, colors.HexColor("#d0d8e8")),
            ("ALIGN", (2,0), (2,-1), "RIGHT"),
            ("LEFTPADDING",  (0,0), (-1,-1), 6),
            ("RIGHTPADDING", (0,0), (-1,-1), 6),
            ("TOPPADDING",   (0,0), (-1,-1), 4),
            ("BOTTOMPADDING",(0,0), (-1,-1), 4),
        ]))
        story.append(t)
        story.append(sp(6))

    # Récapitulatif financier
    story.append(subsection("Récapitulatif financier"))
    heures = data.get("temps_main_oeuvre", 0)
    tarif  = data.get("tarif_horaire", 81.25)
    mo     = heures * tarif
    tp     = sum(p.get("prix",0) for p in pieces)
    total  = mo + tp
    fin_rows = [
        ["Main d'œuvre", f"{heures:.2f} h × {tarif:.2f} €/h", f"{mo:.2f} € HTVA"],
        ["Pièces & composants", "",                              f"{tp:.2f} € HTVA"],
        ["", "<b>TOTAL HTVA</b>",                               f"<b>{total:.2f} €</b>"],
        ["", "TVA 21%",                                         f"{total*0.21:.2f} €"],
        ["", "<b>TOTAL TVAC</b>",                               f"<b>{total*1.21:.2f} €</b>"],
    ]
    t = Table([[para(r[0]), para(r[1]), para(r[2],"right")] for r in fin_rows],
              colWidths=[W*0.25, W*0.38, W*0.25])
    t.setStyle(TableStyle([
        ("FONTSIZE",   (0,0), (-1,-1), 8.5),
        ("BACKGROUND", (0,-2), (-1,-2), colors.HexColor("#e8f0ff")),
        ("BACKGROUND", (0,-1), (-1,-1), SC_BLUE),
        ("TEXTCOLOR",  (0,-1), (-1,-1), SC_WHITE),
        ("GRID", (0,0), (-1,-1), 0.3, colors.HexColor("#d0d8e8")),
        ("ALIGN", (2,0), (2,-1), "RIGHT"),
        ("LEFTPADDING",  (0,0), (-1,-1), 6),
        ("RIGHTPADDING", (0,0), (-1,-1), 6),
        ("TOPPADDING",   (0,0), (-1,-1), 4),
        ("BOTTOMPADDING",(0,0), (-1,-1), 4),
    ]))
    story.append(t)

    if data.get("notes"):
        story.append(sp(6))
        story.append(subsection("Notes"))
        story.append(para(data["notes"], "body"))

    # Signature réception
    story.append(sp(16))
    story.append(hr(color=SC_LGREY))
    sign_rows = [[
        [para("Bon pour réception – Client", "sign_label"), sp(20), para("Date : __________ / Signature :", "small")],
        [para("Technicien", "sign_label"), sp(2), para(data.get("technicien","Mathieu Pleitinx"), "sign_name"), sp(20), para("Signature :", "small")],
    ]]
    t = Table(sign_rows, colWidths=[W*0.44, W*0.44])
    t.setStyle(TableStyle([("VALIGN",(0,0),(-1,-1),"TOP"),
                            ("LEFTPADDING",(0,0),(-1,-1),8),
                            ("TOPPADDING",(0,0),(-1,-1),10)]))
    story.append(t)

    doc.build(story, onFirstPage=fp, onLaterPages=lp)
    return path


# ── 4. RAPPORT DATA SHREDDING ──────────────────────────────────────────────────
def generate_shredding_report(path, data):
    """
    data: {
      client: {nom, ...},
      reference: str,
      date_operation: str,
      technicien: str,
      methode: str,    # ex: DoD 5220.22-M, NIST 800-88, Gutmann
      supports: [{type, marque, modele, serie, capacite, passes, resultat, hash}],
      notes: str,
      on_site: bool,
    }
    """
    ref = data.get("reference", "DS-" + date.today().strftime("%Y%m%d"))
    doc, fp, lp = _base_doc(path, f"Rapport d'effacement certifié – {ref}", ref)
    story = []

    story.append(sp(14))
    story.append(para("RAPPORT D'EFFACEMENT SÉCURISÉ", "title_doc"))
    story.append(para("Data Shredding – Certificat d'effacement certifié", "subtitle"))
    story.append(para(f"Référence : {ref}  |  Méthode : {data.get('methode','DoD 5220.22-M')}", "subtitle2"))
    story.append(hr(thickness=2))

    info_rows = [
        ["Client",       data["client"].get("nom",""),   "Technicien",      data.get("technicien","Mathieu Pleitinx")],
        ["Date opération", data.get("date_operation",""), "On-site",        "Oui" if data.get("on_site") else "Non"],
        ["Référence",    ref,                             "Nb supports",     str(len(data.get("supports",[])))],
    ]
    t = Table(info_rows, colWidths=[W*0.18, W*0.28, W*0.18, W*0.28])
    t.setStyle(TableStyle([
        ("FONTNAME",   (0,0), (0,-1), "Helvetica-Bold"),
        ("FONTNAME",   (2,0), (2,-1), "Helvetica-Bold"),
        ("FONTSIZE",   (0,0), (-1,-1), 8.5),
        ("BACKGROUND", (0,0), (0,-1), colors.HexColor("#f0f4ff")),
        ("BACKGROUND", (2,0), (2,-1), colors.HexColor("#f0f4ff")),
        ("GRID",       (0,0), (-1,-1), 0.4, colors.HexColor("#d0d8e8")),
        ("LEFTPADDING",  (0,0), (-1,-1), 6),
        ("TOPPADDING",   (0,0), (-1,-1), 4),
        ("BOTTOMPADDING",(0,0), (-1,-1), 4),
    ]))
    story.append(t)
    story.append(sp(10))

    story.append(subsection("Supports traités"))
    sup_header = [para(h, "body_bold") for h in
                  ["Type", "Marque / Modèle", "N° Série", "Capacité", "Passes", "Résultat", "Hash SHA-256"]]
    sup_rows = [sup_header]
    for s in data.get("supports", []):
        result_color = colors.HexColor("#22c55e") if s.get("resultat","") == "OK" else colors.HexColor("#ff4d6d")
        r_para = Paragraph(s.get("resultat",""), ParagraphStyle("res", fontName="Helvetica-Bold",
                           fontSize=8, textColor=result_color))
        sup_rows.append([
            para(s.get("type","")),
            para(s.get("marque_modele", f"{s.get('marque','')} {s.get('modele','')}")),
            para(s.get("serie","")),
            para(s.get("capacite","")),
            para(str(s.get("passes","3")), "center"),
            r_para,
            para(s.get("hash","")[:16] + "…" if len(s.get("hash","")) > 16 else s.get("hash",""), "small"),
        ])
    t = Table(sup_rows, colWidths=[W*0.10, W*0.18, W*0.14, W*0.09, W*0.07, W*0.08, W*0.20])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), SC_BLUE),
        ("TEXTCOLOR",  (0,0), (-1,0), SC_WHITE),
        ("FONTSIZE",   (0,0), (-1,-1), 7.5),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [SC_WHITE, colors.HexColor("#f5f7ff")]),
        ("GRID", (0,0), (-1,-1), 0.3, colors.HexColor("#d0d8e8")),
        ("ALIGN", (4,0), (5,-1), "CENTER"),
        ("LEFTPADDING",  (0,0), (-1,-1), 4),
        ("RIGHTPADDING", (0,0), (-1,-1), 4),
        ("TOPPADDING",   (0,0), (-1,-1), 4),
        ("BOTTOMPADDING",(0,0), (-1,-1), 4),
    ]))
    story.append(t)
    story.append(sp(8))

    story.append(para(
        "Certifié conforme : Les supports listés ci-dessus ont été effacés de manière irréversible selon la méthode indiquée. "
        "Aucune donnée résiduelle ne peut être récupérée au terme de ce processus. Ce document constitue le certificat officiel d'effacement.",
        "body"))

    if data.get("notes"):
        story.append(sp(6))
        story.append(subsection("Notes"))
        story.append(para(data["notes"], "body"))

    story.append(sp(16))
    story.append(hr(color=SC_LGREY))
    sign_rows = [[
        [para("Attestation client", "sign_label"), sp(2),
         para("Je soussigné(e) atteste avoir remis les supports ci-dessus.", "small"), sp(14),
         para("Date : __________ / Signature :", "small")],
        [para("Technicien certifié", "sign_label"), sp(2),
         para(data.get("technicien","Mathieu Pleitinx"), "sign_name"), sp(14),
         para("Signature :", "small")],
    ]]
    t = Table(sign_rows, colWidths=[W*0.44, W*0.44])
    t.setStyle(TableStyle([("VALIGN",(0,0),(-1,-1),"TOP"),
                            ("LEFTPADDING",(0,0),(-1,-1),8),
                            ("TOPPADDING",(0,0),(-1,-1),10)]))
    story.append(t)

    doc.build(story, onFirstPage=fp, onLaterPages=lp)
    return path
