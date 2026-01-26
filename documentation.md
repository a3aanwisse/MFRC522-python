# Pin Layout

## RC522

Also see  [this website](https://pimylifeup.com/raspberry-pi-rfid-rc522/)

Pin layout based on [raspberry Pi 3 model B+](https://www.etechnophiles.com/raspberry-pi-3-b-pinout-with-gpio-functions-schematic-and-specs-in-detail/)

| RFID Pin | Raspberry Pin | Function  | Color RP | Color network  | Checked |
|----------|---------------|-----------|----------|----------------|---------|
| SDA      | 24            | CEO / CSO | Purple   | Blue / White   | Y       |
| SCK      | 23            | SCLK      | Brown    | Brown          | Y       |
| MOSI     | 19            | SPI MOSI  | Green    | Green          | Y       |
| MISO     | 21            | SPI MISO  | Orange   | Orange         | Y       |
| IRQ      | -             | -         | -        |                |         |
| GnD      | 6             | Ground    | Black    | Green / White  | Y       |
| RST      | 22            | GPIO 25   | Blue     | Blue           | Y       |
| 3.3V     | 1             | 3.3V      | Red      | Orange / White | Y       | 

## Reed 1

| Raspberry Pin | Function | Color | Checked |
|---------------|----------|-------|---------|
| 13            | GPIO 22  | White | Y       |
| 14            | Ground   | Black | Y       |

## Reed 2

| Raspberry Pin | Function | Color | Checked |
|---------------|----------|-------|---------|
| 29            | GPIO 23  | White | N       |
| 30            | Ground   | Black | N       |

## Relay

### Pi side

| Relay In | Raspberry Pin | Function      | Color | Checked |
|----------|---------------|---------------|-------|---------|
| GND      | 9             | Ground        | Black | Y       |
| IN       | 11            | PIO 17 / SPI1 | White | Y       |
| VCC      | 17            | 3.3V          | Red   | Y       |

### Outgoing side

| Relay Out | Function      | Checked |
|-----------|---------------|---------|
| NC        | Ground        | N       |
| COM       | PIO 17 / SPI1 | N       |
| NO        | 3.3V          | N       |

# Raspberry Pi

## Setup

Updated via git on the pi

## Installed in crontab:
sudo crontab -e

## Run

```python3 app.py```

Navigate to website: [http://192.168.68.138:5000/test](http://192.168.68.138:5000/test)