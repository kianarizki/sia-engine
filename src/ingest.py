import pandas as pd

KONSEKUENSI_PROXY = {
    "Unsafe acts": "Sedang",   
    "Unsafe conditions": "Sedang",  
}

KEKERAPAN_PROXY = {
    # Diverifikasi dari data BEATS
    "Equipment used beyond operational limits": "Langka",
    "Hazardous chemical spills": "Langka",
    "Overhead hazards": "Langka",
    "Poor housekeeping": "Langka",
    # Tidak ada di BEATS — estimasi berdasarkan kemiripan konsep
    "Operating faulty or damaged equipment": "Langka",
    "Malfunctioning or damaged tools and equipment": "Langka",
    "Missing tools, equipment, or machinery to do task": "Langka",
    "Standing, walking, or running in dangerous zone": "Langka",
    "Inadequate ventilation or temperature control": "Langka",
    "Unstable, dangerous, and loose ground in work areas": "Langka",
}


def load_and_harmonize(beats_path: str, amcare_path: str) -> pd.DataFrame:
    beats = pd.read_excel(beats_path)
    amcare = pd.read_excel(amcare_path)

    # ── BEATS → CSE ──
    b = pd.DataFrame({
        "event_id": beats["task_id"].astype(str),
        "source": "BEATS",
        "description": beats["deskripsi"].fillna(beats["ketidaksesuaian"]),
        "root_cause": beats["akar_permasalahan"].fillna(""),
        "hazard_l1": beats["hazard_l1"],
        "hazard_l2": beats["hazard_l2"],
        "hazard_category": beats["hazard_category"],
        "rca_l1": beats["rca_l1"],
        "rca_l2": beats["rca_l2"],
        "golden_violated": (
            beats["golden_rules_violation"].str.contains("Melanggar", na=False) &
            ~beats["golden_rules_violation"].str.contains("Tidak", na=False)
        ),
        "status": beats["status_hazard_l1"],
        "status_overdue": beats["status_hazard_l2"].fillna(""),
        "location": beats["site"].fillna("") + " | " + beats["lokasi"].fillna(""),
        "fleet_area": beats["fleet_type"],
        "konsekuensi": beats["konsekuensi"],
        "kekerapan": beats["kekerapan"],
        "nilai_resiko": beats["nilai_resiko"],
        "corrective_action": beats["tindakan"].fillna(""),
    })

    # ── AM Care → CSE ──
    a = pd.DataFrame({
        "event_id": amcare["kode"].astype(str),
        "source": "AMCARE",
        "description": amcare["deskripsi_temuan"],
        "root_cause": amcare["akar_permasalahan"].fillna(""),
        "hazard_l1": amcare["hazard_l1"],
        "hazard_l2": amcare["hazard_l2"],
        "hazard_category": amcare["hazard_category"],
        "rca_l1": amcare["rca_l1"],
        "rca_l2": amcare["rca_l2"],
        "golden_violated": (
            amcare["golden_rules_violation"].str.contains("Melanggar", na=False) &
            ~amcare["golden_rules_violation"].str.contains("Tidak", na=False)
        ),
        "status": amcare["status_hazard_l1"],
        "status_overdue": amcare["status_hazard_l2"].fillna(""),
        "location": amcare["lokasi"].fillna("") + " | " + amcare["sublokasi"].fillna(""),
        "fleet_area": amcare["category"],
        "konsekuensi": amcare["hazard_category"].map(KONSEKUENSI_PROXY),
        "kekerapan": amcare["hazard_l2"].map(KEKERAPAN_PROXY).fillna("Langka"),
        "nilai_resiko": None,
        "corrective_action": amcare["tindakan_perbaikan"].fillna(""),
    })

    return pd.concat([b, a], ignore_index=True)
