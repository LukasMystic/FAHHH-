# C2 · Logic rules

| | |
|---|---|
| **Owner** | William |
| **Used by** | Kezia, Stanley |
| **Due** | Mon 26 Oct, 18:00 |
| **Status** | DRAFT, menunggu persetujuan empat anggota |

Hanya William yang mengedit file ini. Setelah diterbitkan sebagai kontrak final, perubahan memerlukan `CONTRACT CHANGE C2` dan 👍 dari keempat anggota.

Aturan ini mengikuti `firmware/c1_aligned/sketch.ino` versi usulan. Sketch tersebut lolos pemeriksaan sintaks lokal, tetapi belum diuji ulang di Wokwi. Kolom MQTT di bawah adalah **pemetaan usulan untuk C3**, bukan event yang sudah dikirim oleh ESP32.

## States

| State | Feature | Condition / threshold | Output (pattern) | MQTT event |
|---|---|---|---|---|
| `SELECT_LINE` | P2 | Awal perangkat atau reset; putar rotary untuk memilih Demo A/B, tekan singkat untuk lanjut | Serial `MENU line`; 1 bunyi pendek saat pilihan berubah | Belum ada |
| `SELECT_DEST` | P2 | Putar rotary untuk memilih stasiun dalam jalur demo; tekan singkat untuk mengunci tujuan | Serial `MENU destination`; 1 bunyi pendek saat pilihan berubah | Belum ada |
| `SEEK_PLATFORM` | P2 | Tujuan dikunci; menunggu tag RFID terdaftar atau `SIM TAG <ID>` | Serial `ROUTE`, lalu `RFID_CHECKPOINT` dan `CHECKPOINT` saat tag terbaca | Usulan `GUIDE_STEP`; `ARRIVED_PLATFORM` belum dapat diklaim karena tag belum membuktikan peron |
| `WAIT_TRAIN` | P2/P1 | Tag RFID terdaftar selain tujuan. Potensiometer beacon dianggap dekat jika ADC >2600 dan dianggap menjauh jika ADC ≤2100. Tekan rotary setelah pengguna mengonfirmasi naik | 2 bunyi pendek saat masuk; `SIM_TRAIN_NEAR` dan 3 bunyi pendek ketika dekat; `BOARDING_CONFIRMED_BY_USER` setelah konfirmasi | `BOARDING_GAP` **belum tersedia**: celah atau undakan peron-kereta belum diukur |
| `ON_TRAIN` | P1 | Konfirmasi naik dari `WAIT_TRAIN`; `SIM ARRIVE <ID>` yang cocok dengan tujuan atau tag tujuan dalam demo memicu tahap berikutnya | 2 bunyi sedang saat naik; sumber kedatangan diberi label simulasi di Serial | `BOARDING_GAP` **belum tersedia** |
| `ARRIVING` | P1 | Sinyal kedatangan simulasi cocok dengan tujuan; tekan rotary setelah pengguna mengonfirmasi turun | `SIM_DESTINATION_APPROACH` jika lewat `SIM ARRIVE`; 3 bunyi sedang; lalu `ALIGHTING_CONFIRMED_BY_USER` | Belum ada event kedatangan nyata; sumber masih simulasi |
| `COMPLETE` | P1/P2 | Konfirmasi turun, atau tag tujuan terbaca saat `SEEK_PLATFORM` dalam demo | 3 bunyi pendek; status akhir di Serial | Belum ada |
| Semua state, tanpa mengubah state perjalanan | S1/P3 | HC-SR04: jarak > baseline +15 cm dan >25 cm selama 3 bacaan berturut-turut, tiap 120 ms. Aman kembali setelah 700 ms bacaan valid. Koreksi `jarak × cos(sudut MPU)` jika sudut ≤65°; jika MPU tidak valid, pakai jarak mentah dan baseline mentah terpisah | `EDGE_WARNING` dan 1 bunyi panjang; `EDGE_CLEAR` saat aman. Kehilangan echo memicu `EDGE_SENSOR_FAULT`; kegagalan MPU memicu `MPU_FAULT_RAW_FALLBACK`. Peringatan lama tidak hilang hanya karena sensor gagal | Usulan `LEVEL_CHANGE` untuk `EDGE_WARNING`; belum dipublish |
| `EMERGENCY` | S2/P3 | Tombol bantuan LOW stabil 40 ms lalu ditahan 3 detik dari state mana pun; terkunci sampai `ACK HELP` khusus demo | `HELP_REQUEST`, pola 4 bunyi bernada tinggi; status bantuan lokal aktif tanpa Wi-Fi | Usulan `EMERGENCY`; belum dipublish dan belum berarti bantuan diterima |
| Belum ada state/aturan | P1 | Pengukuran celah atau undakan peron-kereta belum diimplementasikan | Tidak ada klaim keselamatan celah | `BOARDING_GAP` belum boleh dikirim sebagai pengukuran nyata |
| Belum ada state/aturan | Baterai | Tidak ada sensor atau pembacaan tegangan baterai | Tidak ada | `LOW_BATTERY` belum boleh dikirim |

Perpindahan utama: `SELECT_LINE` → `SELECT_DEST` → `SEEK_PLATFORM` → `WAIT_TRAIN` → `ON_TRAIN` → `ARRIVING` → `COMPLETE`. Dari `SEEK_PLATFORM`, tag tujuan bisa langsung menuju `COMPLETE` hanya dalam demo. Tombol bantuan membawa state apa pun ke `EMERGENCY`. Tekan rotary lebih dari 1,2 detik mengulang menu jika darurat tidak aktif; `ACK HELP` lewat Serial hanya mereset demo.

## Alert language

| Pattern | Meaning |
|---|---|
| 1 bunyi pendek, 650 Hz, 45 ms | Pilihan rotary berpindah; konfirmasi navigasi biasa |
| 2 bunyi pendek, 700 Hz, 100 ms | Titik RFID dikenali dan alur masuk `WAIT_TRAIN` |
| 3 bunyi pendek, 900 Hz, 100 ms | Beacon **simulasi** memberi petunjuk kereta dekat; pengguna tetap memverifikasi jalur dan arah |
| 1 bunyi panjang, 1200 Hz, 700 ms | Bahaya tepi atau gangguan sensor yang memerlukan kewaspadaan |
| 2 bunyi, 750 Hz, 220 ms | Kemiringan tongkat >65° selama 2 detik; `CANE_TILT_ADVISORY` |
| 4 bunyi, 1600 Hz, 250 ms | Permintaan bantuan lokal aktif; `HELP_REQUEST` |

Prioritas: peringatan tepi/gangguan sensor dapat memotong bunyi bantuan, lalu bunyi bantuan berlanjut. Bunyi navigasi biasa tidak menimpa peringatan bahaya atau bantuan. LED pada Wokwi mewakili keluaran getar, tetapi belum ada motor getar maupun suara yang menyebut nama stasiun.

**Aturan P3:** keputusan peringatan keselamatan S1 dibuat di ESP32 dan tidak menunggu Wi-Fi/MQTT. Aturan yang sama wajib berlaku untuk P1 setelah pengukuran celah diimplementasikan. Tombol bantuan S2 juga memicu bunyi lokal tanpa koneksi. Ketika C3 disepakati, Stanley dan William perlu menetapkan payload, sumber waktu, dan pemetaan event sebelum MQTT diaktifkan.

**Label simulasi:** potensiometer mewakili RSSI BLE, `SIM ARRIVE` mewakili telemetri kereta, dan `SIM TAG` mewakili pembacaan RFID melalui Serial. RFID fisik hanya membuktikan tag terdaftar terbaca; tag tidak membuktikan peron atau kereta yang benar. Menu saat ini hanya menampilkan nama stasiun di Serial, sehingga belum dapat dipakai mandiri oleh pengguna tunanetra.