# SIA Engine — Safety Intelligence Advisory
**Technical Assessment: AI Engineer**

---

## Latar Belakang

Perusahaan memiliki dua sistem pelaporan keselamatan yang terpisah:

- **BEATS** — laporan dari Safety Observer yang berpatroli. Sudah memiliki kolom `kekerapan`, `konsekuensi`, dan `nilai_resiko` yang diisi langsung oleh Safety Observer saat membuat laporan.
- **AM Care** — laporan langsung dari crew kapal (Nahkoda, Engineer, dll). Tidak ada kolom risk score — crew hanya mencatat kejadian apa yang mereka lihat tanpa menilai tingkat bahayanya.

SIA Engine menggabungkan kedua dataset, menghitung risk score otomatis, dan memberikan rekomendasi mitigasi berbasis SOP internal.

---

## Struktur Folder

```
sia-engine/
├── app.py                          ← Streamlit UI (jalankan ini)
├── requirements.txt
├── data/
│   ├── beats_silver_sample_data.xlsx
│   └── amcare_silver_sample_data.xlsx
├── src/
│   ├── ingest.py                   ← Step 1: harmonisasi schema
│   ├── risk_engine.py              ← Step 2: hitung risk score
│   └── rag_engine.py               ← Step 3: RAG advisory berbasis SOP
└── mock_sop/
    └── maritime_safety_sop.md      ← Dokumen SOP referensi (buatan)
```

---

## Cara Menjalankan

### Menggunakan uv (direkomendasikan)

```bash
# 1. Cek uv sudah terinstall
uv --version

# Jika belum:
pip install uv

# 2. Buat virtual environment
uv venv

# 3. Aktifkan venv
# Windows:
.venv\Scripts\activate
# Mac / Linux:
source .venv/bin/activate

# Setelah aktif, prompt berubah jadi:
# (.venv) PS D:\Project\sia-engine>

# 4. Install dependencies
uv pip install -r requirements.txt

# 5. Jalankan
streamlit run app.py
```

### Menggunakan pip biasa

```bash
python -m venv .venv
.venv\Scripts\activate      # Windows
source .venv/bin/activate   # Mac / Linux
pip install -r requirements.txt
streamlit run app.py
```

---

## Alur Sistem

```
[BEATS xlsx]        [AM Care xlsx]
     │                    │
     └──────────┬──────────┘
                ▼
         src/ingest.py
         Harmonisasi → Canonical Safety Event (CSE)
                ▼
         src/risk_engine.py
         Hitung risk_score 0–100 → CRITICAL / HIGH / MEDIUM / LOW
                ▼
       ┌────────┴────────┐
       ▼                 ▼
 mock_sop/          src/rag_engine.py
 Dokumen SOP   →    Advisory berbasis SOP
                         ▼
                    app.py (Streamlit UI)
```

---

## Step 1 — Harmonisasi Schema (`ingest.py`)

### Perbedaan mendasar kedua dataset

BEATS dan AM Care mencatat kejadian yang sama (hazard di kapal/area operasi), tapi dengan format dan kelengkapan data yang berbeda. Tantangan utamanya:

| Dimensi | BEATS | AM Care |
|---------|-------|---------|
| Siapa yang lapor | Safety Observer (patroli) | Crew kapal langsung |
| Risk score | Ada — `konsekuensi`, `kekerapan`, `nilai_resiko` | Tidak ada sama sekali |
| Format status | `CLOSED`, `PROGRESS`, `BUKAN TEMUAN`, `RESUBMITTED` | `SUBMITTED`, `CONFIRMED_YES_BY_PELAPOR`, dll |
| Format lokasi | `site` + `lokasi` (nama kapal/unit) | `lokasi` + `sublokasi` (area di dalam kapal) |

### Kolom yang identik di kedua sistem (langsung digabung)

Kolom-kolom berikut nama dan nilainya identik — tidak perlu transformasi apapun:

| Kolom | Nilai contoh | Keterangan |
|-------|-------------|------------|
| `hazard_l1` | "Tools, equipments, machineries..." | Taksonomi bahaya level 1 |
| `hazard_l2` | "Equipment used beyond operational limits" | Taksonomi bahaya level 2 — lebih spesifik |
| `hazard_category` | "Unsafe acts" / "Unsafe conditions" | Kategori bahaya umum |
| `golden_rules_violation` | "Melanggar Golden Rules" / "Tidak Melanggar..." | Pelanggaran aturan fundamental |
| `rca_l1` | "Equipment, Design, and Engineering" | Root cause level 1 |
| `rca_l2` | "Faulty Equipment or Tools..." | Root cause level 2 — lebih detail |
| `akar_permasalahan` | Teks bebas penyebab | Penjelasan naratif akar masalah |
| `status_hazard_l1` | "OPEN" / "CLOSED" | Status penanganan (sudah seragam) |
| `status_hazard_l2` | "Open Overdue" / "Closed on Time" | Detail status + info overdue |

> **Kenapa pakai `status_hazard_l1` bukan kolom `status`?**
> Kolom `status` namanya sama di kedua sistem tapi nilainya berbeda total — BEATS menggunakan CLOSED/PROGRESS/BUKAN TEMUAN/RESUBMITTED sedangkan AM Care menggunakan SUBMITTED/CONFIRMED_YES_BY_PELAPOR/dll. Tidak ada satu pun nilai yang sama. Sebaliknya, `status_hazard_l1` sudah berisi OPEN/CLOSED yang identik di kedua sistem sehingga bisa langsung digabung tanpa normalisasi.

### Kolom yang berbeda (perlu pemetaan)

| Field CSE | Dari BEATS | Dari AM Care |
|-----------|-----------|-------------|
| `event_id` | `task_id` (integer) | `kode` (string HZD...) |
| `description` | `deskripsi` | `deskripsi_temuan` |
| `location` | `site` + `lokasi` → "MARINE \| Towing Tug" | `lokasi` + `sublokasi` → "Engine Room \| Auxiliary Engine" |
| `fleet_area` | `fleet_type` | `category` |
| `corrective_action` | `tindakan` | `tindakan_perbaikan` |

### Kolom yang tidak ada di AM Care (diestimasi)

AM Care tidak meminta crew mengisi tingkat bahaya — crew hanya melaporkan kejadian. Tiga kolom risk score diestimasi dari kolom lain yang tersedia:

#### Estimasi `konsekuensi` dari `hazard_category`

Dasar: pola dari data BEATS menunjukkan hubungan konsisten antara `hazard_category` dan `konsekuensi`:

| hazard_category | Pola di BEATS | Estimasi untuk AM Care | Alasan |
|-----------------|--------------|----------------------|--------|
| Unsafe acts | 2/2 record = Sedang | **Sedang** | Tindakan manusia yang salah — bisa diperbaiki dengan pelatihan, dampak tidak selalu fatal |
| Unsafe conditions | 11x Major, 4x Sedang | **Sedang** (konservatif) | Kondisi fisik berbahaya. Mayoritas Major di BEATS, tapi saya pakai Sedang sebagai nilai konservatif agar tidak overestimate |

#### Estimasi `kekerapan` dari `hazard_l2`

Dipilih `hazard_l2` (bukan `hazard_l1`) karena lebih spesifik: `hazard_l1` hanya 6 nilai unik sedangkan `hazard_l2` ada 10 nilai unik sehingga bisa membedakan kondisi lebih baik.

| hazard_l2 di AM Care | Estimasi kekerapan | Dasar |
|---------------------|-------------------|-------|
| Equipment used beyond operational limits | **Langka** | Diverifikasi dari BEATS: 1 record = Langka |
| Hazardous chemical spills | **Langka** | Diverifikasi dari BEATS: 1 record = Langka |
| Overhead hazards | **Langka** | Diverifikasi dari BEATS: 1 record = Langka |
| Poor housekeeping | **Langka** | Diverifikasi dari BEATS: 5 record, semua = Langka |
| Operating faulty or damaged equipment | **Langka** | Tidak ada di BEATS — mirip "Equipment used beyond" → Langka |
| Malfunctioning or damaged tools | **Langka** | Tidak ada di BEATS — mirip "Equipment used beyond" → Langka |
| Missing tools, equipment | **Langka** | Tidak ada di BEATS — kondisi kekurangan stok → Langka |
| Standing in dangerous zone | **Langka** | Tidak ada di BEATS — situasional, tidak rutin → Langka |
| Inadequate ventilation | **Langka** | Tidak ada di BEATS — kondisi permanen → Langka |
| Unstable, dangerous ground | **Langka** | Tidak ada di BEATS — kondisi situasional → Langka |

> **Catatan keterbatasan:** Semua `hazard_l2` AM Care diestimasi Langka karena itu yang konsisten di data BEATS. Di production yang ideal, AM Care seharusnya menambah kolom `kekerapan` agar tidak perlu estimasi.

---

## Step 2 — Risk Ranking Engine (`risk_engine.py`)

### Dasar teori: Likelihood × Severity Risk Matrix

Risk engine menggunakan **Risk Matrix standar industri HSE (Health, Safety, Environment)** — standar yang sudah diimplementasikan di BEATS (kolom `kekerapan` = Likelihood, `konsekuensi` = Severity) dan dikenal di industri maritim global melalui ISM Code dan SOLAS.

```
risk_score = s_konsekuensi + s_kekerapan + s_golden + s_status + s_keyword

  s_konsekuensi = (nilai_konsekuensi / 5) × 35   → max 35 poin
  s_kekerapan   = (nilai_kekerapan / 5) × 25      → max 25 poin
  s_golden      = 20 jika melanggar, 0 jika tidak → max 20 poin
  s_status      = berdasarkan status + overdue     → max 20 poin
  s_keyword     = dari kata bahaya dalam deskripsi → max 10 poin
  ────────────────────────────────────────────────────────────────
  TOTAL                                            → max 110 poin (normalnya max 100)
```

### Bobot per faktor dan alasannya

| Faktor | Bobot | Alasan |
|--------|-------|--------|
| Konsekuensi/Severity | 35% | Di safety maritim, **dampak** lebih diutamakan dari frekuensi — satu kejadian fatal lebih kritis dari banyak kejadian minor meski jarang terjadi. Mengacu ISM Code dan SOLAS |
| Kekerapan/Likelihood | 25% | Frekuensi penting untuk prioritas pencegahan, tapi tidak melebihi dampaknya |
| Golden Rules Violation | 20% | Pelanggaran aturan keselamatan paling fundamental perusahaan — otomatis menaikkan tier risiko apapun kondisinya |
| Status + Overdue | 20% | Kejadian yang dibiarkan tidak ditangani makin berbahaya seiring waktu, apalagi jika sudah melewati deadline |
| Keyword bahaya | 10% | Bonus dari deskripsi teks — kata seperti "patah", "propeler", "tali", "kebakaran" menambah urgensi |

### Tabel nilai Konsekuensi

| Nilai | Skor mentah | Normalisasi | Poin (×35%) | Sumber |
|-------|-------------|-------------|-------------|--------|
| Major | 5 | 5/5 = 1.0 | **35.0** | BEATS: kolom `konsekuensi` / AM Care: `hazard_category = "Unsafe acts"` |
| Sedang | 3 | 3/5 = 0.6 | **21.0** | BEATS: kolom `konsekuensi` / AM Care: semua estimasi → Sedang |
| Minor | 1 | 1/5 = 0.2 | **7.0** | BEATS: kolom `konsekuensi` / AM Care: fallback |
| NULL | — | default 2 | **14.0** | 3 record BEATS tidak punya nilai — pakai nilai tengah |

### Tabel nilai Kekerapan

| Nilai | Skor mentah | Normalisasi | Poin (×25%) | Sumber |
|-------|-------------|-------------|-------------|--------|
| Sering | 5 | 5/5 = 1.0 | **25.0** | Hanya BEATS |
| Mungkin | 4 | 4/5 = 0.8 | **20.0** | Hanya BEATS |
| Kadang | 3 | 3/5 = 0.6 | **15.0** | Hanya BEATS |
| Kemungkinan Kecil | 2 | 2/5 = 0.4 | **10.0** | Hanya BEATS |
| Langka | 1 | 1/5 = 0.2 | **5.0** | BEATS (asli) dan semua AM Care (estimasi) |
| NULL | — | default 1 | **5.0** | 3 record BEATS tidak punya nilai |

> **Catatan:** Semua record AM Care diestimasi Langka (5 poin) — nilai minimum. Ini membuat skor kekerapan AM Care selalu rendah. Faktor Golden Rules dan Status+Overdue yang mengkompensasi untuk kejadian kritis.

### Tabel nilai Status + Overdue

Menggunakan kombinasi `status_hazard_l1` + `status_hazard_l2`:

| status (l1) | status_overdue (l2) | Poin | Logika |
|-------------|---------------------|------|--------|
| OPEN | Open Overdue | **20** | Belum ditangani + sudah lewat deadline → paling darurat |
| OPEN | (kosong/null) | **14** | Belum ditangani, belum ada info overdue |
| IN_REVIEW | — | **7** | Sedang diproses |
| CLOSED | Closed Overdue | **3** | Selesai tapi terlambat |
| CLOSED | Closed on Time | **0** | Selesai tepat waktu |

### Tabel nilai Golden Rules

| Kondisi | Poin | Sumber |
|---------|------|--------|
| "Melanggar Golden Rules" | **20** | `golden_rules_violation` — identik di kedua sistem |
| "Tidak Melanggar Golden Rules" | **0** | `golden_rules_violation` — identik di kedua sistem |

### Risk Matrix Likelihood × Severity (referensi)

|  | Minor (7 poin) | Sedang (21 poin) | Major (35 poin) |
|--|----------------|-----------------|----------------|
| **Sering (25 poin)** | 32 → MEDIUM | 46 → MEDIUM | 60 → HIGH |
| **Mungkin (20 poin)** | 27 → LOW | 41 → MEDIUM | 55 → HIGH |
| **Kadang (15 poin)** | 22 → LOW | 36 → MEDIUM | 50 → HIGH |
| **Kemungkinan Kecil (10 poin)** | 17 → LOW | 31 → MEDIUM | 45 → MEDIUM |
| **Langka (5 poin)** | 12 → LOW | 26 → LOW | 40 → MEDIUM |

> Angka di atas belum termasuk Golden Rules (+20) dan Status+Overdue (+0 s/d +20). Kedua faktor itulah yang bisa mendorong kejadian ke HIGH atau CRITICAL.

### Risk Tier Output

| Skor | Tier | Tindakan |
|------|------|----------|
| 70–110 | CRITICAL | Eskalasi hari ini, pertimbangkan hentikan operasi |
| 50–69 | HIGH | Selesaikan hari ini |
| 30–49 | MEDIUM | Selesaikan dalam 7 hari |
| 0–29 | LOW | Monitor dan log |

### Contoh perhitungan nyata dari data

#### Contoh 1 — AM Care HZD05260034: tali second towing mulai jabuk, spare habis

| Faktor | Nilai dari CSE | Konversi | Rumus | Poin |
|--------|---------------|----------|-------|------|
| Konsekuensi | Sedang *(estimasi dari hazard_category = "Unsafe conditions")* | 3 | 3/5 × 35 | 21.0 |
| Kekerapan | Langka *(estimasi dari hazard_l2 = "Equipment used beyond...", diverifikasi dari BEATS)* | 1 | 1/5 × 25 | 5.0 |
| Golden Rules | True — Melanggar *(data asli AM Care)* | 1 | 1 × 20 | 20.0 |
| Status + Overdue | OPEN + Open Overdue *(data asli AM Care)* | 20 | langsung | 20.0 |
| Keyword | "tali" terdeteksi dalam deskripsi | 1 | 1 × 2.5 | 2.5 |
| **TOTAL** | | | | **68.5 → HIGH** |

> Golden Rules (20) + Open Overdue (20) = 40 poin yang menentukan. Tanpa keduanya skornya hanya 28.5 → LOW.

#### Contoh 2 — BEATS 8640269: ceceran batubara di lambung kanan tongkang

| Faktor | Nilai dari CSE | Konversi | Rumus | Poin |
|--------|---------------|----------|-------|------|
| Konsekuensi | Major *(data asli dari Safety Observer BEATS)* | 5 | 5/5 × 35 | 35.0 |
| Kekerapan | Langka *(data asli dari Safety Observer BEATS)* | 1 | 1/5 × 25 | 5.0 |
| Golden Rules | False — Tidak Melanggar *(data asli BEATS)* | 0 | 0 × 20 | 0.0 |
| Status + Overdue | OPEN + (kosong) *(data asli BEATS)* | 14 | langsung | 14.0 |
| Keyword | tidak ada kata bahaya | 0 | 0 × 2.5 | 0.0 |
| **TOTAL** | | | | **54.0 → HIGH** |

> Konsekuensi Major penuh (35 poin) tapi kekerapan Langka dan tidak ada Golden Rules violation — total hanya 54. Kalau frekuensinya "Sering" dan ada overdue, bisa mencapai 85 → CRITICAL.

---

## Step 3 — RAG Advisory Engine (`rag_engine.py`)

### Mengapa RAG dan bukan langsung tanya LLM?

Konteks safety maritim tidak boleh ada halusinasi. Risiko nyata jika LLM menjawab dari pengetahuan umum:
- LLM bisa menyebut prosedur APAR yang berbeda dari SOP internal perusahaan
- LLM bisa merekomendasikan tindakan yang tidak sesuai regulasi SOLAS yang berlaku di kapal ini

Dengan RAG, setiap rekomendasi **harus mengacu ke SOP spesifik** yang tersimpan di `mock_sop/`.

### Alur RAG

```
Insiden dipilih dari Risk Heatmap
          ↓
retrieve() — cari SOP relevan via keyword matching dari hazard_l1 + deskripsi
          ↓
build_prompt() — inject detail insiden + SOP ke dalam prompt LLM
          ↓
generate_advisory() — LLM hanya boleh jawab dari SOP yang diberikan
          ↓
Tampil di Streamlit + referensi SOP
```

---

## Mock SOP — Alasan Pembuatan

SOP internal perusahaan tidak disertakan di dataset. Mock SOP dibuat berdasarkan **kejadian nyata yang ada di data** — bukan dikarang bebas. Isi SOP mengacu standar maritim internasional: SOLAS, ISM Code, MARPOL, dan MLC 2006.

| SOP | Kejadian nyata di dataset yang mendasari |
|-----|------------------------------------------|
| **SOP-HSE-001** APAR | BEATS: *"APAR bulan Mei belum diinspeksi"* (8640223, 8640490) |
| **SOP-HSE-002** Tali tambat & towing | AM Care HZD05260034: *"tali towing jabuk, spare habis"* — rank #1. Juga HZD05260055: *"tali tongkang putus"*, HZD05260033: *"tali tambat jabuk"* |
| **SOP-HSE-003** Engine Room | AM Care HZD05260052: *"shaft propeler patah"*, HZD05260032: *"alternator hangus"*, HZD05260050: *"lantai kamar mesin kotor"* |
| **SOP-HSE-004** Tumpahan batu bara & kimia | AM Care HZD05260046: *"oli hidrolik menggenang di crane"*, BEATS 8640269: *"ceceran batu bara di tongkang"* |
| **SOP-HSE-005** Crane | AM Care HZD05260035: *"lantai crane licin karena bauxite"*, HZD05260046: *"oli bocor di kolom crane"* |
| **SOP-HSE-006** APD | BEATS 8640275/8640286: *"tidak ada tali life buoy"*, *"APD tidak sesuai/layak"* |

---

## Step 4 — Streamlit UI (`app.py`)

### Fitur utama

1. **KPI summary** — total insiden, jumlah per tier, masih OPEN, Golden Rules violated
2. **Filter sidebar** — filter per Risk Tier, Status, dan Sumber data
3. **Risk Heatmap** — tabel 21 kolom CSE diurutkan `risk_score` tertinggi
4. **Breakdown skor** — expand per insiden untuk lihat s_konsekuensi, s_kekerapan, dll
5. **SIA Advisory** — klik "Tanya SIA" → rekomendasi berbasis SOP dengan referensi

### Integrasi Leading Indicator Dashboard

Di production, dashboard lama diembed via `st.components.iframe()` dengan shared JWT token. Kedua sistem membaca dari tabel Unity Catalog yang sama sehingga data selalu sinkron.

---

## Arsitektur Production (Databricks)

| Komponen | Development (repo ini) | Production (Databricks) |
|----------|----------------------|------------------------|
| Data source | File Excel lokal | Unity Catalog silver tables |
| Status | `status_hazard_l1` langsung | `status_hazard_l1` langsung |
| Vector store | Keyword matching | Databricks Vector Search |
| LLM | Mock (rule-based) | Azure OpenAI / Claude via Bedrock |
| Auth | Tidak ada | OIDC/OAuth 2.0 + Service Principal |
| Deployment | `streamlit run` | Databricks Apps |

### Koneksi Unity Catalog

```python
from databricks.sdk import WorkspaceClient

w = WorkspaceClient(
    host  = os.environ['DATABRICKS_HOST'],
    token = os.environ['DATABRICKS_TOKEN']   # OAuth M2M token
)

beats_df  = spark.table('safety_catalog.silver.beats_data')
amcare_df = spark.table('safety_catalog.silver.amcare_data')
```

### Keamanan — OIDC/OAuth 2.0

Ada dua alur autentikasi yang berbeda tergantung siapa yang mengakses sistem:

#### Alur 1 — Authorization Code Flow (untuk Safety Evaluator yang buka browser)

Ini untuk user manusia yang membuka aplikasi SIA via browser.

```
User membuka aplikasi SIA melalui browser
        ↓
Sistem mengarahkan user ke halaman login perusahaan (SSO)
        ↓
User login menggunakan akun perusahaan
        ↓
Sistem autentikasi perusahaan memverifikasi user
        ↓
Sistem memberikan access token sementara
        ↓
Token disimpan di session aplikasi
        ↓
Setiap akses data menggunakan token tersebut
        ↓
Sistem memeriksa role user sebelum memberikan akses data
```

Keuntungan pendekatan ini:
- User tidak pernah memasukkan password langsung ke aplikasi SIA
- Seluruh proses login dilakukan melalui sistem autentikasi perusahaan yang lebih aman dan terpusat
- Access token memiliki masa berlaku terbatas sehingga lebih aman dibanding password permanen
- Hak akses data dapat dibatasi berdasarkan role user

#### Alur 2 — M2M Client Credentials Flow (untuk pipeline batch otomatis)

Ini untuk proses yang berjalan otomatis tanpa ada manusia yang login, misalnya pipeline yang setiap 15 menit mengambil data baru dari BEATS dan AM Care.

```
Pipeline otomatis berjalan sesuai jadwal
        ↓
Sistem menggunakan Service Account khusus mesin
        ↓
Service Account meminta access token secara aman
        ↓
Sistem autentikasi memberikan token sementara
        ↓
Pipeline menggunakan token untuk baca/tulis data
        ↓
Token diperbarui otomatis saat expired
```

Credential Protection
Credential Service Account (client_id, client_secret) disimpan di secure secret manager dan tidak pernah ditulis langsung di source code maupun environment variable yang dapat dilihat user.

Keuntungan pendekatan ini:
- Pipeline tetap dapat berjalan otomatis tanpa login manual
- Credential tidak terekspos di kode aplikasi
- Access token memiliki masa berlaku terbatas dan diperbarui otomatis
- Hak akses pipeline dapat dibatasi sesuai kebutuhan proses ingestion

#### Row-Level Security di Unity Catalog

Token JWT dari OIDC membawa informasi role dan wilayah user. Unity Catalog membaca informasi ini dan otomatis memfilter data tanpa developer perlu menulis filter manual:

```
Token JWT berisi:
  { "user": "budi@perusahaan.com",
    "role": "safety_evaluator",
    "region": "Berau-Kaltim" }
        ↓
Unity Catalog baca token → jalankan policy:
  IF role = "safety_evaluator"
    THEN SELECT * WHERE area_proyek = "Berau-Kaltim"
  IF role = "safety_manager"
    THEN SELECT * (semua data)
        ↓
Budi hanya mendapat data wilayah Berau-Kaltim
Safety Manager mendapat semua data
```

#### Ringkasan Arsitektur Keamanan

| Komponen | Fungsi | Implementasi |
|----------|-----------|------------|
| User Authentication | Login user perusahaan secara aman | SSO — satu login untuk semua aplikasi perusahaan |
| Automated Pipeline Authentication | Autentikasi proses otomatis tanpa login manual | Machine-to-Machine OAuth Flow |
| Access Token | Token sementara untuk akses sistem | JWT (JSON Web Token) berisi role dan wilayah user, berlaku 1 jam |
| Access Control | Pembatasan akses data berdasarkan role user | Role-Based Access Control (RBAC) |
| Secret Management | Penyimpanan credential & API key secara aman | Secure Secret Manager |
| Audit & Monitoring | Pencatatan aktivitas akses sistem | Audit logging & monitoring |

---

## Skalabilitas — Sumber Data Masa Depan

| Sumber | Integrasi | Mapping ke CSE |
|--------|-----------|----------------|
| PMS (Technical Maintenance System) | Integrasi data maintenance kapal | Work order maintenance menjadi hazard equipment |
| VTO (Operational Voyage System) | Integrasi data operasional pelayaran | Incident selama perjalanan kapal dikonversi menjadi data hazard operasional |
| CCTV & Computer Vision | Deteksi otomatis pelanggaran safety | PPE violation atau unsafe behavior |
| Port Authority System | Integrasi audit & inspeksi eksternal | Hasil audit pelabuhan masuk ke sistem safety |

---

## Keterbatasan yang Diketahui

| Keterbatasan | Dampak | Solusi di Production |
|-------------|--------|---------------------|
| Konsekuensi AM Care diestimasi dari `hazard_category` | Semua record AM Care dapat konsekuensi "Sedang" — tidak membedakan yang benar-benar Major | Tambah kolom `konsekuensi` di form input AM Care |
| Kekerapan AM Care semua = Langka | Skor kekerapan selalu minimum (5 poin) untuk semua record AM Care | Tambah kolom `kekerapan` di form input AM Care |
| 3 record BEATS punya konsekuensi dan kekerapan NULL | Dapat nilai default (14 poin konsekuensi, 5 poin kekerapan) | Wajibkan pengisian di form BEATS |
| Mock SOP bukan SOP asli perusahaan | Advisory berbasis SOP mock, bukan prosedur resmi | Ganti dengan SOP asli perusahaan di Vector Store |
