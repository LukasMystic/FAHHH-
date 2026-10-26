// Tongkat Pintar Teman Netra - SELF TEST WIRING
// Tempel menggantikan isi sketch.ino di Wokwi, lalu jalankan dan buka Serial Monitor.
// Library yang dibutuhkan: MFRC522 (miguelbalboa)
//
// Tes otomatis (jalan sendiri saat start): LED, buzzer, MPU6050, chip MFRC522
// Tes manual (kamu yang aksi di simulator): HC-SR04, potensiometer, KY-040,
// tombol emergency, tap kartu RFID

#include <Wire.h>
#include <SPI.h>
#include <MFRC522.h>
#include <math.h>

// ---------- Pin (sesuai diagram wiring) ----------
const int PIN_TRIG     = 26;  // HC-SR04 TRIG
const int PIN_ECHO     = 27;  // HC-SR04 ECHO
const int PIN_SDA      = 21;  // MPU6050 SDA
const int PIN_SCL      = 22;  // MPU6050 SCL
const int PIN_RFID_SS  = 5;   // MFRC522 SDA (SS)
const int PIN_RFID_RST = 4;   // MFRC522 RST
const int PIN_ENC_CLK  = 32;  // KY-040 CLK
const int PIN_ENC_DT   = 33;  // KY-040 DT
const int PIN_ENC_SW   = 25;  // KY-040 SW
const int PIN_SOS      = 13;  // Tombol emergency (1.r)
const int PIN_BUZZER   = 14;  // Buzzer +
const int PIN_VIBRATE  = 17;  // LED pengganti getar (GPIO 17)
const int PIN_POT      = 34;  // Potensiometer SIG

const uint8_t MPU_ADDR = 0x68;

MFRC522 rfid(PIN_RFID_SS, PIN_RFID_RST);

const int PIN_LED = 17;

void setup() {
  pinMode(PIN_LED, OUTPUT);
}

void loop() {
  digitalWrite(PIN_LED, HIGH);
  delay(500);
  digitalWrite(PIN_LED, LOW);
  delay(500);
}

// ---------- Daftar tes ----------
enum Tes {
  T_MPU, T_RFID_CHIP, T_ULTRA, T_POT,
  T_ENC_CW, T_ENC_CCW, T_ENC_SW, T_SOS, T_RFID_TAG,
  T_JUMLAH
};

const char* NAMA_TES[T_JUMLAH] = {
  "MPU6050 terbaca lewat I2C",
  "MFRC522 terdeteksi lewat SPI",
  "HC-SR04 mengukur jarak",
  "Potensiometer diputar",
  "KY-040 diputar searah jarum jam",
  "KY-040 diputar berlawanan arah",
  "KY-040 tombol ditekan",
  "Tombol emergency ditekan",
  "Tag RFID di-tap"
};

const char* PETUNJUK[T_JUMLAH] = {
  "cek SDA->21, SCL->22, VCC->3V3, GND",
  "cek SDA->5, SCK->18, MOSI->23, MISO->19, RST->4, 3.3V->3V3, GND",
  "klik sensor lalu atur jarak; cek TRIG->26, ECHO->27, VCC->5V, GND",
  "putar knob potensiometer; cek SIG->34, VCC->3V3, GND",
  "klik encoder lalu tekan panah kanan/atas; cek CLK->32, DT->33",
  "klik encoder lalu tekan panah kiri/bawah",
  "klik encoder lalu tekan spasi; cek SW->25",
  "klik tombol (atau tekan tombol keyboard-nya); cek 1.r->13, 2.r->GND",
  "klik modul MFRC522, pilih kartu, tekan Tap"
};

bool lulus[T_JUMLAH];
bool ringkasanTercetak = false;

// ---------- Fungsi bantu ----------
void tandai(Tes t, const char* info) {
  if (lulus[t]) return;
  lulus[t] = true;
  Serial.printf("[OK]    %s %s\n", NAMA_TES[t], info);
}

void gagal(Tes t, const char* info) {
  Serial.printf("[GAGAL] %s: %s\n        -> %s\n", NAMA_TES[t], info, PETUNJUK[t]);
}

// Bunyi manual tanpa tone(), supaya jalan di semua versi core ESP32
void beep(int freq, int ms) {
  unsigned long half = 500000UL / freq;
  unsigned long end = millis() + ms;
  while (millis() < end) {
    digitalWrite(PIN_BUZZER, HIGH);
    delayMicroseconds(half);
    digitalWrite(PIN_BUZZER, LOW);
    delayMicroseconds(half);
  }
}

float jarakCm() {
  digitalWrite(PIN_TRIG, LOW);
  delayMicroseconds(2);
  digitalWrite(PIN_TRIG, HIGH);
  delayMicroseconds(10);
  digitalWrite(PIN_TRIG, LOW);
  unsigned long dur = pulseIn(PIN_ECHO, HIGH, 30000UL);
  if (dur == 0) return -1;
  return dur / 58.0;
}

// Mengembalikan 0 = tidak membalas, 1 = OK, 2 = membalas tapi nilai aneh
int cekMPU(float &g) {
  Wire.beginTransmission(MPU_ADDR);
  Wire.write(0x6B);  // PWR_MGMT_1
  Wire.write(0);     // bangunkan sensor
  if (Wire.endTransmission() != 0) return 0;
  delay(20);

  Wire.beginTransmission(MPU_ADDR);
  Wire.write(0x3B);  // ACCEL_XOUT_H
  Wire.endTransmission(false);
  Wire.requestFrom(MPU_ADDR, (uint8_t)6);
  if (Wire.available() < 6) return 0;
  uint8_t b[6];
  for (int i = 0; i < 6; i++) b[i] = Wire.read();
  float ax = (int16_t)((b[0] << 8) | b[1]) / 16384.0;
  float ay = (int16_t)((b[2] << 8) | b[3]) / 16384.0;
  float az = (int16_t)((b[4] << 8) | b[5]) / 16384.0;
  g = sqrt(ax * ax + ay * ay + az * az);
  return (g > 0.5 && g < 1.5) ? 1 : 2;
}

// ---------- Setup: tes otomatis ----------
void setup() {
  Serial.begin(115200);
  delay(300);

  pinMode(PIN_TRIG, OUTPUT);
  pinMode(PIN_ECHO, INPUT);
  pinMode(PIN_ENC_CLK, INPUT_PULLUP);
  pinMode(PIN_ENC_DT, INPUT_PULLUP);
  pinMode(PIN_ENC_SW, INPUT_PULLUP);
  pinMode(PIN_SOS, INPUT_PULLUP);
  pinMode(PIN_BUZZER, OUTPUT);
  pinMode(PIN_VIBRATE, OUTPUT);

  Wire.begin(PIN_SDA, PIN_SCL);
  SPI.begin();  // SCK 18, MISO 19, MOSI 23
  rfid.PCD_Init();

  Serial.println();
  Serial.println("=== SELF TEST TONGKAT PINTAR ===");

  Serial.println("[TES]   LED pengganti getar: harus berkedip 3x");
  for (int i = 0; i < 3; i++) {
    digitalWrite(PIN_VIBRATE, HIGH);
    delay(150);
    digitalWrite(PIN_VIBRATE, LOW);
    delay(150);
  }

  Serial.println("[TES]   Buzzer: harus terdengar dua bunyi bip (rendah lalu tinggi)");
  beep(1000, 150);
  delay(80);
  beep(1500, 150);

  float g = 0;
  int mpu = cekMPU(g);
  if (mpu == 1) {
    char info[32];
    snprintf(info, sizeof(info), "(total %.2f g)", g);
    tandai(T_MPU, info);
  } else if (mpu == 2) {
    char info[48];
    snprintf(info, sizeof(info), "membalas, tapi nilai aneh (%.2f g)", g);
    gagal(T_MPU, info);
  } else {
    gagal(T_MPU, "tidak membalas di alamat 0x68");
  }

  byte ver = rfid.PCD_ReadRegister(MFRC522::VersionReg);
  if (ver != 0x00 && ver != 0xFF) {
    char info[24];
    snprintf(info, sizeof(info), "(versi 0x%02X)", ver);
    tandai(T_RFID_CHIP, info);
  } else {
    gagal(T_RFID_CHIP, "tidak ada respons dari chip");
  }

  Serial.println("--- Tes manual: lakukan aksi di simulator, hasilnya muncul di sini ---");
}

// ---------- Loop: tes manual ----------
int lastClk = HIGH;
int lastSw = HIGH;
int lastSos = HIGH;
int posisiEnc = 0;

int potAwal = -1;
int potTerakhir = -1;
float jarakTerakhir = -100;

unsigned long tPot = 0, tJarak = 0, tRfid = 0, tIngat = 0;

void loop() {
  unsigned long now = millis();

  // KY-040: putar
  int clk = digitalRead(PIN_ENC_CLK);
  if (clk != lastClk) {
    lastClk = clk;
    if (clk == LOW) {
      if (digitalRead(PIN_ENC_DT) == HIGH) {
        posisiEnc++;
        Serial.printf("Encoder: searah jarum jam (posisi %d)\n", posisiEnc);
        tandai(T_ENC_CW, "");
      } else {
        posisiEnc--;
        Serial.printf("Encoder: berlawanan arah (posisi %d)\n", posisiEnc);
        tandai(T_ENC_CCW, "");
      }
    }
  }

  // KY-040: tombol
  int sw = digitalRead(PIN_ENC_SW);
  if (sw == LOW && lastSw == HIGH) {
    Serial.println("Encoder: tombol ditekan");
    tandai(T_ENC_SW, "");
    beep(1500, 60);
  }
  lastSw = sw;

  // Tombol emergency
  int sos = digitalRead(PIN_SOS);
  if (sos == LOW && lastSos == HIGH) {
    Serial.println("Emergency: tombol ditekan");
    tandai(T_SOS, "");
    beep(2000, 100);
  }
  lastSos = sos;

  // Potensiometer
  if (now - tPot >= 100) {
    tPot = now;
    int v = analogRead(PIN_POT);
    if (potAwal < 0) {
      potAwal = v;
      potTerakhir = v;
    }
    if (abs(v - potTerakhir) >= 300) {
      potTerakhir = v;
      Serial.printf("Potensiometer: %d (setara RSSI %d dBm)\n", v, (int)map(v, 0, 4095, -100, -40));
    }
    if (abs(v - potAwal) >= 1000) tandai(T_POT, "");
  }

  // HC-SR04
  if (now - tJarak >= 300) {
    tJarak = now;
    float d = jarakCm();
    if (d > 2 && d < 400) {
      if (!lulus[T_ULTRA]) {
        char info[24];
        snprintf(info, sizeof(info), "(%.1f cm)", d);
        tandai(T_ULTRA, info);
      }
      if (fabs(d - jarakTerakhir) >= 5) {
        jarakTerakhir = d;
        Serial.printf("HC-SR04: %.1f cm\n", d);
      }
    }
  }

  // MFRC522: tap kartu
  if (now - tRfid >= 100) {
    tRfid = now;
    if (rfid.PICC_IsNewCardPresent() && rfid.PICC_ReadCardSerial()) {
      Serial.print("RFID: UID =");
      for (byte i = 0; i < rfid.uid.size; i++) Serial.printf(" %02X", rfid.uid.uidByte[i]);
      Serial.println();
      tandai(T_RFID_TAG, "");
      rfid.PICC_HaltA();
    }
  }

  // Pengingat tes yang belum lulus (tiap 10 detik)
  if (now - tIngat >= 10000) {
    tIngat = now;
    bool adaYangBelum = false;
    for (int i = 0; i < T_JUMLAH; i++) {
      if (!lulus[i]) {
        if (!adaYangBelum) Serial.println("--- Belum lulus ---");
        adaYangBelum = true;
        Serial.printf("[ ]     %s\n        -> %s\n", NAMA_TES[i], PETUNJUK[i]);
      }
    }
  }

  // Ringkasan kalau semua sudah lulus
  if (!ringkasanTercetak) {
    bool semua = true;
    for (int i = 0; i < T_JUMLAH; i++) {
      if (!lulus[i]) semua = false;
    }
    if (semua) {
      ringkasanTercetak = true;
      Serial.println("=== SEMUA TES LULUS: wiring sesuai diagram ===");
      Serial.println("Catatan: LED dan buzzer tidak bisa dicek oleh kode, konfirmasi dari lampu dan suara di simulator.");
    }
  }
}

