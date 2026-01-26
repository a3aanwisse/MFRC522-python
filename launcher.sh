#!/bin/bash

# This script acts as a watchdog for the main Python application.
# It allows the application to be restarted and updated remotely.

export VALID_CARDS_FILE_PATH="/home/pi/valid_card_ids_2.txt"

# Navigate to the script's directory to ensure correct relative paths
cd "$(dirname "$0")"

# The main application loop
while true; do
    # Launch the Python application
    # The '--dev' flag should NOT be used here as this is for production.
    python3 app.py

    # Capture the exit status of the Python script
    STATUS=$?

    # Check the exit status to decide what to do next
    if [ $STATUS -eq 10 ]; then
        # Exit code 10 means: "Update and restart"
        echo "UPDATE: Application signaled for an update. Pulling latest code from git..."
        git pull
        echo "UPDATE: Git pull complete. Restarting application in 2 seconds..."
        sleep 2
    else
        # Any other exit code means a crash or a clean shutdown
        echo "INFO: Application exited with status $STATUS. Shutting down launcher."
        break
    fi
done
