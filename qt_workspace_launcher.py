"""
SmartHub — Point d'entrée workspace
Vérifie la configuration API au démarrage, affiche le login si nécessaire.
"""
import sys
from PyQt6.QtWidgets import QApplication, QMessageBox
from PyQt6.QtCore import Qt

# Import relatif — à adapter selon ta structure de fichiers
# Si ce fichier est à la racine du projet Qt :
from smarthub.config import is_configured, get_api_key, get_api_base
from smarthub.login_dialog import LoginDialog


def check_auth() -> bool:
    """
    Vérifie la connexion au serveur.
    Retourne True si OK, False si abandon.
    """
    import httpx
    key  = get_api_key()
    base = get_api_base()

    if not key:
        return False

    try:
        r = httpx.get(f"{base}/auth/me", headers={"X-API-Key": key}, timeout=5)
        return r.status_code == 200
    except Exception:
        return False  # Réseau indispo — on laisse quand même passer (mode offline partiel)


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("SmartHub")
    app.setOrganizationName("Smartclick")

    # ── Vérification auth ──
    if not is_configured():
        dlg = LoginDialog(message="Bienvenue ! Configurez votre connexion pour commencer.")
        if dlg.exec() != LoginDialog.DialogCode.Accepted:
            sys.exit(0)
    elif not check_auth():
        dlg = LoginDialog(message="❌ Clé API invalide ou serveur inaccessible. Vérifiez la configuration.")
        if dlg.exec() != LoginDialog.DialogCode.Accepted:
            sys.exit(0)

    # ── Lancement workspace principal ──
    from smarthub.workspace_main import WorkspaceWindow
    window = WorkspaceWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
