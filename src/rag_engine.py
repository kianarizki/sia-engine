import re
from pathlib import Path
# File SOP
SOP_FILE = Path(__file__).parent.parent / "mock_sop" / "maritime_safety_sop.md"

# Setiap SOP dipetakan ke keyword yang muncul di:
#   - deskripsi kejadian (description)
#   - hazard_l1
#   - hazard_l2
#
# Dasar pemilihan keyword: dari deskripsi nyata di kedua dataset
# Baca file SOP dan pecah per seksi SOP-HSE-XXX

# Keyword mapping per SOP
SOP_KEYWORDS = {
    "SOP-HSE-001": {
        "keywords": ["apar", "fire fighting", "kebakaran", "ffa", "hydrant", "pemadam", "sprinkler"],
        "hazard_l2": ["skipping pre-use inspections or safety checks", "insufficient emergency exit routes or marking"],
        "hazard_l1": ["failure to follow standard process steps"],
    },
    "SOP-HSE-002": {
        "keywords": ["tali", "towing", "tambat", "jabuk", "putus", "mooring", "wire", "rope", "layang", "luka"],
        "hazard_l2": ["equipment used beyond operational limits", "missing tools, equipment, or machinery to do task", "overhead hazards", "unsecured items or cargo"],
        "hazard_l1": ["physical environment", "tools, equipments, machineries, and vehicle deficiencies"],
    },
    "SOP-HSE-003": {
        "keywords": ["engine", "mesin", "alternator", "propeler", "shaft", "auxiliary", "echosounder", "radar", "navigasi", "generator", "pompa", "kondensor", "ac", "freon",
                     "baut", "bracket", "patah", "hangus"],
        "hazard_l2": ["operating faulty or damaged equipment", "malfunctioning or damaged tools and equipment", "inadequate ventilation or temperature control",
                      "poor housekeeping"],
        "hazard_l1": ["improper use of equipment", "tools, equipments, machineries, and vehicle deficiencies"],
    },
    "SOP-HSE-004": {
        "keywords": ["batu bara", "batubara", "coal", "oli", "hidrolik", "tumpahan", "ceceran", "kimia", "gas lpg", "lpg", "chemical", "spill", "conveyor", "belt"],
        "hazard_l2": ["hazardous chemical spills", "poor housekeeping", "slippery or uneven surfaces"],
        "hazard_l1": ["chemical and dust exposure"],
    },
    "SOP-HSE-005": {
        "keywords": ["crane", "angkat", "hidrolik", "bauxite", "licin", "kolom crane", "hoist"],
        "hazard_l2": ["hazardous chemical spills", "unstable, dangerous, and loose ground in work areas","overhead hazards"],
        "hazard_l1": ["physical environment"],
    },
    "SOP-HSE-006": {
        "keywords": ["apd", "life buoy", "life jacket", "helm", "rompi", "harness", "safety shoes", "pelampung", "full body harness", "sarung tangan"],
        "hazard_l2": ["misplacement of lifesaving equipment and ppe", "insufficient or improper lifesaving equipment", "disabling or bypassing safety devices"],
        "hazard_l1": ["insufficient safety equipment and infrastructure"],
    },
}


def load_sop() -> dict:
    raw = SOP_FILE.read_text(encoding="utf-8")
    sections = re.split(r"(?=^## SOP-HSE-)", raw, flags=re.MULTILINE)
    sops = {}
     # Pecah per section SOP-HSE-XXX
    for s in sections:
        m = re.match(r"## (SOP-HSE-\d+) — (.+)", s)
        if m:
            sops[m.group(1)] = {
                "title"  : m.group(2).strip(),
                "content": s[:800]
            }
    return sops


def retrieve(description: str, hazard_l1: str, hazard_l2: str = "") -> list[dict]:
    """
    Cari SOP paling relevan untuk satu insiden.
    Strategi scoring per SOP (makin tinggi makin relevan):
      +3 jika keyword cocok di description
      +2 jika hazard_l2 cocok di daftar hazard_l2 SOP
      +1 jika hazard_l1 cocok di daftar hazard_l1 SOP

    Mengembalikan top-2 SOP dengan skor tertinggi.
    """
    desc_lower = description.lower()
    l1_lower = hazard_l1.lower()
    l2_lower = hazard_l2.lower()

    sops = load_sop()
    scored = []
    # Scoring per SOP
    for ref, mapping in SOP_KEYWORDS.items():
        if ref not in sops:
            continue # Skip SOP yang tidak ada

        score = 0
        # Cek keyword di deskripsi (bobot tertinggi)
        for kw in mapping["keywords"]:
            if kw in desc_lower:
                score += 3

        # Cek hazard_l2 (bobot menengah)
        for h2 in mapping["hazard_l2"]:
            if h2 in l2_lower:
                score += 2

        # Cek hazard_l1 (bobot terendah)
        for h1 in mapping["hazard_l1"]:
            if h1 in l1_lower:
                score += 1

        if score > 0:
            scored.append((score, ref, sops[ref]))

    # Urutkan dari skor tertinggi
    scored.sort(key=lambda x: x[0], reverse=True)
    result = [{"ref": ref, **data} for _, ref, data in scored[:2]]

    if not result:
        result = [{"ref": "SOP-HSE-003", **sops.get("SOP-HSE-003", {})}] # Fallback SOP-HSE-003 jika tidak ada yang cocok
    return result


def generate_advisory(insiden: dict) -> str:
    """Generate rekomendasi berbasis SOP untuk satu insiden."""
    sops = retrieve(
        description = str(insiden.get("description", "")),
        hazard_l1 = str(insiden.get("hazard_l1", "")),
        hazard_l2 = str(insiden.get("hazard_l2", "")),
    )
    # Join SOP references
    ref_list = " | ".join(s["ref"] for s in sops)
    stop_ops = insiden.get("golden_violated", False)
    tier = insiden.get("risk_tier", "")
    score = insiden.get("risk_score", "-")
    rca = insiden.get("rca_l2", insiden.get("rca_l1", "-"))
    root = insiden.get("root_cause", "-")
    overdue = insiden.get("status_overdue", "")

    tindakan_segera = (
        "Hentikan operasi segera dan isolasi area."
        if stop_ops else
        "Pasang safety barrier dan batasi akses ke area."
    )

    overdue_note = (
        f"\n- Status **{overdue}** — eskalasi ke Safety Manager segera."
        if overdue else ""
    )

    sop_refs = "\n".join(
        f"- **{s['ref']}** — {s.get('title', '')}" for s in sops
    )

    return f"""
## 1. Ringkasan Risiko
Risk Score **{score}/100** → tier **{tier}**.
{"**PELANGGARAN GOLDEN RULES TERDETEKSI** — eskalasi wajib ke Safety Officer hari ini." if stop_ops else "Tidak ada pelanggaran Golden Rules."}

## 2. Tindakan Segera
- {tindakan_segera}{overdue_note}
- Laporkan ke Marine Safety Officer dalam 1 jam.
- Dokumentasikan kondisi dengan foto dan catat di logbook.
- Ikuti prosedur: **{ref_list}**

## 3. Akar Masalah
{root}
Klasifikasi RCA: {rca}

## 4. Mitigasi Jangka Panjang
- Jadwalkan inspeksi berkala sesuai **{ref_list}**.
- Pastikan stok suku cadang/pengganti selalu tersedia di kapal.
- Lakukan toolbox meeting khusus topik ini dalam 7 hari.
- Evaluasi apakah SOP perlu diperbarui berdasarkan insiden ini.

## 5. Referensi SOP
{sop_refs}
""".strip()
