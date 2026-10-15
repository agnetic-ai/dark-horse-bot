# Dark Horse Genesis Automation Bot 🐎

Automasi bot multi-account untuk platform **Dark Horse Genesis** ([genesis.dhorse.fun](https://genesis.dhorse.fun/mine)) pada ekosistem Bitcoin RGB. Bot ini dirancang untuk menjalankan siklus pemeliharaan akun harian, mempertahankan streak *daily check-in*, serta mengklaim reward penambangan (*mining claim*) secara otomatis menggunakan isolasi sirkuit jaringan Tor SOCKS5.

---

## 🌟 Fitur Utama

- **Multi-Account Management:** Kelola puluhan akun sekaligus secara terpusat melalui file database `accounts.json`.
- **Tor Circuit Stream Isolation:** Setiap akun otomatis mendapatkan alamat IP publik (*Exit IP*) yang berbeda via SOCKS5 proxy `socks5://<user>:<pass>@127.0.0.1:9050` tanpa perlu me-restart service Tor.
- **Automated Daily Check-In:** Memeriksa status streak harian (`POST /api/checkin`) dan melakukan check-in jika belum diklaim hari ini.
- **Smart Mining Claim Engine:** Memantau akumulasi poin mining (`POST /api/mining/claim`) dan otomatis mengeksekusi klaim begitu saldo mencapai batas minimal (default: ≥ 1.0 poin / 1 Horseshoe).
- **Session Auto-Validation:** Langsung memvalidasi masa aktif sesi cookie ke endpoint `/api/me` dan menandai status akun jika cookie kedaluwarsa.
- **Interactive CLI Manager:** Mendukung perintah command line sederhana untuk melihat tabel status akun (`status`), mengeksekusi siklus klaim (`run`), dan mendaftarkan akun baru (`add`).

---

## 📁 Struktur Direktori

```text
dark-horse-bot/
├── darkhorse_bot.py       # Core runner & CLI manager
├── accounts.example.json  # Template schema konfigurasi akun (dummy data)
├── .env.example           # Template environment variables
├── requirements.txt       # Daftar pustaka dependensi Python
├── .gitignore             # Proteksi kredensial pribadi dari commit Git
└── README.md              # Dokumentasi lengkap proyek
```

---

## 🛠️ Prasyarat Sistem

1. **Python:** Python 3.10 atau versi lebih baru.
2. **Tor Daemon:** Service Tor lokal aktif pada port SOCKS5 `127.0.0.1:9050`.
   ```bash
   sudo apt update && sudo apt install -y tor
   sudo systemctl enable --now tor
   ```

---

## 🚀 Instalasi Cepat

1. **Clone Repository:**
   ```bash
   git clone https://github.com/agnetic-ai/dark-horse-bot.git
   cd dark-horse-bot
   ```

2. **Install Dependensi:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Inisialisasi File Data Akun:**
   Salin template contoh akun ke `accounts.json`:
   ```bash
   cp accounts.example.json accounts.json
   ```

---

## 🔑 Cara Mendapatkan Cookie Sesi (`genesis_session`)

Platform Genesis menggunakan autentikasi OAuth Twitter/X yang menetapkan cookie sesi `genesis_session`:

1. Buka browser dan login ke akun X (Twitter) Anda.
2. Kunjungi [https://genesis.dhorse.fun/mine](https://genesis.dhorse.fun/mine) dan hubungkan akun X Anda.
3. Buka **Developer Tools** (tekan `F12` atau `Ctrl + Shift + I`).
4. Masuk ke tab **Application** (atau **Storage** di Firefox) -> buka menu **Cookies** -> pilih `https://genesis.dhorse.fun`.
5. Cari baris bernama `genesis_session`, lalu salin seluruh nilai (*Value*) cookie tersebut.

---

## 💻 Panduan Penggunaan CLI

### 1. Menambahkan Akun Baru
Gunakan perintah `add` untuk menambahkan akun tanpa perlu mengedit file JSON secara manual:
```bash
python3 darkhorse_bot.py add --handle <HANDLE_X> --cookie <NILAI_COOKIE>
```
*Contoh:*
```bash
python3 darkhorse_bot.py add --handle airdrop_user --cookie a1b2c3d4-e5f6-7890-abcd-ef0123456789...
```

### 2. Memeriksa Status Semua Akun
Menampilkan ringkasan status akun, level tier, total poin, reward claimable, status check-in, dan IP Tor:
```bash
python3 darkhorse_bot.py status
```
*Contoh Output:*
```text
Total Dark Horse Accounts: 2
===============================================================================================
No  | Handle           | Tier     | Points   | Claimable    | Checkin    | Tor Exit IP
-----------------------------------------------------------------------------------------------
1   | @bholam_         | knight   | 1000     | 0.42 (+25/d) | Day 2 ✓    | 185.220.101.109
2   | @airdropbh03     | knight   | 1000     | 0.00 (+25/d) | Day 1 ✓    | 192.42.116.14
===============================================================================================
```

### 3. Menjalankan Siklus Otomasi (Check-in & Claim Mining)
```bash
python3 darkhorse_bot.py run
```

---

## ⏰ Konfigurasi Penjadwalan Otomatis (Cronjob)

Untuk menjalankan automasi di background secara terjadwal:
- **Claim Mining:** Dijalankan setiap 2 jam sekali.
- **Daily Check-In:** Otomatis tereksekusi pada putaran pertama tiap hari baru.

Buka editor crontab sistem:
```bash
crontab -e
```

Tambahkan baris berikut di bagian bawah:
```cron
# Dark Horse Genesis: Claim mining setiap 2 jam & daily check-in
0 */2 * * * cd /opt/dark-horse && /usr/bin/python3 darkhorse_bot.py run >> /opt/dark-horse/bot.log 2>&1
```

---

## 🔒 Keamanan & Kebijakan Data Pribadi

- File `accounts.json` memuat cookie sesi akun pribadi dan **wajib** dijaga kerahasiaannya. File ini telah didaftarkan pada `.gitignore` dan tidak akan pernah ter-push ke repository publik.
- Selalu gunakan file `.env.example` dan `accounts.example.json` sebagai acuan format template.

---

## 📄 Lisensi

Didistribusikan di bawah lisensi MIT. Silakan gunakan dan kembangkan secara bebas untuk kebutuhan automasi komunitas.
