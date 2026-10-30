# Skenario pengujian

Owner: Stanley. Dipakai langsung untuk laporan bagian 10 (Skenario dan Hasil Pengujian) dan 11 (Bukti Visual), jadi ditulis dalam Bahasa Indonesia.

**Aturan:** kolom *Hasil aktual* dan *Status* hanya diisi dari percobaan nyata di Wokwi (dan dashboard). Belum dijalankan = `[TBD — jalankan di Wokwi]`. Tidak ada hasil yang dikarang (AGENTS.md §7).

**Dijalankan:** Jum 30 Okt 2026 oleh Stanley, firmware `main` (PR #12), C3 v4. Detail, log Serial dan CSV dashboard: `tests/results/2026-10-30_firmware-tests.md`. Screenshot: `assets/screenshots/R4_test_*.png`. Bunyi diperiksa dengan telinga (tidak tercatat di log).

Sumber perilaku yang diharapkan: firmware `firmware/sketch.ino` (PR #12, William), C2 (aturan logika) dan C3 v4 (MQTT, Stanley). Angka ambang dan pola bunyi diambil dari firmware.

## Ringkasan

| Kasus uji | Fitur | Jenis |
|---|---|---|
| T1 | P2 Pemandu menuju peron (checkpoint berurutan) | Normal |
| T2 | P1 Kereta datang, naik dengan tag pintu, tiba, turun, keluar | Normal |
| T3 | S1 Peringatan perubahan ketinggian tanah | Perubahan kondisi |
| T4 | S1 Tongkat terlalu miring (MPU6050) | Abnormal |
| T5 | S2 Tombol darurat + bahaya tepi saat darurat | Abnormal |
| T6 | S2 Tombol darurat ditekan singkat (< 3 s) | Abnormal |
| T7a | P3 Tongkat terputus: Last Will dan pemulihan dashboard | Abnormal |
| T7b | P3 Broker tidak terjangkau: alarm tetap lokal | Abnormal |
| T8 | Dashboard mengabaikan pesan rusak atau asing (bukan uji keamanan) | Abnormal |
| T9 | Kartu RFID tidak terdaftar | Abnormal |
| T10 | P2 Salah peron: tag peron yang salah ditolak | Abnormal |
| T11 | P1 Naik terlalu awal dan kereta salah | Abnormal |

Minimal yang wajib (guideline): 3 skenario, termasuk abnormal. Jika waktu sempit, prioritas: **T1, T2, T3, T5, T7b, T10**.

## Kartu RFID dan perintah Serial (rute bawaan)

Rute bawaan firmware: datar (`FLAT`) di stasiun asal dan tujuan, peron P1/P1, tujuan `DEMO_B`. Titik simpang tidak punya kartu, jadi dimasukkan lewat Serial (`SIM TAG …`). Setiap kartu juga bisa diganti dengan `SIM TAG <titik>` (sumber event menjadi `SERIAL_SIMULATION`).

| Titik | Arti | Kartu Wokwi (UID) |
|---|---|---|
| `A_MASUK` | Pintu masuk stasiun A | `01 02 03 04` |
| `A_SIMPANG` | Simpang di stasiun A | tidak ada, `SIM TAG A_SIMPANG` |
| `A_P1_WAIT` | Peron 1 stasiun A | `11 22 33 44` |
| `A_P2_WAIT` | Peron 2 stasiun A | `55 66 77 88` |
| `TRAIN_INSIDE` | Tag di dalam pintu kereta | `AA BB CC DD` |
| `B_P1_PERON` | Peron 1 stasiun tujuan B | kartu abu-abu, terbaca `04 11 22 33` (atau `04 11 22 33 44 55 66`) |
| `B_SIMPANG` | Simpang di stasiun B | tidak ada, `SIM TAG B_SIMPANG` |
| `B_LUAR` | Pintu keluar stasiun B | `C0 FF EE 99` |

Rute lift/ramp dan peron P2 dipilih dengan `SIM CONFIG <asal> <tujuan> <peron asal> <peron tujuan>` sebelum menekan KY-040; titik-titiknya hanya lewat `SIM TAG`.

**Penting saat menguji:** bunyi navigasi (checkpoint, siap naik, tag ditolak) tidak diputar selama ada peringatan tepi aktif. Jaga slider HC-SR04 tetap stabil kecuali di T3/T5.

## Tabel pengujian (format laporan bagian 10)

| Kasus uji | Input atau kondisi | Hasil yang diharapkan | Hasil aktual | Status |
|---|---|---|---|---|
| T1 — Pilih tujuan dan checkpoint menuju peron | Biarkan tujuan di `DEMO_B` (setiap putaran KY-040 berganti `DEMO_B`/`DEMO_C`). Tekan KY-040. Tap `01 02 03 04` (A_MASUK). Ketik `SIM TAG A_SIMPANG`. Tap `11 22 33 44` (A_P1_WAIT). | Serial: `ROUTE destination=DEMO_B … next=A_MASUK`, lalu `CHECKPOINT A_MASUK … next=A_SIMPANG`, `CHECKPOINT A_SIMPANG source=SERIAL_SIMULATION …`, `CHECKPOINT A_P1_WAIT …`, `WAIT_TRAIN at A_P1_WAIT; expected train=TRAIN01 side=P1 dest=DEMO_B`. State `SELECT_DEST → SEEK_PLATFORM → WAIT_TRAIN`. Buzzer/LED: 1 bunyi pendek tiap putaran (650 Hz), 1 bunyi saat rute dikonfirmasi (700 Hz), 1 bunyi tiap checkpoint (800 Hz). Dashboard: *Waiting for Train*, Destination *Station B*, Last Station *Station A*, Journey "Wait for the train" = *Now*; event *Checkpoint Tag Read* dari *RFID card* dan dari *simulated tag (Serial)*. | Sesuai: `ROUTE destination=DEMO_B`, `CHECKPOINT A_MASUK` (kartu Blue), `CHECKPOINT A_SIMPANG` (`SIM TAG`), lalu kartu Green → `WAIT_TRAIN at A_P1_WAIT`. Bunyi terdengar. Dashboard: *Waiting for Train*, Station B / Station A. Bukti: `R4_test_01a`, `R4_test_01b`; `tests/results/2026-10-30_firmware-tests.md` | **Berhasil** |
| T2 — Kereta datang, naik, tiba, turun, keluar | Lanjutan T1. Putar potensiometer sampai ADC > 2600. Ketik `SIM TRAIN TRAIN01 P1 B`, `SIM STOPPED`, `SIM DOOR OPEN P1`. Tap `AA BB CC DD` (TRAIN_INSIDE). Ketik `SIM ARRIVE B`, `SIM STOPPED`, `SIM DOOR OPEN P1`. Tap kartu abu-abu (B_P1_PERON). Ketik `SIM TAG B_SIMPANG`. Tap `C0 FF EE 99` (B_LUAR). | `SIM_TRAIN_NEAR` + 2 bunyi 900 Hz; `TRAIN_MATCH`, `TRAIN_STOPPED`, `TRAIN_DOOR_OPEN`, lalu `BOARDING_READY` + 3 bunyi 1000 Hz. Tag pintu: state `ON_TRAIN`, `BOARDING_CONFIRMED_BY_TAG`, 2 bunyi 850 Hz. `SIM ARRIVE B`: state `ARRIVING`, `SIM_DESTINATION_APPROACH`, 3 bunyi 1100 Hz. Kartu abu-abu: `DESTINATION_PLATFORM_CONFIRMED B_P1_PERON next=B_SIMPANG`, 2 bunyi 900 Hz. Kartu B_LUAR: state `COMPLETE`, 3 bunyi 950 Hz. Dashboard: *Train Door Nearby = Yes* sampai naik; event *Right Train*, *Train Stopped*, *Doors Open*, *Ready to Board*, *Boarded*, *Arriving at Destination* (sumber kereta tertulis *simulated train data (Serial)*); Last Station berubah ke *Station B*; semua langkah Journey *Done*. | Sesuai: `ARRIVING`, `DESTINATION_PLATFORM_CONFIRMED B_P1_PERON` (NFC Tag fisik), `CHECKPOINT B_SIMPANG`, Key Fob → `COMPLETE`. Dashboard: Last Station *Station B*, semua langkah Journey *Done*. Bukti: `R4_test_02a`–`02e` | **Berhasil** |
| T3 — Tepi peron / turunan | MPU6050 tegak (sudut ≤ 65°). Atur jarak HC-SR04 ke **20 cm**, tunggu stabil (± 3 s). Ubah ke **60 cm**. Setelah peringatan, kembalikan ke 20 cm. | Jarak > baseline + 15 cm dan > 25 cm selama 3 pembacaan (± 0,36 s) → `EDGE_WARNING`, 1 bunyi panjang 1200 Hz. Kembali normal ≥ 0,7 s → `EDGE_CLEAR`. Dashboard: kartu *Edge Ahead*, penanda segitiga oranye di grafik jarak, *Edge Warnings* bertambah 1. | Sesuai: `EDGE_WARNING` (sumber `HC_SR04_MPU6050`, 84,7 cm) dengan bunyi panjang, `EDGE_CLEAR` setelah kembali normal. Dashboard: *Edge Ahead*, penanda segitiga. Bukti: `R4_test_03a`, `R4_test_03b` | **Berhasil** |
| T4 — Tongkat terlalu miring | Ubah rotasi MPU6050 sehingga sudut > 65° dan tahan ≥ 2 s. Sambil miring, ubah jarak HC-SR04 seperti T3. | `CANE_TILT_ADVISORY` + 2 bunyi 750 Hz setelah 2 s. Deteksi tepi **tetap berjalan** memakai jarak mentah (C2); sumber `EDGE_WARNING` = `HC_SR04_RAW_FALLBACK`. Dashboard: *Cane Tilt* > 65° (oranye), garis tilt melewati batas *Too far*, event tepi *from distance sensor, raw reading*. | Sesuai: miring 73°, `CANE_TILT_ADVISORY` + 2 bunyi; tepi tetap terdeteksi dengan sumber `HC_SR04_RAW_FALLBACK` (86,7 cm). Bukti: `R4_test_04` | **Berhasil** |
| T5 — Darurat, lalu ada tepi | Tahan tombol hijau **3 s**. Selama status darurat, ubah jarak HC-SR04 20 → 60 cm. | Setelah 3 s: `HELP_REQUEST`, state `EMERGENCY`, 4 bunyi 1600 Hz; status bantuan tetap aktif tanpa Wi-Fi. Peringatan tepi **tetap berbunyi** dan memotong pola darurat (C2). Dashboard: kartu *Emergency*, *Help Requests* = 1; status tetap darurat sampai `ACK HELP` di Serial (reset demo ke `SELECT_DEST`, bukan bukti bantuan datang). | Sesuai: `HELP_REQUEST`, `EMERGENCY`, 4 bunyi; `EDGE_WARNING` tetap terdeteksi selama darurat dan bunyinya memotong pola bantuan; `ACK HELP` → `SELECT_DEST` (reset demo). Bukti: `R4_test_05a`, `R4_test_05b` | **Berhasil** |
| T6 — Tombol darurat ditekan singkat | Tekan tombol hijau ± 1 s, lepas. | Tidak ada `HELP_REQUEST`; state tidak berubah (butuh tahan 3 s, debounce 40 ms). Dashboard tidak berubah. | Sesuai: tidak ada `HELP_REQUEST` atau perubahan state setelah tekan singkat (log Serial) | **Berhasil** |
| T7a — Tongkat terputus, lalu pulih | Saat dashboard menampilkan *Online*: tekan **Stop** di Wokwi dan catat waktunya. Tunggu dashboard berubah. Lalu tekan **Play** lagi. | Dalam ± 6 s tanpa status, dashboard tidak lagi *Online* (*No data* atau *Offline*). Broker mengirim Last Will `online=0` → dashboard *Offline*; nilai terakhir tetap tampil dengan label. Catat berapa detik sampai *Offline* (bisa segera bila koneksi ditutup, atau sampai ± 1,5 × keep-alive = ± 45 s dengan keep-alive 30 s). Setelah Play: Wi-Fi bergabung dan MQTT tersambung ulang (TLS ± 6–7 s pada uji konektivitas, belum termasuk Wi-Fi); dashboard kembali *Online* dalam **satu heartbeat (2 s) setelah MQTT tersambung**. Catat waktu total dari Play sampai *Online*. | Sesuai: status terakhir 11:19:10, Last Will `online=0` 11:19:55 (45 s = 1,5 × keep-alive 30 s); setelah Play, status pertama pada uptime 8 s. Juga terjadi putus diam-diam (half-open): ± 20 status hilang, Last Will tetap datang 45 s kemudian. Dashboard: *No Data* (abu-abu) beberapa detik setelah simulasi berhenti, lalu *Offline* setelah Last Will. Bukti: `R4_test_07a_1`, `R4_test_07a_2`, `R4_test_07b_1` | **Berhasil** |
| T7b — Broker tidak terjangkau, alarm tetap lokal | Di salinan proyek Wokwi (jangan di-commit), ganti sementara `MQTT_HOST` di `sketch.ino` ke `10.255.255.1` (alamat yang tidak menjawab, jadi setiap percobaan connect menunggu sampai timeout: kasus terberat untuk klaim non-blocking). Jalankan Wokwi (Wi-Fi tetap tersambung) dan ulangi langkah T3 (20 → 60 cm). | Serial tidak menampilkan `MQTT connected`, tetapi `EDGE_WARNING` dan bunyi panjang **tetap muncul tepat waktu** seperti T3 (P3). Dashboard tidak menerima data (wajar). Catat `loopMaxMs` dari status Serial 5 s selama percobaan tersambung: ini bukti klaim non-blocking di firmware lengkap (C3). | Sesuai: `MQTT_HOST=10.255.255.1`, MQTT *offline* selama 57 s (drop 2 → 29, tidak menumpuk); `EDGE_WARNING` + bunyi tetap langsung muncul. `loopMaxMs` 13,6 ms (median) vs 13,5 ms saat broker tersambung, kondisi sama. Bukti: `R4_test_07b_1`, `R4_test_07b_2` | **Berhasil** |
| T8 — Dashboard mengabaikan pesan rusak atau asing | Dari HiveMQ WebSocket Client, publish ke `sic8/fahhh/device/status`: (a) teks `hello`, (b) `{"device_id":"other"}`. | Dashboard tidak error dan tidak menampilkan data dari pesan tersebut; penghitung *Ignored … message(s)* di bawah daftar event bertambah 2. **Bukan uji keamanan:** broker publik tidak memakai login, jadi pesan valid dengan `device_id: unit-01` dari pihak lain tetap akan diterima. Batasan ini dicatat di laporan 8.2 dan 14. | Sesuai: dashboard tetap berjalan dan tidak menampilkan data dari pesan rusak/asing; penghitung *Ignored 4 message(s)*: kedua pesan uji masing-masing dipublish dua kali, jadi 4 dari 4 pesan rusak diabaikan. Bukti: `R4_test_08a`, `R4_test_08b` | **Berhasil** |
| T9 — Kartu RFID tidak terdaftar | Pada state `SEEK_PLATFORM`, tap kartu RFID yang UID-nya tidak ada di tabel kartu. Jika semua kartu Wokwi sudah terdaftar, ketik `SIM TAG XYZ`. | Kartu: Serial `RFID_UNREGISTERED uid=…`, event `CHECKPOINT_REJECTED` (sumber `RFID_UNREGISTERED`). `SIM TAG XYZ`: Serial `CHECKPOINT_REJECTED got=XYZ …` (sumber `SERIAL_SIMULATION`). Keduanya: 5 bunyi pendek 400 Hz, state tidak berubah, tidak ada `CHECKPOINT`. Dashboard: *Wrong or Unknown Tag* (Warning). | Sesuai (lewat `SIM TAG XYZ`, karena keenam kartu Wokwi sudah terdaftar): `CHECKPOINT_REJECTED got=XYZ`, 5 bunyi pendek, state tetap. Dashboard: *Wrong or Unknown Tag*. Bukti: `R4_test_09` | **Berhasil** |
| T10 — Salah peron | Seperti T1 sampai `SIM TAG A_SIMPANG` (rute ke P1). Tap `55 66 77 88` (A_P2_WAIT). Lalu tap `11 22 33 44` (A_P1_WAIT). | Tag P2: Serial `CHECKPOINT_REJECTED got=A_P2_WAIT expected=A_P1_WAIT state=SEEK_PLATFORM …`, 5 bunyi pendek 400 Hz, state tetap `SEEK_PLATFORM`. Tag P1: diterima, state `WAIT_TRAIN`. Dashboard: *Wrong or Unknown Tag* (Warning, *from RFID card*) dan penanda silang oranye di grafik jarak, lalu *Waiting for Train*. | Sesuai: `CHECKPOINT_REJECTED got=A_P2_WAIT expected=A_P1_WAIT`, 5 bunyi pendek, state tetap `SEEK_PLATFORM`; kartu P1 kemudian diterima. Dashboard: *Wrong or Unknown Tag* + tanda silang oranye. Bukti: `R4_test_10` | **Berhasil** |
| T11 — Naik terlalu awal dan kereta salah | Lanjutan T1 (`WAIT_TRAIN`, potensiometer > 2600). (a) Tap `AA BB CC DD` sebelum perintah kereta. (b) Ketik `SIM TRAIN TRAIN01 P2 B` (sisi salah). (c) Ketik `SIM TRAIN TRAIN01 P1 B`, `SIM STOPPED`, `SIM DOOR OPEN P1`, lalu tap `AA BB CC DD`. | (a) `CHECKPOINT_REJECTED got=TRAIN_INSIDE …`, 5 bunyi pendek 400 Hz, state tetap `WAIT_TRAIN`. (b) Serial `TRAIN_REJECTED got=TRAIN01/P2/B expected=TRAIN01/P1/B`, event `TRAIN_REJECTED`, tidak ada `BOARDING_READY`. Firmware tidak memberi bunyi khusus untuk kereta salah; pengguna hanya tidak mendapat bunyi *siap naik* (catat sebagai batasan). (c) `BOARDING_READY` lalu `ON_TRAIN`. Dashboard: *Wrong or Unknown Tag*, *Wrong Train* (Warning), lalu *Ready to Board* dan *Boarded*. | Sesuai: (a) tag pintu ditolak sebelum siap; (b) `TRAIN_REJECTED got=TRAIN01/P2/B`, tanpa bunyi dan tanpa `BOARDING_READY` (batasan dicatat); (c) `BOARDING_READY` (3 bunyi) lalu `ON_TRAIN`. Bukti: `R4_test_11a`–`11f` | **Berhasil** |

## Cara menjalankan

1. **Dashboard** (laptop Stanley): `source SIC/bin/activate`, lalu `cd dashboard && python dashboard.py`, buka http://127.0.0.1:8050. Pastikan *Connected to broker*.
2. **Wokwi**: buka proyek tim (`firmware/wokwi-project.txt`, https://wokwi.com/projects/478926704931540993) dan jalankan. Serial Monitor harus menampilkan `MQTT connected; QoS 0 publishes enabled`. Letakkan Wokwi dan dashboard di **dua jendela berdampingan**, bukan dua tab (tab di belakang memperlambat simulasi).
3. Jalankan T1 → T11 berurutan. Untuk tiap kasus:
   - screenshot **Serial Monitor** dan **dashboard** pada saat hasil terlihat;
   - simpan sebagai `assets/screenshots/R4_test_NN<huruf>_<deskripsi>.png` (satu screenshot layar penuh berisi Wokwi + Serial dan dashboard);
   - isi *Hasil aktual* dengan apa yang benar-benar terlihat, dan *Status* = **Berhasil** / **Gagal** / **Sebagian** (jelaskan).
4. Setelah selesai, salin CSV log dashboard (`dashboard/data/messages_<waktu>.csv`) yang dipakai ke `tests/results/` sebagai bukti.
5. Jika ada kasus gagal: catat apa yang terjadi, jangan diubah menjadi "berhasil". Gagal yang dijelaskan dengan jujur tetap bernilai di laporan.

## Catatan untuk laporan

- T7b adalah bukti paling penting untuk P3 (edge computing): alarm tidak bergantung pada broker, MQTT hanya melapor. T7a menguji sisi dashboard: Last Will dan pemulihan.
- T10 dan T11 adalah bukti fitur arah peron dan naik kereta: tag yang salah ditolak dengan bunyi sendiri, dan naik hanya diterima setelah semua pemeriksaan lolos.
- T8 hanya menguji ketahanan dashboard terhadap pesan rusak atau asing. Keamanan (autentikasi) tidak ada di broker publik; itu pekerjaan lanjutan (klaster HiveMQ Cloud privat dengan login).
- Batasan yang harus disebut (dari C2/C3/firmware): potensiometer = simulasi BLE; data kereta (identitas, berhenti, pintu) dan `SIM ARRIVE` = simulasi lewat Serial; titik simpang hanya lewat `SIM TAG`; LED = pengganti motor getar; stasiun `DEMO_A/B/C` fiktif; MQTT QoS 0 (event bisa hilang, status 2 s memulihkan tampilan); celah peron–kereta (P1) belum diukur; tidak ada isyarat kiri/kanan di simpang (urutan checkpoint saja).
