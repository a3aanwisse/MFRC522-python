# MFRC522-python

This project controls a garage door using an RFID reader (RC522) and a Raspberry Pi. It includes a Flask web interface for management and monitoring.

## Hardware Setup

### Pin Layout

#### RC522 RFID Reader

| RFID Pin | Raspberry Pi Pin | Function |
|---|---|---|
| SDA | 24 | CEO / CSO |
| SCK | 23 | SCLK |
| MOSI | 19 | SPI MOSI |
| MISO | 21 | SPI MISO |
| IRQ | - | - |
| GND | 6 | Ground |
| RST | 22 | GPIO 25 |
| 3.3V | 1 | 3.3V |

#### Reed Switches

*   **Reed 1 (Closed Door):** Pin 13 (GPIO 22) & Pin 14 (Ground)
*   **Reed 2 (Open Door):** Pin 29 (GPIO 23) & Pin 30 (Ground)

#### Relay

*   **Input:**
    *   GND -> Pin 9 (Ground)
    *   IN -> Pin 11 (GPIO 17)
    *   VCC -> Pin 17 (3.3V)

## Software Setup

### Prerequisites

*   Raspberry Pi with Raspberry Pi OS
*   Python 3
*   `pip`

### Installation

1.  Clone the repository:
    ```bash
    git clone <repository_url>
    cd MFRC522-python
    ```

2.  Install dependencies:
    *   **Production:**
        ```bash
        pip install -r requirements.txt
        ```
    *   **Development (with mocks):**
        ```bash
        pip install -r requirements-dev.txt
        ```

### Configuration

1.  Create a `config.ini` file (or use the provided example).
2.  Configure the following sections:
    *   `[credentials]`: Username and password for the web interface.
    *   `[paths]`: Path to the `valid_card_ids.txt` file.
    *   `[ntfy]`: Topic for ntfy notifications.

### Running the Application

#### Production

Use the `launcher.sh` script to run the application with auto-update capabilities:

```bash
./launcher.sh
```

Or run directly with Python:

```bash
python3 app.py --config /path/to/config.ini
```

#### Development

Run with the `--dev` flag to mock hardware interactions:

```bash
python3 app.py --dev --config config.ini
```

### Web Interface

Access the web interface at `http://<raspberry_pi_ip>:5000`.

*   **Login:** Use credentials from `config.ini`.
*   **Manage Cards:** Add or view allowed RFID cards.
*   **Test:** Test relay and reed switch status.
*   **Update:** Trigger a git pull and restart via the web interface.

## Features

*   **RFID Access Control:** Toggles a relay to open/close the garage door when a valid card is scanned.
*   **Web Management:** Manage valid cards and monitor door status remotely.
*   **Door Status Monitoring:** Uses reed switches to detect if the door is open or closed.
*   **Notifications:** Sends notifications via `ntfy.sh` if the door is left open for too long.
*   **Auto-Update:** The `launcher.sh` script handles application updates and restarts.
