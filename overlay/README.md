# SmartHub Overlay — Time Tracker

Always-on-top, cross-platform (Windows / Linux / macOS)

## Installation

```bash
pip install -r requirements.txt
```

## Lancement

```bash
python overlay.py
```

## Autostart Windows

1. Crée un raccourci vers `overlay.pyw` (renomme overlay.py en overlay.pyw pour éviter la console)
2. Copie le raccourci dans `shell:startup` (Win+R → shell:startup)

## Autostart Linux

```bash
cp smarthub-overlay.desktop ~/.config/autostart/
```

## Config

Modifier l'URL de l'API dans overlay.py ligne 20 :
```python
API_BASE = "http://10.0.2.202:8080/api/v1"
```
