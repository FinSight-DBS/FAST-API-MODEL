import logging
from typing import List, Optional

from openai import AsyncOpenAI

from src.core.config import settings

logger = logging.getLogger(__name__)

SYSTEM_PROMPT_COACH = """Kamu adalah FinSight AI Coach — asisten keuangan personal yang berbicara seperti teman dekat yang jujur dan peduli. Tugasmu adalah membantu nasabah memahami pola keuangan mereka berdasarkan data transaksi nyata.

Aturan penulisan yang WAJIB diikuti:
- Tulis dalam bentuk paragraf mengalir, bukan poin-poin atau daftar bernomor
- DILARANG menggunakan heading, subjudul, atau tanda bintang untuk bold/italic
- DILARANG menggunakan emoji atau emoticon dalam bentuk apapun
- Gunakan bahasa Indonesia yang hangat, natural, dan seperti percakapan
- Sertakan angka spesifik (nominal Rupiah, persentase) langsung di dalam kalimat
- Sampaikan semua hal — baik, buruk, maupun anomali — dalam alur narasi yang mengalir
- Tutup dengan 2-3 saran konkret yang disampaikan dalam bentuk kalimat biasa, bukan poin"""


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

    return f"""=== DATA KEUANGAN MINGGUAN ===
Periode       : {period_start} s/d {period_end}
Nasabah       : {user_name} ({user_id})
Persona       : {persona}
Gaji Bulanan  : Rp {gaji:,.0f}
Saldo Akhir   : Rp {saldo_terakhir:,.0f}

RINGKASAN 7 HARI:
- Total Pengeluaran : Rp {total_pengeluaran:,.0f}
- Wants (keinginan) : Rp {wants_amount:,.0f} ({wants_ratio:.1%})
- Needs (kebutuhan) : Rp {needs_amount:,.0f} ({needs_ratio:.1%}){anomali_section}"""


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


async def call_llm(context: str, is_monthly: bool = False) -> str:
    instruction = (
        "Tulis laporan bulanan dalam tepat 3 paragraf padat, tanpa heading, poin, atau emoji. "
        "Paragraf 1: ringkasan performa bulan ini — angka utama, persona, dan apakah keuangan sehat atau tidak. "
        "Paragraf 2: 2-3 pola perilaku paling menonjol dari data, langsung ke intinya. "
        "Paragraf 3: 2-3 saran konkret untuk bulan depan dalam kalimat biasa. "
        "Tidak perlu basa-basi, sapaan panjang, atau pengulangan data."
        if is_monthly
        else "Tulis laporan mingguan dalam tepat 3 paragraf padat, tanpa heading, poin, atau emoji. "
        "Paragraf 1: ringkasan pengeluaran minggu ini — total, proporsi wants vs needs, kondisi saldo. "
        "Paragraf 2: anomali atau pola yang perlu diperhatikan, langsung ke intinya. "
        "Paragraf 3: 2-3 saran konkret untuk minggu depan dalam kalimat biasa. "
        "Tidak perlu basa-basi, sapaan panjang, atau pengulangan data."
    )

    client = _get_llm_client()
    response = await client.chat.completions.create(
        model=settings.LLM_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT_COACH},
            {"role": "user", "content": f"{context}\n\nINSTRUKSI:\n{instruction}"},
        ],
        temperature=0.7,
        max_tokens=600,
        extra_body={"reasoning": {"enabled": True}},
    )
    return response.choices[0].message.content
