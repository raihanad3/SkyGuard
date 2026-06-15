# Panduan Integrasi Tailscale (Mode Dinamis)

Project Vessel berjalan di atas arsitektur terdistribusi (4 Komputer) dan perannya **bisa ditukar-tukar** antar laptop. Untuk mempermudah konfigurasi tanpa perlu melakukan *export* manual setiap kali bertukar peran, kita telah menerapkan sistem **Central Node IP**.

---

## 1. Instalasi Tailscale

Langkah pertama adalah menginstal Tailscale di semua perangkat (Komputer 1, 2, 3, dan 4).
1. Daftar akun di [Tailscale](https://tailscale.com/).
2. Unduh dan instal aplikasi Tailscale di masing-masing komputer (Windows, Linux, atau macOS).
3. Login menggunakan akun yang sama di keempat komputer.
4. Catat **IP Tailscale** masing-masing laptop (contoh: `100.115.92.2`).

---

## 2. Cara Bekerja & Bertukar Peran (Sangat Mudah!)

Karena peran laptop bisa berubah (hari ini kamu Komputer 4, besok temanmu Komputer 4), ikuti langkah ini setiap kali ingin mulai mengerjakan project:

### Langkah 1: Tentukan Siapa "Komputer 4" (Central Node)
Komputer 4 adalah komputer yang menjalankan Backend API, Postgres, dan Kafka. 
Tanya kepada teman yang bertugas menjadi Komputer 4: **"Berapa IP Tailscale-mu?"** (Misalnya IP-nya `100.100.10.4`).

### Langkah 2: Edit file `.env`
**SEMUA ORANG** (baik yang memegang Komputer 1, 2, 3, maupun 4) cukup membuka file `.env` yang berada di folder paling luar (root folder) project `Vessel`.
Ubah isinya menjadi IP teman yang menjadi Komputer 4:

```env
CENTRAL_NODE_IP=100.100.10.4
```
*(Jika kalian sedang mengerjakan sendiri secara lokal di 1 laptop, cukup ubah kembali menjadi `CENTRAL_NODE_IP=localhost`)*

### Langkah 3: Jalankan Script
Setelah file `.env` disimpan, setiap orang cukup menjalankan `start_all.py` sesuai perannya masing-masing. Script secara **otomatis** akan menyambungkan Kafka, Database, dan UI Dashboard ke IP tersebut!

- **Teman yang bertugas sebagai Komputer 1**:
  ```bash
  python start_all.py -c 1
  ```
- **Kamu yang bertugas sebagai Komputer 2**:
  ```bash
  python start_all.py -c 2
  ```
- **Teman yang bertugas sebagai Komputer 3**:
  ```bash
  python start_all.py -c 3
  ```
- **Teman yang bertugas sebagai Komputer 4 (Central Node)**:
  ```bash
  python start_all.py -c 4
  ```

> [!TIP]
> Jika teman yang memegang Komputer 4 juga ingin menjalankan Dashboard Frontend, ia bisa menjalankan: `python start_all.py -c 5` (atau menjalankan semuanya tanpa `-c`). Kalian yang di laptop lain bisa langsung melihat Dashboard dengan membuka browser ke `http://100.100.10.4:5173`!

---

## Selesai! 🎉
Dengan sistem ini, tidak ada lagi proses manual. Kalian bebas bertukar peran kapan saja hanya dengan mengubah satu baris teks di file `.env`!
