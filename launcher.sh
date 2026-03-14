#!/bin/bash
# launcher.sh

# This script acts as a watchdog for the main Python application.
# It allows the application to be restarted and updated remotely.
# It is also capable of updating itself.

# Stop the script if an error occurs
set -e

# Function to log messages to syslog with timestamp
log() {
    local timestamp=$(date +"%Y-%m-%d %H:%M:%S")
    echo "${timestamp} - $1"
    logger -t dooropener-launcher "${timestamp} - $1"
}

log "================================================="
log "INFO: Launcher script started."
log "================================================="

# Navigate to the script's directory to ensure correct relative paths
cd "$(dirname "$0")" || exit 1


app_dir=/home/pi/MFRC522-python
home_dir=/home/pi/dooropener
# Get the current git branch
branch_name=$(git rev-parse --abbrev-ref HEAD)
# The name for the virtual environment
venv_dir="${home_dir}/venv_${branch_name}"
req_file="${app_dir}/requirements.txt"
installed_req_file="${venv_dir}/.installed_requirements"


# Check if python3 is available
if ! command -v /usr/bin/python3 &> /dev/null
then
    log "/usr/bin/python3 not found. Please install Python 3 to run this script."
    exit 1
fi

# Create the virtual environment if it doesn't exist
if [ ! -d "${venv_dir}" ]; then
    log "Creating virtual environment in '${venv_dir}'..."
    python3 -m venv "${venv_dir}"
else
  log "Virtual environment in '${venv_dir}' is already existing."
fi

# Activate the virtual environment
log "Activating virtual environment in '${venv_dir}'..."
source "${venv_dir}/bin/activate"

# Check if the requirements file has changed since the last installation
if [ ! -f "${installed_req_file}" ] || ! cmp -s "${req_file}" "${installed_req_file}"; then
    log "Dependencies have changed or are missing, installing..."
    pip install -r "${req_file}"
    log "Copying the installed requirements file '${req_file}' to '${installed_req_file}' to track future changes"
    cp "${req_file}" "${installed_req_file}"
else
    log "Dependencies are up-to-date."
fi

# Navigate to the application directory
cd "${app_dir}" || { log "CRITICAL: Failed to navigate to ${app_dir}. Exiting."; exit 1; }

# The main application loop
while true; do
    log "INFO: Starting python application..."
    # The python app's output will be captured by the system journal via cron's configuration
    set +e
    python app.py --config "${home_dir}/config.ini"
    set -e

    status=$?
    log "INFO: Python application exited with status ${status}."

    if [ "${status}" -eq 10 ]; then
        # Exit code 10 means: "Update and restart"
        log "UPDATE: Application signaled for an update. Pulling latest code from git..."
        # Prevent git from hanging on authentication
        git_terminal_prompt=0 /usr/bin/git pull
        git_pull_status=$?
        log "INFO: Git pull finished with status ${git_pull_status}."

        if [ "${git_pull_status}" -eq 0 ]; then
            log "UPDATE: Git pull successful. Restarting the launcher..."
            # Use exec to replace the current process with the new version.
            exec "${app_dir}/launcher.sh"
        else
            log "ERROR: Git pull failed with status ${git_pull_status}. Will not restart. Exiting."
            break
        fi
    else
        # Any other exit code means a crash or a clean shutdown
        log "INFO: Application exited with status ${status}. Shutting down launcher."
        break
    fi
done

log "================================================="
log "INFO: Launcher script finished."
log "================================================="
