#!/bin/bash
# switch_branch.sh

# Stop het script als er een fout optreedt
set -e

# Stop het draaiende Python-script
echo "Stoppen van het Python-script 'python app.py'..."
# Gebruik een robuuster pkill patroon om zowel 'python app.py' als 'python3 app.py' te vangen
pkill -f "python.*app.py" || true

echo "Switch branch naar experiments-2"
git checkout experiments-2


echo "Launching launcher.sh in background..."
# Start launcher.sh in de achtergrond met nohup om het los te koppelen van de huidige shell
nohup ./launcher.sh >/home/pi/dooropener/logs/dooropener 2>&1 &
echo "Script switch_branch.sh is voltooid."