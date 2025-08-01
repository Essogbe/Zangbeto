#!/bin/sh
set -euo pipefail

# ------------------------------
# Configuration (modifiez si besoin)
# ------------------------------
PROJECT_DIR="$HOME/zangbeto-monitor"         # Répertoire du projet
VENV_DIR="$PROJECT_DIR/.venv"             # Emplacement du virtualenv
SERVICE_NAME="zangbeto-monitor"                   # Nom du service systemd (sans .service)
PYTHON_BIN="$VENV_DIR/bin/python"        # Interpréteur Python du venv
MONITOR_SCRIPT="$PROJECT_DIR/main.py" # Script principal
REPORT_PATH="$PROJECT_DIR/rapport.html"  # Chemin du rapport HTML
USER="$(whoami)"               # Utilisateur courant pour systemd

# ------------------------------
# 1. Création du projet
# ------------------------------
echo " Création du dossier de projet : $PROJECT_DIR"
mkdir -p "$PROJECT_DIR"
cp -r $PWD/* "$PROJECT_DIR" || {
  echo "Erreur lors de la copie des fichiers dans $PROJECT_DIR"
  exit 1
}
cd "$PROJECT_DIR"

# (Assurez-vous d’y placer monitor.py, templates/, notify.py, etc.)
# Vous pouvez cloner ou copier vos fichiers existants ici.

# ------------------------------
# 2. Création du virtualenv
# ------------------------------
if [[ -d "$VENV_DIR" ]]; then
  echo "  Virtualenv déjà existant dans $VENV_DIR, le supprime."
    rm -rf "$VENV_DIR"
    echo "  Création et activation d’un nouveau virtualenv dans $VENV_DIR"
    python3 -m venv "$VENV_DIR"
    echo "   -> Virtualenv créé."
    echo "  Activation du virtualenv"
    source "$VENV_DIR/bin/activate"
    echo "   -> Virtualenv activé."
 
  
else
  echo "  Aucun virtualenv trouvé dans $VENV_DIR, création en cours."
  echo "  Création et activation d’un virtualenv dans $VENV_DIR"
 python3 -m venv "$VENV_DIR"
 echo "   -> Virtualenv créé."

fi

echo "   Installation des dépendances dans le venv"
"$VENV_DIR/bin/pip" install --upgrade pip
# Créez ou mettez à jour requirements.txt dans PROJECT_DIR avant
if [[ -f requirements.txt ]]; then
  "$VENV_DIR/bin/pip" install -r requirements.txt
else
  echo "requirements.txt introuvable, installe les paquets manuellement si nécessaire."
fi

# ------------------------------
# 3. Création des unit files systemd
# ------------------------------
echo "  Création des fichiers systemd dans /etc/systemd/system/"
SERVICE_PATH="/etc/systemd/system/${SERVICE_NAME}.service"
TIMER_PATH="/etc/systemd/system/${SERVICE_NAME}.timer"

sudo tee "$SERVICE_PATH" > /dev/null <<EOF
[Unit]
Description=Site Monitoring Service
After=network.target

[Service]
Type=oneshot
User=${USER}
WorkingDirectory=${PROJECT_DIR}
ExecStart=${PYTHON_BIN} ${MONITOR_SCRIPT} \\
    --frequency 30 \\
    --output ${REPORT_PATH} \\
    --interval 12
EOF

sudo tee "$TIMER_PATH" > /dev/null <<EOF
[Unit]
Description=Timer for Site Monitoring Service

[Timer]
OnBootSec=1min
OnUnitActiveSec=30min
Unit=${SERVICE_NAME}.service

[Install]
WantedBy=timers.target
EOF

echo "   -> Créés :"
echo "      • $SERVICE_PATH"
echo "      • $TIMER_PATH"

# ------------------------------
# 4. Activation et démarrage
# ------------------------------
echo " Activation du timer systemd"
sudo systemctl daemon-reload
sudo systemctl enable "${SERVICE_NAME}.timer"
sudo systemctl start "${SERVICE_NAME}.timer"

echo " Setup terminé !"
echo "   • Vérifier le timer : systemctl list-timers --all | grep ${SERVICE_NAME}"
echo "   • Logs du service : journalctl -u ${SERVICE_NAME}.service -f"
