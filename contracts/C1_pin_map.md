# C1 · Pin map

| | |
|---|---|
| **Owner** | Gebi |
| **Used by** | William |
| **Due** | Mon 26 Oct, 12:00 |
| **Status** | COMPLETED |

Only the owner edits this file. Changes after publishing: `CONTRACT CHANGE C1` + 👍 from all four.

| No. | Component | Device pin | ESP32 GPIO | Function / note | In Wokwi? |
|---|---|---|---|---|---|
| 1 | HC-SR04 | TRIG | 26 | Ultrasonic trigger (output). Ground-height change alert | Yes |
| 2 | HC-SR04 | ECHO | 27 | Ultrasonic echo (input). Real device: 1 kΩ + 2 kΩ divider to drop 5 V to 3.3 V | Yes |
| 3 | MPU6050 | SDA | 21 | I2C data. Cane tilt angle, used to correct the HC-SR04 distance | Yes |
| 4 | MPU6050 | SCL | 22 | I2C clock | Yes |
| 5 | MFRC522 | SDA (SS) | 5 | SPI chip select. Reads RFID tags in the guiding tiles (guidance to the platform) | Yes |
| 6 | MFRC522 | SCK | 18 | SPI clock | Yes |
| 7 | MFRC522 | MOSI | 23 | SPI data out | Yes |
| 8 | MFRC522 | MISO | 19 | SPI data in | Yes |
| 9 | MFRC522 | RST | 4 | Reset | Yes |
| 10 | KY-040 | CLK | 32 | Rotation signal A. Select destination platform (INPUT_PULLUP) | Yes |
| 11 | KY-040 | DT | 33 | Rotation signal B (INPUT_PULLUP) | Yes |
| 12 | KY-040 | SW | 25 | Confirm button (INPUT_PULLUP, active low) | Yes |
| 13 | Pushbutton | 1.r (2.r to GND) | 13 | Emergency button. Long press about 3 s (INPUT_PULLUP, active low) | Yes |
| 14 | Buzzer | 2 (+) (pin 1 to GND) | 14 | Hazard warning and emergency alarm | Yes |
| 15 | LED + 220 Ω resistor | Anode via resistor (cathode to GND) | 17 | Stand-in for the vibration motor (navigation haptics) | Stand-in |
| 16 | Potentiometer | SIG | 34 | Stand-in for the train-door BLE beacon RSSI. Input-only ADC1 pin, safe while WiFi is on | Stand-in |
| 17 | MPU6050, MFRC522, KY-040, potentiometer | VCC / 3.3V | 3V3 | 3.3 V supply. MFRC522 must never get 5 V | Yes |
| 18 | HC-SR04 | VCC | 5V | 5 V supply | Yes |
| 19 | All components | GND | GND | Common ground | Yes |

**Stand-in parts** (real part → Wokwi substitute, and why):
- Coin vibration motor (+ 2N2222 transistor, 1N4007 diode, 1 kΩ base resistor) → LED + 220 Ω on GPIO 17. Wokwi has no vibration motor, so the LED blinks with the same on/off pattern the motor will use.
- BLE scan for the train-door beacon (ESP32 built-in BLE) → potentiometer on GPIO 34, read as RSSI (−100 to −40 dBm). BLE is not reliably emulated in Wokwi. The sketch keeps this in one function, `readDoorBeaconRSSI()`, so only that function changes on real hardware.
- 18650 Li-ion + TP4056 charger + MT3608 5 V boost → none. Wokwi powers the board virtually; on the real device the boost output goes to VIN.
- Waterproof metal emergency button → standard pushbutton. Same behavior (momentary, active low).
- RFID tags under the guiding tiles → Wokwi's virtual card on the MFRC522 (Tap button).
