# -*- coding: utf-8 -*-
"""
SmartHub — Générateurs PDF côté serveur
Contrats, lettres de mission, fiches intervention, shredding, forensics
Utilise pdf_common pour la charte graphique unifiée.
"""
import io
import os
from datetime import date
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.colors import HexColor
from reportlab.lib.units import mm
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, PageBreak, KeepTogether, Image as RLImage
)

from .pdf_common import (
    # Palette
    SC_BLUE, SC_LBLUE, SC_DARK, SC_GREY, SC_LGREY,
    SC_WHITE, SC_BLACK, SC_AMBER, SC_RED, SC_GREEN,
    # Constantes
    W, H, PRESTATAIRE, STYLES,
    # Helpers
    hr, sp, para, bullet_item, section, subsection,
    # Blocs
    parties_block, sign_block, price_table, annex_banner,
    # Factory
    base_doc, common_clauses,
)

# ══════════════════════════════════════════════════════════════════════════════
#  1. LETTRE DE MISSION GÉNÉRIQUE
# ══════════════════════════════════════════════════════════════════════════════

def generate_lm(data: dict) -> bytes:
    """
    Génère une lettre de mission. Retourne les bytes du PDF.
    data: {
      client: {nom, forme, nentreprise, siege, representant, email},
      type: 'gestion_it' | 'cloud' | 'full_inclusive' | 'full_exclusive' | ...
      reference, date_doc, lieu, contexte, missions, exclusions,
      tarif_horaire, forfait_mensuel, budget_materiel, inclus_visites,
      creation_user_prix, installation_poste, duree, notes, ...
    }
    """
    TYPE_TITLES = {
        "gestion_it":       ("Gestion IT opérationnelle & parc informatique",
                             "Lettre de mission – Contrat de services"),
        "cloud":            ("Infrastructure serveurs Cloud",
                             "Location, exploitation & administration"),
        "reseau":           ("Projet réseau — Starter Pack PME",
                             "Fourniture, installation & configuration"),
        "full_inclusive":   ("IT at your service – Full Inclusive",
                             "Forfait mensuel tout compris"),
        "full_exclusive":   ("IT at your service – Full Exclusive",
                             "Facturation à la consommation"),
        "forensics":        ("Mission de forensics informatique",
                             "Lettre de mission – Expertise technique"),
        "dev":              ("Mission de développement informatique",
                             "Lettre de mission – Développement sur mesure"),
        "ponctuel":         ("Mission ponctuelle",
                             "Lettre de mission – Prestation de services"),
        "recherche_donnees":("Mission de recherche de données",
                             "Lettre de mission – Migration / Récupération"),
        "maintenance":      ("Gestion & maintenance IT",
                             "Lettre de mission – Services managés"),
    }

    t = data.get("type", "ponctuel")

    # Templates dédiés avec sections alignées
    if t == "cloud":
        return _generate_cloud_lm(data)
    if t == "gestion_it":
        return _generate_gestion_it_lm(data)
    if t == "reseau":
        return _generate_reseau_lm(data)
    if t == "full_inclusive":
        return _generate_full_inclusive_lm(data)

    title1, title2 = TYPE_TITLES.get(t, ("Lettre de Mission", "Contrat de services"))
    ref = data.get("reference", "")

    buf = io.BytesIO()
    doc, fp, lp = base_doc(buf, title1, ref)
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
    story.append(para(
        data.get("contexte",
                 "Le client souhaite confier au prestataire les prestations décrites ci-après."),
        "body"))
    story.append(sp(6))
    story.append(hr(color=SC_LGREY, thickness=0.5))
    story.append(para("IL A ENSUITE ÉTÉ CONVENU CE QUI SUIT", "body_bold"))
    story.append(sp(6))

    # ── 1. Objet ──
    story.append(section(1, "Objet de la convention"))
    story.append(para(
        "Le présent contrat a pour objet la fourniture, par le prestataire, des "
        "prestations de services informatiques décrites ci-après, au bénéfice du "
        "client, dans le cadre d'une obligation de moyens.", "body"))

    # ── 2. Missions ──
    story.append(section(2, "Missions du prestataire"))
    story.append(para("Les missions confiées au prestataire comprennent notamment :", "body"))
    for m in data.get("missions", []):
        story.append(bullet_item(m))

    # ── Forensics spécifique ──
    if t == "forensics":
        story.append(sp(4))
        story.append(section(3, "Nature de l'intervention – Forensics"))
        story.append(para(
            "Le prestataire agit exclusivement en qualité d'expert technique "
            "indépendant. Il ne procède à aucune qualification juridique, disciplinaire "
            "ou pénale des faits observés. Les constatations consignées dans le rapport "
            "sont strictement techniques et factuelles.", "body"))
        story.append(section(4, "Préservation des données et intégrité"))
        story.append(para(
            "Le prestataire s'engage à respecter les bonnes pratiques de préservation "
            "des données numériques. Lorsque cela est pertinent, il procède à la "
            "réalisation d'images forensiques des supports, constituant les éléments "
            "techniques de référence pour l'analyse.", "body"))
        story.append(section(5, "Conservation des supports"))
        story.append(para(
            "Le prestataire n'a pas vocation à conserver le matériel analysé. La "
            "conservation des supports physiques relève de la responsabilité du client. "
            "Les éléments techniques produits (images, hashes, documentation) sont conservés "
            "pendant la durée strictement nécessaire.", "body"))
        story.append(section(6, "Rapport et utilisation"))
        story.append(para(
            "Le prestataire remet au client un rapport de forensics informatique "
            "reprenant les constatations techniques effectuées. Ce rapport est destiné "
            "au client et pourra, sous sa responsabilité exclusive, être transmis à ses "
            "conseils juridiques ou aux autorités compétentes.", "body"))

    # ── Full Inclusive ──
    if t == "full_inclusive" and data.get("forfait_mensuel"):
        story.append(section(3, "Formule Full Inclusive – Détail du forfait"))
        story.append(para(
            f"Forfait mensuel : <b>{data['forfait_mensuel']:.2f} € HTVA / mois</b>", "body"))
        if data.get("inclus_visites"):
            story.append(para(
                f"Visites incluses : {data['inclus_visites']} visite(s) par mois et par "
                f"site (si planifiée et consommée).", "body"))
        if data.get("budget_materiel"):
            story.append(para(
                f"Budget matériel inclus : {data['budget_materiel']:.2f} € HTVA "
                f"(utilisable pour matériel standard, accord préalable requis).", "body"))

    # ── Exclusions ──
    excl_num = 7 if t == "forensics" else 3
    story.append(section(excl_num, "Prestations exclues"))
    default_excl = [
        "Forensics (lettre de mission spécifique).",
        "Projets/migrations majeurs non expressément convenus (devis préalable).",
        "Interventions d'urgence hors heures ouvrées sans accord préalable.",
    ]
    if t in ("gestion_it",):
        default_excl = [
            "Administration des serveurs Cloud (contrat séparé).",
            "Forensics (lettre de mission spécifique).",
            "Projets/migrations majeurs non convenus (devis).",
        ]
    elif t == "cloud":
        default_excl = [
            "Support utilisateur final (Office/Outlook/Teams, usage applicatif).",
            "Installation et maintenance des postes de travail (contrat séparé).",
            "Forensics et effacement sécurisé (contrats spécifiques).",
            "Projets/migrations non expressément convenus (devis/bon de commande).",
        ]
    elif t == "forensics":
        default_excl = [
            "Toute qualification juridique, disciplinaire ou pénale des faits observés.",
            "Récupération garantie de données (dépend de l'état des supports).",
            "Conservation des supports physiques au-delà de la mission.",
        ]
    for e in (data.get("exclusions") or default_excl):
        story.append(bullet_item(e))

    # ── Honoraires ──
    story.append(section(excl_num + 1, "Honoraires et frais"))
    tarif = data.get("tarif_horaire", 81.25)

    if t == "cloud" and data.get("cloud"):
        _build_cloud_pricing(story, data, tarif)
    elif t == "reseau" and data.get("reseau"):
        _build_reseau_pricing(story, data)
    else:
        story.append(para(
            f"Les prestations sont facturées sur base d'un tarif horaire de "
            f"<b>{tarif:.2f} € HTVA</b>. La facturation est réalisée sur base "
            "du temps réellement presté, sauf forfaits expressément convenus.", "body"))
        if data.get("installation_poste"):
            story.append(para(
                f"Installation d'un nouveau poste : "
                f"<b>{data['installation_poste']:.2f} € HTVA</b>.", "body"))
        if data.get("creation_user_prix"):
            story.append(para(
                f"Création d'un nouvel utilisateur : "
                f"<b>{data['creation_user_prix']:.2f} € HTVA</b>.", "body"))

    # ── Durée ──
    story.append(section(excl_num + 2, "Durée du contrat"))
    duree = data.get("duree", "indeterminee")
    if duree == "indeterminee":
        story.append(para(
            "Le présent contrat est conclu pour une durée indéterminée. Il peut être "
            "résilié par l'une ou l'autre des parties moyennant un préavis raisonnable "
            "d'un (1) mois, sans préjudice des prestations déjà réalisées.", "body"))
    elif duree == "ponctuelle":
        story.append(para(
            "La présente mission est un ordre de mission ponctuel. Le contrat prend fin "
            "à la remise du livrable convenu.", "body"))
    else:
        story.append(para(
            f"Le présent contrat est conclu pour une durée déterminée : "
            f"{data.get('duree_texte', 'à convenir')}.", "body"))

    # ── Clauses communes ──
    story += common_clauses()

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
        client_fn=data["client"].get("representant", ""),
    ))

    # ── ANNEXE Grille tarifaire ──
    story.append(PageBreak())
    story.append(annex_banner("Grille tarifaire"))
    story.append(sp(8))

    if t == "cloud":
        _build_cloud_annex(story, data)
    elif t == "reseau" and data.get("reseau"):
        _build_reseau_annex(story, data)
    else:
        _build_standard_annex(story, data, tarif)

    doc.build(story, onFirstPage=fp, onLaterPages=lp)
    return buf.getvalue()


# ══════════════════════════════════════════════════════════════════════════════
#  1b. LETTRE DE MISSION GESTION IT — Sections alignées sur Cloud
# ══════════════════════════════════════════════════════════════════════════════

def _generate_gestion_it_lm(data: dict) -> bytes:
    """
    Template dédié pour les contrats Gestion IT opérationnelle.
    Structure alignée sur le template Cloud.
    """
    ref = data.get("reference", "")
    buf = io.BytesIO()
    doc, fp, lp = base_doc(buf, "Gestion IT opérationnelle & parc informatique", ref)
    story = []

    # ── Couverture ──
    story.append(sp(18))
    story.append(para("LETTRE DE MISSION", "title_doc"))
    story.append(para("Gestion IT opérationnelle & parc informatique", "subtitle"))
    story.append(para("Lettre de mission – Contrat de services", "subtitle2"))
    story.append(hr(thickness=2, space_before=4, space_after=16))

    # §1 PARTIES
    story.append(section(1, "Parties"))
    story.append(para("Entre les soussignés :", "body"))
    story.append(sp(6))
    story.append(parties_block(PRESTATAIRE, data["client"]))
    story.append(sp(8))

    # §2 OBJET
    story.append(hr(color=SC_LGREY, thickness=0.5))
    story.append(para("IL A PRÉALABLEMENT ÉTÉ EXPOSÉ CE QUI SUIT", "body_bold"))
    story.append(sp(4))
    story.append(para(
        data.get("contexte",
                 "Le client souhaite confier au prestataire la gestion opérationnelle "
                 "de son parc informatique et de son infrastructure IT."),
        "body"))
    story.append(sp(6))
    story.append(hr(color=SC_LGREY, thickness=0.5))
    story.append(para("IL A ENSUITE ÉTÉ CONVENU CE QUI SUIT", "body_bold"))
    story.append(sp(6))

    story.append(section(2, "Objet de la convention"))
    story.append(para(
        "Le présent contrat a pour objet la fourniture, par le prestataire, des "
        "prestations de services informatiques décrites ci-après, au bénéfice du "
        "client, dans le cadre d'une obligation de moyens.", "body"))

    # §3 PÉRIMÈTRE DES SERVICES
    story.append(section(3, "Périmètre des services"))

    story.append(subsection("3.1 Prestations incluses"))
    story.append(para(
        "Les missions confiées au prestataire comprennent notamment :", "body"))
    for m in data.get("missions", []):
        story.append(bullet_item(m))

    story.append(sp(4))
    story.append(subsection("3.2 Prestations exclues"))
    default_excl = [
        "Administration des serveurs Cloud (contrat séparé).",
        "Forensics (lettre de mission spécifique).",
        "Projets/migrations majeurs non convenus (devis).",
    ]
    for e in (data.get("exclusions") or default_excl):
        story.append(bullet_item(e))

    # §4 SLA & SUPPORT
    story.append(section(4, "SLA & Support"))

    story.append(subsection("4.1 Horaires"))
    story.append(para(
        "Le support est assuré du lundi au vendredi, de 8h00 à 18h00, "
        "hors jours fériés légaux.", "body"))

    story.append(sp(4))
    story.append(subsection("4.2 Organisation"))
    story.append(para(
        "Les demandes sont traitées en fonction de leur criticité "
        "et de la charge de travail.", "body"))

    story.append(sp(4))
    story.append(subsection("4.3 Délais"))
    story.append(para(
        "Les délais d'intervention sont fournis à titre indicatif "
        "et constituent une obligation de moyens.", "body"))

    # §5 SÉCURITÉ & RESPONSABILITÉ UTILISATEUR
    story.append(section(5, "Sécurité & responsabilité utilisateur"))
    story.append(para(
        "Le client est responsable de l'usage des équipements "
        "et des comptes utilisateurs.", "body"))
    story.append(para(
        "Le prestataire ne peut être tenu responsable des conséquences liées à :",
        "body"))
    story.append(bullet_item("Mots de passe faibles ou partagés."))
    story.append(bullet_item("Absence de mesures de sécurité recommandées."))
    story.append(bullet_item("Mauvaise utilisation des outils et équipements."))
    story.append(para(
        "Le client s'engage à collaborer activement avec le prestataire en "
        "fournissant les accès et informations nécessaires à la résolution des "
        "incidents et à l'exécution des prestations.", "body"))
    story.append(para(
        "Le client garantit un accès technique suffisant aux équipements "
        "et systèmes.", "body"))

    # §6 HONORAIRES ET FRAIS
    story.append(section(6, "Honoraires et frais"))
    tarif = data.get("tarif_horaire", 81.25)
    story.append(para(
        f"Les prestations sont facturées sur base d'un tarif horaire de "
        f"<b>{tarif:.2f} € HTVA</b>. La facturation est réalisée sur base "
        "du temps réellement presté, sauf forfaits expressément convenus.", "body"))
    if data.get("installation_poste"):
        story.append(para(
            f"Installation d'un nouveau poste : "
            f"<b>{data['installation_poste']:.2f} € HTVA</b>.", "body"))
    if data.get("creation_user_prix"):
        story.append(para(
            f"Création d'un nouvel utilisateur : "
            f"<b>{data['creation_user_prix']:.2f} € HTVA</b>.", "body"))
    if data.get("forfait_mensuel"):
        story.append(para(
            f"Forfait mensuel : <b>{data['forfait_mensuel']:.2f} € HTVA / mois</b>.",
            "body"))

    story.append(sp(4))
    story.append(subsection("Conditions de paiement"))
    story.append(para(
        "Les factures sont payables dans un délai de <b>15 jours</b> à compter "
        "de leur date d'émission.", "body"))
    story.append(para(
        "En cas de non-paiement persistant malgré rappel, le prestataire se "
        "réserve le droit de suspendre tout ou partie des services après "
        "notification préalable au client, sans que cela ne puisse engager sa "
        "responsabilité.", "body"))

    # §7 DURÉE ET RÉSILIATION
    story.append(section(7, "Durée et résiliation"))
    duree = data.get("duree", "indeterminee")
    if duree == "indeterminee":
        story.append(para(
            "Le présent contrat est conclu pour une durée indéterminée. "
            "Il est renouvelé par tacite reconduction.", "body"))
    elif duree == "ponctuelle":
        story.append(para(
            "La présente mission est un ordre de mission ponctuel. Le contrat "
            "prend fin à la remise du livrable convenu.", "body"))
    else:
        duree_texte = data.get("duree_texte", "à convenir")
        story.append(para(
            f"Le présent contrat est conclu pour une durée déterminée de "
            f"<b>{duree_texte}</b>, renouvelable par tacite reconduction.",
            "body"))
    story.append(para(
        "Chaque partie peut résilier le contrat moyennant un préavis d'un (1) mois, "
        "notifié par écrit, sans préjudice des prestations déjà réalisées.", "body"))

    # §8 RESPONSABILITÉ
    story.append(section(8, "Responsabilité"))
    story.append(para(
        "Le prestataire ne pourra être tenu responsable des dommages indirects, "
        "pertes de données, interruptions d'activité ou conséquences découlant "
        "de l'exécution des prestations. Sa responsabilité est limitée au montant "
        "des honoraires facturés sur la période concernée.", "body"))

    # §9 CONFIDENTIALITÉ
    story.append(section(9, "Confidentialité"))
    story.append(para(
        "Le prestataire est tenu à une obligation de confidentialité renforcée "
        "concernant l'ensemble des informations, données et documents auxquels "
        "il a accès dans le cadre de la présente mission. Cette obligation "
        "perdure après la fin du contrat.", "body"))

    # §10 DROIT APPLICABLE
    story.append(section(10, "Droit applicable et juridiction compétente"))
    story.append(para(
        "La présente convention est soumise au droit belge. En cas de litige, "
        "les parties s'engagent à recourir préalablement à la médiation. "
        "À défaut d'accord, les tribunaux de l'arrondissement judiciaire de "
        "Bruxelles seront seuls compétents.", "body"))

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
        client_fn=data["client"].get("representant", ""),
    ))

    # ── ANNEXE Grille tarifaire ──
    story.append(PageBreak())
    story.append(annex_banner("Grille tarifaire"))
    story.append(sp(8))
    _build_standard_annex(story, data, tarif)

    doc.build(story, onFirstPage=fp, onLaterPages=lp)
    return buf.getvalue()


# ══════════════════════════════════════════════════════════════════════════════
#  1c. LETTRE DE MISSION FULL INCLUSIVE
# ══════════════════════════════════════════════════════════════════════════════

def _generate_full_inclusive_lm(data: dict) -> bytes:
    """
    Template dédié pour les contrats IT Full Inclusive.
    Forfait mensuel tout compris — ton marketing attractif + protections prestataire.
    """
    ref = data.get("reference", "")
    buf = io.BytesIO()
    doc, fp, lp = base_doc(buf, "IT at your service – Full Inclusive", ref)
    story = []

    # ── Couverture ──
    story.append(sp(18))
    story.append(para("LETTRE DE MISSION", "title_doc"))
    story.append(para("IT at your service – Full Inclusive", "subtitle"))
    story.append(para("Forfait mensuel tout compris", "subtitle2"))
    story.append(hr(thickness=2, space_before=4, space_after=16))

    # §1 PARTIES
    story.append(section(1, "Parties"))
    story.append(para("Entre les soussignés :", "body"))
    story.append(sp(6))
    story.append(parties_block(PRESTATAIRE, data["client"]))
    story.append(sp(8))

    # §2 OBJET
    story.append(hr(color=SC_LGREY, thickness=0.5))
    story.append(para("IL A PRÉALABLEMENT ÉTÉ EXPOSÉ CE QUI SUIT", "body_bold"))
    story.append(sp(4))
    story.append(para(
        data.get("contexte",
                 "Le client souhaite confier au prestataire la gestion complète "
                 "de son informatique dans le cadre d'un forfait mensuel tout compris."),
        "body"))
    story.append(sp(6))
    story.append(hr(color=SC_LGREY, thickness=0.5))
    story.append(para("IL A ENSUITE ÉTÉ CONVENU CE QUI SUIT", "body_bold"))
    story.append(sp(6))

    story.append(section(2, "Objet de la convention"))
    story.append(para(
        "Le présent contrat a pour objet la fourniture, par le prestataire, d'un "
        "service IT complet au bénéfice du client, dans le cadre d'une obligation "
        "de moyens et d'un forfait mensuel.", "body"))

    # §3 PÉRIMÈTRE DES SERVICES
    story.append(section(3, "Périmètre des services"))

    story.append(subsection("3.1 Prestations incluses"))
    story.append(para(
        "Le forfait Full Inclusive comprend notamment :", "body"))
    for m in data.get("missions", []):
        story.append(bullet_item(m))

    story.append(sp(4))
    story.append(subsection("3.2 Prestations exclues"))
    default_excl = [
        "Forensics (lettre de mission spécifique).",
        "Projets/migrations majeurs non expressément convenus (devis préalable).",
        "Interventions d'urgence hors heures ouvrées sans accord préalable.",
    ]
    for e in (data.get("exclusions") or default_excl):
        story.append(bullet_item(e))

    story.append(sp(4))
    story.append(subsection("3.3 Limitation d'usage"))
    story.append(para(
        "Le présent forfait couvre un usage raisonnable des services IT, "
        "correspondant à une utilisation normale d'une PME.", "body"))
    story.append(para(
        "En cas de charge anormalement élevée ou d'augmentation significative "
        "du périmètre (nombre d'utilisateurs, équipements ou sites), "
        "un ajustement du forfait pourra être proposé.", "body"))
    nb_users = data.get("nb_users")
    if nb_users:
        story.append(para(
            f"Le forfait est basé sur un périmètre de <b>{nb_users} utilisateurs</b>. "
            "Toute évolution significative pourra entraîner une révision tarifaire.",
            "body"))

    # §4 DÉTAIL DU FORFAIT
    story.append(section(4, "Détail du forfait"))
    forfait = data.get("forfait_mensuel")
    if forfait:
        story.append(para(
            f"Forfait mensuel : <b>{forfait:.2f} € HTVA / mois</b>", "body"))

    if data.get("inclus_visites"):
        story.append(para(
            f"Visites incluses : {data['inclus_visites']} visite(s) par mois et par "
            "site (si planifiée et consommée).", "body"))
        story.append(para(
            "Les visites incluses sont planifiées à l'avance, non cumulables "
            "et non reportables sauf accord préalable.", "body"))

    if data.get("budget_materiel"):
        story.append(para(
            f"Budget matériel inclus : <b>{data['budget_materiel']:.2f} € HTVA / mois</b> "
            "(utilisable pour matériel standard, accord préalable requis).", "body"))
        story.append(para(
            "Le budget matériel mensuel n'est pas cumulable et doit être utilisé "
            "dans le mois concerné, sauf accord contraire.", "body"))

    # §5 SLA & SUPPORT
    story.append(section(5, "SLA & Support"))

    story.append(subsection("5.1 Horaires"))
    story.append(para(
        "Le support est assuré du lundi au vendredi, de 8h00 à 18h00, "
        "hors jours fériés légaux.", "body"))

    story.append(sp(4))
    story.append(subsection("5.2 Organisation"))
    story.append(para(
        "Les demandes sont traitées selon leur priorité et la charge de travail.",
        "body"))

    story.append(sp(4))
    story.append(subsection("5.3 Délais"))
    story.append(para(
        "Les délais d'intervention constituent une obligation de moyens.",
        "body"))

    # §6 SÉCURITÉ & RESPONSABILITÉ UTILISATEUR
    story.append(section(6, "Sécurité & responsabilité utilisateur"))
    story.append(para(
        "Le client est responsable de l'usage des équipements "
        "et des comptes utilisateurs.", "body"))
    story.append(para(
        "Le prestataire ne peut être tenu responsable des conséquences liées à :",
        "body"))
    story.append(bullet_item("Mots de passe faibles ou partagés."))
    story.append(bullet_item("Absence de mesures de sécurité recommandées."))
    story.append(bullet_item("Mauvaise utilisation des outils et équipements."))
    story.append(para(
        "Le client s'engage à collaborer activement avec le prestataire en "
        "fournissant les accès et informations nécessaires.", "body"))
    story.append(para(
        "Le client garantit un accès technique suffisant aux équipements "
        "et systèmes.", "body"))

    # §7 HONORAIRES ET FRAIS
    story.append(section(7, "Honoraires et frais"))
    tarif = data.get("tarif_horaire", 81.25)
    story.append(para(
        f"Tarif horaire (prestations hors périmètre du forfait uniquement) : "
        f"<b>{tarif:.2f} € HTVA / heure</b>.", "body"))
    if data.get("installation_poste"):
        story.append(para(
            f"Installation d'un nouveau poste : "
            f"<b>{data['installation_poste']:.2f} € HTVA</b>.", "body"))
    if data.get("creation_user_prix"):
        story.append(para(
            f"Création d'un nouvel utilisateur : "
            f"<b>{data['creation_user_prix']:.2f} € HTVA</b>.", "body"))

    story.append(sp(4))
    story.append(subsection("Conditions de paiement"))
    story.append(para(
        "Les factures sont payables dans un délai de <b>15 jours</b> à compter "
        "de leur date d'émission.", "body"))
    story.append(para(
        "En cas de non-paiement persistant malgré rappel, le prestataire se "
        "réserve le droit de suspendre les services après notification préalable.",
        "body"))

    # §8 DURÉE ET RÉSILIATION
    story.append(section(8, "Durée et résiliation"))
    duree = data.get("duree", "indeterminee")
    if duree == "indeterminee":
        story.append(para(
            "Le présent contrat est conclu pour une durée indéterminée. "
            "Il est renouvelé par tacite reconduction.", "body"))
    else:
        duree_texte = data.get("duree_texte", "à convenir")
        story.append(para(
            f"Le présent contrat est conclu pour une durée déterminée de "
            f"<b>{duree_texte}</b>, renouvelable par tacite reconduction.",
            "body"))
    story.append(para(
        "Chaque partie peut résilier le contrat moyennant un préavis d'un (1) mois, "
        "notifié par écrit, sans préjudice des prestations déjà réalisées.", "body"))

    # §9 RESPONSABILITÉ
    story.append(section(9, "Responsabilité"))
    story.append(para(
        "Le prestataire ne pourra être tenu responsable des dommages indirects, "
        "pertes de données ou interruptions d'activité. Sa responsabilité est "
        "limitée au montant des honoraires facturés sur la période concernée.",
        "body"))

    # §10 CONFIDENTIALITÉ
    story.append(section(10, "Confidentialité"))
    story.append(para(
        "Le prestataire est tenu à une obligation de confidentialité renforcée "
        "concernant l'ensemble des informations auxquelles il a accès dans le "
        "cadre de la présente mission. Cette obligation perdure après la fin "
        "du contrat.", "body"))

    # §11 DROIT APPLICABLE
    story.append(section(11, "Droit applicable et juridiction compétente"))
    story.append(para(
        "La présente convention est soumise au droit belge. En cas de litige, "
        "les parties s'engagent à recourir préalablement à la médiation. "
        "À défaut d'accord, les tribunaux de l'arrondissement judiciaire de "
        "Bruxelles seront seuls compétents.", "body"))

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
        client_fn=data["client"].get("representant", ""),
    ))

    # ── ANNEXE Grille tarifaire ──
    story.append(PageBreak())
    story.append(annex_banner("Grille tarifaire"))
    story.append(sp(8))
    _build_standard_annex(story, data, tarif)

    doc.build(story, onFirstPage=fp, onLaterPages=lp)
    return buf.getvalue()


# ══════════════════════════════════════════════════════════════════════════════
#  1d. LETTRE DE MISSION RÉSEAU / STARTER PACK PME
# ══════════════════════════════════════════════════════════════════════════════

def _generate_reseau_lm(data: dict) -> bytes:
    """
    Template dédié pour les contrats Réseau / Starter Pack PME.
    Structure alignée sur les templates Cloud et Gestion IT.
    """
    ref = data.get("reference", "")
    reseau = data.get("reseau", {})
    buf = io.BytesIO()
    doc, fp, lp = base_doc(buf, "Projet réseau — Starter Pack PME", ref)
    story = []

    # ── Couverture ──
    story.append(sp(18))
    story.append(para("LETTRE DE MISSION", "title_doc"))
    story.append(para("Projet réseau — Starter Pack PME", "subtitle"))
    story.append(para("Fourniture, installation & configuration", "subtitle2"))
    story.append(hr(thickness=2, space_before=4, space_after=16))

    # §1 PARTIES
    story.append(section(1, "Parties"))
    story.append(para("Entre les soussignés :", "body"))
    story.append(sp(6))
    story.append(parties_block(PRESTATAIRE, data["client"]))
    story.append(sp(8))

    # §2 OBJET
    story.append(hr(color=SC_LGREY, thickness=0.5))
    story.append(para("IL A PRÉALABLEMENT ÉTÉ EXPOSÉ CE QUI SUIT", "body_bold"))
    story.append(sp(4))
    story.append(para(
        data.get("contexte",
                 "Le client souhaite confier au prestataire la fourniture, "
                 "l'installation et la configuration de son infrastructure réseau."),
        "body"))
    story.append(sp(6))
    story.append(hr(color=SC_LGREY, thickness=0.5))
    story.append(para("IL A ENSUITE ÉTÉ CONVENU CE QUI SUIT", "body_bold"))
    story.append(sp(6))

    story.append(section(2, "Objet de la convention"))
    story.append(para(
        "Le présent contrat a pour objet la fourniture, par le prestataire, des "
        "prestations décrites ci-après, au bénéfice du client.", "body"))

    # §3 PRÉREQUIS CLIENT
    story.append(section(3, "Prérequis client"))
    story.append(para(
        "Le client s'engage à fournir un environnement opérationnel permettant "
        "l'exécution de la mission, notamment :", "body"))
    story.append(bullet_item("Accès internet fonctionnel."))
    story.append(bullet_item("Alimentation électrique disponible."))
    story.append(bullet_item("Accès aux locaux et équipements."))
    story.append(bullet_item("Informations techniques nécessaires."))
    story.append(para(
        "Tout retard ou impossibilité d'intervention lié à ces éléments pourra "
        "entraîner une replanification ou une facturation complémentaire.", "body"))

    # §4 PÉRIMÈTRE DES SERVICES
    story.append(section(4, "Périmètre des services"))

    story.append(subsection("4.1 Prestations incluses"))
    story.append(para(
        "Les missions confiées au prestataire comprennent :", "body"))
    for m in data.get("missions", []):
        story.append(bullet_item(m))

    story.append(sp(4))
    story.append(subsection("4.2 Prestations exclues"))
    default_excl = [
        "Travaux de câblage structuré (électricien certifié).",
        "Fourniture de mobilier ou d'alimentation électrique.",
        "Développement applicatif ou formation utilisateur.",
    ]
    for e in (data.get("exclusions") or default_excl):
        story.append(bullet_item(e))

    story.append(sp(4))
    story.append(subsection("4.3 Demandes supplémentaires"))
    story.append(para(
        "Tout travail non prévu dans le périmètre initial fera l'objet d'un "
        "accord préalable et d'une facturation complémentaire.", "body"))

    # §5 VALIDATION & RÉCEPTION
    story.append(section(5, "Validation & réception"))
    story.append(para(
        "À la fin de l'installation, un test de fonctionnement est réalisé.",
        "body"))
    story.append(para(
        "La mission est considérée comme acceptée dès validation par le client ou, "
        "à défaut de remarques dans un délai de 5 jours ouvrables, comme tacitement "
        "acceptée.", "body"))

    # §6 DÉLAIS
    story.append(section(6, "Délais"))
    story.append(para(
        "Les délais d'intervention sont donnés à titre indicatif et peuvent être "
        "adaptés en fonction des contraintes techniques ou logistiques.", "body"))

    # §7 HONORAIRES ET FRAIS
    story.append(section(7, "Honoraires et frais"))
    if reseau:
        _build_reseau_pricing(story, data)
    else:
        tarif = data.get("tarif_horaire", 81.25)
        story.append(para(
            f"Les prestations sont facturées au tarif horaire de "
            f"<b>{tarif:.2f} € HTVA</b>.", "body"))

    story.append(sp(4))
    story.append(subsection("Garantie matériel"))
    story.append(para(
        "Le matériel fourni est couvert par la garantie constructeur. "
        "Le prestataire n'assure pas de garantie supplémentaire, sauf "
        "mention contraire.", "body"))

    story.append(sp(4))
    story.append(subsection("Conditions de paiement"))
    story.append(para(
        "Les factures sont payables dans un délai de <b>15 jours</b> à compter "
        "de leur date d'émission.", "body"))
    story.append(para(
        "En cas de non-paiement persistant malgré rappel, le prestataire se "
        "réserve le droit de suspendre les services après notification préalable.",
        "body"))

    # §8 RESPONSABILITÉ
    story.append(section(8, "Responsabilité"))
    story.append(para(
        "Le prestataire ne pourra être tenu responsable des dommages indirects, "
        "pertes de données ou interruptions d'activité. Sa responsabilité est "
        "limitée au montant des honoraires facturés.", "body"))
    story.append(para(
        "Le prestataire ne peut être tenu responsable des dysfonctionnements liés "
        "à une infrastructure existante, à des équipements tiers ou à des "
        "configurations antérieures.", "body"))

    # §9 CONFIDENTIALITÉ
    story.append(section(9, "Confidentialité"))
    story.append(para(
        "Le prestataire est tenu à une obligation de confidentialité renforcée "
        "concernant l'ensemble des informations auxquelles il a accès dans le "
        "cadre de la présente mission. Cette obligation perdure après la fin "
        "du contrat.", "body"))

    # §10 DROIT APPLICABLE
    story.append(section(10, "Droit applicable et juridiction compétente"))
    story.append(para(
        "La présente convention est soumise au droit belge. En cas de litige, "
        "les parties s'engagent à recourir préalablement à la médiation. "
        "À défaut d'accord, les tribunaux de l'arrondissement judiciaire de "
        "Bruxelles seront seuls compétents.", "body"))

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
        client_fn=data["client"].get("representant", ""),
    ))

    # ── ANNEXE Grille tarifaire ──
    story.append(PageBreak())
    story.append(annex_banner("Grille tarifaire"))
    story.append(sp(8))
    if reseau:
        _build_reseau_annex(story, data)
    else:
        _build_standard_annex(story, data, data.get("tarif_horaire", 81.25))

    doc.build(story, onFirstPage=fp, onLaterPages=lp)
    return buf.getvalue()


# ══════════════════════════════════════════════════════════════════════════════
#  1d. LETTRE DE MISSION CLOUD — Template 15 sections
# ══════════════════════════════════════════════════════════════════════════════

def _generate_cloud_lm(data: dict) -> bytes:
    """
    Template dédié pour les contrats Cloud (Infrastructure serveurs).
    15 sections contractuelles + section §4.4 conditionnelle (priorité TVA).
    """
    ref = data.get("reference", "")
    buf = io.BytesIO()
    doc, fp, lp = base_doc(buf, "Infrastructure serveurs Cloud", ref)
    story = []

    # ── Couverture ──
    story.append(sp(18))
    story.append(para("LETTRE DE MISSION", "title_doc"))
    story.append(para("Infrastructure serveurs Cloud", "subtitle"))
    story.append(para("Location, exploitation & administration", "subtitle2"))
    story.append(hr(thickness=2, space_before=4, space_after=16))

    # ═══════════════════════════════════════════════════════════════════════
    # §1 PARTIES
    # ═══════════════════════════════════════════════════════════════════════
    story.append(section(1, "Parties"))
    story.append(para("Entre les soussignés :", "body"))
    story.append(sp(6))
    story.append(parties_block(PRESTATAIRE, data["client"]))
    story.append(sp(8))

    # ═══════════════════════════════════════════════════════════════════════
    # §2 OBJET
    # ═══════════════════════════════════════════════════════════════════════
    story.append(hr(color=SC_LGREY, thickness=0.5))
    story.append(para("IL A PRÉALABLEMENT ÉTÉ EXPOSÉ CE QUI SUIT", "body_bold"))
    story.append(sp(4))
    story.append(para(
        data.get("contexte",
                 "Le client souhaite confier au prestataire l'hébergement, "
                 "l'exploitation et l'administration de son infrastructure "
                 "serveurs Cloud."),
        "body"))
    story.append(sp(6))
    story.append(hr(color=SC_LGREY, thickness=0.5))
    story.append(para("IL A ENSUITE ÉTÉ CONVENU CE QUI SUIT", "body_bold"))
    story.append(sp(6))

    story.append(section(2, "Objet de la convention"))
    story.append(para(
        "Le présent contrat a pour objet la fourniture, par le prestataire, des "
        "prestations de services informatiques décrites ci-après, au bénéfice du "
        "client, dans le cadre d'une obligation de moyens.", "body"))

    # ═══════════════════════════════════════════════════════════════════════
    # §3 PÉRIMÈTRE DES SERVICES
    # ═══════════════════════════════════════════════════════════════════════
    story.append(section(3, "Périmètre des services"))

    story.append(subsection("3.1 Prestations incluses"))
    story.append(para(
        "Les missions confiées au prestataire comprennent notamment :", "body"))
    for m in data.get("missions", []):
        story.append(bullet_item(m))
    story.append(bullet_item(
        "Support technique de base lié à l'infrastructure "
        "(accès, disponibilité, incidents)."))

    story.append(sp(4))
    story.append(subsection("3.2 Prestations exclues"))
    default_excl = [
        "Support utilisateur avancé (usage applicatif, formation, assistance bureautique).",
        "Installation et maintenance des postes de travail (contrat séparé).",
        "Interventions sur site chez le client (sauf accord préalable, devis séparé).",
        "Projets/migrations non expressément convenus (devis/bon de commande).",
        "Forensics et effacement sécurisé (contrats spécifiques).",
    ]
    for e in (data.get("exclusions") or default_excl):
        story.append(bullet_item(e))

    # ═══════════════════════════════════════════════════════════════════════
    # §4 SLA & SUPPORT
    # ═══════════════════════════════════════════════════════════════════════
    story.append(section(4, "SLA & Support"))

    story.append(subsection("4.1 Horaires de support"))
    story.append(para(
        "Le support est assuré du lundi au vendredi, de 8h00 à 18h00, "
        "hors jours fériés légaux belges.", "body"))

    story.append(sp(4))
    story.append(subsection("4.2 Délais d'intervention"))
    story.append(para(
        "<b>Incident critique</b> (infrastructure complètement indisponible) : "
        "prise en charge dans les <b>4 heures</b> ouvrables.", "body"))
    story.append(para(
        "<b>Incident standard</b> (dégradation de service, fonctionnalité isolée) : "
        "prise en charge dans le <b>jour ouvrable</b>.", "body"))

    story.append(sp(4))
    story.append(subsection("4.3 Limitations"))
    story.append(para(
        "Les délais ci-dessus constituent des objectifs de moyens et non des "
        "engagements de résultat. Ils peuvent être impactés par la charge de "
        "travail, les contraintes techniques et les dépendances fournisseurs "
        "(Microsoft, OVH, opérateurs Internet).", "body"))
    story.append(para(
        "Le prestataire privilégie une approche pragmatique et adaptée aux "
        "contraintes métier du client, notamment dans les périodes critiques.",
        "body"))

    # §4.4 Priorité périodes fiscales (conditionnel)
    if data.get("priorite_tva"):
        story.append(sp(4))
        story.append(subsection("4.4 Priorité – Périodes fiscales (clients comptables)"))
        story.append(para(
            "Pour les clients dont l'activité est liée à des obligations fiscales "
            "périodiques (notamment déclarations TVA), le prestataire adapte ses "
            "priorités d'intervention durant les périodes critiques.", "body"))
        story.append(sp(4))
        story.append(para("<b>Engagement :</b>", "body"))
        story.append(bullet_item(
            "Priorisation des incidents bloquants liés à l'accès aux systèmes "
            "comptables, aux serveurs RDS et aux outils nécessaires aux "
            "déclarations TVA."))
        story.append(bullet_item(
            "Réduction des délais d'intervention dans la mesure du possible."))
        story.append(sp(4))
        story.append(para("<b>Limitations importantes :</b>", "body"))
        story.append(bullet_item(
            "Cet engagement ne constitue pas une obligation de résultat ni de "
            "disponibilité étendue."))
        story.append(bullet_item(
            "Aucun SLA garanti spécifique n'est contractuellement imposé."))
        story.append(bullet_item(
            "Les interventions restent soumises à la charge de travail globale, "
            "aux contraintes techniques et aux dépendances fournisseurs."))

    # ═══════════════════════════════════════════════════════════════════════
    # §5 SÉCURITÉ & RESPONSABILITÉ UTILISATEUR
    # ═══════════════════════════════════════════════════════════════════════
    story.append(section(5, "Sécurité & responsabilité utilisateur"))
    story.append(para(
        "Le client s'engage à respecter les consignes de sécurité communiquées "
        "par le prestataire, notamment en matière de mots de passe, "
        "d'authentification multi-facteur et de gestion des accès utilisateurs. "
        "Le prestataire ne pourra être tenu responsable des conséquences d'un "
        "non-respect de ces consignes (compromission de comptes, fuites de données, "
        "etc.).", "body"))
    story.append(para(
        "Le client est responsable de l'usage fait par ses utilisateurs des "
        "ressources mises à disposition. Tout abus, utilisation frauduleuse ou "
        "non conforme aux conditions d'utilisation des fournisseurs (Microsoft, "
        "OVH) relève de la responsabilité exclusive du client.", "body"))
    story.append(para(
        "Le client s'engage à collaborer activement avec le prestataire en "
        "fournissant, dans des délais raisonnables, les informations et accès "
        "nécessaires à la résolution des incidents et à l'exécution des "
        "prestations.", "body"))
    story.append(para(
        "Le client garantit au prestataire un accès technique suffisant aux "
        "systèmes, équipements et informations nécessaires à la bonne exécution "
        "des prestations.", "body"))

    # ═══════════════════════════════════════════════════════════════════════
    # §6 SAUVEGARDES (BACKUP)
    # ═══════════════════════════════════════════════════════════════════════
    story.append(section(6, "Sauvegardes (Backup)"))
    story.append(para(
        "Le prestataire met en place et supervise une politique de sauvegarde "
        "adaptée à l'infrastructure du client. Les sauvegardes sont réalisées "
        "selon un planning défini conjointement (quotidien, hebdomadaire, mensuel).",
        "body"))
    story.append(para(
        "Le prestataire s'engage à vérifier régulièrement le bon fonctionnement "
        "des sauvegardes et à informer le client en cas d'anomalie détectée. "
        "Toutefois, le prestataire ne peut garantir la récupération intégrale des "
        "données en toutes circonstances, la restauration dépendant de l'état des "
        "supports et de la nature de l'incident.", "body"))
    story.append(para(
        "Les besoins spécifiques du client en matière de rétention ou de stratégie "
        "de sauvegarde peuvent faire l'objet d'une adaptation contractuelle.",
        "body"))

    # ═══════════════════════════════════════════════════════════════════════
    # §7 HONORAIRES
    # ═══════════════════════════════════════════════════════════════════════
    story.append(section(7, "Honoraires et frais"))

    tarif = data.get("tarif_horaire", 81.25)

    story.append(subsection("7.1 Abonnement mensuel"))
    if data.get("cloud"):
        _build_cloud_pricing(story, data, tarif)
    else:
        story.append(para(
            "Le détail de l'abonnement mensuel est repris en annexe.", "body"))

    story.append(sp(4))
    story.append(subsection("7.2 Prestations hors forfait"))
    story.append(para(
        f"Les interventions ponctuelles hors périmètre du forfait mensuel sont "
        f"facturées au tarif horaire de <b>{tarif:.2f} € HTVA</b> "
        f"(facturation à la minute).", "body"))

    story.append(sp(4))
    story.append(subsection("7.3 Conditions de paiement"))
    story.append(para(
        "Les factures sont payables dans un délai de <b>15 jours</b> à compter "
        "de leur date d'émission. Tout retard de paiement entraîne de plein "
        "droit et sans mise en demeure un intérêt de retard au taux légal, "
        "ainsi qu'une indemnité forfaitaire de 10 % du montant impayé avec un "
        "minimum de 40 €.", "body"))
    story.append(para(
        "En cas de non-paiement persistant malgré rappel, le prestataire se "
        "réserve le droit de suspendre tout ou partie des services après "
        "notification préalable au client, sans que cela ne puisse engager sa "
        "responsabilité.", "body"))

    # ═══════════════════════════════════════════════════════════════════════
    # §8 DURÉE & RÉSILIATION
    # ═══════════════════════════════════════════════════════════════════════
    story.append(section(8, "Durée et résiliation"))
    duree = data.get("duree", "indeterminee")
    if duree == "indeterminee":
        story.append(para(
            "Le présent contrat est conclu pour une durée indéterminée. "
            "Il est renouvelé par tacite reconduction. Chaque partie peut y "
            "mettre fin moyennant un préavis d'un (1) mois, notifié par écrit, "
            "sans préjudice des prestations déjà réalisées.", "body"))
    else:
        duree_texte = data.get("duree_texte", "à convenir")
        story.append(para(
            f"Le présent contrat est conclu pour une durée déterminée de "
            f"<b>{duree_texte}</b>, renouvelable par tacite reconduction "
            f"sauf préavis d'un (1) mois avant l'échéance.", "body"))

    # ═══════════════════════════════════════════════════════════════════════
    # §9 RÉVERSIBILITÉ
    # ═══════════════════════════════════════════════════════════════════════
    story.append(section(9, "Réversibilité"))
    story.append(para(
        "En cas de résiliation du contrat, le prestataire s'engage à faciliter "
        "la transition vers un nouveau prestataire ou vers une solution internalisée. "
        "Il fournira au client, dans un délai raisonnable, l'ensemble des données, "
        "accès et documentations nécessaires à la reprise des services.", "body"))
    story.append(para(
        "Les prestations liées à la réversibilité (migration, export de données, "
        "assistance technique) sont facturées au tarif horaire en vigueur.", "body"))

    # ═══════════════════════════════════════════════════════════════════════
    # §10 DÉPENDANCE AUX FOURNISSEURS
    # ═══════════════════════════════════════════════════════════════════════
    story.append(section(10, "Dépendance aux fournisseurs tiers"))
    story.append(para(
        "L'infrastructure repose sur des services tiers (Microsoft 365, OVH/Cloud, "
        "opérateurs Internet). Le prestataire ne peut être tenu responsable des "
        "interruptions, modifications tarifaires ou de service décidées "
        "unilatéralement par ces fournisseurs.", "body"))
    story.append(para(
        "En cas de panne majeure d'un fournisseur tiers, le prestataire s'engage "
        "à informer le client dans les meilleurs délais et à mettre en œuvre les "
        "mesures palliatives raisonnablement à sa disposition.", "body"))

    # ═══════════════════════════════════════════════════════════════════════
    # §11 RESPONSABILITÉ
    # ═══════════════════════════════════════════════════════════════════════
    story.append(section(11, "Responsabilité"))
    story.append(para(
        "La responsabilité globale du prestataire au titre du présent contrat "
        "est limitée au montant total des honoraires facturés au cours des "
        "<b>12 derniers mois</b> précédant l'événement ayant donné lieu à "
        "la réclamation.", "body"))
    story.append(para(
        "Sont expressément exclus les dommages indirects, les pertes de "
        "données, pertes d'exploitation, manque à gagner et préjudices "
        "immatériels de toute nature.", "body"))

    # ═══════════════════════════════════════════════════════════════════════
    # §12 CONFIDENTIALITÉ
    # ═══════════════════════════════════════════════════════════════════════
    story.append(section(12, "Confidentialité"))
    story.append(para(
        "Le prestataire est tenu à une obligation de confidentialité renforcée "
        "concernant l'ensemble des informations, données et documents auxquels "
        "il a accès dans le cadre de la présente mission. Cette obligation "
        "s'applique également à toute personne intervenant pour son compte et "
        "perdure après la fin du contrat.", "body"))

    # ═══════════════════════════════════════════════════════════════════════
    # §13 INDEXATION
    # ═══════════════════════════════════════════════════════════════════════
    story.append(section(13, "Indexation"))
    story.append(para(
        "Les tarifs et redevances prévus au présent contrat sont susceptibles "
        "d'être indexés annuellement sur base de l'indice des prix à la "
        "consommation (IPC) publié par le SPF Économie, à la date anniversaire "
        "du contrat. Le prestataire informera le client de toute adaptation "
        "tarifaire au moins 30 jours à l'avance.", "body"))

    # ═══════════════════════════════════════════════════════════════════════
    # §14 DROIT APPLICABLE
    # ═══════════════════════════════════════════════════════════════════════
    story.append(section(14, "Droit applicable et juridiction compétente"))
    story.append(para(
        "La présente convention est soumise au droit belge. En cas de litige, "
        "les parties s'engagent à recourir préalablement à la médiation. "
        "À défaut d'accord, les tribunaux de l'arrondissement judiciaire de "
        "Bruxelles seront seuls compétents.", "body"))

    # ═══════════════════════════════════════════════════════════════════════
    # §15 SIGNATURE
    # ═══════════════════════════════════════════════════════════════════════
    if data.get("notes"):
        story.append(section("N", "Notes et conditions particulières"))
        story.append(para(data["notes"], "body"))

    story.append(sp(10))
    story.append(hr(color=SC_LGREY))
    story.append(sign_block(
        lieu=data.get("lieu", ""),
        date_str=data.get("date_doc", ""),
        client_nom=data["client"]["nom"],
        client_fn=data["client"].get("representant", ""),
    ))

    # ── ANNEXE Grille tarifaire ──
    story.append(PageBreak())
    story.append(annex_banner("Grille tarifaire"))
    story.append(sp(8))
    _build_cloud_annex(story, data)

    doc.build(story, onFirstPage=fp, onLaterPages=lp)
    return buf.getvalue()


# ── Helpers tarification cloud ───────────────────────────────────────────────

def _build_cloud_pricing(story, data, tarif):
    cloud  = data["cloud"]
    nb_u   = cloud.get("nb_users", 1)
    prix_u = cloud.get("prix_par_user")
    server_lbl = cloud.get("server_label", "")
    total_m    = cloud.get("total_mensuel", 0)

    story.append(para(
        "La facturation est établie sur base d'un abonnement mensuel forfaitaire "
        "selon le détail ci-dessous. Les interventions ponctuelles hors périmètre "
        "sont facturées au tarif horaire en vigueur. Toute modification du nombre "
        "d'utilisateurs ou des options active fait l'objet d'un avenant.", "body"))
    story.append(sp(6))

    def hdr_cell(txt):
        return Paragraph(f"<b>{txt}</b>",
            ParagraphStyle("ch", fontName="Helvetica-Bold", fontSize=9,
                           textColor=colors.white, leading=12))
    def cell(txt, align="left"):
        al = TA_RIGHT if align == "right" else TA_LEFT
        return Paragraph(txt,
            ParagraphStyle("cc", fontName="Helvetica", fontSize=9,
                           textColor=SC_BLACK, leading=12, alignment=al))
    def total_cell(txt):
        return Paragraph(f"<b>{txt}</b>",
            ParagraphStyle("ct", fontName="Helvetica-Bold", fontSize=9,
                           textColor=SC_BLUE, leading=12, alignment=TA_RIGHT))

    tbl_data = [[
        hdr_cell("Prestation"), hdr_cell("Qté"),
        hdr_cell("Prix unit. HTVA"), hdr_cell("Total HTVA / mois"),
    ]]

    if prix_u:
        tbl_data.append([
            cell(f"Abonnement {server_lbl}"),
            cell(f"{nb_u} user(s)"),
            cell(f"{prix_u:.2f} €", "right"),
            cell(f"{prix_u * nb_u:.2f} €", "right"),
        ])
    else:
        tbl_data.append([
            cell(f"Abonnement {server_lbl} (SLA)"),
            cell("—"), cell("selon SLA"),
            cell(f"{cloud.get('base_mensuelle', 0):.2f} €", "right"),
        ])

    for opt in cloud.get("options", []):
        if "user" in opt.get("unite", ""):
            try:
                unit_p = float(opt["detail"].split("×")[1].strip().split(" ")[0].replace(",", "."))
            except Exception:
                unit_p = round(opt["prix"] / nb_u, 2) if nb_u else opt["prix"]
            tbl_data.append([
                cell(opt["label"]), cell(f"{nb_u} user(s)"),
                cell(f"{unit_p:.2f} €", "right"),
                cell(f"{opt['prix']:.2f} €", "right"),
            ])
        else:
            tbl_data.append([
                cell(opt["label"]), cell("1"),
                cell(f"{opt['prix']:.2f} €", "right"),
                cell(f"{opt['prix']:.2f} €", "right"),
            ])

    tbl_data.append([cell(""), cell(""), cell(""), cell("")])
    tbl_data.append([
        total_cell("TOTAL MENSUEL HTVA"), cell(""), cell(""),
        total_cell(f"{total_m:.2f} €"),
    ])

    tbl = Table(tbl_data, colWidths=[195, 75, 100, 115])
    n = len(tbl_data)
    tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, 0), SC_BLUE),
        ("FONTNAME",      (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",      (0, 0), (-1, -1), 9),
        ("ROWBACKGROUNDS",(0, 1), (-1, n - 3), [colors.white, SC_LGREY]),
        ("GRID",          (0, 0), (-1, n - 3), 0.3, colors.lightgrey),
        ("LINEABOVE",     (0, n - 1), (-1, n - 1), 0.8, SC_BLUE),
        ("BACKGROUND",    (0, n - 1), (-1, n - 1), HexColor("#E8F0FB")),
        ("TOPPADDING",    (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING",   (0, 0), (-1, -1), 7),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 7),
    ]))
    story.append(tbl)
    story.append(sp(4))


def _build_reseau_pricing(story, data):
    reseau = data["reseau"]
    story.append(para(
        f"La présente mission fait l'objet d'une facturation forfaitaire de "
        f"<b>{reseau['prix']:,.2f} € HTVA</b>, comprenant la fourniture du matériel "
        f"et l'installation complète selon le pack <b>{reseau['pack_label']}</b>.",
        "body"))
    story.append(para(
        "Le forfait couvre le câblage structuré, la configuration complète des équipements, "
        "la documentation réseau et le plan IP remis au client à la fin de l'intervention.",
        "body"))

    mat_rows = [[
        Paragraph("<b>Matériel & prestations inclus</b>",
            ParagraphStyle("mh", fontName="Helvetica-Bold", fontSize=9,
                           textColor=colors.white, leading=12)),
    ]]
    for item in reseau.get("materiel", []):
        mat_rows.append([Paragraph(f"• {item}",
            ParagraphStyle("mb", fontName="Helvetica", fontSize=9,
                           textColor=SC_BLACK, leading=13))])
    mat_rows.append([Paragraph(
        f"<b>Total forfaitaire HTVA : {reseau['prix']:,.2f} €</b>",
        ParagraphStyle("mt", fontName="Helvetica-Bold", fontSize=10,
                       textColor=SC_BLUE, leading=14, alignment=TA_RIGHT))])

    tbl = Table(mat_rows, colWidths=[485])
    n = len(mat_rows)
    tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (0, 0), SC_BLUE),
        ("ROWBACKGROUNDS",(0, 1), (0, n - 2), [colors.white, SC_LGREY]),
        ("BACKGROUND",    (0, n - 1), (0, n - 1), HexColor("#E8F0FB")),
        ("LINEABOVE",     (0, n - 1), (0, n - 1), 0.8, SC_BLUE),
        ("GRID",          (0, 0), (0, n - 2), 0.3, colors.lightgrey),
        ("TOPPADDING",    (0, 0), (0, -1), 5),
        ("BOTTOMPADDING", (0, 0), (0, -1), 5),
        ("LEFTPADDING",   (0, 0), (0, -1), 10),
    ]))
    story.append(sp(6))
    story.append(tbl)
    story.append(sp(4))

    if reseau.get("support"):
        story.append(para(
            f"Les interventions de support post-installation sont facturées au tarif horaire "
            f"de <b>{reseau['tarif_support']:.2f} € HTVA/heure</b> (facturation à la minute).",
            "body"))


def _build_cloud_annex(story, data):
    story.append(subsection("Prestations associées — hors abonnement mensuel"))
    story.append(sp(4))
    story += price_table([
        ("Tarif horaire (facturation à la minute)",       "81,25 € HTVA / heure"),
        ("Installation de poste de travail",              "150,00 € HTVA / poste"),
        ("Création d'utilisateur complet",                "110,00 € HTVA / utilisateur"),
        ("Installation serveur forfaitaire (≤ 20 users)", "325,00 € HTVA"),
        ("Installation serveur (> 20 utilisateurs)",      "Sur devis"),
        ("Migration de données",                          "Sur devis — selon volume"),
    ])
    story.append(sp(14))
    _append_shredding_annex(story)


def _build_reseau_annex(story, data):
    reseau = data["reseau"]
    story.append(subsection(f"Pack {reseau['pack_label']}"))
    story.append(para(reseau.get("pack_tagline", ""), "body"))
    story.append(sp(4))
    pack_rows = [(item, "") for item in reseau.get("materiel", [])]
    pack_rows.append(("", ""))
    pack_rows.append(("TOTAL FORFAITAIRE HTVA", f"{reseau['prix']:,.2f} €"))
    story += price_table(pack_rows)
    story.append(sp(12))
    story.append(subsection("Prestations associées"))
    story.append(sp(4))
    story += price_table([
        ("Tarif horaire support (facturation à la minute)", "81,25 € HTVA / heure"),
        ("Installation poste de travail supplémentaire",    "150,00 € HTVA / poste"),
        ("Création d'utilisateur (périmètre complet)",     "110,00 € HTVA / utilisateur"),
        ("Extension réseau / points d'accès supplémentaires", "Sur devis"),
    ])


def _build_standard_annex(story, data, tarif):
    rows = [("Tarif horaire", f"{tarif:.2f} € HTVA / heure")]
    if data.get("installation_poste"):
        rows.append(("Installation nouvelle machine", f"{data['installation_poste']:.2f} € HTVA"))
    if data.get("creation_user_prix"):
        rows.append(("Création utilisateur complet", f"{data['creation_user_prix']:.2f} € HTVA"))
    if data.get("forfait_mensuel"):
        rows.append(("Forfait mensuel", f"{data['forfait_mensuel']:.2f} € HTVA / mois"))
    if data.get("budget_materiel"):
        rows.append(("Budget matériel inclus (mensuel)", f"{data['budget_materiel']:.2f} € HTVA / mois"))
    story += price_table(rows, "Tarification des prestations")
    story.append(sp(10))
    _append_shredding_annex(story)


def _append_shredding_annex(story):
    story.append(subsection("Data Shredding – Effacement sécurisé certifié"))
    story += price_table([
        ("HDD / SSD (standard) – jusqu'à 1 TB", "35,00 € HTVA / drive"),
        ("HDD / SSD (large) – plus de 1 TB",     "45,00 € HTVA / drive"),
        ("USB Stick / Carte SD (toute taille)",   "15,00 € HTVA / device"),
        ("Serveur / NAS (jusqu'à 4 baies)",      "90,00 € HTVA / système"),
        ("Rapport d'effacement certifié PDF",     "Offert"),
        ("Option déplacement on-site",            "85,00 € HTVA + tarif drive"),
    ])
    story.append(para("Référence : https://www.smartclick.be/data-shredding/", "small"))


# ══════════════════════════════════════════════════════════════════════════════
#  2. CONTRAT DE MAINTENANCE
# ══════════════════════════════════════════════════════════════════════════════

def generate_maintenance(data: dict) -> bytes:
    """Génère un contrat de maintenance. Retourne les bytes du PDF."""
    ref = data.get("reference", "")
    buf = io.BytesIO()
    doc, fp, lp = base_doc(buf, "Contrat de maintenance", ref)
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
    story.append(para(
        data.get("contexte",
                 "Le client souhaite confier au prestataire la maintenance de son infrastructure."),
        "body"))
    story.append(sp(6))
    story.append(hr(color=SC_LGREY, thickness=0.5))
    story.append(para("IL A ENSUITE ÉTÉ CONVENU CE QUI SUIT", "body_bold"))
    story.append(sp(6))

    story.append(section(1, "Objet du contrat"))
    story.append(para(
        "Le présent contrat a pour objet de définir les conditions et le contenu des "
        "prestations de maintenance délivrées par le prestataire. Le périmètre couvert "
        "est spécifié en Annexe 1.", "body"))

    story.append(section(2, "Services couverts"))
    for s in (data.get("services") or [
        "Maintenance corrective des équipements listés en Annexe 1.",
        "Maintenance préventive planifiée.",
        "Service de garde passif en heures ouvrées.",
        "Support téléphonique et téléassistance.",
    ]):
        story.append(bullet_item(s))

    story.append(section(3, "Maintenance corrective"))
    story.append(para(
        "La maintenance corrective couvre la prise en charge et la résolution de tout "
        "incident résultant d'un comportement erroné documenté et provoqué par une anomalie. "
        "Dès la survenance d'un incident, le client notifiera sans délai le problème via le "
        "helpdesk (www.support.smartclick.be).", "body"))
    story.append(subsection("Niveaux de criticité"))
    for c, d_c in [
        ("Critique",  "Empêche l'utilisation dans son ensemble ou bloque l'activité du client."),
        ("Élevée",    "Empêche un sous-ensemble vital, perturbant fortement l'activité."),
        ("Moyenne",   "Bloque un sous-ensemble non vital, la majorité des activités peut continuer."),
        ("Basse",     "N'empêche pas l'utilisation ou est de nature cosmétique."),
    ]:
        story.append(para(f"<b>{c}</b> : {d_c}", "bullet"))

    story.append(section(4, "Maintenance préventive"))
    story.append(para(
        "La maintenance préventive consiste en une série de tâches planifiées destinées à "
        "prolonger la durée de vie des appareils. Les interventions sont planifiées à l'avance "
        "avec le client et documentées dans le système helpdesk.", "body"))

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
    story.append(para(
        f"Le contrat est conclu pour une durée déterminée de {nb_ans} an(s), renouvelable "
        "par tacite reconduction sauf préavis d'un (1) mois avant l'échéance.", "body"))

    story.append(section(7, "Conditions financières"))
    story.append(para(
        "La redevance est facturée avant le début de chaque période. Ce montant est "
        "irréductible et forfaitaire. Les interventions curatives du mois sont facturées "
        "avec la redevance mensuelle.", "body"))
    total = data.get("total_htva", 0)
    if total:
        story.append(para(f"<b>Total annuel HTVA : {total:.2f} €</b>", "body_bold"))

    story += common_clauses()

    if data.get("notes"):
        story.append(section("N", "Notes et conditions particulières"))
        story.append(para(data["notes"], "body"))

    story.append(sp(10))
    story.append(hr(color=SC_LGREY))
    story.append(sign_block(
        data.get("lieu", ""), data.get("date_doc", ""),
        data["client"]["nom"], data["client"].get("representant", "")))

    # ── ANNEXE 1 – Dispositifs ──
    if data.get("dispositifs"):
        story.append(PageBreak())
        story.append(annex_banner("Annexe 1 – Dispositifs sous contrat de maintenance"))
        story.append(sp(8))
        dev_header = [para(h, "body_bold") for h in ["Dispositif", "Description", "Quantité"]]
        dev_rows = [dev_header]
        for d_item in data["dispositifs"]:
            dev_rows.append([
                para(d_item.get("nom", "")),
                para(d_item.get("description", "")),
                para(str(d_item.get("quantite", "1")), "center"),
            ])
        t = Table(dev_rows, colWidths=[W * 0.35, W * 0.40, W * 0.12])
        t.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1, 0), SC_BLUE),
            ("TEXTCOLOR",     (0, 0), (-1, 0), SC_WHITE),
            ("FONTNAME",      (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE",      (0, 0), (-1, -1), 8.5),
            ("ROWBACKGROUNDS",(0, 1), (-1, -1), [SC_WHITE, HexColor("#f5f7ff")]),
            ("GRID",          (0, 0), (-1, -1), 0.3, HexColor("#d0d8e8")),
            ("LEFTPADDING",   (0, 0), (-1, -1), 8),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 8),
            ("TOPPADDING",    (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("ALIGN",         (2, 0), (2, -1), "CENTER"),
        ]))
        story.append(t)

    # ── ANNEXE 2 – Tarification ──
    story.append(PageBreak())
    story.append(annex_banner("Annexe 2 – Tarification"))
    story.append(sp(8))

    annual_rows = []
    if data.get("tarif_garde_5_7"):
        annual_rows.append(("Redevance de garde – 5/7 passif en semaine (lu-ve)",
                            f"{data['tarif_garde_5_7']:.2f} € HTVA / semaine"))
    if data.get("tarif_garde_7_7"):
        annual_rows.append(("Redevance de garde – 7/7 passif (vacances scolaires / avril-novembre)",
                            f"{data['tarif_garde_7_7']:.2f} € HTVA / semaine"))
    if data.get("tarif_preventif"):
        annual_rows.append(("Maintenance préventive technique (par journée)",
                            f"{data['tarif_preventif']:.2f} € HTVA / jour"))
    if data.get("nb_interventions_offertes"):
        annual_rows.append(("Interventions offertes dans le contrat",
                            f"{data['nb_interventions_offertes']} interventions"))
    if annual_rows:
        story += price_table(annual_rows, "Tarification annuelle")

    story.append(sp(6))
    curatif_rows = []
    if data.get("tarif_horaire_curateur"):
        th = data["tarif_horaire_curateur"]
        curatif_rows += [
            ("Intervention curative à distance – semaine /h",  f"{th:.2f} € HTVA"),
            ("Intervention curative sur site – semaine /h",    f"{th:.2f} € HTVA"),
            ("*Intervention curative à distance – weekend /h", f"{th * 1.17:.2f} € HTVA"),
            ("*Intervention curative sur site – weekend /h",   f"{th * 1.41:.2f} € HTVA"),
        ]
    if data.get("tarif_deplacement"):
        curatif_rows.append(("Déplacement en semaine / déplacement",
                             f"{data['tarif_deplacement']:.2f} € HTVA"))
    if curatif_rows:
        story += price_table(curatif_rows, "Grille tarifaire interventions curatives")

    # ── ANNEXE 3 – SLA ──
    story.append(PageBreak())
    story.append(annex_banner("Annexe 3 – Service Level Agreement (SLA)"))
    story.append(sp(8))
    sla_data = data.get("sla") or [
        {"criticite": "Critique",  "reaction": "4 heures",           "analyse": "1 jour ouvrable",   "resolution": "1 jour ouvrable *"},
        {"criticite": "Élevée",    "reaction": "4 heures ouvrables", "analyse": "1 jour ouvrable",   "resolution": "3 jours ouvrables *"},
        {"criticite": "Moyenne",   "reaction": "1 jour ouvrable",    "analyse": "3 jours ouvrables", "resolution": "7 jours ouvrables *"},
        {"criticite": "Basse",     "reaction": "1 jour ouvrable",    "analyse": "5 jours ouvrables", "resolution": "7 jours ouvrables *"},
    ]
    sla_header = [para(h, "body_bold") for h in
                  ["Priorité", "Criticité", "Délai réaction", "Délai analyse", "Délai résolution"]]
    sla_rows = [sla_header]
    for i, row in enumerate(sla_data, 1):
        sla_rows.append([
            para(str(i), "center"),
            para(f"<b>{row['criticite']}</b>"),
            para(row["reaction"]),
            para(row["analyse"]),
            para(row["resolution"]),
        ])
    t = Table(sla_rows, colWidths=[W * 0.07, W * 0.13, W * 0.22, W * 0.22, W * 0.22])
    t.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, 0), SC_BLUE),
        ("TEXTCOLOR",     (0, 0), (-1, 0), SC_WHITE),
        ("FONTNAME",      (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",      (0, 0), (-1, -1), 8.5),
        ("ROWBACKGROUNDS",(0, 1), (-1, -1), [SC_WHITE, HexColor("#f5f7ff")]),
        ("GRID",          (0, 0), (-1, -1), 0.3, HexColor("#d0d8e8")),
        ("ALIGN",         (0, 0), (0, -1), "CENTER"),
        ("LEFTPADDING",   (0, 0), (-1, -1), 6),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 6),
        ("TOPPADDING",    (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(t)
    story.append(sp(6))
    story.append(para(
        "(*) Le délai de résolution sera communiqué sur base de l'analyse réalisée par "
        "l'équipe de support. Le client peut contacter le prestataire en cas de panne "
        "critique afin de trouver un consensus sur le moment d'intervention.", "small"))

    doc.build(story, onFirstPage=fp, onLaterPages=lp)
    return buf.getvalue()


# ══════════════════════════════════════════════════════════════════════════════
#  3. FICHE D'INTERVENTION ATELIER
# ══════════════════════════════════════════════════════════════════════════════

def generate_fiche_intervention(data: dict) -> bytes:
    """Génère une fiche d'intervention. Retourne les bytes du PDF."""
    ref = data.get("reference", "FI-" + date.today().strftime("%Y%m%d"))
    buf = io.BytesIO()
    doc, fp, lp = base_doc(buf, f"Fiche d'intervention – {ref}", ref)
    story = []

    story.append(sp(14))
    story.append(para("FICHE D'INTERVENTION", "title_doc"))
    story.append(para("Atelier de réparation informatique", "subtitle2"))
    story.append(hr(thickness=2))

    machine = data.get("machine", {})
    client  = data.get("client", {})
    info_rows = [
        ["Référence", ref, "Client", client.get("nom", "")],
        ["Date réception", data.get("date_reception", ""),
         "Date prévue restitution", data.get("date_restitution_prev", "")],
        ["Technicien", data.get("technicien", "Mathieu Pleitinx"),
         "Statut", data.get("statut", "En cours")],
        ["Marque / Modèle", f"{machine.get('marque', '')} {machine.get('modele', '')}",
         "N° Série", machine.get("serie", "")],
        ["Type appareil", machine.get("type", ""), "", ""],
    ]
    t = Table(info_rows, colWidths=[W * 0.18, W * 0.28, W * 0.18, W * 0.28])
    t.setStyle(TableStyle([
        ("FONTNAME",   (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME",   (2, 0), (2, -1), "Helvetica-Bold"),
        ("FONTSIZE",   (0, 0), (-1, -1), 8.5),
        ("BACKGROUND", (0, 0), (0, -1), HexColor("#f0f4ff")),
        ("BACKGROUND", (2, 0), (2, -1), HexColor("#f0f4ff")),
        ("GRID",       (0, 0), (-1, -1), 0.4, HexColor("#d0d8e8")),
        ("LEFTPADDING",  (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING",   (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 4),
        ("TEXTCOLOR",    (0, 0), (-1, -1), SC_BLACK),
    ]))
    story.append(t)
    story.append(sp(8))

    story.append(subsection("Symptômes / Problème rapporté"))
    story.append(para(data.get("symptomes", "—"), "body"))
    story.append(sp(6))

    story.append(subsection("Diagnostic technique"))
    story.append(para(data.get("diagnostic", "—"), "body"))
    story.append(sp(6))

    story.append(subsection("Travaux effectués"))
    for w in (data.get("travaux") or ["—"]):
        story.append(bullet_item(w))
    story.append(sp(6))

    pieces = data.get("pieces", [])
    if pieces:
        story.append(subsection("Pièces utilisées"))
        pieces_header = [para(h, "body_bold") for h in ["Désignation", "Référence"]]
        pieces_data = [pieces_header]
        for p in pieces:
            pieces_data.append([para(p.get("designation", "")), para(p.get("ref", ""))])
        t = Table(pieces_data, colWidths=[W * 0.52, W * 0.36])
        t.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1, 0), SC_BLUE),
            ("TEXTCOLOR",     (0, 0), (-1, 0), SC_WHITE),
            ("FONTSIZE",      (0, 0), (-1, -1), 8.5),
            ("ROWBACKGROUNDS",(0, 1), (-1, -1), [SC_WHITE, HexColor("#f5f7ff")]),
            ("GRID",          (0, 0), (-1, -1), 0.3, HexColor("#d0d8e8")),
            ("LEFTPADDING",   (0, 0), (-1, -1), 6),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 6),
            ("TOPPADDING",    (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(t)
        story.append(sp(6))

    heures = data.get("temps_main_oeuvre", 0)
    if heures:
        story.append(subsection("Main d'œuvre"))
        story.append(para(f"Temps de main d'œuvre : <b>{heures:.2f} h</b>", "body"))

    if data.get("notes"):
        story.append(sp(6))
        story.append(subsection("Notes"))
        story.append(para(data["notes"], "body"))

    story.append(sp(16))
    story.append(hr(color=SC_LGREY))
    sign_rows = [[
        [para("Bon pour réception – Client", "sign_label"),
         sp(20), para("Date : __________ / Signature :", "small")],
        [para("Technicien", "sign_label"), sp(2),
         para(data.get("technicien", "Mathieu Pleitinx"), "sign_name"),
         sp(20), para("Signature :", "small")],
    ]]
    t = Table(sign_rows, colWidths=[W * 0.44, W * 0.44])
    t.setStyle(TableStyle([
        ("VALIGN",      (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING",  (0, 0), (-1, -1), 10),
    ]))
    story.append(t)

    doc.build(story, onFirstPage=fp, onLaterPages=lp)
    return buf.getvalue()


# ══════════════════════════════════════════════════════════════════════════════
#  4. RAPPORT DATA SHREDDING
# ══════════════════════════════════════════════════════════════════════════════

def generate_shredding_report(data: dict) -> bytes:
    """Génère un rapport d'effacement certifié. Retourne les bytes du PDF."""
    ref = data.get("reference", "DS-" + date.today().strftime("%Y%m%d"))
    buf = io.BytesIO()
    doc, fp, lp = base_doc(buf, f"Rapport d'effacement certifié – {ref}", ref)
    story = []

    story.append(sp(14))
    story.append(para("RAPPORT D'EFFACEMENT SÉCURISÉ", "title_doc"))
    story.append(para("Data Shredding – Certificat d'effacement certifié", "subtitle"))
    story.append(para(
        f"Référence : {ref}  |  Méthode : {data.get('methode', 'DoD 5220.22-M')}",
        "subtitle2"))
    story.append(hr(thickness=2))

    info_rows = [
        ["Client",         data["client"].get("nom", ""),
         "Technicien",     data.get("technicien", "Mathieu Pleitinx")],
        ["Date opération", data.get("date_operation", ""),
         "On-site",        "Oui" if data.get("on_site") else "Non"],
        ["Référence",      ref,
         "Nb supports",    str(len(data.get("supports", [])))],
    ]
    t = Table(info_rows, colWidths=[W * 0.18, W * 0.28, W * 0.18, W * 0.28])
    t.setStyle(TableStyle([
        ("FONTNAME",   (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME",   (2, 0), (2, -1), "Helvetica-Bold"),
        ("FONTSIZE",   (0, 0), (-1, -1), 8.5),
        ("BACKGROUND", (0, 0), (0, -1), HexColor("#f0f4ff")),
        ("BACKGROUND", (2, 0), (2, -1), HexColor("#f0f4ff")),
        ("GRID",       (0, 0), (-1, -1), 0.4, HexColor("#d0d8e8")),
        ("LEFTPADDING",  (0, 0), (-1, -1), 6),
        ("TOPPADDING",   (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 4),
    ]))
    story.append(t)
    story.append(sp(10))

    story.append(subsection("Supports traités"))
    sup_header = [para(h, "body_bold") for h in
                  ["Type", "Marque / Modèle", "N° Série", "Capacité", "Passes", "Résultat", "Hash SHA-256"]]
    sup_rows = [sup_header]
    for s in data.get("supports", []):
        result_color = SC_GREEN if s.get("resultat", "") == "OK" else SC_RED
        r_para = Paragraph(s.get("resultat", ""), ParagraphStyle("res",
            fontName="Helvetica-Bold", fontSize=8, textColor=result_color))
        sup_rows.append([
            para(s.get("type", "")),
            para(s.get("marque_modele", f"{s.get('marque', '')} {s.get('modele', '')}")),
            para(s.get("serie", "")),
            para(s.get("capacite", "")),
            para(str(s.get("passes", "3")), "center"),
            r_para,
            para(s.get("hash", "")[:16] + "…" if len(s.get("hash", "")) > 16
                 else s.get("hash", ""), "small"),
        ])
    t = Table(sup_rows, colWidths=[W * 0.10, W * 0.18, W * 0.14, W * 0.09, W * 0.07, W * 0.08, W * 0.20])
    t.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, 0), SC_BLUE),
        ("TEXTCOLOR",     (0, 0), (-1, 0), SC_WHITE),
        ("FONTSIZE",      (0, 0), (-1, -1), 7.5),
        ("ROWBACKGROUNDS",(0, 1), (-1, -1), [SC_WHITE, HexColor("#f5f7ff")]),
        ("GRID",          (0, 0), (-1, -1), 0.3, HexColor("#d0d8e8")),
        ("ALIGN",         (4, 0), (5, -1), "CENTER"),
        ("LEFTPADDING",   (0, 0), (-1, -1), 4),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 4),
        ("TOPPADDING",    (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(t)
    story.append(sp(8))

    story.append(para(
        "Certifié conforme : Les supports listés ci-dessus ont été effacés de manière "
        "irréversible selon la méthode indiquée. Aucune donnée résiduelle ne peut être "
        "récupérée au terme de ce processus. Ce document constitue le certificat officiel "
        "d'effacement.", "body"))

    if data.get("notes"):
        story.append(sp(6))
        story.append(subsection("Notes"))
        story.append(para(data["notes"], "body"))

    story.append(sp(16))
    story.append(hr(color=SC_LGREY))
    sign_rows = [[
        [para("Attestation client", "sign_label"), sp(2),
         para("Je soussigné(e) atteste avoir remis les supports ci-dessus.", "small"),
         sp(14), para("Date : __________ / Signature :", "small")],
        [para("Technicien certifié", "sign_label"), sp(2),
         para(data.get("technicien", "Mathieu Pleitinx"), "sign_name"),
         sp(14), para("Signature :", "small")],
    ]]
    t = Table(sign_rows, colWidths=[W * 0.44, W * 0.44])
    t.setStyle(TableStyle([
        ("VALIGN",      (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING",  (0, 0), (-1, -1), 10),
    ]))
    story.append(t)

    doc.build(story, onFirstPage=fp, onLaterPages=lp)
    return buf.getvalue()


# ══════════════════════════════════════════════════════════════════════════════
#  5. RAPPORT FORENSICS
# ══════════════════════════════════════════════════════════════════════════════

def generate_forensics_report(data: dict) -> bytes:
    """Génère le rapport PDF certifié d'une mission forensics. Retourne bytes."""
    ref     = data.get("reference", "FOR-???")
    client  = data.get("client_name", "")

    buf = io.BytesIO()
    doc, fp, lp = base_doc(buf, f"Rapport Forensics — {ref}", ref)
    story = []

    def ts_lbl(ts):
        if not ts:
            return "—"
        try:
            return ts[:16].replace("T", "  ")
        except Exception:
            return str(ts)

    def FOR_section(txt):
        return para(txt, "section")

    def FOR_sub(txt):
        return Paragraph(f"<b>{txt}</b>",
            ParagraphStyle("fsub", fontName="Helvetica-Bold", fontSize=10,
                           textColor=SC_BLUE, leading=14, spaceAfter=4, spaceBefore=8))

    def field_row(label, value, value_color=None):
        vc = value_color or SC_BLACK
        rows = [[
            Paragraph(label, ParagraphStyle("fl", fontName="Helvetica-Bold",
                      fontSize=9, textColor=SC_GREY, leading=13)),
            Paragraph(str(value) if value else "—",
                      ParagraphStyle("fv", fontName="Helvetica",
                      fontSize=9, textColor=vc, leading=13)),
        ]]
        t = Table(rows, colWidths=[W * 0.28, W * 0.56])
        t.setStyle(TableStyle([
            ("VALIGN",       (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING",   (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING",(0, 0), (-1, -1), 3),
            ("LEFTPADDING",  (0, 0), (-1, -1), 0),
        ]))
        return t

    def proof_image(path_img):
        ext  = os.path.splitext(path_img)[1].lower()
        name = os.path.basename(path_img)
        if ext in (".png", ".jpg", ".jpeg", ".bmp") and os.path.exists(path_img):
            try:
                img = RLImage(path_img, width=W * 0.75, height=None)
                img.hAlign = "LEFT"
                return [sp(4), img, para(f"↑ {name}", "small")]
            except Exception:
                pass
        return [para(f"📎 Preuve jointe : {name}", "small")]

    # ── COUVERTURE ──
    story.append(sp(24))
    story.append(para("RAPPORT D'EXPERTISE FORENSIQUE INFORMATIQUE", "title_doc"))
    story.append(para("Constatations techniques — Document confidentiel", "subtitle"))
    story.append(hr(thickness=2, space_before=6, space_after=20))

    for label, value in [
        ("Référence mission", ref),
        ("Client",            client),
        ("Demandeur",         data.get("demandeur", "—")),
        ("LM liée",           data.get("contract_ref", "—")),
        ("Date de création",  ts_lbl(data.get("created_at", ""))),
        ("Date du rapport",   ts_lbl(data.get("generated_at", ""))),
        ("Technicien",        PRESTATAIRE["representant"]),
    ]:
        story.append(field_row(label, value))

    # Mention légale
    story.append(sp(16))
    mention = Table([[Paragraph(
        "⚖️  Ce rapport est strictement factuel et technique. Il ne constitue pas "
        "une expertise judiciaire et n'emporte aucune qualification juridique des faits "
        "observés. Il est établi dans le cadre de la mission définie par la lettre de "
        "mission référencée ci-dessus.",
        ParagraphStyle("mention", fontName="Helvetica", fontSize=8,
                       textColor=SC_GREY, leading=12))]], colWidths=[W * 0.84])
    mention.setStyle(TableStyle([
        ("BACKGROUND",   (0, 0), (0, 0), HexColor("#FEF3C7")),
        ("LINEABOVE",    (0, 0), (0, 0), 1, SC_AMBER),
        ("LINEBELOW",    (0, 0), (0, 0), 1, SC_AMBER),
        ("LEFTPADDING",  (0, 0), (0, 0), 10),
        ("TOPPADDING",   (0, 0), (0, 0), 8),
        ("BOTTOMPADDING",(0, 0), (0, 0), 8),
    ]))
    story.append(mention)

    p6 = data.get("phase6", {})
    if p6.get("confidentialite"):
        story.append(sp(8))
        story.append(para(p6["confidentialite"], "small"))

    story.append(PageBreak())

    # ── PHASE 1 ──
    story.append(FOR_section("1. Ouverture & mandat"))
    p1 = data.get("phase1", {})
    story.append(field_row("Objet du mandat", data.get("mandat", "—")))
    story.append(field_row("Lieu",            p1.get("lieu", "—")))
    story.append(field_row("Date de début",   p1.get("date_debut", "—")))

    if p1.get("contexte"):
        story.append(sp(6))
        story.append(FOR_sub("Contexte factuel"))
        story.append(para(p1["contexte"], "body"))
    if p1.get("perimetre"):
        story.append(FOR_sub("Périmètre technique confié"))
        story.append(para(p1["perimetre"], "body"))
    if p1.get("questions"):
        story.append(FOR_sub("Questions techniques à répondre"))
        for q in p1["questions"].splitlines():
            if q.strip():
                story.append(bullet_item(q.strip()))

    story.append(sp(12))

    # ── PHASE 2 ──
    story.append(FOR_section("2. Réception & chaîne de custody"))
    p2 = data.get("phase2", {})
    story.append(field_row("Conditions de remise", p2.get("conditions", "—")))
    story.append(field_row("Horodatage réception", ts_lbl(p2.get("completed_at", ""))))

    supports = p2.get("supports", [])
    if supports:
        story.append(sp(6))
        story.append(FOR_sub("Supports reçus"))
        hdr_row = [[
            Paragraph(h, ParagraphStyle("th", fontName="Helvetica-Bold",
                      fontSize=8, textColor=SC_WHITE, leading=11))
            for h in ["Type", "Marque / Modèle", "N° Série", "Capacité", "État", "Reçu de"]
        ]]
        data_rows = []
        for s in supports:
            data_rows.append([
                Paragraph(s.get("type", ""), ParagraphStyle("td",
                    fontName="Helvetica", fontSize=8, textColor=SC_BLACK, leading=11)),
                Paragraph(s.get("modele", ""), ParagraphStyle("td2",
                    fontName="Helvetica", fontSize=8, textColor=SC_BLACK, leading=11)),
                Paragraph(s.get("serie", ""), ParagraphStyle("td3",
                    fontName="Helvetica", fontSize=8, textColor=SC_BLACK, leading=11)),
                Paragraph(s.get("capacite", ""), ParagraphStyle("td4",
                    fontName="Helvetica", fontSize=8, textColor=SC_BLACK, leading=11)),
                Paragraph(s.get("etat", ""), ParagraphStyle("td5",
                    fontName="Helvetica", fontSize=8, textColor=SC_BLACK, leading=11)),
                Paragraph(s.get("recu_de", ""), ParagraphStyle("td6",
                    fontName="Helvetica", fontSize=8, textColor=SC_BLACK, leading=11)),
            ])
        tbl = Table(hdr_row + data_rows, colWidths=[55, 110, 85, 55, 80, 80])
        n = len(data_rows)
        tbl.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1, 0), SC_BLUE),
            ("ROWBACKGROUNDS",(0, 1), (-1, -1), [SC_WHITE, SC_LGREY]),
            ("GRID",          (0, 0), (-1, -1), 0.3, colors.lightgrey),
            ("TOPPADDING",    (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING",   (0, 0), (-1, -1), 6),
        ]))
        story.append(tbl)

    story.append(sp(12))

    # ── PHASE 3 ──
    story.append(FOR_section("3. Acquisition & intégrité des données"))
    p3 = data.get("phase3", {})
    story.append(field_row("Méthode",       p3.get("methode", "—")))
    story.append(field_row("Outil utilisé", p3.get("outil", "—")))
    story.append(field_row("Horodatage",    ts_lbl(p3.get("completed_at", ""))))

    if p3.get("notes"):
        story.append(sp(4))
        story.append(para(p3["notes"], "body"))

    fichiers = p3.get("fichiers", [])
    if fichiers:
        story.append(sp(6))
        story.append(FOR_sub("Fichiers analysés & empreintes cryptographiques"))
        for f in fichiers:
            fname = os.path.basename(f.get("file", ""))
            frows = [
                [Paragraph("Fichier", ParagraphStyle("hl", fontName="Helvetica-Bold",
                           fontSize=8, textColor=SC_GREY, leading=12)),
                 Paragraph(fname, ParagraphStyle("hv", fontName="Helvetica",
                           fontSize=8, textColor=SC_BLACK, leading=12))],
                [Paragraph("MD5", ParagraphStyle("hl2", fontName="Helvetica-Bold",
                           fontSize=8, textColor=SC_GREY, leading=12)),
                 Paragraph(f.get("md5", "—"),
                           ParagraphStyle("hvm", fontName="Courier", fontSize=7,
                                          textColor=HexColor("#1a7f4e"), leading=12))],
                [Paragraph("SHA256", ParagraphStyle("hl3", fontName="Helvetica-Bold",
                           fontSize=8, textColor=SC_GREY, leading=12)),
                 Paragraph(f.get("sha256", "—"),
                           ParagraphStyle("hvs", fontName="Courier", fontSize=7,
                                          textColor=HexColor("#1a7f4e"), leading=12))],
            ]
            ft = Table(frows, colWidths=[W * 0.14, W * 0.70])
            ft.setStyle(TableStyle([
                ("BACKGROUND",    (0, 0), (-1, -1), HexColor("#f0f9f4")),
                ("LINEABOVE",     (0, 0), (0, 0),   0.5, SC_GREEN),
                ("TOPPADDING",    (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("LEFTPADDING",   (0, 0), (-1, -1), 8),
            ]))
            story.append(ft)
            story.append(sp(4))

    story.append(PageBreak())

    # ── PHASE 4 ──
    story.append(FOR_section("4. Chronologie de l'analyse"))
    p4 = data.get("phase4", {})
    etapes = p4.get("etapes", [])

    if not etapes:
        story.append(para("Aucune étape d'analyse enregistrée.", "body"))
    else:
        for etape in etapes:
            story.append(sp(6))
            etape_hdr = Table([[
                Paragraph(f"Étape {etape.get('num', '')}",
                    ParagraphStyle("enum", fontName="Helvetica-Bold", fontSize=9,
                                   textColor=SC_WHITE, leading=13)),
                Paragraph(etape.get("timestamp", ""),
                    ParagraphStyle("ets", fontName="Courier", fontSize=8,
                                   textColor=SC_WHITE, leading=13)),
            ]], colWidths=[W * 0.18, W * 0.66])
            etape_hdr.setStyle(TableStyle([
                ("BACKGROUND",    (0, 0), (-1, -1), SC_BLUE),
                ("TOPPADDING",    (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("LEFTPADDING",   (0, 0), (-1, -1), 10),
            ]))
            story.append(etape_hdr)

            if etape.get("action"):
                story.append(field_row("Action réalisée", etape["action"]))
            if etape.get("observations"):
                story.append(FOR_sub("Observations techniques"))
                for line in etape["observations"].splitlines():
                    if line.strip():
                        story.append(bullet_item(line.strip()))
            for pv_path in etape.get("preuves", []):
                for elem in proof_image(pv_path):
                    story.append(elem)

    story.append(PageBreak())

    # ── PHASE 5 ──
    story.append(FOR_section("5. Constatations factuelles"))
    p5 = data.get("phase5", {})

    p1_questions = data.get("phase1", {}).get("questions", "")
    if p1_questions:
        story.append(FOR_sub("Réponses aux questions du mandat"))

    if p5.get("reponses"):
        story.append(para(p5["reponses"], "body"))
    if p5.get("complementaires"):
        story.append(FOR_sub("Constatations complémentaires"))
        story.append(para(p5["complementaires"], "body"))
    if p5.get("limites"):
        story.append(sp(6))
        lim_tbl = Table([[Paragraph(
            f"⚠️  Limites de l'analyse : {p5['limites']}",
            ParagraphStyle("lim", fontName="Helvetica", fontSize=9,
                           textColor=HexColor("#92400e"), leading=13)
        )]], colWidths=[W * 0.84])
        lim_tbl.setStyle(TableStyle([
            ("BACKGROUND",   (0, 0), (0, 0), HexColor("#FEF3C7")),
            ("LEFTPADDING",  (0, 0), (0, 0), 10),
            ("TOPPADDING",   (0, 0), (0, 0), 8),
            ("BOTTOMPADDING",(0, 0), (0, 0), 8),
            ("LINEABOVE",    (0, 0), (0, 0), 1, SC_AMBER),
        ]))
        story.append(lim_tbl)

    story.append(sp(12))

    # ── PHASE 6 ──
    story.append(FOR_section("6. Clôture"))
    story.append(field_row("Date de clôture",     p6.get("date_fin", "—")))
    story.append(field_row("Retour des supports",  p6.get("retour_supports", "—")))
    story.append(field_row("Destinataires",        p6.get("destinataires", "—")))

    story.append(sp(20))
    story.append(hr(thickness=1, color=SC_LGREY))
    story.append(sp(6))
    story.append(para("Mention légale", "sign_label"))
    story.append(para(
        "Ce rapport a été établi par Smartclick S.R.L. à la demande du client identifié "
        "en première page. Il constitue un document de constatations techniques factuelles "
        "et ne peut être interprété comme une expertise judiciaire. Smartclick S.R.L. décline "
        "toute responsabilité quant à l'interprétation juridique ou disciplinaire de son contenu.",
        "small"))

    story.append(sp(20))
    story.append(hr(thickness=1, color=SC_LGREY))

    sign_rows = [[
        [para("Représentant du client", "sign_label"), sp(2),
         para(data.get("demandeur", "") or "Nom & fonction", "small"),
         sp(18), para("Date : __________ / Signature :", "small")],
        [para("Technicien certifié", "sign_label"), sp(2),
         para(PRESTATAIRE["representant"], "sign_name"),
         para(PRESTATAIRE["titre"], "small"),
         sp(14), para("Signature :", "small")],
    ]]
    t = Table(sign_rows, colWidths=[W * 0.44, W * 0.44])
    t.setStyle(TableStyle([
        ("VALIGN",      (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING",  (0, 0), (-1, -1), 10),
    ]))
    story.append(t)

    doc.build(story, onFirstPage=fp, onLaterPages=lp)
    return buf.getvalue()
