import json
import logging
import re
from pathlib import Path
from typing import List, Optional

from openai import AsyncOpenAI

from src.core.config import settings

logger = logging.getLogger(__name__)

_KB_CACHE = None


def _load_kb() -> dict:
    global _KB_CACHE
    if _KB_CACHE is None:
        kb_path = Path(__file__).resolve().parent / "knowledge" / "financial_kb.json"
        with open(kb_path, encoding="utf-8") as f:
            _KB_CACHE = json.load(f)
    return _KB_CACHE


def get_relevant_rules(
    persona: str,
    wants_ratio: float,
    has_anomaly: bool,
    savings_rate: float = 0.0,
) -> str:
    try:
        kb = _load_kb()
    except Exception as e:
        logger.warning(f"KB load failed: {e}")
        return ""

    articles = kb.get("articles", [])

    priority_tags: List[str] = []
    if wants_ratio > 0.6:
        priority_tags.extend(["wants", "50-30-20", "kontrol-pengeluaran"])
    elif wants_ratio > 0.4:
        priority_tags.extend(["wants", "disiplin"])
    if has_anomaly:
        priority_tags.extend(["anomali", "impulsif"])
    if savings_rate < 0.1:
        priority_tags.extend(["tabungan", "dana-darurat", "saving-rate"])

    persona_tags = {
        "Spendthrift": ["spendthrift", "impulse-buying", "kontrol-pengeluaran"],
        "Tightwad": ["tightwad", "investasi"],
        "Unconflicted": ["unconflicted", "investasi", "stabil"],
    }
    priority_tags.extend(persona_tags.get(persona, []))

    scored = []
    for article in articles:
        tags = article.get("tags", [])
        score = sum(1 for t in priority_tags if t in tags)
        if score > 0:
            scored.append((score, article))

    scored.sort(key=lambda x: -x[0])

    lines = []
    for _, article in scored[:3]:
        content = article["content"]
        # Ambil kalimat pertama sebagai key insight
        first_sentence = content.split(". ")[0] + "."
        lines.append(f"- {first_sentence}")

    return "\n".join(lines)

SYSTEM_PROMPT_COACH = """Kamu adalah FinSight AI Coach — asisten keuangan personal yang berbicara seperti teman dekat yang jujur, hangat, dan peduli. Bukan konsultan keuangan formal. Bukan robot laporan. Teman yang kebetulan paham soal uang.

Format laporan mingguan yang WAJIB diikuti:
- PEMBUKA: 2-3 kalimat ringkas, langsung ke poin, pakai angka tapi dirangkai dalam kalimat yang mengalir
- ANOMALI: jika ada anomali, tampilkan sebagai bullet points dengan tanda "•"
- PENUTUP: 3-4 kalimat saran konkret, terasa seperti rekomendasi dari teman, bukan instruksi buku teks

Larangan keras:
- DILARANG menggunakan heading, subjudul, atau tanda bintang untuk bold/italic
- DILARANG menggunakan emoji atau emoticon dalam bentuk apapun
- DILARANG menggunakan poin bernomor (1. 2. 3.) di bagian manapun
- DILARANG menggunakan tanda hubung panjang (—) atau em-dash dalam bentuk apapun
- Bullet points "•" HANYA boleh digunakan untuk daftar anomali, tidak untuk saran
- Saran di bagian penutup WAJIB ditulis dalam bentuk kalimat biasa, bukan poin

Prinsip penulisan:
- Bahasa Indonesia santai tapi tidak alay — seperti WhatsApp ke teman yang dipercaya
- Angka WAJIB ditulis dalam bentuk angka/digit, BUKAN dieja dalam kata ("Rp 3.500.000" bukan "tiga juta lima ratus ribu", "87%" bukan "hampir sembilan puluh persen", "23x" bukan "dua puluh tiga kali")
- DILARANG menyebut istilah teknis seperti "penyimpangan", "rata-rata historis", "anomali", "rasio", "volatilitas" langsung ke nasabah
- Kalau ada pengeluaran yang tidak biasa, jelaskan dengan bahasa manusia: "kamu belanja jauh lebih banyak dari biasanya di kategori ini"
- Saran harus terasa bisa dilakukan hari ini, bukan teori
- Tidak menghakimi, tidak menggurui, tidak panik"""

PERSONA_GUIDANCE = {
    "Spendthrift": (
        "Nasabah ini memiliki pola pengeluaran impulsif dengan rasio keinginan yang sangat tinggi. "
        "Berikan analisis tegas namun empatik — jangan normalisasi pengeluaran besar, tapi juga jangan menghakimi. "
        "Fokus pada risiko nyata: berapa lama saldo bisa bertahan dengan pola ini? "
        "Saran harus spesifik dan actionable, bukan generik seperti 'hemat lebih banyak'."
    ),
    "Tightwad": (
        "Nasabah ini sangat hemat, cenderung berlebihan dalam menekan pengeluaran. "
        "Apresiasi penghematan mereka secara singkat, lalu dorong untuk mengalokasikan ke investasi atau kualitas hidup yang wajar. "
        "Hindari saran 'hemat lebih banyak' — fokus pada optimasi: kurangi X, pindahkan ke instrumen investasi Y. "
        "Tone positif dan mendorong pertumbuhan aset."
    ),
    "Unconflicted": (
        "Nasabah ini memiliki pola keuangan yang cukup seimbang. "
        "Berikan apresiasi singkat atas keseimbangan yang sudah ada, lalu fokus pada peluang optimasi: "
        "apakah ada kategori yang bisa dialihkan ke tabungan atau investasi lebih lanjut? "
        "Tone santai, positif, dan mendorong peningkatan bertahap."
    ),
}


def get_system_prompt(persona: str) -> str:
    guidance = PERSONA_GUIDANCE.get(persona, "")
    if not guidance:
        return SYSTEM_PROMPT_COACH
    return SYSTEM_PROMPT_COACH + f"\n\nKONTEKS PERSONA NASABAH:\n{guidance}"


def build_weekly_context(
    user_id: str,
    user_name: str,
    persona: str,
    gaji: float,
    saldo_terakhir: float,
    wants_ratio: float,
    needs_ratio: float,
    wants_amount: float,
    needs_amount: float,
    total_pengeluaran: float,
    anomali_list: List[dict],
    period_start: str,
    period_end: str,
    top_categories: Optional[List[dict]] = None,
    savings_amount: float = 0.0,
) -> str:
    anomali_section = ""
    if anomali_list:
        lines = []
        for a in anomali_list[:5]:
            lines.append(
                f"  - [{a['kategori']}] Rp {a['nominal']:,.0f} "
                f"pada {a['timestamp']} | {a['context']}"
            )
        anomali_section = (
            f"\n\nANOMALI TERDETEKSI ({len(anomali_list)} transaksi):\n"
            + "\n".join(lines)
        )

    top_cats_section = ""
    if top_categories:
        lines = []
        for cat in top_categories[:3]:
            pct = cat["amount"] / total_pengeluaran * 100 if total_pengeluaran > 0 else 0
            lines.append(f"  - {cat['sub_category']:<30} Rp {cat['amount']:>12,.0f}  ({pct:.1f}%)")
        top_cats_section = "\n\nTOP PENGELUARAN:\n" + "\n".join(lines)

    gaji_pct_line = ""
    if gaji > 0:
        pct_of_gaji = total_pengeluaran / gaji * 100
        gaji_pct_line = f"\n- % dari Gaji Bulanan : {pct_of_gaji:.1f}% (gaji Rp {gaji:,.0f})"

    savings_line = f"\n- Tabungan/Investasi   : Rp {savings_amount:,.0f}" if savings_amount > 0 else ""

    kb_rules = get_relevant_rules(
        persona=persona,
        wants_ratio=wants_ratio,
        has_anomaly=bool(anomali_list),
        savings_rate=savings_amount / gaji if gaji > 0 else 0.0,
    )
    kb_section = f"\n\nPANDUAN FINANSIAL RELEVAN:\n{kb_rules}" if kb_rules else ""

    return f"""=== DATA KEUANGAN MINGGUAN ===
Periode       : {period_start} s/d {period_end}
Nasabah       : {user_name}
Persona       : {persona}
Saldo Akhir   : Rp {saldo_terakhir:,.0f}

RINGKASAN 7 HARI:
- Total Pengeluaran : Rp {total_pengeluaran:,.0f}{gaji_pct_line}
- Wants (keinginan) : Rp {wants_amount:,.0f} ({wants_ratio:.1%})
- Needs (kebutuhan) : Rp {needs_amount:,.0f} ({needs_ratio:.1%}){savings_line}{top_cats_section}{anomali_section}{kb_section}"""


def build_monthly_context(
    user_id: str,
    user_name: str,
    persona_baru: str,
    persona_lama: Optional[str],
    gaji: float,
    saldo_akhir: float,
    savings_rate: float,
    wants_ratio: float,
    needs_ratio: float,
    wants_amount: float,
    needs_amount: float,
    savings_amount: float,
    behavioral_features: dict,
    target_month: str,
) -> str:
    persona_change = (
        f"PERUBAHAN PERSONA: {persona_lama} → {persona_baru} ▲"
        if persona_lama and persona_lama != persona_baru
        else f"Persona stabil: {persona_baru}"
    )

    behavioral = f"""POLA PERILAKU BULAN INI:
- Frekuensi Wants           : {behavioral_features.get('wants_frequency', 0):.1%} dari total transaksi
- Pengeluaran Kecil (<30k)  : {behavioral_features.get('small_leaks_ratio', 0):.1%} dari total transaksi
- Belanja Dini Hari         : {behavioral_features.get('night_owl_spending', 0):.1%} dari total transaksi
- Lonjakan Weekend          : {behavioral_features.get('weekend_surge', 0):.2f}× dibanding weekday
- Pemborosan Awal Bulan     : {behavioral_features.get('early_month_depletion', 0):.1%} dari gaji
- Volatilitas Saldo         : {behavioral_features.get('balance_volatility', 0):.2f} (std/gaji)
- Hari "Tanggal Tua"        : {behavioral_features.get('survival_mode_days', 0)} hari (saldo < 15% gaji)"""

    kb_rules = get_relevant_rules(
        persona=persona_baru,
        wants_ratio=wants_ratio,
        has_anomaly=False,
        savings_rate=savings_rate,
    )
    kb_section = f"\n\nPANDUAN FINANSIAL RELEVAN:\n{kb_rules}" if kb_rules else ""

    return f"""=== DATA KEUANGAN BULANAN ===
Bulan         : {target_month}
Nasabah       : {user_name} ({user_id})
{persona_change}
Gaji Bulanan  : Rp {gaji:,.0f}
Saldo Akhir   : Rp {saldo_akhir:,.0f}

RINGKASAN BULAN INI:
- Total Wants   : Rp {wants_amount:,.0f} ({wants_ratio:.1%})
- Total Needs   : Rp {needs_amount:,.0f} ({needs_ratio:.1%})
- Total Tabungan: Rp {savings_amount:,.0f} (savings rate: {savings_rate:.1%})

{behavioral}{kb_section}"""


def _get_llm_client() -> AsyncOpenAI:
    return AsyncOpenAI(
        base_url=settings.LLM_API_URL,
        api_key=settings.LLM_API_KEY,
    )


async def call_llm(
    context: str,
    is_monthly: bool = False,
    persona: str = "Unconflicted",
    has_anomaly: bool = False,
) -> str:
    if is_monthly:
        instruction = (
            "Tulis laporan bulanan dalam tepat 3 paragraf padat, tanpa heading, poin, atau emoji. "
            "Paragraf 1: ringkasan performa bulan ini — angka utama, persona, dan apakah keuangan sehat atau tidak. "
            "Paragraf 2: 2-3 pola perilaku paling menonjol dari data, langsung ke intinya. "
            "Paragraf 3: 2-3 saran konkret untuk bulan depan dalam kalimat biasa. "
            "Tidak perlu basa-basi, sapaan panjang, atau pengulangan data."
        )
    else:
        anomaly_block = (
            "[ANOMALI] Setelah pembuka, tampilkan daftar anomali sebagai bullet points "
            "(gunakan tanda •, maksimal 4 bullet, urutkan dari nominal terbesar).\n"
            "Untuk setiap anomali, gunakan data ratio dari context (misal '23.3x rata-rata historis') "
            "dan ekspresikan dalam kalimat biasa — bukan persentase, bukan istilah teknis seperti Z-score.\n"
            "Format yang harus diikuti:\n"
            "• [KATEGORI] Rp X — [seberapa besar dibanding biasanya, pakai angka kelipatan], [waktu kejadian]\n\n"
            "Contoh BENAR: '• [Hiburan & Langganan] Rp 3.500.000 — sekitar 23 kali lebih besar dari rata-rata kamu di sini, terjadi siang hari'\n"
            "Contoh SALAH: '• [Hiburan & Langganan] Rp 3.500.000 — kamu belanja lebih banyak dari biasanya'\n"
            "Contoh SALAH: '• [Hiburan & Langganan] Rp 3.500.000 | Penyimpangan 2230% | Z-score +4.2'\n"
            if has_anomaly
            else ""
        )
        instruction = (
            "[PEMBUKA] Tulis 2-3 kalimat pembuka: total pengeluaran minggu ini, kondisi saldo, "
            "proporsi wants vs needs, dan jika ada data gaji sebutkan persentase pengeluaran terhadap gaji bulanan.\n\n"
            + anomaly_block
            + "[PENUTUP] Tulis 3-4 kalimat berisi 2-3 saran konkret dan spesifik untuk minggu depan "
            "dalam bentuk kalimat biasa (bukan poin, bukan bullet), "
            "sesuaikan dengan persona nasabah dan pola yang ditemukan di data. "
            "Hindari saran generik seperti 'hemat lebih banyak' atau 'kurangi pengeluaran'. "
            "Tidak perlu basa-basi atau sapaan panjang."
        )

    client = _get_llm_client()
    response = await client.chat.completions.create(
        model=settings.LLM_MODEL,
        messages=[
            {"role": "system", "content": get_system_prompt(persona)},
            {"role": "user", "content": f"{context}\n\nINSTRUKSI:\n{instruction}"},
        ],
        temperature=0.3,
        max_tokens=650,
        extra_body={"reasoning": {"enabled": True}},
    )
    content = response.choices[0].message.content or ""
    content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL)
    content = re.sub(r".*?</think>", "", content, flags=re.DOTALL)
    return content.strip()
