#!/bin/bash

# This script acts as a watchdog for the main Python application.
# It allows the application to be restarted and updated remotely.
# It is also capable of updating itself.

HOME_DIR=/home/pi/dooropener

# Navigate to the script's directory to ensure correct relative paths
cd "$(dirname "$0")" || exit 1

# The main application loop
while true; do
    # Launch the Python application.
    # The config file is specified here for production deployment.
    python3 app.py --config $HOME_DIR/config.ini

    # Capture the exit status of the Python script
    STATUS=$?

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
