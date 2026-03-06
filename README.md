# revisa_bh_st — Boletas de Honorarios

Repositorio: **[github.com/Derehckz/revisa_bh_st](https://github.com/Derehckz/revisa_bh_st)**

Flujo de trabajo para solicitud, recepción, validación e informe de boletas de honorarios (BH). Los scripts se ejecutan en **Windows** y usan **Outlook** para envío y extracción de correos.

---

## Clonar e instalar

```bash
git clone https://github.com/Derehckz/revisa_bh_st.git
cd revisa_bh_st
pip install -r requirements.txt
```

---

## Configuración

- **`config.py`**: Ajusta la ruta raíz del proyecto (`RAIZ`), correos, fechas de recepción y horario. Es el único lugar donde conviene cambiar estas constantes.
- **`utils.py`**: Funciones compartidas (selector de opciones, normalización de RUT, resolución de conflictos, backup).

Tras clonar, edita `config.py` y define `RAIZ` apuntando a la carpeta donde quieras trabajar (ahí se crearán las carpetas **Año/Mes** al ejecutar los scripts).

---

## Estructura esperada

Los scripts crean y usan esta estructura bajo `RAIZ`:

- `RAIZ / Año / Mes /` (ej. `2026 / Enero /`, `2026 / Febrero /`)
- En cada mes: archivo Excel de solicitud, y tras la extracción, XML/PDF y subcarpetas `logs_*`, `reporte_avance`, `IP/`, `CFT/`.

Las carpetas de años **no** van en el repositorio; se generan al usar los scripts.

---

## Orden sugerido de ejecución

| # | Script | Descripción |
|---|--------|-------------|
| 1 | `1.-envia_correo_mensual_bh.py` | Envía correos de solicitud de boletas (y opcionalmente recordatorios) según el Excel del mes. |
| 2 | `2.-extrae_xml_correo.py` | Extrae adjuntos XML y PDF de Outlook en un rango de fechas y los guarda en la carpeta año/mes. |
| 3 | `3.-revisa_solicitud_VS_recibidas.py` | Compara la solicitud (Excel) con los archivos recibidos y actualiza estado (RECIBIDO / NO RECIBIDO / RECIBIDO CON ERROR). |
| 4 | `4.-extrae_datos_xml_al_excel.py` | Llena columnas del Excel con datos extraídos de cada XML (RUT, montos, fecha boleta, etc.). |
| 5 | `5.-Informe_final_boletas.py` | Genera la hoja "Resumen Boletas" con las filas aprobadas para pago. |
| 6 | `6.-Envia_mail_pagos.py` | Envía correos con la información de pago (fecha, banco, cuenta, monto) según la hoja Pagos. |
| 7 | `7.-separa_bh_ip_cft.py` | Separa/copia archivos BH en subcarpetas por institución (IP/CFT). |
| 8 | `8.-agrupa_por_docente.py` | Crea carpetas por docente dentro de IP/CFT. |
| 9 | `9.-revisa_carpetas_ip_cft.py` | Revisa que cada carpeta de docente tenga los documentos esperados (CT, IA, BH, CP) y genera un Excel de revisión. |

---

## Requisitos

- **Python 3.9+** (por `zoneinfo` en config).
- **Outlook** instalado y configurado (para scripts 1, 2 y 6).
- Estructura bajo `RAIZ`: carpetas **Año/Mes** con el Excel de solicitud y, tras la extracción, los XML/PDF.

Instalación de dependencias:

```bash
pip install -r requirements.txt
```

---

## Tests

Para ejecutar los tests de las funciones compartidas (`utils`):

```bash
python -m pytest tests/ -v
```

---

## Notas

- Cada script que modifica el Excel hace backup previo (ZIP) cuando usa `utils.backup_file`.
- Los logs se guardan en subcarpetas `logs_*` dentro de la carpeta del mes.
- El script 9 puede usar OCR (PyMuPDF, pdf2image, pytesseract) si están instalados; si no, trabaja solo por nombres de archivo.
