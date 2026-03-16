#!/bin/bash
# switch_branch.sh

# Stop het script als er een fout optreedt
set -e

# Stop het draaiende Python-script
echo "Stoppen van het Python-script 'python3 app.py'..."
pkill -f "python3 app.py" || true

echo "Switch branch naar experiments-2"
git checkout experiments-2

echo "Launch!"
./launcher.sh >/home/pi/dooropener/logs/dooropener 2>&1