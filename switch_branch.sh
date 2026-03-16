#!/bin/bash
# switch_branch.sh

# Stop het script als er een fout optreedt
set -e

# Stop het draaiende Python-script
echo "Stoppen van het Python-script 'python app.py'..."
pkill -f "python app.py"

git checkout experiments-2

./launcher.sh