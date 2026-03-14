#!/bin/bash
# launcher.sh

# This script acts as a watchdog for the main Python application.
# It allows the application to be restarted and updated remotely.
# It is also capable of updating itself.

# Stop het script als er een fout optreedt
set -e

HOME_DIR=/home/pi/dooropener
CHECKOUT_DIR=/home/pi/MFRC522-python
# Haal de huidige git branch op

# Navigate to the script's directory to ensure correct relative paths
cd "$(dirname "$0")" || exit 1

BRANCH_NAME=$(git rev-parse --abbrev-ref HEAD)
# De naam voor de virtuele omgeving
VENV_DIR="$HOME_DIR/venv_${BRANCH_NAME}"

# Controleer of python3 beschikbaar is
if ! command -v python3 &> /dev/null
then
    echo "python3 is niet gevonden. Installeer Python 3 om dit script uit te voeren."
    exit 1
fi

REQ_FILE="${CHECKOUT_DIR}/requirements.txt"
INSTALLED_REQ_FILE="${VENV_DIR}/.installed_requirements"

# Creëer de virtuele omgeving als deze nog niet bestaat
if [ ! -d "$VENV_DIR" ]; then
    echo "Virtuele omgeving wordt aangemaakt in '$VENV_DIR'..."
    python3 -m venv "$VENV_DIR"
fi

# Activeer de virtuele omgeving
source "$VENV_DIR/bin/activate"

# Controleer of het requirements bestand is veranderd sinds de laatste installatie
if [ ! -f "$INSTALLED_REQ_FILE" ] || ! cmp -s "$REQ_FILE" "$INSTALLED_REQ_FILE"; then
    echo "Dependencies zijn gewijzigd of ontbreken, installeren..."
    pip install -r "$REQ_FILE"
    # Kopieer het geïnstalleerde requirements bestand om wijzigingen in de toekomst bij te houden
    cp "$REQ_FILE" "$INSTALLED_REQ_FILE"
else
    echo "Dependencies zijn up-to-date."
fi

cd $CHECKOUT_DIR || exit 1

# The main application loop
while true; do
    # Launch the Python application.
    # The config file is specified here for production deployment.
    set +e
    python3 app.py --config $HOME_DIR/config.ini

    # Capture the exit status of the Python script
    STATUS=$?
    set -e

    # Check the exit status to decide what to do next
    if [ $STATUS -eq 10 ]; then
        # Exit code 10 means: "Update and restart"
        echo "UPDATE: Application signaled for an update. Pulling latest code from git..."
        git pull
        echo "UPDATE: Git pull complete. Restarting the launcher to apply any updates to itself as well..."
        # Use exec to replace the current process with a new one from the updated file on disk.
        # This ensures that if launcher.sh itself was updated, the new version is used.
        exec ./launcher.sh
    else
        # Any other exit code means a crash or a clean shutdown
        echo "INFO: Application exited with status $STATUS. Shutting down launcher."
        break
    fi
done
