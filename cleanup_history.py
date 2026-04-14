# cleanup_history.py
"""
Reporte mensual LIB07 — envía un correo con estadísticas del histórico acumulado.
NO elimina filas. Se ejecuta desde monthly_report.yml (trigger mensual).
"""
import os
import smtplib
import zipfile
from io import BytesIO
from pathlib import Path
from datetime import datetime, timezone
from email.message import EmailMessage

import pandas as pd

HIST_DIR = Path("salida_csv/historico")
MAX_ATTACH_MB = int(os.getenv("MAX_ATTACH_MB", "20"))

EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_APP_PASSWORD = os.getenv("EMAIL_APP_PASSWORD")
EMAIL_TO = os.getenv("EMAIL_TO")

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 465


def read_csv_robust(file: Path) -> pd.DataFrame:
    try:
        return pd.read_csv(file, sep=";", dtype=str, encoding="utf-8-sig",
                           engine="python", on_bad_lines="skip")
    except Exception:
        return pd.read_csv(file, sep=";", dtype=str, encoding="utf-8",
                           engine="python", on_bad_lines="skip")


def build_summary() -> tuple:
    """Genera el texto resumen y el adjunto ZIP con el histórico completo."""
    hist_file = HIST_DIR / "lib07_horarios_historico.csv"

    if not hist_file.exists():
        return "No existe el archivo histórico todavía.", None

    df = read_csv_robust(hist_file)
    if df.empty:
        return "El archivo histórico existe pero está vacío.", None

    row_count = len(df)
    col_count = len(df.columns)

    fecha_min = df["fecha"].dropna().iloc[0] if "fecha" in df.columns else "N/D"
    fecha_max = df["fecha"].dropna().iloc[-1] if "fecha" in df.columns else "N/D"
    captura_min = df["captura_utc"].dropna().iloc[0] if "captura_utc" in df.columns else "N/D"
    captura_max = df["captura_utc"].dropna().iloc[-1] if "captura_utc" in df.columns else "N/D"

    summary_text = (
        f"Reporte mensual LIB07 – Estación Liberia\n"
        f"{'=' * 50}\n"
        f"Registros acumulados : {row_count:,}\n"
        f"Columnas             : {col_count}\n"
        f"Fecha más antigua    : {fecha_min}\n"
        f"Fecha más reciente   : {fecha_max}\n"
        f"Primera captura UTC  : {captura_min}\n"
        f"Última captura UTC   : {captura_max}\n"
        f"\nGenerado: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}\n"
    )

    # Adjunto: CSV histórico completo comprimido en ZIP
    csv_bytes = df.to_csv(index=False, sep=";", encoding="utf-8-sig").encode("utf-8-sig")
    mem = BytesIO()
    with zipfile.ZipFile(mem, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("lib07_horarios_historico.csv", csv_bytes)
    mem.seek(0)
    zip_bytes = mem.read()

    zip_mb = len(zip_bytes) / (1024 * 1024)
    attach = zip_bytes if zip_mb <= MAX_ATTACH_MB else None
    if attach is None:
        summary_text += (
            f"\n[Adjunto omitido: {zip_mb:.1f} MB supera el límite de {MAX_ATTACH_MB} MB]\n"
        )

    return summary_text, attach


def send_report_email(summary_text: str, attach_zip_bytes=None):
    if not EMAIL_USER or not EMAIL_APP_PASSWORD:
        raise RuntimeError("Faltan EMAIL_USER o EMAIL_APP_PASSWORD en variables de entorno.")
    if not EMAIL_TO:
        raise RuntimeError("Falta variable de entorno EMAIL_TO.")

    now = datetime.now(timezone.utc)
    msg = EmailMessage()
    msg["Subject"] = f"LIB07 Reporte mensual – {now.strftime('%B %Y')}"
    msg["From"] = EMAIL_USER
    msg["To"] = EMAIL_TO
    msg.set_content(summary_text)

    if attach_zip_bytes:
        msg.add_attachment(
            attach_zip_bytes,
            maintype="application",
            subtype="zip",
            filename="lib07_horarios_historico.zip",
        )

    with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT) as smtp:
        smtp.login(EMAIL_USER, EMAIL_APP_PASSWORD)
        smtp.send_message(msg)


def main():
    print("[INFO] Generando reporte mensual LIB07...")
    summary_text, attach = build_summary()
    print(summary_text)

    try:
        send_report_email(summary_text, attach_zip_bytes=attach)
        print(f"[OK] Correo enviado ({'con' if attach else 'sin'} adjunto ZIP).")
    except Exception as e:
        print(f"[ERROR] Fallo al enviar correo: {e}")
        raise


if __name__ == "__main__":
    main()