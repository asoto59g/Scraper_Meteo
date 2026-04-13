# LIB07 Scraper (IMN) — Histórico acumulado por hora + GitHub Actions

Extrae la tabla de datos horarios de la estación LIB07 del IMN:

`https://www.imn.ac.cr/especial/tablas/lib07.html`

Formato LATAM:

- Separador de columnas: `;`
- Decimal: `,`
- Miles: `.`

---

## Arquitectura

Cada ejecución del workflow:

1. Descarga la página del IMN (ventana deslizante de 24 h).
2. Guarda el estado actual en `salida_csv/lib07_horarios.csv` (sobreescribe).
3. Compara las 24 filas contra el histórico usando `fecha` como clave:
   inserta **solo las horas nuevas** que aún no están registradas.
4. Hace commit/push si hubo cambios.

El histórico crece de forma limpia —≈1 fila nueva por hora— sin duplicados
ni metadatos artificiales de slot.

---

## Archivos principales

### `export_lib07_csv.py`
Descarga y procesa **únicamente** la tabla horarios.
Genera:
- `salida_csv/lib07_horarios.csv` — ventana actual de 24 h (sobreescrita cada run).
- `salida_csv/historico/lib07_horarios_historico.csv` — acumulado histórico (crece con filas nuevas).

### `run_guarded_capture.py`
Punto de entrada del scraper. Llama a `export_outputs()`.

### `cleanup_history.py`
Envía un correo mensual con:
- Estadísticas del histórico (total de registros, rango de fechas, etc.).
- El CSV histórico completo adjunto en ZIP (si no supera 20 MB).
**No elimina filas.** Se ejecuta desde `monthly_report.yml`.

### `dedupe_history.py`
Utilidad de emergencia para eliminar duplicados en el histórico.
No se invoca en flujo normal; usar solo si se detecta inconsistencia.

### `scraper_lib07.yml`
Workflow principal (cron `*/5 * * * *`):
- Captura y merge al histórico.
- Commit/push con hasta 3 reintentos.

### `monthly_report.yml`
Workflow mensual (1° de cada mes a las 08:00 UTC):
- Ejecuta `cleanup_history.py` para enviar el reporte por correo.

---

## Variables y secretos requeridos en GitHub

| Tipo | Nombre | Descripción |
|---|---|---|
| Secret | `EMAIL_USER` | Cuenta Gmail del remitente |
| Secret | `EMAIL_APP_PASSWORD` | App Password de Gmail |
| Variable | `EMAIL_TO` | Destinatario del reporte mensual |

> ⚠️ `EMAIL_TO` **debe** estar configurado como variable de repositorio (`vars.EMAIL_TO`).
> Si falta, el script falla con error explícito.

---

## Requisitos locales

```bash
pip install -r requirements.txt
```

## Ejecución local

```bash
# Captura normal
python run_guarded_capture.py

# Debug con columnas detalladas
python export_lib07_csv.py

# Ver el histórico acumulado
# salida_csv/historico/lib07_horarios_historico.csv

# Deduplicar histórico (emergencia)
python dedupe_history.py

# Enviar reporte mensual manualmente (requiere vars EMAIL_* en entorno)
EMAIL_USER=tu@gmail.com EMAIL_APP_PASSWORD=xxx EMAIL_TO=dest@gmail.com python cleanup_history.py
```