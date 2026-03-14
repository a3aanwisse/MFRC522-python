#!/bin/bash

# This script acts as a watchdog for the main Python application.
# It allows the application to be restarted and updated remotely.
# It is also capable of updating itself.

APP_DIR=/home/pi/MFRC522-python
HOME_DIR=/home/pi/dooropener

# Function to log messages to syslog
log() {
    echo "$1"
    logger -t dooropener-launcher "$1"
}

log "================================================="
log "INFO: Launcher script started."
log "================================================="

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
