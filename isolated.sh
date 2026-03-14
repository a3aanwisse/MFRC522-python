#!/bin/sh

# Stop het script als er een fout optreedt
set -e

# De naam voor de virtuele omgeving
VENV_DIR="isolated_venv"

# Controleer of python3 beschikbaar is
if ! command -v python3 &> /dev/null
then
    echo "python3 is niet gevonden. Installeer Python 3 om dit script uit te voeren."
    exit 1
fi

# Maak de virtuele omgeving aan als deze nog niet bestaat
if [ ! -d "$VENV_DIR" ]; then
    echo "Virtuele omgeving wordt aangemaakt in '$VENV_DIR'..."
    python3 -m venv $VENV_DIR
fi

# Activeer de virtuele omgeving en installeer de dependencies
echo "Dependencies worden geïnstalleerd..."
. $VENV_DIR/bin/activate
pip install -r isolated_requirements.txt

# Voer het testscript uit
echo "Het testscript wordt gestart. Druk op Ctrl+C om te stoppen."
python3 app.py

# Deactiveer de virtuele omgeving na afloop
deactivate

echo "Script is voltooid."
