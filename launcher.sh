#!/bin/sh
# launcher.sh
export VALID_CARDS_FILE_PATH="/home/valid_card_ids_2.txt"

cd /
cd home/pi/MFRC522-python || exit
python3 app.py
cd /