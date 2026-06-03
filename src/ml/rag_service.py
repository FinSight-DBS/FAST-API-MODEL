import logging
from typing import List, Optional

from openai import AsyncOpenAI

from src.core.config import settings

logger = logging.getLogger(__name__)

SYSTEM_PROMPT_COACH = """Kamu adalah FinSight AI Coach — asisten keuangan personal yang berbicara seperti teman dekat yang jujur dan peduli. Tugasmu adalah membantu nasabah memahami pola keuangan mereka berdasarkan data transaksi nyata.

Format laporan mingguan yang WAJIB diikuti:
- PEMBUKA: 2-3 kalimat paragraf singkat berisi ringkasan angka utama
- ANOMALI: jika ada anomali, tampilkan sebagai bullet points dengan tanda "•" (bukan angka, bukan tanda "-")
- PENUTUP: 3-4 kalimat paragraf berisi saran konkret

Larangan keras:
- DILARANG menggunakan heading, subjudul, atau tanda bintang untuk bold/italic
- DILARANG menggunakan emoji atau emoticon dalam bentuk apapun
- DILARANG menggunakan poin bernomor (1. 2. 3.) di bagian manapun
- Bullet points "•" HANYA boleh digunakan untuk daftar anomali, tidak untuk saran
- Saran di bagian penutup WAJIB ditulis dalam bentuk kalimat biasa, bukan poin

Prinsip penulisan:
- Gunakan bahasa Indonesia yang hangat, natural, dan seperti percakapan
- Sertakan angka spesifik (nominal Rupiah, persentase) langsung di dalam kalimat
- Kamu adalah penasihat finansial yang logis — saran harus realistis, berbasis data, tidak menghakimi"""

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

    return f"""=== DATA KEUANGAN MINGGUAN ===
Periode       : {period_start} s/d {period_end}
Nasabah       : {user_name}
Persona       : {persona}
Saldo Akhir   : Rp {saldo_terakhir:,.0f}

RINGKASAN 7 HARI:
- Total Pengeluaran : Rp {total_pengeluaran:,.0f}{gaji_pct_line}
- Wants (keinginan) : Rp {wants_amount:,.0f} ({wants_ratio:.1%})
- Needs (kebutuhan) : Rp {needs_amount:,.0f} ({needs_ratio:.1%}){savings_line}{top_cats_section}{anomali_section}"""


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

{behavioral}"""


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
            "[ANOMALI] Setelah pembuka, tampilkan daftar anomali dengan format bullet tepat seperti ini "
            "(gunakan tanda • bukan - atau angka, maksimal 4 bullet, urutkan dari nominal terbesar):\n"
            "• [KATEGORI] Rp X | Penyimpangan Y% dari rata-rata historis, terjadi pukul HH.00\n"
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
    return response.choices[0].message.content
