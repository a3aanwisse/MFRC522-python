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

if [[ "$ARCH" == "armv6l" || "$ARCH" == "armv7l" ]]; then
    echo "ARMv6/v7 architecture detected (Pi 1/Zero/2/3).. Installing Java 8."
    sudo apt-get install -y openjdk-8-jre wget curl jq
elif [ "$ARCH" = "aarch64" ]; then
    echo "ARM64 architecture detected (Pi 3/4 64-bit OS).. Installing default Java."
    sudo apt-get install -y default-jre wget curl jq
else
    echo "Unknown or non-ARM architecture ($ARCH). Installing default Java."
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

LATEST_URL=""
NATIVE_BUILD_SUFFIX=""

# Determine the preferred native build suffix based on detected architecture
if [ "$ARCH" = "aarch64" ]; then
    NATIVE_BUILD_SUFFIX="arm64-native.tar.gz"
elif [[ "$ARCH" == arm* ]]; then
    NATIVE_BUILD_SUFFIX="armhf-native.tar.gz"
fi

# Try to find the most appropriate native build first
if [ -n "$NATIVE_BUILD_SUFFIX" ]; then
    echo "Attempting to find native build for $ARCH: *$NATIVE_BUILD_SUFFIX*"
    LATEST_URL=$(curl -s https://api.github.com/repos/AsamK/signal-cli/releases/latest | \
                 jq -r ".assets[] | select(.name | endswith(\"$NATIVE_BUILD_SUFFIX\")) | .browser_download_url" | \
                 head -n 1)
fi

# If specific native build not found, or if ARCH was not ARM, fall back to generic source tar.gz
if [ -z "$LATEST_URL" ]; then
    echo "WARNING: Specific native build for $ARCH not found. Falling back to generic source tar.gz."
    LATEST_URL=$(curl -s https://api.github.com/repos/AsamK/signal-cli/releases/latest | \
                 jq -r ".assets[] | select(.name | endswith(\".tar.gz\") and (.name | contains(\"native\") | not)) | .browser_download_url" | \
                 head -n 1)
fi

# If still empty, try any .tar.gz as a last resort (might be x86_64 or other non-compatible, but better than nothing)
if [ -z "$LATEST_URL" ]; then
    echo "WARNING: Generic source tar.gz not found. Trying any .tar.gz (may not be compatible)."
    LATEST_URL=$(curl -s https://api.github.com/repos/AsamK/signal-cli/releases/latest | \
                 jq -r ".assets[] | select(.name | endswith(\".tar.gz\")) | .browser_download_url" | \
                 head -n 1)
fi

if [ -z "$LATEST_URL" ]; then
    echo "ERROR: Could not find any suitable signal-cli download URL. Please check the GitHub page manually."
    exit 1
fi

FILENAME=$(basename "$LATEST_URL")
echo "Downloading $FILENAME..."
echo "Attempting to download from URL: $LATEST_URL"
wget --show-progress "$LATEST_URL"

# --- Step 3: Extract and Install ---
echo "[3/4] Installing signal-cli..."

# Find the signal-cli executable within the extracted directory (whose name we don't know)
SIGNAL_CLI_EXECUTABLE=$(find . -name "signal-cli" -type f | head -n 1)

if [ -z "$SIGNAL_CLI_EXECUTABLE" ]; then
    echo "ERROR: Could not find 'signal-cli' executable in the extracted archive."
    exit 1
fi

echo "Found executable at: $SIGNAL_CLI_EXECUTABLE"

# Move the found executable to a system-wide location
sudo mv "$SIGNAL_CLI_EXECUTABLE" /usr/local/bin/

echo "signal-cli has been installed to /usr/local/bin/"

# --- Step 4: Clean Up ---
echo "[4/4] Cleaning up..."
# The extracted directory name is unpredictable, so we find it based on the tarball name
DIR_NAME=$(tar -tf "$FILENAME" | head -1 | cut -f1 -d"/")
if [ -d "$DIR_NAME" ]; then
    rm -r "$DIR_NAME"
fi
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