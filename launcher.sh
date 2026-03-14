#!/bin/bash
# launcher.sh

# This script acts as a watchdog for the main Python application.
# It allows the application to be restarted and updated remotely.
# It is also capable of updating itself.

# Stop het script als er een fout optreedt
set -e

APP_DIR=/home/pi/MFRC522-python
HOME_DIR=/home/pi/dooropener
REQ_FILE="${CHECKOUT_DIR}/requirements.txt"
INSTALLED_REQ_FILE="${VENV_DIR}/.installed_requirements"

# This script acts as a watchdog for the main Python application.
# It allows the application to be restarted and updated remotely.
# It is also capable of updating itself.


# Function to log messages to syslog
log() {
    echo "$1"
    logger -t dooropener-launcher "$1"
}

log "================================================="
log "INFO: Launcher script started."
log "================================================="

# Navigate to the script's directory to ensure correct relative paths
cd "$(dirname "$0")" || exit 1

# Haal de huidige git branch op
BRANCH_NAME=$(git rev-parse --abbrev-ref HEAD)
# De naam voor de virtuele omgeving
VENV_DIR="$HOME_DIR/venv_${BRANCH_NAME}"

# Controleer of python3 beschikbaar is
if ! command -v python3 &> /dev/null
then
    log "python3 is niet gevonden. Installeer Python 3 om dit script uit te voeren."
    exit 1
fi

# Creëer de virtuele omgeving als deze nog niet bestaat
if [ ! -d "$VENV_DIR" ]; then
    log "Virtuele omgeving wordt aangemaakt in '$VENV_DIR'..."
    python3 -m venv "$VENV_DIR"
fi

# Activeer de virtuele omgeving
source "$VENV_DIR/bin/activate"

# Controleer of het requirements bestand is veranderd sinds de laatste installatie
if [ ! -f "$INSTALLED_REQ_FILE" ] || ! cmp -s "$REQ_FILE" "$INSTALLED_REQ_FILE"; then
    log "Dependencies zijn gewijzigd of ontbreken, installeren..."
    pip install -r "$REQ_FILE"
    # Kopieer het geïnstalleerde requirements bestand om wijzigingen in de toekomst bij te houden
    cp "$REQ_FILE" "$INSTALLED_REQ_FILE"
else
    log "Dependencies zijn up-to-date."
fi

cd $CHECKOUT_DIR || exit 1

# Navigate to the application directory
cd "$APP_DIR" || { log "CRITICAL: Failed to navigate to $APP_DIR. Exiting."; exit 1; }

# The main application loop
while true; do
    log "INFO: Starting python application..."
    # The python app's output will be captured by the system journal via cron's configuration
    /usr/bin/python3 app.py --config "$HOME_DIR/config.ini"

    STATUS=$?
    log "INFO: Python application exited with status $STATUS."

    if [ "$STATUS" -eq 10 ]; then
        # Exit code 10 means: "Update and restart"
        log "UPDATE: Application signaled for an update. Pulling latest code from git..."
        # Prevent git from hanging on authentication
        GIT_TERMINAL_PROMPT=0 /usr/bin/git pull
        GIT_PULL_STATUS=$?
        log "INFO: Git pull finished with status $GIT_PULL_STATUS."

        if [ "$GIT_PULL_STATUS" -eq 0 ]; then
            log "UPDATE: Git pull successful. Restarting the launcher..."
            # Use exec to replace the current process with the new version.
            exec "$APP_DIR/launcher.sh"
        else
            log "ERROR: Git pull failed with status $GIT_PULL_STATUS. Will not restart. Exiting."
            break
        fi
    else
        # Any other exit code means a crash or a clean shutdown
        log "INFO: Application exited with status $STATUS. Shutting down launcher."
        break
    fi
done

log "================================================="
log "INFO: Launcher script finished."
log "================================================="
