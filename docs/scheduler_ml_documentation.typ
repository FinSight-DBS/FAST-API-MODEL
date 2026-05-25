#set document(title: "FinSight FastAPI — Scheduler & ML Documentation", author: "FinSight DBS")
#set page(paper: "a4", margin: (top: 2.5cm, bottom: 2.5cm, left: 2.5cm, right: 2.5cm))
#set text(font: "New Computer Modern", size: 11pt, lang: "id")
#set heading(numbering: "1.1.")
#set par(justify: true, leading: 0.65em)
#show link: underline

#v(2cm)
#align(center)[
  #text(size: 22pt, weight: "bold")[FinSight FastAPI]
  #linebreak()
  #text(size: 16pt, weight: "regular")[Dokumentasi Teknis: Modul Scheduler & ML]
  #v(0.4cm)
  #text(size: 11pt, fill: gray)[DBS Coding Camp Capstone — 2026]
]

#v(1.5cm)
#outline(title: "Daftar Isi", indent: 1.5em)

#pagebreak()

= Gambaran Umum

FinSight adalah microservice FastAPI yang bertanggung jawab atas seluruh inferensi ML dan pembuatan laporan keuangan personal. Layanan ini berjalan secara internal (tidak terekspos ke publik) dan dikonsumsi oleh NestJS sebagai orchestrator utama.

*Prinsip arsitektur:*
- NestJS adalah _ground truth_ untuk skema database — FastAPI tidak pernah membuat atau mengubah tabel maupun tipe enum PostgreSQL.
- FastAPI hanya membaca dan menulis data melalui SQLAlchemy async (`asyncpg`).
- Semua operasi ML berjalan sebagai _background task_ (non-blocking).
- Model artifacts dimuat sekali saat startup menggunakan `@lru_cache`.

== Struktur Direktori

```
src/
├── features/
│   └── scheduler/
│       ├── scheduler_controller.py   # Route definitions (FastAPI Router)
│       ├── scheduler_dependencies.py # Auth + DI factories
│       ├── weekly/
│       │   └── schemas.py            # Pydantic I/O schemas untuk weekly
│       ├── monthly/
│       │   └── schemas.py            # Pydantic I/O schemas untuk monthly
│       └── usecase/
│           ├── run_weekly_usecase.py # Logika pipeline mingguan
│           └── run_monthly_usecase.py# Logika pipeline bulanan
└── ml/
    ├── model_loader.py               # Lazy-load semua model artifacts
    ├── nlp_service.py                # TF-IDF + klasifikasi P2P
    ├── autoencoder_service.py        # Deteksi anomali transaksi
    ├── clustering_service.py         # Feature engineering + prediksi persona
    ├── rag_service.py                # Pembuat konteks + LLM coach
    └── knowledge/
        └── financial_kb.json         # Knowledge base keuangan personal
```

== Alur Data End-to-End

```
HTTP POST /scheduler/weekly
         │
         ▼
  scheduler_controller.py
  → generate job_id
  → BackgroundTasks.add_task()
  → return 202 Accepted
         │
         ▼ (async background)
  RunWeeklyUseCase.execute()
  → fetch transactions (last 7 days)
  → classify P2P via NLP
  → map main_category
  → preprocess for Autoencoder
  → detect_anomalies()
  → build_weekly_context()
  → call_llm()  [OpenRouter API]
  → upsert WeeklyReport + DetectedAnomaly
```

#pagebreak()

= Modul ML (`src/ml/`)

== Model Loader (`model_loader.py`)

Bertanggung jawab untuk memuat semua model artifacts dari disk ke memori. Menggunakan `@lru_cache(maxsize=1)` sehingga setiap model hanya dimuat sekali selama lifetime proses.

=== Fungsi

#table(
  columns: (1fr, 1.8fr, 1.2fr),
  inset: 8pt,
  align: (left, left, left),
  stroke: 0.5pt,
  fill: (_, row) => if row == 0 { luma(230) } else { white },
  [*Fungsi*], [*Deskripsi*], [*Return Type*],
  [`get_nlp_pipeline()`],
  [Memuat TF-IDF vectorizer dan model klasifikasi dari path `settings.NLP_TOKENIZER_PATH` dan `settings.NLP_MODEL_PATH`.],
  [`tuple[vectorizer, model]`],

  [`get_autoencoder()`],
  [Memuat Keras autoencoder dari `settings.AUTOENCODER_MODEL_PATH` tanpa kompilasi ulang (`compile=False`).],
  [`tf.keras.Model`],

  [`get_autoencoder_meta()`],
  [Memuat dua file joblib: `preprocessing_meta.pkl` dan `model_meta.pkl` dari direktori yang sama dengan model Keras.],
  [`tuple[dict, dict]`],

  [`get_clustering_pipeline()`],
  [Memuat empat artefak: `scaler_all.pkl`, `umap_all.pkl`, `kmeans_all_umap.pkl`, dan `label_map.json` untuk pipeline prediksi persona.],
  [`tuple[scaler, umap, kmeans, dict]`],

  [`preload_all_models()`],
  [Dipanggil sekali saat startup aplikasi untuk _warm-up_ semua model ke cache. Error pada satu model tidak menghentikan proses pemuatan model lain.],
  [`None`],
)

=== Model Artifacts

#table(
  columns: (1.5fr, 1.5fr, 2fr),
  inset: 8pt,
  align: (left, left, left),
  stroke: 0.5pt,
  fill: (_, row) => if row == 0 { luma(230) } else { white },
  [*File*], [*Lokasi*], [*Deskripsi*],
  [`autoencoder.keras`], [`model/autoencoder/`], [Model Keras autoencoder untuk deteksi anomali.],
  [`preprocessing_meta.pkl`], [`model/autoencoder/`], [Dict berisi: `ohe`, `scaler`, `kat_cap`, `z_stats`, `feature_cols`, `ohe_cols`.],
  [`model_meta.pkl`], [`model/autoencoder/`], [Dict berisi: `threshold_user_kat` (per user+kategori) dan `threshold_kat` (per kategori).],
  [`scaler_all.pkl`], [`model/clustering/`], [StandardScaler untuk 10 fitur perilaku bulanan.],
  [`umap_all.pkl`], [`model/clustering/`], [UMAP dimensionality reduction model.],
  [`kmeans_all_umap.pkl`], [`model/clustering/`], [KMeans model (3 cluster → persona).],
  [`label_map.json`], [`model/clustering/`], [Mapping `{cluster_id: persona_name}`, e.g. `{"0": "Tightwad", "1": "Unconflicted", "2": "Spendthrift"}`.],
  [`tfidf_vectorizer.pkl`], [`model/nlp/`], [TF-IDF vectorizer untuk teks transaksi P2P.],
  [`nlp_model.pkl`], [`model/nlp/`], [Classifier (e.g. Logistic Regression) untuk prediksi sub-kategori dari teks.],
)

#pagebreak()

== NLP Service (`nlp_service.py`)

Modul ini menangani dua fungsi: reklasifikasi transaksi P2P menggunakan model NLP, dan pemetaan `sub_category` ke `main_category` (wants / needs / savings).

=== Konstanta

*`P2P_CATEGORY = "Transfer P2P"`* — nilai sentinel yang menandai transaksi P2P yang perlu diklasifikasikan ulang.

*`CATEGORY_MAP`* — dictionary yang memetakan nilai `sub_category` ke `main_category`. Mendukung dua format:

#table(
  columns: (1.2fr, 0.8fr, 1.8fr),
  inset: 8pt,
  stroke: 0.5pt,
  fill: (_, row) => if row == 0 { luma(230) } else { white },
  [*sub_category*], [*main_category*], [*Sumber*],
  [`"Transportasi"`, `"Tagihan & Utilitas"`, `"Kesehatan & Perawatan Diri"`, `"Groceries & Kebutuhan Pokok"`], [`needs`], [Output model NLP (title case)],
  [`"Belanja Online & Fashion"`, `"Produktivitas & Digital"`, `"F&B dan Nongkrong"`, `"Hiburan & Langganan"`, `"Transfer P2P"`], [`wants`], [Output model NLP (title case)],
  [`"Investasi & Finansial"`], [`savings`], [Output model NLP (title case)],
  [`"sewa_kos"`, `"belanja_dapur"`, `"listrik"`, `"internet"`, `"bpjs_kesehatan"`, `"makan"`, `"transport"`], [`needs`], [Nilai raw DB (snake_case)],
  [`"belanja_online"`, `"hiburan"`, `"makan_restoran"`, `"gadget"`, `"pakaian"`, `"kafe"`, `"langganan_streaming"`, `"Makan & Minum"`], [`wants`], [Nilai raw DB (snake_case)],
  [`"transfer_tabungan"`], [`savings`], [Nilai raw DB (snake_case)],
  [`"Pendapatan Bulanan"`, `"Pemasukan Tambahan"`], [`None`], [Transaksi kredit — dikecualikan dari kalkulasi],
)

=== Fungsi

*`_clean(text: str) -> str`*

Preprocessing teks untuk input NLP: lowercase, hapus karakter non-alphanumeric, normalisasi whitespace.

*`classify_p2p_transactions(df: DataFrame) -> DataFrame`*

Reklasifikasi transaksi dengan `sub_category == "Transfer P2P"` menggunakan model NLP. Menggabungkan kolom `description` dan `notes` sebagai input teks. Mengembalikan DataFrame dengan `sub_category` diperbarui in-place. Jika model tidak tersedia, DataFrame dikembalikan tanpa perubahan.

*`map_main_category(df: DataFrame) -> DataFrame`*

Menambahkan kolom `main_category` ke DataFrame berdasarkan lookup `CATEGORY_MAP`. Nilai yang tidak ada di map → `None` (diabaikan dalam kalkulasi rasio).

=== Alur Proses

```
df masuk
   │
   ├─ ada baris sub_category == "Transfer P2P"?
   │       │
   │     Ya │
   │       ▼
   │  load NLP pipeline (cached)
   │  gabung description + notes → clean text
   │  TF-IDF vectorize
   │  predict sub_category baru
   │  update df.sub_category
   │
   ▼
map_main_category()
   → df["main_category"] = df["sub_category"].map(CATEGORY_MAP)
```

#pagebreak()

== Autoencoder Service (`autoencoder_service.py`)

Modul deteksi anomali berbasis reconstruction error dari autoencoder neural network. Anomali adalah transaksi yang tidak sesuai dengan pola historis user di kategori tersebut.

=== Konstanta

- `MIN_Z = 3` — jumlah minimum transaksi historis user di kategori tertentu sebelum z-score dianggap valid.
- `_CONT_COLS = ["nominal", "hour_sin", "hour_cos", "nominal_z_user_kat"]` — nama kolom kontinu yang digunakan oleh model (sesuai nama saat training).

=== Fungsi: `preprocess_for_autoencoder(df, meta) -> np.ndarray`

Mempersiapkan DataFrame transaksi menjadi array numerik yang siap diinput ke autoencoder.

*Langkah-langkah preprocessing:*

+ *Rename kolom* — menyesuaikan nama kolom entity ke nama yang digunakan saat training:
  #table(
    columns: (1fr, 1fr),
    inset: 6pt,
    stroke: 0.5pt,
    fill: (_, row) => if row == 0 { luma(230) } else { white },
    [*Nama Entity (runtime)*], [*Nama Model (training)*],
    [`sub_category`], [`kategori_detail`],
    [`customer_id`], [`id_user`],
    [`amount`], [`nominal`],
  )

+ *Fitur waktu* — ekstrak `hour` dari `transaction_timestamp`, lalu encode siklik: `hour_sin = sin(2π × hour / 24)`, `hour_cos = cos(2π × hour / 24)`.

+ *Log transform nominal* — cap nominal berdasarkan `kat_cap` per kategori, lalu `log1p(nominal)`.

+ *One-hot encoding* — transform `kategori_detail` menggunakan OHE yang tersimpan di `meta["ohe"]`.

+ *Z-score per user-kategori* — merge dengan `z_stats` (mean dan std historis per `id_user` × `kategori_detail`). Hanya dihitung jika `z_count >= MIN_Z`. Hasil 0.0 jika data historis tidak cukup.

+ *Standard scaling* — transform 4 kolom kontinu menggunakan `meta["scaler"]`.

+ *Clip z-score* — nilai `nominal_z_user_kat_scaled` di-clip ke rentang `[-5, 5]`.

+ *Gabungkan fitur* — return array numpy shape `(n_rows, n_features)` dari semua kolom `_scaled`.

=== Fungsi: `detect_anomalies(df, X_scaled, model_meta, df_baseline, weekly_report_id)`

Menjalankan prediksi autoencoder dan menentukan anomali.

*Algoritma:*

+ Reconstruct input: `X_rec = autoencoder.predict(X_scaled)`.
+ Hitung per-row MAE: `mae = |X_scaled − X_rec|.mean(axis=1)`.
+ Tentukan threshold per transaksi: lookup di `threshold_user_kat` (per user+kategori), fallback ke `threshold_kat` (per kategori), fallback ke median semua threshold.
+ Hitung `mean_amount` historis per user×kategori dari `df_baseline`.
+ Suatu transaksi dinyatakan anomali jika: `mae > threshold AND amount > mean_amount`. Kondisi kedua memastikan hanya transaksi yang *lebih besar* dari biasanya yang diflagging.
+ Buat objek `DetectedAnomaly` untuk setiap baris anomali, lengkap dengan `anomaly_context`.

=== Fungsi: `_build_anomaly_context(row, df_baseline) -> str`

Menghasilkan teks narasi konteks anomali yang digunakan dalam laporan LLM.

*Komponen konteks:*
- Rasio nominal terhadap rata-rata historis user di kategori tersebut.
- Z-score (hanya ditampilkan jika `|z| >= 2.0`).
- Deskripsi jam transaksi (dini hari / pagi / siang / sore / malam).

=== Domain Entity: `DetectedAnomaly`

#table(
  columns: (1.3fr, 1fr, 1.8fr),
  inset: 7pt,
  stroke: 0.5pt,
  fill: (_, row) => if row == 0 { luma(230) } else { white },
  [*Field*], [*Tipe*], [*Deskripsi*],
  [`transaction_id`], [`str`], [UUID transaksi yang terdeteksi anomali.],
  [`customer_id`], [`str`], [ID nasabah.],
  [`weekly_report_id`], [`str`], [UUID laporan mingguan yang menampung anomali ini.],
  [`sub_category`], [`str`], [Kategori transaksi (setelah reklasifikasi NLP jika P2P).],
  [`amount`], [`int`], [Nominal transaksi dalam Rupiah.],
  [`mae`], [`float`], [Mean Absolute Error rekonstruksi autoencoder.],
  [`threshold_val`], [`float`], [Threshold MAE untuk user+kategori ini.],
  [`ratio`], [`float`], [`mae / (threshold_val + 1e-9)` — severity score.],
  [`anomaly_context`], [`str`], [Teks narasi konteks anomali untuk LLM.],
  [`detected_at`], [`Optional[datetime]`], [Timestamp deteksi, diisi oleh database.],
)

#pagebreak()

== Clustering Service (`clustering_service.py`)

Modul yang menghitung 10 fitur perilaku keuangan bulanan dari data transaksi, lalu memprediksi persona nasabah menggunakan pipeline KMeans.

=== Fungsi: `compute_monthly_features(df_debit, df_all, gaji, prev_month_balance) -> dict`

*Input:*
- `df_debit` — DataFrame transaksi debit bulan ini (sudah terklasifikasi).
- `df_all` — DataFrame semua transaksi bulan ini (debit + kredit, untuk saldo).
- `gaji` — penghasilan bulanan nasabah dalam Rupiah.
- `prev_month_balance` — saldo akhir bulan sebelumnya.

*Output — 10 fitur:*

#table(
  columns: (1.6fr, 0.8fr, 2fr),
  inset: 7pt,
  stroke: 0.5pt,
  fill: (_, row) => if row == 0 { luma(230) } else { white },
  [*Fitur*], [*Tipe*], [*Definisi*],
  [`wants_ratio`], [`float`], [Total wants / total pengeluaran debit.],
  [`fixed_costs_ratio`], [`float`], [Total needs / total pengeluaran debit.],
  [`savings_rate`], [`float`], [`(investasi + delta_saldo) / gaji`.],
  [`wants_frequency`], [`float`], [Jumlah transaksi wants / total transaksi debit.],
  [`small_leaks_ratio`], [`float`], [Transaksi < Rp 30.000 / total transaksi debit.],
  [`night_owl_spending`], [`float`], [Transaksi jam 22:00–04:00 / total transaksi debit.],
  [`weekend_surge`], [`float`], [Rata-rata amount weekend / rata-rata amount weekday.],
  [`early_month_depletion`], [`float`], [Total pengeluaran tanggal 1–5 / gaji.],
  [`balance_volatility`], [`float`], [Std saldo harian / gaji.],
  [`survival_mode_days`], [`int`], [Jumlah hari saldo < 15% dari gaji.],
)

*Catatan:* Kolom `hour`, `day_of_week`, dan `day_of_month` bersifat opsional — jika tidak ada, fitur terkait di-default ke 0.

=== Fungsi: `predict_persona(features: dict) -> str`

Memprediksi persona nasabah dari 10 fitur. Return salah satu dari `"Tightwad"`, `"Unconflicted"`, atau `"Spendthrift"`. Default ke `"Unconflicted"` jika model tidak tersedia atau prediksi gagal.

*Pipeline:*
+ Log-transform 4 fitur berikut untuk menstabilkan distribusi skewed: `wants_frequency`, `weekend_surge`, `balance_volatility`, `survival_mode_days`.
+ Buat array shape `(1, 10)` dari semua fitur sesuai urutan `ALL_FEATURES`.
+ `scaler.transform()` — StandardScaler.
+ `umap_model.transform()` — reduksi dimensi.
+ `kmeans.predict()` — prediksi cluster ID.
+ Lookup `label_map[cluster_id]` → string persona.

=== Enum Persona

#table(
  columns: (1fr, 2fr),
  inset: 7pt,
  stroke: 0.5pt,
  fill: (_, row) => if row == 0 { luma(230) } else { white },
  [*Persona*], [*Profil Singkat*],
  [`Tightwad`], [Sangat hemat, wants ratio rendah (< 15%), tabungan tinggi, namun berisiko mengorbankan kualitas hidup.],
  [`Unconflicted`], [Seimbang antara kebutuhan dan keinginan. Wants 20–35%, needs 40–55%, savings 15–25%. Pola paling sehat.],
  [`Spendthrift`], [Cenderung boros, wants ratio > 40%, savings rate rendah atau negatif. Pemicu umum: impulse buying, FOMO.],
)

#pagebreak()

== RAG Service (`rag_service.py`)

Modul yang membangun konteks terstruktur dari data keuangan dan memanggil LLM eksternal (melalui OpenRouter) untuk menghasilkan laporan naratif personal.

=== System Prompt

```
SYSTEM_PROMPT_COACH:
Kamu adalah FinSight AI Coach — asisten keuangan personal yang berbicara
seperti teman dekat yang jujur dan peduli.

Aturan WAJIB:
- Tulis dalam bentuk paragraf mengalir, bukan poin-poin atau daftar bernomor
- DILARANG menggunakan heading, subjudul, atau tanda bintang
- DILARANG menggunakan emoji atau emoticon dalam bentuk apapun
- Gunakan bahasa Indonesia yang hangat, natural, dan seperti percakapan
- Sertakan angka spesifik (nominal Rupiah, persentase) langsung dalam kalimat
- Tutup dengan 2-3 saran konkret dalam bentuk kalimat biasa, bukan poin
```

=== Fungsi: `build_weekly_context(...) -> str`

Membangun prompt konteks untuk laporan mingguan.

*Parameter:*

#table(
  columns: (1.3fr, 0.8fr, 1.8fr),
  inset: 7pt,
  stroke: 0.5pt,
  fill: (_, row) => if row == 0 { luma(230) } else { white },
  [*Parameter*], [*Tipe*], [*Deskripsi*],
  [`user_id`], [`str`], [ID nasabah.],
  [`user_name`], [`str`], [Nama tampilan (saat ini sama dengan user_id).],
  [`persona`], [`str`], [Persona aktif nasabah dari laporan bulanan terakhir.],
  [`gaji`], [`float`], [Penghasilan bulanan (saat ini 0.0 — tidak digunakan di weekly).],
  [`saldo_terakhir`], [`float`], [Running balance transaksi terakhir dalam periode.],
  [`wants_ratio`], [`float`], [Proporsi wants dari total consumable spending.],
  [`needs_ratio`], [`float`], [Proporsi needs dari total consumable spending.],
  [`wants_amount`], [`float`], [Nominal wants dalam Rupiah.],
  [`needs_amount`], [`float`], [Nominal needs dalam Rupiah.],
  [`total_pengeluaran`], [`float`], [Total debit 7 hari terakhir.],
  [`anomali_list`], [`list[dict]`], [Maks. 5 anomali teratas. Setiap dict: `kategori`, `nominal`, `timestamp`, `context`.],
  [`period_start`], [`str`], [Tanggal mulai periode (YYYY-MM-DD).],
  [`period_end`], [`str`], [Tanggal akhir periode (YYYY-MM-DD).],
)

=== Fungsi: `build_monthly_context(...) -> str`

Membangun prompt konteks untuk laporan bulanan. Parameter tambahan dibanding weekly:

#table(
  columns: (1.5fr, 0.8fr, 1.8fr),
  inset: 7pt,
  stroke: 0.5pt,
  fill: (_, row) => if row == 0 { luma(230) } else { white },
  [*Parameter Tambahan*], [*Tipe*], [*Deskripsi*],
  [`persona_baru`], [`str`], [Persona hasil prediksi bulan ini.],
  [`persona_lama`], [`Optional[str]`], [Persona bulan sebelumnya (ditampilkan jika berubah).],
  [`savings_rate`], [`float`], [Tingkat tabungan bulan ini.],
  [`savings_amount`], [`float`], [Nominal tabungan dalam Rupiah.],
  [`behavioral_features`], [`dict`], [10 fitur perilaku dari `compute_monthly_features()`.],
  [`target_month`], [`str`], [Bulan target format YYYY-MM.],
)

=== Fungsi: `call_llm(context: str, is_monthly: bool = False) -> str`

Memanggil LLM melalui OpenRouter dengan format prompt yang sudah ditentukan.

*Konfigurasi:*
- Model: `settings.LLM_MODEL`
- API base URL: `settings.LLM_API_URL`
- Temperature: `0.7`
- Max tokens: `600`
- Extra body: `{"reasoning": {"enabled": True}}`

*Format instruksi output — weekly:*
```
Tepat 3 paragraf padat, tanpa heading, poin, atau emoji.
Paragraf 1: ringkasan pengeluaran — total, proporsi wants vs needs, kondisi saldo.
Paragraf 2: anomali atau pola yang perlu diperhatikan.
Paragraf 3: 2-3 saran konkret untuk minggu depan dalam kalimat biasa.
Tidak perlu basa-basi, sapaan panjang, atau pengulangan data.
```

*Format instruksi output — monthly:*
```
Tepat 3 paragraf padat, tanpa heading, poin, atau emoji.
Paragraf 1: ringkasan performa bulan ini — angka utama, persona, kondisi keuangan.
Paragraf 2: 2-3 pola perilaku paling menonjol dari data.
Paragraf 3: 2-3 saran konkret untuk bulan depan dalam kalimat biasa.
```

=== Knowledge Base (`knowledge/financial_kb.json`)

File JSON berisi artikel keuangan personal yang dapat digunakan sebagai RAG context. Setiap artikel memiliki struktur:

```json
{
  "id": "rule_50_30_20",
  "title": "Aturan Anggaran 50/30/20 untuk Keuangan Sehat",
  "content": "...",
  "tags": ["budgeting", "50-30-20", "needs", "wants", "savings"]
}
```

*Topik yang tersedia (13 artikel):*
- `rule_50_30_20` — Aturan anggaran 50/30/20.
- `persona_tightwad`, `persona_unconflicted`, `persona_spendthrift` — Profil dan saran per persona.
- `anomali_transaksi` — Cara memahami dan merespons anomali.
- `survival_mode` — Tindakan saat saldo kritis.
- `early_month_depletion` — Efek paycheck / boros di awal bulan.
- `night_owl_spending` — Pengeluaran impulsif dini hari.
- `weekend_surge` — Lonjakan pengeluaran akhir pekan.
- `small_leaks` — Kebocoran kecil yang kumulatif.
- `savings_strategy` — Strategi menabung efektif.
- `balance_volatility` — Volatilitas saldo dan cash flow.
- `wants_control` — Teknik mengontrol pengeluaran wants.

#pagebreak()

= Modul Scheduler (`src/features/scheduler/`)

== Dependencies & Autentikasi (`scheduler_dependencies.py`)

Semua endpoint scheduler dilindungi oleh header autentikasi internal.

=== `verify_internal_key(x_internal_key: str = Header(...)) -> None`

Membandingkan nilai header `X-Internal-Key` dengan `settings.INTERNAL_API_KEY`. Mengembalikan `HTTP 403 Forbidden` jika tidak cocok.

*Header yang diperlukan:*
```
X-Internal-Key: <nilai dari env INTERNAL_API_KEY>
```

=== DI Factory Functions

```python
def get_run_weekly_use_case() -> RunWeeklyUseCase
def get_run_monthly_use_case() -> RunMonthlyUseCase
```

Membuat instance use case baru per request (stateless). Diinjeksikan melalui `Depends()`.

== Controller (`scheduler_controller.py`)

Router FastAPI dengan prefix `/scheduler` dan tag `"scheduler"`.

=== `POST /scheduler/weekly`

*Response:* `202 Accepted`

*Deskripsi:* Memulai pipeline laporan mingguan sebagai background task. Mengembalikan respons segera tanpa menunggu pipeline selesai. Output pipeline hanya tersedia di server logs.

*Request body (`WeeklySchedulerRequest`):*

#table(
  columns: (1.2fr, 1fr, 2fr),
  inset: 7pt,
  stroke: 0.5pt,
  fill: (_, row) => if row == 0 { luma(230) } else { white },
  [*Field*], [*Default*], [*Deskripsi*],
  [`customer_ids`], [`[]`], [List UUID customer. Kosong = semua customer aktif di DB.],
  [`reference_date`], [`null`], [Tanggal referensi. Null = hari ini. Pipeline memproses 7 hari sebelum tanggal ini.],
  [`dry_run`], [`false`], [Jika `true`, pipeline berjalan penuh tapi tidak menulis ke DB.],
)

*Response body (`WeeklyJobResponse`):*
```json
{
  "job_id": "weekly-2026-05-25-abc123",
  "status": "queued",
  "customer_count": 0,
  "message": "Weekly scheduler job queued successfully"
}
```

=== `POST /scheduler/monthly`

*Response:* `202 Accepted`

*Deskripsi:* Memulai pipeline laporan bulanan sebagai background task.

*Request body (`MonthlySchedulerRequest`):*

#table(
  columns: (1.2fr, 1fr, 2fr),
  inset: 7pt,
  stroke: 0.5pt,
  fill: (_, row) => if row == 0 { luma(230) } else { white },
  [*Field*], [*Default*], [*Deskripsi*],
  [`customer_ids`], [`[]`], [List UUID customer. Kosong = semua customer aktif.],
  [`target_month`], [`null`], [Format `YYYY-MM`. Null = bulan lalu secara otomatis.],
  [`dry_run`], [`false`], [Jika `true`, tidak menulis ke DB.],
)

*Validasi `target_month`:* Regex `^\d{4}-\d{2}$`. Melempar `422 Unprocessable Entity` jika format salah.

*Response body (`MonthlyJobResponse`):*
```json
{
  "job_id": "monthly-2026-04-abc123",
  "status": "queued",
  "customer_count": 0,
  "target_month": "2026-04",
  "message": "Monthly scheduler job queued successfully"
}
```

=== `GET /scheduler/health`

*Response:* `200 OK`

*Deskripsi:* Mengecek status pemuatan semua model ML. Memanggil setiap loader function dan melaporkan hasilnya.

*Contoh response:*
```json
{
  "status": "ok",
  "models": {
    "nlp": "loaded",
    "autoencoder": "loaded",
    "clustering": "loaded"
  }
}
```

Jika model gagal dimuat, field akan berisi pesan error (maks. 60 karakter pertama).

#pagebreak()

== Use Case: Pipeline Mingguan (`run_weekly_usecase.py`)

=== Request Object

```python
@dataclass
class RunWeeklyRequest:
    job_id: str
    customer_ids: List[str] = []
    reference_date: Optional[date] = None  # default: date.today()
    dry_run: bool = False
```

=== Alur Eksekusi

*`execute(request)`:*

+ Hitung periode: `period_end = reference_date`, `period_start = period_end − 7 hari`.
+ Buka satu `AsyncSession` untuk seluruh job.
+ Ambil semua customer aktif jika `customer_ids` kosong.
+ Proses customer dalam chunk ukuran `CHUNK_SIZE = 50`.

*`_process_chunk(...)`:*

+ Fetch transaksi debit 7 hari terakhir untuk chunk ini via `trx_repo.find_debit_last_7_days()`.
+ Fetch baseline historis untuk anomaly detection via `trx_repo.find_all_for_baseline()`.
+ Klasifikasi P2P dan mapping main_category.
+ Coba load preprocessing meta dan preprocess untuk autoencoder. Jika gagal, set `has_ae = False` dan lanjut tanpa anomaly detection.
+ Iterasi per customer dalam chunk, panggil `_generate_report()`.

*`_generate_report(...)`:*

Langkah detail untuk satu customer:

#table(
  columns: (0.6fr, 2.5fr),
  inset: 7pt,
  stroke: 0.5pt,
  fill: (_, row) => if row == 0 { luma(230) } else { white },
  [*Langkah*], [*Deskripsi*],
  [1], [Hitung `total_expenses`, `wants_nom`, `needs_nom`.],
  [2], [Hitung `wants_ratio` dan `needs_ratio` terhadap `consumable_total = wants_nom + needs_nom` (bukan total pengeluaran — mengecualikan savings).],
  [3], [Jalankan `detect_anomalies()` jika autoencoder tersedia. Ambil 3 anomali terparah untuk konteks LLM.],
  [4], [Ambil persona aktif dari `report_repo.get_latest_monthly_persona()`. Default `"Unconflicted"` jika belum ada.],
  [5], [Ambil saldo terakhir dari `running_balance` transaksi terakhir.],
  [6], [Bangun konteks dengan `build_weekly_context()`.],
  [7], [Panggil `call_llm()`. Jika gagal, gunakan konteks mentah sebagai fallback.],
  [8], [Buat objek `WeeklyReport` dan upsert ke DB (kecuali `dry_run`).],
  [9], [Simpan semua `DetectedAnomaly` ke DB, dengan `weekly_report_id` diisi setelah upsert.],
)

=== Domain Entity: `WeeklyReport`

#table(
  columns: (1.3fr, 1fr, 1.8fr),
  inset: 7pt,
  stroke: 0.5pt,
  fill: (_, row) => if row == 0 { luma(230) } else { white },
  [*Field*], [*Tipe*], [*Deskripsi*],
  [`id`], [`Optional[str]`], [UUID, diisi oleh DB saat upsert.],
  [`customer_id`], [`str`], [ID nasabah.],
  [`report_date`], [`date`], [Tanggal akhir periode (= `period_end`).],
  [`period_start`], [`date`], [Tanggal awal periode (7 hari sebelum `report_date`).],
  [`persona`], [`str`], [Persona aktif nasabah.],
  [`wants_ratio`], [`float`], [Proporsi wants dari consumable spending.],
  [`needs_ratio`], [`float`], [Proporsi needs dari consumable spending.],
  [`total_expenses`], [`int`], [Total pengeluaran debit 7 hari (Rupiah).],
  [`anomaly_count`], [`int`], [Jumlah anomali terdeteksi.],
  [`report_text`], [`str`], [Teks laporan 3 paragraf dari LLM.],
  [`generated_at`], [`Optional[datetime]`], [Timestamp pembuatan, diisi oleh `func.now()` saat upsert.],
)

#pagebreak()

== Use Case: Pipeline Bulanan (`run_monthly_usecase.py`)

=== Request Object

```python
@dataclass
class RunMonthlyRequest:
    job_id: str
    target_month: str   # format YYYY-MM
    customer_ids: List[str] = []
    dry_run: bool = False
```

=== Alur Eksekusi

*`execute(request)`:*

+ Parse `target_month` ke `year`, `month` → hitung `month_start` dan `month_end`.
+ Buka satu `AsyncSession`.
+ Ambil customer aktif jika list kosong.
+ Proses dalam chunk ukuran 50.

*`_process_chunk(...)`:*

+ Fetch semua transaksi dalam bulan target via `trx_repo.find_debit_in_month()`.
+ Klasifikasi P2P dan mapping main_category.
+ Pisahkan `df_debit` (type == "debit") dari `df_all` (semua).
+ Iterasi per customer.

*`_generate_report(...)`:*

#table(
  columns: (0.6fr, 2.5fr),
  inset: 7pt,
  stroke: 0.5pt,
  fill: (_, row) => if row == 0 { luma(230) } else { white },
  [*Langkah*], [*Deskripsi*],
  [1], [Ambil persona sebelumnya dari `report_repo.get_latest_monthly_persona()`.],
  [2], [Ambil `gaji` dari `customer_repo.get_monthly_income()` — query kolom `monthly_income` di tabel `customer`.],
  [3], [Hitung `prev_month_balance` (saldo pertama bulan ini = saldo akhir bulan lalu) dan `saldo_akhir`.],
  [4], [Hitung 10 fitur via `compute_monthly_features()`.],
  [5], [Prediksi `persona_baru` via `predict_persona()`.],
  [6], [Hitung `wants_nom`, `needs_nom`, rasio terhadap `consumable_total`.],
  [7], [Hitung `savings_amount = investasi_nom + max(delta_saldo, 0)`. Investasi dari sub_category "Investasi & Finansial", delta saldo = saldo akhir − saldo awal.],
  [8], [Bangun konteks bulanan dengan `build_monthly_context()`.],
  [9], [Panggil `call_llm(is_monthly=True)`. Fallback ke konteks mentah jika gagal.],
  [10], [Upsert `MonthlyReport` ke DB.],
  [11], [Update `base_persona` di tabel `customer` via `customer_repo.update_base_persona()`.],
)

=== Domain Entity: `MonthlyReport`

#table(
  columns: (1.5fr, 1fr, 1.8fr),
  inset: 7pt,
  stroke: 0.5pt,
  fill: (_, row) => if row == 0 { luma(230) } else { white },
  [*Field*], [*Tipe*], [*Deskripsi*],
  [`id`], [`Optional[str]`], [UUID.],
  [`customer_id`], [`str`], [ID nasabah.],
  [`target_month`], [`str`], [Bulan laporan format YYYY-MM.],
  [`persona`], [`PersonaEnum`], [Persona baru hasil prediksi bulan ini.],
  [`prev_persona`], [`Optional[PersonaEnum]`], [Persona bulan sebelumnya.],
  [`savings_rate`], [`float`], [Tingkat tabungan dari `compute_monthly_features()`.],
  [`wants_ratio`], [`float`], [Proporsi wants dari consumable.],
  [`needs_ratio`], [`float`], [Proporsi needs dari consumable.],
  [`wants_amount`], [`int`], [Nominal wants dalam Rupiah.],
  [`needs_amount`], [`int`], [Nominal needs dalam Rupiah.],
  [`savings_amount`], [`int`], [Investasi + kenaikan saldo bersih.],
  [`behavioral_features`], [`dict`], [10 fitur perilaku (disimpan sebagai JSONB).],
  [`report_text`], [`str`], [Teks laporan 3 paragraf dari LLM.],
  [`generated_at`], [`Optional[datetime]`], [Timestamp, diisi DB.],
)

#pagebreak()

= Konfigurasi

== Environment Variables

#table(
  columns: (1.5fr, 1.5fr, 1.8fr),
  inset: 7pt,
  stroke: 0.5pt,
  fill: (_, row) => if row == 0 { luma(230) } else { white },
  [*Variable*], [*Digunakan di*], [*Deskripsi*],
  [`INTERNAL_API_KEY`], [`scheduler_dependencies.py`], [Key autentikasi header `X-Internal-Key`.],
  [`LLM_API_URL`], [`rag_service.py`], [Base URL OpenRouter (atau LLM provider lain yang OpenAI-compatible).],
  [`LLM_API_KEY`], [`rag_service.py`], [API key untuk LLM provider.],
  [`LLM_MODEL`], [`rag_service.py`], [Nama model LLM, e.g. `"openai/gpt-4o-mini"`.],
  [`AUTOENCODER_MODEL_PATH`], [`model_loader.py`], [Path ke file `autoencoder.keras`.],
  [`KMEANS_MODEL_PATH`], [`model_loader.py`], [Path ke file `kmeans_all_umap.pkl`.],
  [`KMEANS_LABEL_MAP_PATH`], [`model_loader.py`], [Path ke file `label_map.json`.],
  [`NLP_TOKENIZER_PATH`], [`model_loader.py`], [Path ke file `tfidf_vectorizer.pkl`.],
  [`NLP_MODEL_PATH`], [`model_loader.py`], [Path ke file `nlp_model.pkl`.],
)

== Dependency Stack

#table(
  columns: (1fr, 1.2fr, 2fr),
  inset: 7pt,
  stroke: 0.5pt,
  fill: (_, row) => if row == 0 { luma(230) } else { white },
  [*Library*], [*Versi*], [*Kegunaan*],
  [`fastapi`], [≥0.100], [HTTP framework, Router, BackgroundTasks, Depends.],
  [`sqlalchemy`], [≥2.0], [Async ORM, `text()`, `func.now()`.],
  [`asyncpg`], [—], [PostgreSQL async driver.],
  [`pydantic`], [v2], [Request/response validation, `field_validator`.],
  [`pandas`], [—], [Manipulasi DataFrame transaksi.],
  [`numpy`], [—], [Array operations untuk preprocessing.],
  [`tensorflow` / `keras`], [—], [Load dan inferensi model autoencoder.],
  [`joblib`], [—], [Load sklearn artifacts (scaler, KMeans, UMAP).],
  [`umap-learn`], [—], [Dimensionality reduction untuk clustering.],
  [`openai`], [—], [AsyncOpenAI client untuk call LLM.],
)

#pagebreak()

= Catatan Teknis Penting

== PostgreSQL Native Enum

NestJS/TypeORM membuat tipe enum native di PostgreSQL. SQLAlchemy *tidak boleh* mencoba membuat ulang tipe ini. Semua kolom enum di SQLAlchemy harus didefinisikan dengan:

```python
from sqlalchemy.dialects.postgresql import ENUM

_trx_type_enum = ENUM(
    'debit', 'credit',
    name='transactions_transaction_type_enum',
    create_type=False   # <-- kritis: jangan buat ulang
)
```

Nama tipe enum harus persis sesuai yang ada di PostgreSQL (verifiable via `\dT` di psql).

== Rasio Wants vs Needs

`wants_ratio + needs_ratio = 1.0` dijamin karena keduanya dihitung terhadap `consumable_total`:

```python
consumable_total = wants_nom + needs_nom  # savings dikecualikan
wants_ratio = wants_nom / consumable_total
needs_ratio = needs_nom / consumable_total
```

Transaksi dengan `main_category == "savings"` atau `None` tidak dimasukkan dalam denominasi.

== Column Name Bridging (Autoencoder)

Model autoencoder dilatih dengan nama kolom yang berbeda dari nama entity domain. Rename dilakukan di awal `preprocess_for_autoencoder()`, sebelum operasi model apapun:

#table(
  columns: (1fr, 1fr),
  inset: 7pt,
  stroke: 0.5pt,
  fill: (_, row) => if row == 0 { luma(230) } else { white },
  [*Entity (runtime)*], [*Model artifact (training)*],
  [`sub_category`], [`kategori_detail`],
  [`customer_id`], [`id_user`],
  [`amount`], [`nominal`],
)

== Error Handling

Semua error di dalam loop customer bersifat non-fatal — satu customer yang gagal tidak menghentikan pemrosesan customer lain. Error fatal (DB tidak bisa diakses, session gagal dibuka) akan menghentikan seluruh pipeline dan tercatat di logs.

#table(
  columns: (1.5fr, 2.5fr),
  inset: 7pt,
  stroke: 0.5pt,
  fill: (_, row) => if row == 0 { luma(230) } else { white },
  [*Skenario*], [*Penanganan*],
  [Model tidak tersedia (file tidak ada)], [`preload_all_models()` log error, pipeline lanjut tanpa model tersebut.],
  [AE preprocessing gagal], [`has_ae = False`, laporan dibuat tanpa deteksi anomali.],
  [LLM call gagal (timeout, 5xx)], [Gunakan raw context string sebagai `report_text` dengan prefix `"[LLM unavailable]"`.],
  [Customer tidak ada transaksi], [Log warning, skip customer, lanjut ke berikutnya.],
  [Clustering gagal], [`predict_persona()` return `"Unconflicted"` sebagai default.],
)
