#!/bin/bash

# Stop on any error
set -e

echo "--- Signal-CLI Auto-Installer for Raspberry Pi ---"

# --- Step 1: Install Dependencies (with architecture-aware Java installation) ---
echo "[1/4] Installing dependencies..."
sudo apt-get update

# Detect architecture to install the correct Java version
ARCH=$(uname -m)
echo "Detected architecture: $ARCH"

if [ "$ARCH" = "armv6l" ]; then
    echo "ARMv6 architecture detected (Pi 1/Zero). Installing Java 8."
    sudo apt-get install -y openjdk-8-jre wget curl jq
else
    echo "ARMv7 or newer architecture detected. Installing default Java."
    sudo apt-get install -y default-jre wget curl jq
fi

# Verify Java installation
if ! command -v java &> /dev/null; then
    echo "ERROR: Java installation failed. Please install Java manually and try again."
    exit 1
fi
echo "Java is installed successfully."

# Add Java version to the log output
echo "--- Java Version Info ---"
java -version
echo "-------------------------"


# --- Step 2: Find and Download the Latest signal-cli Release ---
echo "[2/4] Finding the latest signal-cli version..."

# Use GitHub API to find the latest release URL for the tar.gz file
LATEST_URL=$(curl -s https://api.github.com/repos/AsamK/signal-cli/releases/latest | jq -r '.assets[] | select(.name | endswith(".tar.gz")) | .browser_download_url')

if [ -z "$LATEST_URL" ]; then
    echo "ERROR: Could not find the latest signal-cli download URL. Please check the GitHub page manually."
    exit 1
fi

FILENAME=$(basename "$LATEST_URL")
echo "Downloading $FILENAME..."

# --- DEBUGGING STEP ---
# Print the URL we are about to download to see if it's valid.
echo "Attempting to download from URL: $LATEST_URL"
# --------------------

# Removed -q flag to make the download process verbose and show progress.
wget --show-progress "$LATEST_URL"

# --- Step 3: Extract and Install ---
echo "[3/4] Installing signal-cli..."

# Extract the archive
tar -xf "$FILENAME"
# The directory name is the filename without the .tar.gz
DIR_NAME="${FILENAME%.tar.gz}"

# Move the binary to a system-wide location
sudo mv "$DIR_NAME/bin/signal-cli" /usr/local/bin/

echo "signal-cli has been installed to /usr/local/bin/"

# --- Step 4: Clean Up ---
echo "[4/4] Cleaning up..."
rm -rf "$DIR_NAME"
rm "$FILENAME"

echo ""
echo "--- ✅ Installation Complete! ---"
echo ""
echo "Next, you MUST link it to your Signal account."
echo "Run the following command and scan the QR code with your phone's Signal app:"
echo "(In Signal: Settings > Linked Devices > +)"
echo ""
echo "    signal-cli link -n \"My Garage Pi\""
echo ""
