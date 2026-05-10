import pandas as pd

SKOR_KONSEKUENSI = {"Major": 5, "Sedang": 3, "Minor": 1}
SKOR_KEKERAPAN = {"Sering": 5, "Mungkin": 4, "Kadang": 3, "Kemungkinan Kecil": 2, "Langka": 1}

KATA_BAHAYA = [
    "patah", "putus", "jabuk", "bocor", "hangus",
    "propeler", "shaft", "alternator", "radar", "echosounder",
    "gas lpg", "apar", "life buoy", "tali towing", "crane",
    "kebakaran", "ledakan", "tenggelam",
]


def hitung_skor_status(status: str, overdue: str) -> int:
    if status == "OPEN" and "Overdue" in str(overdue): 
        return 20
    if status == "OPEN":                                     
        return 14
    if status == "IN_REVIEW":                                
        return 7
    if status == "CLOSED" and "Overdue" in str(overdue): 
        return 3
    return 0


def rank_risks(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    # Faktor 1 — Konsekuensi/Severity (35%)
    df["s_konsekuensi"] = df["konsekuensi"].map(SKOR_KONSEKUENSI).fillna(2) / 5 * 35
    # Faktor 2 — Kekerapan/Frekuensi (25%)
    df["s_kekerapan"] = df["kekerapan"].map(SKOR_KEKERAPAN).fillna(1) / 5 * 25
    # Faktor 3 — Golden Rules Violation (20%)
    df["s_golden"] = df["golden_violated"].astype(int) * 20
    # Faktor 4 — Status + Overdue (20%)
    df["s_status"] = df.apply(
        lambda r: hitung_skor_status(r["status"], r["status_overdue"]), axis=1
    )
    # Keyword bahaya dalam deskripsi
    df["s_keyword"] = df["description"].apply(
        lambda t: min(sum(k in str(t).lower() for k in KATA_BAHAYA) * 2.5, 10)
    )
    # Total
    df["risk_score"] = (
        df["s_konsekuensi"] + df["s_kekerapan"] +
        df["s_golden"] + df["s_status"] + df["s_keyword"]
    ).round(1)

    df["risk_tier"] = df["risk_score"].apply(
        lambda s: "CRITICAL" if s >= 70 else "HIGH" if s >= 50
                  else "MEDIUM" if s >= 30 else "LOW"
    )
    return df.sort_values("risk_score", ascending=False).reset_index(drop=True)
