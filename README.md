# Zangbéto – Gardien de la nuit
<p align="center">
    <img src="https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcREvNSSk-Op-0QgGDqch5TZujeZ2Ys-q6hZaw&s" alt="Zangbéto – Gardien de la nuit" width="600"/>
</p>
Zangbéto est un outil léger et local de monitoring de sites Web. Il vérifie périodiquement la disponibilité de pages statiques et dynamiques, génère des rapports HTML détaillés et envoie des notifications en cas d’incident.

## 📦 Stack technique

* **Langage** : Python 3+
* **HTTP** : `requests`
* **Parsing** : `BeautifulSoup4`
* **Asynchrone** : `schedule` (portabilité)
* **Base de données** : SQLite (`sqlite3`)
* **Templates** : Jinja2
* **Graphiques** : Plotly.js (via CDN)
* **Notifications** : `notify-send`, Email (SMTP), Slack, Telegram
* **Supervision Linux** : systemd (unit + timer)

## 📂 Structure du projet

```
Zangbeto/
├── monitor.py                # Script principal et CLI
├── crawler.py                # Exploration et tests HTTP
├── notifications.py          # Gestionnaire de notifications asynchrone
├── templates/
│   └── report_template.html  # Template Jinja2 pour le rapport
├── history.db                # Base SQLite pour l’historique des checks
├── requirements.txt          # Dépendances Python
└── README.md                 # Présentation et guide d’utilisation
```

## 🚀 Installation

1. **Cloner le dépôt** :

   ```bash
   git clone https://...
   cd Zangbeto
   ```

2. **Créer un environnement virtuel** :

   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **Installer les dépendances** :

   ```bash
   pip install -r requirements.txt
   ```

4. **Initialiser la base de données** :

   ```bash
   python monitor.py --init-db
   ```

## ⚙️ Configuration

* **sites.txt** : liste des URLs à surveiller (une par ligne).
* **Arguments CLI** :

  * `-f`, `--frequency` : intervalle de check en minutes (défaut : 30).
  * `-o`, `--output` : chemin du rapport HTML (défaut : `rapport.html`).
  * `-i`, `--interval` : intervalle en heures pour rapport complet (défaut : 12).

## 📖 Utilisation

```bash
# Lancer le monitoring en continu (CTRL+C pour arrêter)
python monitor.py
```

* Les rapports sont générés dans le fichier spécifié (`rapport.html`).
* Les notifications s’envoient via `notify-send` (par défaut) et peuvent déclencher l’ouverture automatique du rapport.

## 🔧 Intégration systemd (Linux)

1. **Créer** `/etc/systemd/system/monitor.service` et `monitor.timer` (voir dossier `systemd/`).
2. **Recharger et activer** :

   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable monitor.timer
   sudo systemctl start monitor.timer
   ```

3. **Vérifier** :

   ```bash
   systemctl list-timers --all
   journalctl -u monitor.service -f
   ```

## 📝 Roadmap (v2+)

* Tests unitaires et CI
* Passage à un crawler asynchrone
* Support des pages dynamiques (Playwright/Selenium)
* Export PDF automatique
* Dashboard Web (Flask/React)
* Notifications SMS, Discord, Teams
* Gestion de rétention et purge
* Internationalisation (FR/EN)
* Monitoring API
* Monitoring Sites Protégés
* Support Windows
* Packaging PyPI et Docker

---

*Zangbéto – Version 1.0.0*
