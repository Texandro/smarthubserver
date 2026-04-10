# -*- coding: utf-8 -*-
"""
SmartHub — Générateur PDF As-Built Réseau
ReportLab — dessin vectoriel rack, patch panel, floor plan
Utilise pdf_common pour la charte graphique unifiée.
"""
import io
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm, cm
from reportlab.lib import colors
from reportlab.lib.colors import HexColor
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph,
    Spacer, PageBreak, HRFlowable
)
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.graphics.shapes import (
    Drawing, Rect, String, Line, Circle, Group
)

from .pdf_common import (
    # Palette
    SC_BLUE, SC_LBLUE, SC_DARK, SC_GREY, SC_LGREY,
    SC_WHITE, SC_BLACK, SC_GREEN, SC_AMBER,
    # Constantes
    W as PAGE_W, H as PAGE_H, FOOTER_LINE, LOGO_PATH, PRESTATAIRE,
    # Styles & helpers
    STYLES, make_styles, make_page_callbacks,
    hr, sp, para, bullet_item, section, subsection,
    # Header / Footer
    _draw_header, _draw_footer,
)

import os

# ── Couleurs spécifiques rack (équipements) ──────────────────
C_SWITCH     = HexColor("#2196F3")
C_ROUTER     = HexColor("#1976D2")
C_AP         = HexColor("#42A5F5")
C_SERVER     = HexColor("#1565C0")
C_NAS        = HexColor("#0D47A1")
C_UPS        = HexColor("#F44336")
C_PDU        = HexColor("#E53935")
C_PATCH      = HexColor("#757575")
C_SHELF      = HexColor("#9E9E9E")
C_OTHER      = HexColor("#607D8B")
C_EMPTY      = HexColor("#E0E0E0")
C_BORDER     = HexColor("#333333")
C_PORT_OK    = HexColor("#4CAF50")
C_PORT_RES   = HexColor("#FF9800")
C_PORT_DISC  = HexColor("#9E9E9E")
C_BLUE_HDR   = HexColor("#1a2a4a")
C_TEXT_LIGHT  = colors.white
C_TEXT_DARK   = HexColor("#212121")

CATEGORY_COLORS = {
    "switch":       C_SWITCH,
    "router":       C_ROUTER,
    "access_point": C_AP,
    "server":       C_SERVER,
    "nas":          C_NAS,
    "ups":          C_UPS,
    "pdu":          C_PDU,
    "patch_panel":  C_PATCH,
    "shelf":        C_SHELF,
    "other":        C_OTHER,
}

PORT_COLORS = {
    "active":       C_PORT_OK,
    "reserved":     C_PORT_RES,
    "disconnected": C_PORT_DISC,
}

MARGIN = 15 * mm


def _category(slot: dict) -> str:
    cat = None
    if slot.get("catalog_item"):
        cat = slot["catalog_item"].get("category")
    return cat or slot.get("custom_category") or "other"


# ══════════════════════════════════════════════════════════════════════════════
#  DESSINS VECTORIELS (inchangés)
# ══════════════════════════════════════════════════════════════════════════════

def draw_rack(rack: dict, slots: list) -> Drawing:
    """
    Dessine le rack en vue face avant avec silhouettes réalistes.
    U1 en bas, Umax en haut.
    """
    U_PX       = 16
    RACK_W     = 420
    LABEL_W    = 30
    EQUIP_W    = RACK_W - LABEL_W - 4
    rack_size  = rack.get("rack_size_u", 12)
    total_h    = rack_size * U_PX + 40

    d = Drawing(RACK_W + 20, total_h + 20)

    # Fond rack
    d.add(Rect(10, 10, RACK_W, total_h,
               fillColor=HexColor("#1C1C1C"),
               strokeColor=C_BORDER, strokeWidth=2))

    # Header rack
    d.add(Rect(10, 10 + total_h - 35, RACK_W, 35,
               fillColor=C_BLUE_HDR, strokeColor=None))
    d.add(String(RACK_W / 2 + 10, 10 + total_h - 22,
                 f"{rack.get('rack_label', 'Rack')} — {rack_size}U",
                 fontSize=10, fontName="Helvetica-Bold",
                 fillColor=C_TEXT_LIGHT, textAnchor="middle"))

    slot_map = {s["position_u"]: s for s in slots}
    occupied = set()

    for u in range(rack_size, 0, -1):
        y_pos = 10 + (rack_size - u) * U_PX + 5

        d.add(String(14, y_pos + (U_PX * 0.3),
                     f"U{u:02d}",
                     fontSize=6, fontName="Helvetica",
                     fillColor=HexColor("#888888")))

        if u in occupied:
            continue

        slot = slot_map.get(u)
        if slot:
            h_u    = slot.get("height_u", 1)
            eq_h   = h_u * U_PX - 2
            cat    = _category(slot)
            bg_col = CATEGORY_COLORS.get(cat, C_OTHER)

            for uu in range(u, u - h_u, -1):
                occupied.add(uu)

            d.add(Rect(10 + LABEL_W, y_pos, EQUIP_W, eq_h,
                       fillColor=bg_col,
                       strokeColor=HexColor("#444444"),
                       strokeWidth=0.5))

            d.add(Rect(10 + LABEL_W, y_pos, 6, eq_h,
                       fillColor=HexColor("#00000040"),
                       strokeColor=None))

            model_txt = ""
            if slot.get("catalog_item"):
                ci = slot["catalog_item"]
                model_txt = f"{ci.get('manufacturer', '')} {ci.get('model', '')}"
            else:
                model_txt = f"{slot.get('custom_manufacturer', '')} {slot.get('custom_model', '')}"

            hostname = slot.get("hostname") or ""
            ip       = slot.get("ip_address") or ""

            text_y = y_pos + eq_h / 2 + 1
            d.add(String(10 + LABEL_W + 12, text_y,
                         model_txt[:35],
                         fontSize=min(7, eq_h * 0.45),
                         fontName="Helvetica-Bold",
                         fillColor=C_TEXT_LIGHT))

            if hostname or ip:
                sub = f"{hostname}  {ip}".strip()
                d.add(String(10 + LABEL_W + 12, text_y - 8,
                             sub[:40],
                             fontSize=5.5, fontName="Helvetica",
                             fillColor=HexColor("#CCCCCC")))

            if cat in ("switch", "patch_panel") and slot.get("catalog_item"):
                port_count = slot["catalog_item"].get("port_count") or 0
                if port_count and port_count <= 52 and eq_h >= 10:
                    _draw_ports(d, port_count,
                                10 + LABEL_W + EQUIP_W - port_count * 8 - 10,
                                y_pos + 3, min(6, eq_h - 6))

            d.add(Circle(10 + LABEL_W + EQUIP_W - 10, y_pos + eq_h / 2,
                         2.5, fillColor=C_PORT_OK, strokeColor=None))

        else:
            d.add(Rect(10 + LABEL_W, y_pos, EQUIP_W, U_PX - 2,
                       fillColor=C_EMPTY,
                       strokeColor=HexColor("#BBBBBB"),
                       strokeWidth=0.3))

    for ux in [14, RACK_W]:
        for uy in [15, total_h]:
            d.add(Circle(ux, uy, 3,
                         fillColor=HexColor("#555555"),
                         strokeColor=HexColor("#888888"),
                         strokeWidth=0.5))

    return d


def _draw_ports(d: Drawing, count: int, x: float, y: float, h: float):
    """Dessine une rangée de ports miniatures."""
    port_w = min(6, (180 / count) if count > 0 else 6)
    gap = 1
    for i in range(min(count, 48)):
        px = x + i * (port_w + gap)
        d.add(Rect(px, y, port_w, h,
                   fillColor=HexColor("#111111"),
                   strokeColor=HexColor("#333333"),
                   strokeWidth=0.3,
                   rx=1, ry=1))


def draw_patch_panel(port_count: int, mappings: list) -> Drawing:
    """Dessine la face avant d'un patch panel avec ports colorés."""
    PORTS_PER_ROW = 12
    PORT_D        = 18
    GAP           = 6
    ROWS          = (port_count + PORTS_PER_ROW - 1) // PORTS_PER_ROW
    WW            = PORTS_PER_ROW * (PORT_D + GAP) + 40
    HH            = ROWS * (PORT_D + GAP) + 30

    d = Drawing(WW, HH + 10)

    d.add(Rect(0, 0, WW, HH,
               fillColor=HexColor("#2A2A2A"),
               strokeColor=C_BORDER, strokeWidth=1.5))

    mapping_map = {m["port_number"]: m for m in mappings}

    for i in range(1, port_count + 1):
        row = (i - 1) // PORTS_PER_ROW
        col = (i - 1) % PORTS_PER_ROW
        px  = 20 + col * (PORT_D + GAP)
        py  = HH - 20 - row * (PORT_D + GAP)

        m     = mapping_map.get(i)
        color = PORT_COLORS.get(m["status"] if m else "disconnected", C_PORT_DISC)

        d.add(Rect(px, py - PORT_D, PORT_D, PORT_D,
                   fillColor=HexColor("#111111"),
                   strokeColor=color, strokeWidth=2,
                   rx=2, ry=2))

        d.add(Rect(px + 2, py - 4, PORT_D - 4, 3,
                   fillColor=color, strokeColor=None))

        d.add(String(px + PORT_D / 2, py - PORT_D - 8,
                     str(i),
                     fontSize=6, fontName="Helvetica",
                     fillColor=HexColor("#AAAAAA"),
                     textAnchor="middle"))

    return d


def draw_floorplan(fp: dict) -> Drawing:
    """Dessine le plan de situation simplifié."""
    cw = fp.get("canvas_width", 800)
    ch = fp.get("canvas_height", 600)
    SCALE = min(500 / cw, 380 / ch)

    WW = cw * SCALE
    HH = ch * SCALE

    d = Drawing(WW + 20, HH + 20)

    d.add(Rect(0, 0, WW + 20, HH + 20,
               fillColor=HexColor("#F5F5F5"),
               strokeColor=None))

    for room in (fp.get("rooms") or []):
        rx = room.get("x", 0) * SCALE + 10
        ry = (ch - room.get("y", 0) - room.get("height", 100)) * SCALE + 10
        rw = room.get("width", 100) * SCALE
        rh = room.get("height", 100) * SCALE
        d.add(Rect(rx, ry, rw, rh,
                   fillColor=HexColor("#E3F2FD"),
                   strokeColor=HexColor("#1565C0"),
                   strokeWidth=1.5))
        d.add(String(rx + rw / 2, ry + rh / 2,
                     room.get("name", ""),
                     fontSize=8, fontName="Helvetica-Bold",
                     fillColor=HexColor("#1565C0"),
                     textAnchor="middle"))

    for outlet in (fp.get("outlets") or []):
        ox = outlet.get("x", 0) * SCALE + 10
        oy = (ch - outlet.get("y", 0)) * SCALE + 10
        d.add(Rect(ox - 5, oy - 5, 10, 10,
                   fillColor=C_PORT_OK, strokeColor=None, rx=2, ry=2))
        d.add(String(ox, oy - 12,
                     outlet.get("label", ""),
                     fontSize=5.5, fontName="Helvetica",
                     fillColor=C_TEXT_DARK, textAnchor="middle"))

    rp = fp.get("rack_position")
    if rp:
        rpx = rp.get("x", 0) * SCALE + 10
        rpy = (ch - rp.get("y", 0) - 20) * SCALE + 10
        d.add(Rect(rpx - 12, rpy - 10, 24, 20,
                   fillColor=C_BLUE_HDR,
                   strokeColor=C_BORDER, strokeWidth=1))
        d.add(String(rpx, rpy - 5, "RACK",
                     fontSize=6, fontName="Helvetica-Bold",
                     fillColor=C_TEXT_LIGHT, textAnchor="middle"))

    DEVICE_ICONS = {"access_point": "AP", "camera": "CAM", "printer": "PRT"}
    for dev in (fp.get("devices") or []):
        dx = dev.get("x", 0) * SCALE + 10
        dy = (ch - dev.get("y", 0)) * SCALE + 10
        d.add(Circle(dx, dy, 7,
                     fillColor=C_AP, strokeColor=None))
        d.add(String(dx, dy - 3,
                     DEVICE_ICONS.get(dev.get("type", ""), "?"),
                     fontSize=7, fontName="Helvetica-Bold",
                     fillColor=C_TEXT_LIGHT, textAnchor="middle"))
        if dev.get("name"):
            d.add(String(dx, dy - 16, dev["name"],
                         fontSize=5.5, fontName="Helvetica",
                         fillColor=C_TEXT_DARK, textAnchor="middle"))

    return d


# ══════════════════════════════════════════════════════════════════════════════
#  GÉNÉRATION PDF AS-BUILT COMPLET
# ══════════════════════════════════════════════════════════════════════════════

def generate_rack_pdf(document: dict, rack: dict, slots: list,
                      patch_panels: list, floor_plan: dict | None,
                      client_name: str) -> bytes:
    """
    Génère le PDF as-built complet.
    Retourne les bytes du PDF.
    """
    buf = io.BytesIO()

    doc_title = f"AS-BUILT — {document.get('title', '').upper()}"
    ref = doc_title

    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=20 * mm, rightMargin=20 * mm,
        topMargin=20 * mm, bottomMargin=16 * mm,
        title=doc_title,
        author="Smartclick S.R.L.",
    )

    # Styles locaux pour le contenu as-built
    H1 = ParagraphStyle("h1",
        fontName="Helvetica-Bold", fontSize=14,
        textColor=SC_BLUE, spaceBefore=12, spaceAfter=6)
    BODY = ParagraphStyle("body_ab",
        fontName="Helvetica", fontSize=9,
        textColor=SC_BLACK, spaceAfter=4)
    SMALL = ParagraphStyle("small_ab",
        fontName="Helvetica", fontSize=7,
        textColor=SC_GREY)

    story = []

    # ── Page 1 : Garde ───────────────────────────────────────
    story.append(Spacer(1, 30 * mm))

    story.append(Paragraph(
        "<b>AS-BUILT RÉSEAU</b>",
        ParagraphStyle("ct", fontName="Helvetica-Bold", fontSize=22,
                       textColor=SC_BLUE, alignment=TA_LEFT,
                       spaceAfter=12)))
    story.append(Paragraph(
        client_name,
        ParagraphStyle("ct2", fontName="Helvetica-Bold", fontSize=14,
                       textColor=SC_BLACK, alignment=TA_LEFT,
                       spaceAfter=6)))

    story.append(HRFlowable(width="100%", thickness=1, color=SC_LGREY,
                             spaceAfter=8 * mm))

    meta = [
        ["Client",   client_name],
        ["Document", document.get("title", "")],
        ["Version",  f"v{document.get('version', 1)}"],
        ["Date",     datetime.now().strftime("%d/%m/%Y")],
        ["Statut",   document.get("status", "draft").upper()],
    ]
    meta_tbl = Table(meta, colWidths=[40 * mm, PAGE_W - 2 * 20 * mm - 40 * mm])
    meta_tbl.setStyle(TableStyle([
        ("FONTNAME",       (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTSIZE",       (0, 0), (-1, -1), 10),
        ("TEXTCOLOR",      (0, 0), (0, -1),  SC_BLUE),
        ("TEXTCOLOR",      (1, 0), (-1, -1), SC_BLACK),
        ("ROWBACKGROUNDS", (0, 0), (-1, -1),
         [HexColor("#F8F8F8"), colors.white]),
        ("GRID",           (0, 0), (-1, -1), 0.3, HexColor("#DDDDDD")),
        ("TOPPADDING",     (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING",  (0, 0), (-1, -1), 7),
        ("LEFTPADDING",    (0, 0), (-1, -1), 10),
    ]))
    story.append(meta_tbl)
    if document.get("notes"):
        story.append(Spacer(1, 4 * mm))
        story.append(Paragraph(f"<i>{document['notes']}</i>", BODY))
    story.append(PageBreak())

    # ── Page 2 : Vue rack ────────────────────────────────────
    story.append(Paragraph("Vue Rack — Face avant", H1))
    story.append(Paragraph(
        f"{rack.get('rack_label', '')} — {rack.get('rack_size_u', 12)}U"
        + (f" — {rack.get('location', '')}" if rack.get("location") else ""),
        BODY))
    story.append(Spacer(1, 3 * mm))

    rack_drawing = draw_rack(rack, slots)
    rack_drawing.width  = PAGE_W - 2 * 20 * mm
    rack_drawing.height = rack_drawing.height
    story.append(rack_drawing)
    story.append(PageBreak())

    # ── Page 3 : Inventaire rack ─────────────────────────────
    story.append(Paragraph("Inventaire du Rack", H1))
    inv_data = [["U", "Fabricant", "Modèle", "Hostname", "IP", "S/N", "Rôle"]]
    for slot in sorted(slots, key=lambda s: s.get("position_u", 0)):
        ci = slot.get("catalog_item") or {}
        mfr   = ci.get("manufacturer") or slot.get("custom_manufacturer", "")
        model = ci.get("model")        or slot.get("custom_model", "")
        inv_data.append([
            f"U{slot.get('position_u', 0):02d}",
            mfr[:15], model[:20],
            (slot.get("hostname") or "")[:18],
            (slot.get("ip_address") or "")[:15],
            (slot.get("serial_number") or "")[:15],
            (slot.get("role") or "")[:25],
        ])
    inv_tbl = Table(inv_data,
                    colWidths=[12 * mm, 28 * mm, 38 * mm, 32 * mm, 28 * mm, 28 * mm, None])
    inv_tbl.setStyle(TableStyle([
        ("FONTNAME",       (0, 0), (-1, 0),  "Helvetica-Bold"),
        ("FONTSIZE",       (0, 0), (-1, -1), 8),
        ("BACKGROUND",     (0, 0), (-1, 0),  SC_BLUE),
        ("TEXTCOLOR",      (0, 0), (-1, 0),  colors.white),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1),
         [HexColor("#F5F5F5"), colors.white]),
        ("GRID",           (0, 0), (-1, -1), 0.3, HexColor("#CCCCCC")),
        ("TOPPADDING",     (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING",  (0, 0), (-1, -1), 4),
        ("LEFTPADDING",    (0, 0), (-1, -1), 4),
    ]))
    story.append(inv_tbl)
    story.append(PageBreak())

    # ── Page 4+ : Patch panels ───────────────────────────────
    for pp_data in patch_panels:
        slot    = pp_data.get("slot", {})
        ports   = pp_data.get("ports", [])
        ci      = slot.get("catalog_item") or {}
        pc      = ci.get("port_count") or slot.get("port_count") or 24
        title_txt = f"Patch Panel — U{slot.get('position_u', 0):02d} — {ci.get('model', '')}"
        story.append(Paragraph(title_txt, H1))

        pp_drawing = draw_patch_panel(pc, ports)
        story.append(pp_drawing)
        story.append(Spacer(1, 4 * mm))

        if ports:
            map_data = [["Port", "Destination", "Câble", "Longueur", "Switch port", "Statut"]]
            for p in sorted(ports, key=lambda x: x.get("port_number", 0)):
                status_icon = {"active": "■", "reserved": "■", "disconnected": "■"}
                map_data.append([
                    str(p.get("port_number", "")),
                    (p.get("destination_label") or "")[:35],
                    (p.get("cable_type") or "").upper(),
                    f"{p.get('cable_length_m', '')}m" if p.get("cable_length_m") else "",
                    (p.get("connected_switch_port") or "")[:25],
                    status_icon.get(p.get("status", "disconnected"), ""),
                ])
            map_tbl = Table(map_data,
                            colWidths=[12 * mm, 60 * mm, 20 * mm, 20 * mm, 50 * mm, None])
            map_tbl.setStyle(TableStyle([
                ("FONTNAME",       (0, 0), (-1, 0),  "Helvetica-Bold"),
                ("FONTSIZE",       (0, 0), (-1, -1), 8),
                ("BACKGROUND",     (0, 0), (-1, 0),  SC_BLUE),
                ("TEXTCOLOR",      (0, 0), (-1, 0),  C_TEXT_LIGHT),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1),
                 [HexColor("#F5F5F5"), colors.white]),
                ("GRID",           (0, 0), (-1, -1), 0.3, HexColor("#CCCCCC")),
                ("TOPPADDING",     (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING",  (0, 0), (-1, -1), 3),
                ("LEFTPADDING",    (0, 0), (-1, -1), 4),
            ]))
            story.append(map_tbl)

        story.append(PageBreak())

    # ── Floor plan ───────────────────────────────────────────
    if floor_plan and (floor_plan.get("rooms") or floor_plan.get("outlets")):
        story.append(Paragraph("Plan de situation", H1))
        fp_drawing = draw_floorplan(floor_plan)
        story.append(fp_drawing)

        if floor_plan.get("outlets"):
            story.append(Spacer(1, 4 * mm))
            story.append(Paragraph("Légende des prises", H1))
            leg_data = [["Identifiant prise", "Pièce", "Port patch panel"]]
            for o in floor_plan["outlets"]:
                leg_data.append([
                    o.get("label", ""),
                    o.get("room_name", ""),
                    str(o.get("patch_port_id", "")) if o.get("patch_port_id") else "",
                ])
            leg_tbl = Table(leg_data, colWidths=[80 * mm, 60 * mm, None])
            leg_tbl.setStyle(TableStyle([
                ("FONTNAME",       (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE",       (0, 0), (-1, -1), 8),
                ("BACKGROUND",     (0, 0), (-1, 0), SC_BLUE),
                ("TEXTCOLOR",      (0, 0), (-1, 0), C_TEXT_LIGHT),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1),
                 [HexColor("#F5F5F5"), colors.white]),
                ("GRID",           (0, 0), (-1, -1), 0.3, HexColor("#CCCCCC")),
                ("TOPPADDING",     (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING",  (0, 0), (-1, -1), 4),
                ("LEFTPADDING",    (0, 0), (-1, -1), 6),
            ]))
            story.append(leg_tbl)

        story.append(PageBreak())

    # ── Notes & historique ───────────────────────────────────
    story.append(Paragraph("Notes & Historique", H1))
    story.append(Paragraph(
        document.get("notes", "Aucune note.") or "Aucune note.", BODY))

    # ── Build avec header/footer unifiés ─────────────────────
    fp_cb, lp_cb = make_page_callbacks(doc_title, ref)
    doc.build(story, onFirstPage=fp_cb, onLaterPages=lp_cb)
    return buf.getvalue()
