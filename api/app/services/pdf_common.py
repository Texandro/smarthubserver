# -*- coding: utf-8 -*-
"""
SmartHub — Module PDF commun
Charte graphique unifiée : palette, styles, header/footer avec logo,
helpers partagés pour tous les documents (contrats, as-built, forensics, etc.)
"""
import os
from datetime import date
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.colors import HexColor
from reportlab.lib.units import mm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, PageBreak, KeepTogether, Image as RLImage
)
from reportlab.platypus.flowables import Flowable

# ══════════════════════════════════════════════════════════════════════════════
#  LOGO
# ══════════════════════════════════════════════════════════════════════════════

# Chemin du logo — cherche dans plusieurs emplacements
_LOGO_SEARCH_PATHS = [
    os.path.join(os.path.dirname(__file__), "..", "assets", "logo_smartclick.png"),
    os.path.join(os.path.dirname(__file__), "..", "..", "assets", "logo_smartclick.png"),
    "/srv/smarthub/assets/logo_smartclick.png",
    os.path.join(os.path.dirname(__file__), "logo_smartclick.png"),
]

def _find_logo() -> str | None:
    for p in _LOGO_SEARCH_PATHS:
        ap = os.path.abspath(p)
        if os.path.isfile(ap):
            return ap
    return None

LOGO_PATH = _find_logo()

# ══════════════════════════════════════════════════════════════════════════════
#  PALETTE SMARTCLICK
# ══════════════════════════════════════════════════════════════════════════════

SC_BLUE   = HexColor("#1565ff")
SC_LBLUE  = HexColor("#4d8aff")
SC_DARK   = HexColor("#080b10")
SC_GREY   = HexColor("#4a5a7a")
SC_LGREY  = HexColor("#e8edf8")
SC_WHITE  = colors.white
SC_BLACK  = HexColor("#1a1a2e")
SC_AMBER  = HexColor("#f59e0b")
SC_RED    = HexColor("#ff4d6d")
SC_GREEN  = HexColor("#22c55e")

W, H = A4  # 595.27 x 841.89 pt

# ══════════════════════════════════════════════════════════════════════════════
#  INFOS PRESTATAIRE
# ══════════════════════════════════════════════════════════════════════════════

PRESTATAIRE = {
    "nom":          "Smartclick S.R.L.",
    "forme":        "Société à Responsabilité Limitée",
    "nentreprise":  "0746.385.009",
    "siege":        "Brugstraat 22 – 1601 Sint-Pieters-Leeuw",
    "email":        "mathieu.pleitinx@smartclick.be",
    "tel":          "+32 475 43 10 01",
    "representant": "Mathieu Pleitinx",
    "titre":        "Gérant",
}

FOOTER_LINE = (
    "Smartclick S.R.L. – Brugstraat 22 – 1601 Sint-Pieters-Leeuw"
    " – BE 0746.385.009 – mathieu.pleitinx@smartclick.be"
)

# ══════════════════════════════════════════════════════════════════════════════
#  STYLES
# ══════════════════════════════════════════════════════════════════════════════

def make_styles() -> dict:
    base = dict(fontName="Helvetica", fontSize=9, leading=13,
                textColor=SC_BLACK, spaceAfter=4)

    def st(name, **kw):
        return ParagraphStyle(name, **{**base, **kw})

    return {
        "title_doc":    st("title_doc",   fontName="Helvetica-Bold", fontSize=22,
                           textColor=SC_BLUE, spaceAfter=2, leading=26),
        "subtitle":     st("subtitle",    fontName="Helvetica-Bold", fontSize=13,
                           textColor=SC_BLACK, spaceAfter=2),
        "subtitle2":    st("subtitle2",   fontName="Helvetica", fontSize=11,
                           textColor=SC_GREY, spaceAfter=12),
        "section":      st("section",     fontName="Helvetica-Bold", fontSize=11,
                           textColor=SC_BLUE, spaceBefore=10, spaceAfter=4),
        "subsection":   st("subsection",  fontName="Helvetica-Bold", fontSize=9.5,
                           textColor=SC_BLACK, spaceBefore=6, spaceAfter=3),
        "body":         st("body",        alignment=TA_JUSTIFY, leading=14),
        "body_bold":    st("body_bold",   fontName="Helvetica-Bold"),
        "bullet":       st("bullet",      leftIndent=14, firstLineIndent=-8,
                           spaceAfter=3),
        "small":        st("small",       fontSize=8, textColor=SC_GREY),
        "sign_label":   st("sign_label",  fontName="Helvetica-Bold", fontSize=9),
        "sign_name":    st("sign_name",   fontSize=9, textColor=SC_GREY),
        "header_label": st("header_label",fontSize=8, textColor=SC_GREY),
        "header_val":   st("header_val",  fontSize=9, fontName="Helvetica-Bold"),
        "annex_title":  st("annex_title", fontName="Helvetica-Bold", fontSize=11,
                           textColor=SC_WHITE),
        "center":       st("center",      alignment=TA_CENTER, fontName="Helvetica-Bold"),
        "right":        st("right",       alignment=TA_RIGHT, fontSize=8, textColor=SC_GREY),
    }

STYLES = make_styles()


# ══════════════════════════════════════════════════════════════════════════════
#  HEADER / FOOTER UNIFIÉS
# ══════════════════════════════════════════════════════════════════════════════

def _draw_header(canvas, title, ref, first):
    """Header commun : barre bleue + logo + titre + référence."""
    canvas.saveState()

    # ── Barre bleue ──
    canvas.setFillColor(SC_BLUE)
    canvas.rect(0, H - 14 * mm, W, 14 * mm, fill=1, stroke=0)

    # ── Logo ou texte fallback ──
    logo = LOGO_PATH
    if logo and os.path.isfile(logo):
        try:
            logo_h = 9 * mm
            logo_w = logo_h  # carré
            canvas.drawImage(logo, 15 * mm, H - 12.5 * mm, width=logo_w,
                             height=logo_h, preserveAspectRatio=True, mask="auto")
            text_x = 15 * mm + logo_w + 3 * mm
        except Exception:
            text_x = 20 * mm
    else:
        text_x = 20 * mm

    # ── Nom "smartclick" ──
    canvas.setFillColor(SC_WHITE)
    canvas.setFont("Helvetica-Bold", 11)
    canvas.drawString(text_x, H - 9 * mm, "smartclick")

    # ── Référence doc (à droite, toujours) ──
    if ref:
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(HexColor("#aabbdd"))
        canvas.drawRightString(W - 20 * mm, H - 9 * mm, ref)
    elif not first:
        # Sur les pages suivantes, afficher le titre court
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(HexColor("#d0dfff"))
        canvas.drawRightString(W - 20 * mm, H - 9 * mm, title[:60])

    canvas.restoreState()


def _draw_footer(canvas, doc):
    """Footer commun : barre gris clair + infos société + page."""
    canvas.saveState()
    canvas.setFillColor(SC_LGREY)
    canvas.rect(0, 0, W, 10 * mm, fill=1, stroke=0)
    canvas.setFillColor(SC_GREY)
    canvas.setFont("Helvetica", 7)
    canvas.drawString(20 * mm, 3.5 * mm, FOOTER_LINE)
    canvas.drawRightString(W - 20 * mm, 3.5 * mm, f"Page {doc.page}")
    canvas.restoreState()


def make_page_callbacks(doc_title: str, ref: str = ""):
    """Retourne (on_first_page, on_later_pages) pour SimpleDocTemplate.build()."""
    def on_first_page(canvas, doc):
        _draw_header(canvas, doc_title, ref, first=True)
        _draw_footer(canvas, doc)

    def on_later_pages(canvas, doc):
        _draw_header(canvas, doc_title, ref, first=False)
        _draw_footer(canvas, doc)

    return on_first_page, on_later_pages


# ══════════════════════════════════════════════════════════════════════════════
#  FLOWABLE HELPERS
# ══════════════════════════════════════════════════════════════════════════════

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


# ══════════════════════════════════════════════════════════════════════════════
#  BLOCS RÉUTILISABLES
# ══════════════════════════════════════════════════════════════════════════════

def parties_block(prestataire, client):
    """Tableau parties contractantes (prestataire | client)."""
    def party_cell(p, label):
        lines = [
            f"<b>{p['nom']}</b>",
            p.get("forme", ""),
            f"N° d'entreprise : {p.get('nentreprise', '')}",
            f"Siège social : {p.get('siege', '')}",
        ]
        if p.get("representant"):
            lines.append(f"Représentée par : {p['representant']}")
        if p.get("email"):
            lines.append(p["email"])
        content = "<br/>".join(l for l in lines if l.strip())
        return [
            Paragraph(f"<b>{label}</b>", STYLES["small"]),
            sp(3),
            Paragraph(content, STYLES["body"]),
        ]

    data = [[party_cell(prestataire, "LE PRESTATAIRE"),
             party_cell(client, "LE CLIENT")]]
    t = Table(data, colWidths=[W * 0.44, W * 0.44])
    t.setStyle(TableStyle([
        ("VALIGN",       (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING",  (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING",   (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 8),
        ("BOX",          (0, 0), (0, 0),   0.5, SC_LBLUE),
        ("BOX",          (1, 0), (1, 0),   0.5, SC_LBLUE),
        ("BACKGROUND",   (0, 0), (0, 0),   HexColor("#f0f4ff")),
        ("BACKGROUND",   (1, 0), (1, 0),   HexColor("#f8f8ff")),
        ("ROUNDEDCORNERS", [4]),
    ]))
    return t


def sign_block(lieu="", date_str="", client_nom="", client_fn=""):
    """Bloc double signature (client + prestataire)."""
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
        ],
    ]
    t = Table(data, colWidths=[W * 0.44, W * 0.44])
    t.setStyle(TableStyle([
        ("SPAN",         (0, 0), (1, 0)),
        ("VALIGN",       (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING",  (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING",   (1, 0), (-1, -1), 12),
        ("LINEABOVE",    (0, 1), (0, 1),   0.5, SC_LGREY),
        ("LINEABOVE",    (1, 1), (1, 1),   0.5, SC_LGREY),
    ]))
    return t


def price_table(rows, title=None):
    """Tableau tarifaire standard 2 colonnes (Prestation | Prix HTVA)."""
    header = [para(c, "body_bold") for c in ["Prestation", "Prix HTVA"]]
    data = [header] + [[para(r[0]), para(r[1], "right")] for r in rows]
    t = Table(data, colWidths=[W * 0.65, W * 0.22])
    t.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, 0), SC_BLUE),
        ("TEXTCOLOR",     (0, 0), (-1, 0), SC_WHITE),
        ("FONTNAME",      (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",      (0, 0), (-1, -1), 8.5),
        ("ROWBACKGROUNDS",(0, 1), (-1, -1), [colors.white, HexColor("#f5f7ff")]),
        ("GRID",          (0, 0), (-1, -1), 0.3, HexColor("#d0d8e8")),
        ("LEFTPADDING",   (0, 0), (-1, -1), 8),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 8),
        ("TOPPADDING",    (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("ALIGN",         (1, 0), (1, -1),  "RIGHT"),
    ]))
    elems = []
    if title:
        elems.append(para(title, "subsection"))
    elems.append(t)
    return elems


def annex_banner(title):
    """Bannière bleue pleine largeur pour les pages d'annexe."""
    data = [[para(f"ANNEXE – {title}", "annex_title")]]
    t = Table(data, colWidths=[W * 0.88])
    t.setStyle(TableStyle([
        ("BACKGROUND",   (0, 0), (-1, -1), SC_BLUE),
        ("LEFTPADDING",  (0, 0), (-1, -1), 12),
        ("TOPPADDING",   (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 8),
        ("ROUNDEDCORNERS", [4]),
    ]))
    return t


# ══════════════════════════════════════════════════════════════════════════════
#  DOCUMENT FACTORY
# ══════════════════════════════════════════════════════════════════════════════

def base_doc(path_or_buf, title: str, ref: str = ""):
    """
    Crée un SimpleDocTemplate avec marges standard + callbacks header/footer.
    path_or_buf : chemin fichier ou io.BytesIO
    Retourne (doc, on_first_page, on_later_pages)
    """
    doc = SimpleDocTemplate(
        path_or_buf,
        pagesize=A4,
        leftMargin=20 * mm, rightMargin=20 * mm,
        topMargin=20 * mm, bottomMargin=16 * mm,
        title=title,
        author="Smartclick S.R.L.",
    )
    fp, lp = make_page_callbacks(title, ref)
    return doc, fp, lp


# ══════════════════════════════════════════════════════════════════════════════
#  CLAUSES JURIDIQUES COMMUNES
# ══════════════════════════════════════════════════════════════════════════════

def common_clauses(extra_exclusions=None):
    """Clauses : obligations, responsabilité, confidentialité, droit applicable."""
    elems = []
    elems += [
        section(8, "Obligations du prestataire"),
        para(
            "Le prestataire est tenu à une obligation de moyens. Il ne peut garantir "
            "un résultat particulier, l'exécution dépendant notamment de l'état des "
            "systèmes, des contraintes techniques et des dépendances fournisseurs.",
            "body",
        ),
    ]
    elems += [
        section(9, "Responsabilité"),
        para(
            "Le prestataire ne pourra être tenu responsable des dommages indirects, "
            "pertes de données, interruptions d'activité ou conséquences juridiques "
            "découlant de l'exécution ou de l'interprétation des livrables. Sa "
            "responsabilité est limitée au montant des honoraires facturés sur la "
            "période concernée.",
            "body",
        ),
    ]
    elems += [
        section(10, "Confidentialité"),
        para(
            "Le prestataire est tenu à une obligation de confidentialité renforcée "
            "concernant l'ensemble des informations, données et documents auxquels "
            "il a accès dans le cadre de la présente mission. Cette obligation "
            "s'applique également à toute personne intervenant pour son compte.",
            "body",
        ),
    ]
    elems += [
        section(13, "Droit applicable et juridiction compétente"),
        para(
            "La présente convention est soumise au droit belge. En cas de litige, "
            "les parties s'engagent à recourir préalablement à la médiation. À "
            "défaut d'accord, les tribunaux de l'arrondissement judiciaire de "
            "Bruxelles seront seuls compétents.",
            "body",
        ),
    ]
    return elems
