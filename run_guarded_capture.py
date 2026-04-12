# run_guarded_capture.py
from datetime import datetime, timezone, timedelta
from pathlib import Path
import pandas as pd

from export_lib07_csv import export_outputs

HIST_FILE = Path("salida_csv/historico/lib07_actuales_instantanea_historico.csv")
MAX_BACKFILL_MIN = 40  # recupera slots perdidos hasta 40 min atrás


def floor_to_quarter(dt: datetime) -> datetime:
    return dt.replace(minute=(dt.minute // 15) * 15, second=0, microsecond=0)


def load_captured_slots():
    if not HIST_FILE.exists():
        return set()
    try:
        df = pd.read_csv(HIST_FILE, sep=";", dtype=str, encoding="utf-8-sig", engine="python", on_bad_lines="skip")
    except Exception:
        df = pd.read_csv(HIST_FILE, sep=";", dtype=str, encoding="utf-8", engine="python", on_bad_lines="skip")

    if "programado_slot" not in df.columns:
        return set()

    return set(df["programado_slot"].dropna().astype(str).str.strip().tolist())


def choose_slot_to_capture(now_utc: datetime, captured_slots: set):
    current_slot = floor_to_quarter(now_utc)

    # candidatos: slot actual y 2 anteriores (30 min)
    candidates = [
        current_slot - timedelta(minutes=30),
        current_slot - timedelta(minutes=15),
        current_slot,
    ]

    # prioriza el más viejo faltante (backfill primero)
    for slot in candidates:
        age_min = (now_utc - slot).total_seconds() / 60
        if age_min < 0:
            continue
        if age_min <= MAX_BACKFILL_MIN:
            slot_str = slot.strftime("%Y-%m-%d %H:%M:%S")
            if slot_str not in captured_slots:
                return slot

    return None


def main():
    now_utc = datetime.now(timezone.utc)
    captured_slots = load_captured_slots()
    target_slot = choose_slot_to_capture(now_utc, captured_slots)

    if target_slot is None:
        print(f"[SKIP] No hay slot pendiente. now={now_utc.strftime('%Y-%m-%d %H:%M:%S')}")
        return

    slot_str = target_slot.strftime("%Y-%m-%d %H:%M:%S")
    print(f"[RUN] Capturando slot pendiente: {slot_str}")
    export_outputs(debug=False, forced_slot=slot_str)


if __name__ == "__main__":
    main()