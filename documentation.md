# Pin Layout

## RC522

Also see  [this website](https://pimylifeup.com/raspberry-pi-rfid-rc522/)

Pin layout based on [raspberry Pi 3 model B+](https://www.etechnophiles.com/raspberry-pi-3-b-pinout-with-gpio-functions-schematic-and-specs-in-detail/)

| RFID Pin | Raspberry Pin | Function | Color  | Checked |
|----------|---------------|----------|--------|---------|
| SDA      | 24            | CEO      | Purple | Y       |
| SCK      | 23            | SCLK     | Brown  | Y       |
| MOSI     | 19            | SPI MOSI | Green  | Y       |
| MISO     | 21            | SPI MISO | Orange | Y       |
| IRQ      | -             | -        | -      |         |
| GnD      | 6             | Ground   | Black  | Y       |
| RST      | 22            | GPIO 25  | Blue   | Y       |
| 3.3V     | 1             | 3.3V     | Red    | Y       | 

## LED
| Raspberry Pin | Function | Color  | Checked |
|---------------|----------|--------|---------|
| 12            | GPIO 18  | Yellow | Y       |
| 39            | Ground   | Grey   | Y       |

## Reed

| Raspberry Pin | Function | Color | Checked |
|---------------|----------|-------|---------|
| 13            | GPIO 27  | White | Y       |
| 14            | Ground   | Black | Y       |

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

## Run

```python3 app.py```

Navigate to website: [http://192.168.68.138:5000/test](http://192.168.68.138:5000/test)