# 📋 Boletas de Honorarios — Sistema de Gestión Automatizado

**Proyecto:** Sistema de procesamiento automatizado de solicitud, recepción, validación, pago e informe de boletas de honorarios (BH).

**Plataforma:** Windows con Microsoft Outlook integrado | **Python 3.10+**

---

## 🚀 Inicio rápido

### Instalación

```bash
# Clonar el repositorio
git clone https://github.com/Derehckz/revisa_bh_st.git
cd revisa_bh_st

# Instalar dependencias
py -m pip install -r requirements.txt
```

### Configuración inicial

1. **Editar `config.py`**
   - Ajusta `RAIZ` a la carpeta base donde se guardarán los años/meses
   - Configura los emails de destino: `EMAIL_CONTABILIDAD`, `EMAIL_XML_1`, `EMAIL_XML_2`
   - Define fechas límite de recepción: `ULT_FECHA_RECEPCION`, `HORARIO_RECEPCION`

2. **Preparar carpeta base**
   ```
   RAIZ/
     ├── 2024/
     │   ├── Enero/
     │   │   └── Solicitud.xlsx  (archivo principal de cada mes)
     │   └── ...
     ├── 2025/
     └── 2026/
   ```

---

## 📁 Estructura del proyecto

```
.
├── main.py                                 # Orquestador principal (ejecutar scripts en orden)
├── config.py                               # Configuración centralizada
├── utils.py                                # Utilidades compartidas
├── email_templates.py                      # Plantillas HTML de correos (NUEVO)
├── outlook_utils.py                        # Conexión y utilidades de Outlook
│
├── 1.-envia_correo_mensual_bh.py           # Envío de correos de solicitud
├── 2.-extrae_xml_correo.py                 # Extracción de adjuntos XML/PDF
├── 3.-revisa_solicitud_VS_recibidas.py     # Validación vs archivos recibidos
├── 4.-extrae_datos_xml_al_excel.py         # Extracción de datos XML → Excel
├── 5.-Enviar_Correo_Recepcion.py           # Confirmación de recepción (NUEVO)
├── 6.-Informe_final_boletas.py             # Generación de informe final
├── 7.-Envia_mail_pagos.py                  # Envío de información de pagos
├── 8.-separa_bh_ip_cft.py                  # Separación BH por institución
├── 9.-agrupa_por_docente.py                # Agrupación por docente
├── 10.-revisa_carpetas_ip_cft.py           # Revisión de carpetas IP/CFT
│
├── requirements.txt
├── README.md                               # Este archivo
└── tests/                                  # Pruebas unitarias (opcional)
```

---

## 🔄 Pipeline de ejecución

### Flujo completo recomendado

| Paso | Script | Propósito | Input | Output |
|------|--------|-----------|-------|--------|
| **1** | `1.-envia_correo_mensual_bh.py` | 📧 Solicitud de boletas | `Solicitud.xlsx` | Correos enviados; Excel actualizado |
| **2** | `2.-extrae_xml_correo.py` | 📥 Extrae adjuntos de Outlook | Rango de fechas | XML/PDF en carpeta mes |
| **3** | `3.-revisa_solicitud_VS_recibidas.py` | ✅ Valida recepción | `Solicitud.xlsx` + archivos | Estado: RECIBIDO/NO RECIBIDO/ERROR |
| **4** | `4.-extrae_datos_xml_al_excel.py` | 📊 Llena datos desde XML | XML files | Datos extraídos en Excel |
| **5** | `5.-Enviar_Correo_Recepcion.py` | 📧 Confirma recepción | `Solicitud.xlsx` filtrado | Correos de confirmación |
| **6** | `6.-Informe_final_boletas.py` | 📑 Resumen para pago | `Solicitud.xlsx` | Hoja "Resumen Boletas" |
| **7** | `7.-Envia_mail_pagos.py` | 💳 Informa sobre pagos | Hoja "Pagos" | Correos con detalles de deposito |
| **8** | `8.-separa_bh_ip_cft.py` | 📂 Organiza por institución | Archivos BH | Carpetas IP/CFT |
| **9** | `9.-agrupa_por_docente.py` | 👤 Organiza por docente | Archivos IP/CFT | Subcarpetas por docente |
| **10** | `10.-revisa_carpetas_ip_cft.py` | 🔍 Validación final | Carpetas IP/CFT | Reporte de errores |

---

## 💡 Características principales

### ✨ Plantillas de correos centralizadas
- **Archivo nuevo:** `email_templates.py`
- Todas las plantillas HTML de correos se definen en un único módulo
- Fácil edición de contenido sin tocar los scripts de envío
- **Funciones disponibles:**
  - `generar_asunto_solicitud()` / `generar_cuerpo_solicitud()` → Correos de solicitud y recordatorios
  - `generar_asunto_recepcion()` / `generar_cuerpo_recepcion()` → Confirmación de recepción
  - `generar_asunto_pago()` / `generar_cuerpo_pago()` → Información de pagos

### 🛡️ Modo de prueba seguro
- Scripts de correo (`1`, `5`, `7`) incluyen modo `--test` o input interactivo
- **Modo prueba:** Previsualiza correos sin enviar ni modificar Excel
- Ideal para validar contenido antes de envío real

### 🔐 Logging mejorado
- **UTF-8 habilitado** en todos los handlers (console + archivo)
- Emojis se renderan correctamente en Windows (cp1252 → utf-8)
- Logs en: `año/mes/logs_*/` (ej. `2026/Abril/logs_envio_recepcion/`)

### 📧 Outlook integrado
- Conexión automática a Outlook COM
- Extracción de adjuntos con filtros por fecha
- Envío de correos con formato HTML enriquecido
- Manejo de CC/BCC automático

### 🗂️ Selección inteligente de año/mes
- Excluye automáticamente carpetas de sistema (`.git`, `__pycache__`, `.`)
- Selector interactivo con soporte para navegación
- Validación de estructura esperada

---

## 🔧 Uso avanzado

### Ejecutar desde `main.py`
```bash
# Ejecutar todo el pipeline interactivamente
py main.py

# Ejecutar script específico (1-10)
py main.py --script 1
```

### Ejecutar script individual
```bash
# Ejemplo: Envío de correos de solicitud
py "1.-envia_correo_mensual_bh.py"

# Ejemplo: Extracción de XML con modo prueba
py "5.-Enviar_Correo_Recepcion.py"
```

### Modo debug
Los scripts generan logs detallados en:
```
RAIZ/Año/Mes/logs_*/
  ├── envio_recepcion.log
  ├── envio_pagos.log
  └── ...
```

---

## 📋 Archivos principales

### `config.py`
Centro de configuración del proyecto. Ajusta aquí:
- Rutas base (`RAIZ`, `CARPETA_BASE`)
- Emails destinatarios
- Fechas y horarios límite
- Prefijos de archivos
- Zona horaria

### `utils.py`
Funciones compartidas:
- `seleccionar_opcion()` → Selector interactivo en consola
- `validar_email()` → Validación de direcciones de correo
- `normalizar_rut()` → Formato RUT estándar
- `backup_file()` → Copia de seguridad automática
- `listar_carpetas()` → Listar años/meses excluyendo directorios de sistema
- `configurar_logging()` → Setup de logging con RichHandler
- `asegurar_utf8_salida()` → Fuerza UTF-8 en stdout/stderr (Windows)

### `email_templates.py` (NUEVO)
Plantillas centralizadas de HTML para correos:
```python
# Uso en scripts:
asunto = templates.generar_asunto_solicitud(tipo, mes, año, rut, nombre)
cuerpo = templates.generar_cuerpo_solicitud(
    tipo, nombre_completo, rut_docente, ..., monto, ...
)
```

### `outlook_utils.py`
Gestión de Outlook:
- `conectar_outlook_app()` → Conexión COM a Outlook
- `conectar_outlook_ns()` → Acceso MAPI namespace
- `filtrar_correos_por_fecha()` → Filtrado de correos en rango

---

## 📦 Dependencias

```
pandas==3.0.2              # Manipulación de datos y Excel
openpyxl==3.1.5            # Lectura/escritura de .xlsx
rich==13.9.4               # Output rich en terminal
colorama==0.4.6            # Colores en Windows
tqdm==4.67.0               # Barras de progreso
pywin32==311                # COM de Outlook (Windows)
pytest==8.3.3              # Tests (opcional)
```

---

## ⚙️ Requisitos del sistema

- **SO:** Windows (Outlook COM requerido)
- **Python:** 3.10+
- **Outlook:** Instalado y configurado con al menos una cuenta
- **Excel:** 2007+ (.xlsx)

---

## 🧪 Testing y validación

### Modo de prueba para correos
```bash
# Script 1: Solicitud
py "1.-envia_correo_mensual_bh.py"
# → Ofrece opción de previsualizar sin enviar

# Script 5: Recepción
py "5.-Enviar_Correo_Recepcion.py"
# → Modo de prueba: solo muestra primer registro

# Script 7: Pagos
py "7.-Envia_mail_pagos.py"
# → Previsualiza antes de enviar
```

### Validar sintaxis
```bash
py -m py_compile *.py email_templates.py
```

---

## 🐛 Troubleshooting

### Error: "No se puede conectar a Outlook"
- Verifica que Outlook esté abierto
- Asegúrate de tener una sesión iniciada en Outlook

### Error: `UnicodeEncodeError` en logs
- ✅ **Ya solucionado:** UTF-8 habilitado en `utils.py` y `outlook_utils.py`
- Los emojis se renderizan correctamente en Windows

### Archivo Excel bloqueado
- Cierra el archivo antes de ejecutar
- El script automáticamente hace backup antes de sobrescribir

### Carpetas año/mes no detectadas
- Verifica que `RAIZ` sea accesible
- Asegúrate que las carpetas tengan nombres válidos (solo año numérico, ej. `2026`)

---

## 📝 Notas de desarrollo

- Cada script es independiente pero depende de la estructura de carpetas y Excel
- Los cambios en `config.py` se aplican a todos los scripts
- Los logs incluyen timestamps y niveles de severidad
- El código usa type hints y docstrings en Python 3.10+

---

## 🚧 Futuras mejoras

- [ ] API REST para envío remoto
- [ ] Base de datos (SQLite) en lugar de Excel
- [ ] Interfaz web (Flask/FastAPI)
- [ ] Soporte para otros clientes de correo (Gmail, Exchange)
- [ ] Templates personalizables desde archivo

---

## 📄 Licencia

Proyecto interno. Todos los derechos reservados.

---

**Última actualización:** Abril 2026 | **Versión del sistema:** 2.0 (con plantillas centralizadas y logging UTF-8)
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
