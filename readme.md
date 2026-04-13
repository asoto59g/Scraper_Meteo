# LIB07 Scraper (IMN) — CSV/XLSX + GitHub Actions cada 15 min

Extrae tablas climáticas de la estación LIB07 del IMN:

`https://www.imn.ac.cr/especial/tablas/lib07.html`

Genera archivos en formato LATAM:

- Separador de columnas: `;`
- Decimal: `,`
- Miles: `.`

---

## Archivos principales

### `export_lib07_csv.py`
Descarga la página con timeout de 30 s (via `requests`) y extrae las tres tablas:
`Horarios`, `Actuales_resumen`, `Actuales_inst`. Genera:
- `salida_csv/lib07_horarios.csv`
- `salida_csv/lib07_actuales_resumen.csv`
- `salida_csv/lib07_actuales_instantanea.csv`
- `salida_csv/lib07_tablas.xlsx`
- Histórico acumulado en `salida_csv/historico/` con timestamps UTC.

### `run_guarded_capture.py`
Wrapper que evita capturar el mismo slot (15 min) más de una vez por corrida.
Revisa hasta 3 slots anteriores (45 min) para recuperar capturas perdidas (backfill).
Busca slots ya capturados en el primer archivo histórico disponible.

### `cleanup_history.py`
1. Deduplica los históricos antes de limpiar (`dedupe_history.py`).
2. Busca filas antiguas (por defecto > 30 días).
3. Envía correo con listado y adjunto ZIP.
4. **Solo si el correo se envía correctamente**, elimina las filas viejas.

> ⚠️ `EMAIL_TO` **debe** estar configurado como variable de repositorio (`vars.EMAIL_TO`).
> No hay fallback hardcodeado; si falta, el script falla con error explícito.

### `dedupe_history.py`
Elimina filas duplicadas en los CSV históricos (por `programado_slot` + `fecha`).
Se invoca automáticamente desde `cleanup_history.py`. También puede ejecutarse manualmente.

### `scraper_lib07.yml`
Workflow de GitHub Actions que:
- Corre cada 5 min (cron).
- Ejecuta `run_guarded_capture.py` para capturar el slot pendiente.
- Solo si la captura fue exitosa, ejecuta `cleanup_history.py`.
- Hace commit/push de `salida_csv/` con hasta 3 reintentos.
- `cancel-in-progress: false` para no interrumpir commits/push en curso.

---

## Variables y secretos requeridos en GitHub

| Tipo | Nombre | Descripción |
|---|---|---|
| Secret | `EMAIL_USER` | Cuenta Gmail del remitente |
| Secret | `EMAIL_APP_PASSWORD` | App Password de Gmail |
| Variable | `EMAIL_TO` | Destinatario del correo de limpieza |

---

## Requisitos locales

```bash
pip install -r requirements.txt
```

## Ejecución local

```bash
# Captura normal (un slot)
python run_guarded_capture.py

# Forzar un slot específico
python -c "from export_lib07_csv import export_outputs; export_outputs(debug=True)"

# Deduplicar históricos
python dedupe_history.py

# Limpiar históricos (requiere variables EMAIL_* en entorno)
EMAIL_USER=tu@gmail.com EMAIL_APP_PASSWORD=xxx EMAIL_TO=dest@gmail.com python cleanup_history.py
```