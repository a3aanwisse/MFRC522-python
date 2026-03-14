#!/bin/sh
# launcher.sh

# Stop het script als er een fout optreedt
set -e

cd /home/pi/MFRC522-python

# Haal de huidige git branch op
BRANCH_NAME=$(git rev-parse --abbrev-ref HEAD)

# Maak de naam van de virtual environment op basis van de branch
VENV_DIR="venv_${BRANCH_NAME}"

# Controleer of python3 beschikbaar is
if ! command -v python3 &> /dev/null
then
    echo "python3 is niet gevonden. Installeer Python 3 om dit script uit te voeren!"
    exit 1
fi

REQ_FILE="isolated_requirements.txt"
INSTALLED_REQ_FILE="${VENV_DIR}/.installed_requirements"

# Creëer de virtuele omgeving als deze nog niet bestaat
if [ ! -d "$VENV_DIR" ]; then
    echo "Virtuele omgeving wordt aangemaakt in '$VENV_DIR'..."
    python3 -m venv "$VENV_DIR"
fi

# Activeer de virtuele omgeving
. "$VENV_DIR/bin/activate"

# Controleer of het requirements bestand is veranderd sinds de laatste installatie
if [ ! -f "$INSTALLED_REQ_FILE" ] || ! cmp -s "$REQ_FILE" "$INSTALLED_REQ_FILE"; then
    echo "Dependencies zijn gewijzigd of ontbreken, installeren..."
    pip install -r "$REQ_FILE"
    # Kopieer het geïnstalleerde requirements bestand om wijzigingen in de toekomst bij te houden
    cp "$REQ_FILE" "$INSTALLED_REQ_FILE"
else
    echo "Dependencies zijn up-to-date."
fi

# Start de applicatie
python3 app.py

# Deactiveer de virtuele omgeving na afloop
deactivate

echo "Script is voltooid."