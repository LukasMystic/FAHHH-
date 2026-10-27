# Skenario pengujian

Owner: Stanley. Dipakai langsung untuk laporan bagian 10 (Skenario dan Hasil Pengujian) dan 11 (Bukti Visual), jadi ditulis dalam Bahasa Indonesia.

**Aturan:** kolom *Hasil aktual* dan *Status* hanya diisi dari percobaan nyata di Wokwi (dan dashboard). Belum dijalankan = `[TBD — jalankan di Wokwi]`. Tidak ada hasil yang dikarang (AGENTS.md §7).

Sumber perilaku yang diharapkan: C2 (aturan logika, William) dan C3 v3 (MQTT, Stanley). Angka ambang diambil dari C2.

## Ringkasan

| Kasus uji | Fitur | Jenis |
|---|---|---|
| T1 | P2 Pemandu menuju peron | Normal |
| T2 | P1 Bantuan naik dan turun kereta | Normal |
| T3 | S1 Peringatan perubahan ketinggian tanah | Perubahan kondisi |
| T4 | S1 Tongkat terlalu miring (MPU6050) | Abnormal |
| T5 | S2 Tombol darurat + bahaya tepi saat darurat | Abnormal |
| T6 | S2 Tombol darurat ditekan singkat (< 3 s) | Abnormal |
| T7 | P3 Koneksi terputus (alarm tetap lokal) | Abnormal |
| T8 | Keamanan broker publik: pesan asing/rusak | Abnormal |
| T9 | Kartu RFID tidak terdaftar | Abnormal |

Minimal yang wajib (guideline): 3 skenario, termasuk abnormal. Jika waktu sempit, prioritas: **T1, T3, T5, T7**.

## Tabel pengujian (format laporan bagian 10)

| Kasus uji | Input atau kondisi | Hasil yang diharapkan | Hasil aktual | Status |
|---|---|---|---|---|
| T1 — Pilih tujuan dan titik pemeriksaan stasiun | Putar KY-040 ke *Demo A*, tekan; putar ke **A06 Gondangdia**, tekan. Lalu tap kartu biru RFID (A01). | Serial: `MENU line`, `MENU destination`, `ROUTE destination=A06`, lalu `RFID_CHECKPOINT id=A01`. State `SELECT_LINE → SELECT_DEST → SEEK_PLATFORM → WAIT_TRAIN`. Buzzer/LED: 1 bunyi pendek tiap putaran, 2 bunyi pendek (700 Hz) saat checkpoint. Dashboard: *Waiting for Train*, Destination *A06 Gondangdia*, Last Station Tag *A01 Jakarta Kota*, langkah Journey "Wait for the train" = *Now*. | [TBD — jalankan di Wokwi] | [TBD] |
| T2 — Kereta datang, naik, tiba, turun | Lanjutan T1. Naikkan potensiometer sampai ADC > 2600. Tekan KY-040. Ketik `SIM ARRIVE A06` di Serial Monitor. Tekan KY-040. | `SIM_TRAIN_NEAR` + 3 bunyi pendek (900 Hz); `BOARDING_CONFIRMED_BY_USER`, state `ON_TRAIN`; `SIM_DESTINATION_APPROACH`, state `ARRIVING`; `ALIGHTING_CONFIRMED_BY_USER`, state `COMPLETE`. Dashboard: *Train at Door = Yes* lalu urutan Journey sampai *Step off = Done*. Serial menandai potensiometer dan `SIM ARRIVE` sebagai **simulasi**. | [TBD — jalankan di Wokwi] | [TBD] |
| T3 — Tepi peron / turunan | MPU6050 tegak (sudut ≤ 65°). Atur jarak HC-SR04 ke **20 cm**, tunggu stabil (± 3 s). Ubah ke **60 cm**. Setelah peringatan, kembalikan ke 20 cm. | Jarak > baseline + 15 cm dan > 25 cm selama 3 pembacaan (± 0,36 s) → `EDGE_WARNING`, 1 bunyi panjang 1200 Hz. Kembali normal ≥ 0,7 s → `EDGE_CLEAR`. Dashboard: kartu *Edge Ahead*, penanda segitiga oranye di grafik jarak, *Edge Warnings* bertambah 1. | [TBD — jalankan di Wokwi] | [TBD] |
| T4 — Tongkat terlalu miring | Ubah rotasi MPU6050 sehingga sudut > 65° dan tahan ≥ 2 s. Sambil miring, ubah jarak HC-SR04 seperti T3. | `CANE_TILT_ADVISORY` + 2 bunyi 750 Hz setelah 2 s. Deteksi tepi **tetap berjalan** memakai jarak mentah (C2). Dashboard: *Cane Tilt* > 65° (oranye), garis tilt melewati batas *Too far*. | [TBD — jalankan di Wokwi] | [TBD] |
| T5 — Darurat, lalu ada tepi | Tahan tombol hijau **3 s**. Selama status darurat, ubah jarak HC-SR04 20 → 60 cm. | Setelah 3 s: `HELP_REQUEST`, state `EMERGENCY`, 4 bunyi 1600 Hz; status bantuan tetap aktif tanpa Wi-Fi. Peringatan tepi **tetap berbunyi** dan memotong pola darurat (C2). Dashboard: kartu *Emergency*, *Help Requests* = 1; status tetap darurat sampai `ACK HELP` di Serial (reset demo, bukan bukti bantuan datang). | [TBD — jalankan di Wokwi] | [TBD] |
| T6 — Tombol darurat ditekan singkat | Tekan tombol hijau ± 1 s, lepas. | Tidak ada `HELP_REQUEST`; state tidak berubah (butuh tahan 3 s, debounce 40 ms). Dashboard tidak berubah. | [TBD — jalankan di Wokwi] | [TBD] |
| T7 — Koneksi terputus | Saat dashboard menampilkan *Online*: hentikan simulasi Wokwi (atau putuskan Wi-Fi). Uji juga: broker tidak dapat dijangkau sementara sensor tetap diuji seperti T3. | Dashboard menjadi *Offline* (Last Will `online=0`), nilai terakhir tetap tampil dengan label. Alarm tepi di tongkat **tetap berbunyi** tanpa koneksi (P3). Setelah tersambung lagi, dashboard kembali *Online* dalam ± 1 heartbeat (2 s). Catat `loopMaxMs` dari Serial saat broker tidak terjangkau (bukti klaim non-blocking, C3). | [TBD — jalankan di Wokwi] | [TBD] |
| T8 — Pesan asing atau rusak di broker publik | Dari HiveMQ WebSocket Client, publish ke `sic8/fahhh/device/status`: (a) teks `hello`, (b) `{"device_id":"other"}`. | Dashboard tidak error dan tidak menampilkan data palsu; penghitung *Ignored … message(s)* di bawah daftar event bertambah 2. | [TBD — jalankan di Wokwi] | [TBD] |
| T9 — Kartu RFID tidak terdaftar | Pada state `SEEK_PLATFORM`, tap kartu RFID dengan UID yang tidak ada di daftar. | Serial `RFID_UNREGISTERED uid=…`; state tidak berubah; tidak ada event `CHECKPOINT`. | [TBD — jalankan di Wokwi] | [TBD] |

## Cara menjalankan (untuk sesi integrasi Rabu)

1. **Dashboard** (laptop Stanley): `source SIC/bin/activate`, lalu `cd dashboard && python dashboard.py`, buka http://127.0.0.1:8050. Pastikan *Connected to broker*.
2. **Wokwi**: buka proyek tim, jalankan. Serial Monitor harus menampilkan boot message dan koneksi MQTT.
3. Jalankan T1 → T9 berurutan. Untuk tiap kasus:
   - screenshot **Serial Monitor** dan **dashboard** pada saat hasil terlihat;
   - simpan sebagai `assets/screenshots/R4_test_NN_serial.png` dan `R4_test_NN_dashboard.png` (NN = nomor kasus);
   - isi *Hasil aktual* dengan apa yang benar-benar terlihat, dan *Status* = **Berhasil** / **Gagal** / **Sebagian** (jelaskan).
4. Setelah selesai, salin CSV log dashboard (`dashboard/data/messages_<waktu>.csv`) yang dipakai ke `tests/results/` sebagai bukti.
5. Jika ada kasus gagal: catat apa yang terjadi, jangan diubah menjadi "berhasil". Gagal yang dijelaskan dengan jujur tetap bernilai di laporan.

## Catatan untuk laporan

- T7 adalah bukti paling penting untuk P3 (edge computing): alarm tidak bergantung pada internet, MQTT hanya melapor.
- Batasan yang harus disebut (dari C2/C3): potensiometer = simulasi BLE, `SIM ARRIVE` = simulasi telemetri kereta, LED = pengganti motor getar, MQTT QoS 0 (event bisa hilang, status 2 s memulihkan tampilan), celah peron–kereta (P1) belum diukur.
