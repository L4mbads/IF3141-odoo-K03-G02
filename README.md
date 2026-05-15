# Sistem Informasi Operasional Terintegrasi Kedai Janari

**Perusahaan:** Kedai Janari  
**Kelompok:** G02  
**Kelas:** K03  

### Anggota Kelompok:
- 13523127 - Boye Mangaratua Ginting
- 13523128 - Andi Farhan Hidayat
- 13523136 - Danendra Shafi Athallah
- 13523153 - Muhammad Farrel Wibowo
- 13523162 - Fachriza Ahmad Setiyono

---

## Deskripsi Sistem

Sistem Informasi Operasional Terintegrasi Kedai Janari adalah sebuah solusi perangkat lunak berbasis Enterprise Resource Planning (ERP) menggunakan framework Odoo. Sistem ini dirancang secara spesifik untuk digitalisasi dan sentralisasi seluruh proses bisnis utama di Kedai Janari. Fungsionalitas utamanya mencakup manajemen *Point of Sale* (POS) yang memfasilitasi pencatatan pesanan dan pembayaran, serta *Kitchen Display System* (KDS) terintegrasi yang memungkinkan staf dapur dan *packer* untuk memantau status pesanan secara *real-time* melalui tampilan papan *Kanban*.

Lebih dari sekadar pencatatan transaksi, sistem ini juga dibekali dengan fitur otomatisasi manajemen *inventory* dan *Bill of Materials* (BOM). Ketika transaksi diselesaikan di POS, sistem secara cerdas akan langsung memotong ketersediaan bahan baku di gudang berdasarkan resep (BOM) menu terkait, lengkap dengan konversi satuannya. Jika terdapat bahan baku yang menyentuh batas minimum (*reorder point*), sistem akan secara otomatis memberikan peringatan dini (*alert*) di antarmuka sistem serta mengirim pesan peringatan darurat ke saluran komunikasi internal, memastikan kelancaran operasional kedai tidak terhambat oleh kekosongan stok.

---

## Cara Menjalankan Sistem

Untuk menjalankan sistem Odoo beserta basis datanya secara lokal menggunakan Docker, ikuti panduan berikut:

1. **Persiapan Lingkungan**  
   Pastikan perangkat Anda telah terinstal Docker dan Docker Compose. *Clone* atau unduh *repository* ini ke komputer Anda.
   
2. **Menjalankan Container**  
   Buka terminal (*command prompt* / *PowerShell*), arahkan direktori aktif ke dalam *root* dari *repository* ini, kemudian jalankan perintah:
   ```bash
   docker compose up -d
   ```
   *Expected Result:* Terminal akan melakukan proses *pulling images* (jika belum ada), membuat *network*, lalu memunculkan tulisan `Started` atau `Running` pada *container* basis data (PostgreSQL) dan *web* (Odoo).

3. **Mengakses Aplikasi**  
   Buka *web browser* Anda, lalu kunjungi alamat:
   [http://localhost:8069](http://localhost:8069)
   *Expected Result:* Anda akan diarahkan langsung ke halaman *login* utama dari sistem Odoo Kedai Janari.

**Panduan Fitur & Screenshot Sistem Web:**  
Untuk panduan detail tentang cara menggunakan fitur-fitur di dalam aplikasi (POS, KDS, Laporan, dsb) beserta *screenshot expected result* di dalam sistem webnya, silakan merujuk pada dokumen referensi di bawah ini:  
[IF3141 - Milestone 5 - K03 - G02.pdf](./IF3141%20-%20Milestone%205%20-%20K03%20-%20G02.pdf)

---

## Kredensial Pengguna

Sistem ini mendukung pembagian *role* yang memiliki batasan akses berbeda. Silakan gunakan kredensial bawaan berikut untuk mencoba fitur-fitur yang ada:

| Role | Nama User | Login | Password | Akses Utama |
|---|---|---|---|---|
| **Kasir** | Andi Kasir | `kasir` | `kasir123` | Membuat Pesanan (POS) dan memvalidasi Transaksi. |
| **Packer** | Budi Packer | `packer` | `packer123` | KDS (Dapat mengubah status item ke *Processed* dan *Done*). |
| **Dapur** | Doni Dapur | `dapur` | `dapur123` | KDS (*Read-only*, hanya dapat memantau antrean pesanan). |
| **Kepala Staf** | Sari Kepala Staf | `kepala` | `kepala123` | Manajemen Bahan Baku, Menu, Resep (BOM), dan Restock. |
| **Pemilik** | Bapak Pemilik | `pemilik` | `pemilik123` | Mengakses modul Laporan/Dashboard & Manajemen User. |

---

## Kesimpulan dan Saran

**Kesimpulan:**  
Sistem Informasi Operasional Terintegrasi Kedai Janari sukses menjembatani kesenjangan komunikasi antara area depan (kasir) dan belakang (dapur/gudang). Dengan adanya integrasi POS, KDS, dan manajemen stok berbasis BOM, proses bisnis menjadi lebih efisien, terukur, dan transparan. Peringatan otomatis batas stok terbukti sangat mempermudah pengambilan keputusan inventaris dengan cepat.

**Saran:**  
Untuk pengembangan di masa depan, sistem akan lebih kuat jika diintegrasikan langsung dengan *Payment Gateway* lokal (seperti integrasi API QRIS/E-Wallet otomatis) guna menghindari *human error* saat verifikasi pembayaran kasir. Selain itu, penambahan sistem modul loyalitas (*Loyalty/Rewards Program*) dapat mengoptimalkan retensi pelanggan Kedai Janari.