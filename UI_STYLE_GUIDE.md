# Guía de Estilo UI/UX Terminal - Suite Boletas de Honorarios

## 1. Uso de Bibliotecas

**Librería Principal**: `rich` (para toda la interfaz de usuario)
**Librería Secundaria**: `colorama` (inicialización - NO usar después)
**Importar**:
```python
import config
import utils
# Listo, utils ya tiene todo lo que necesitas
```

## 2. Convenciones de Color y Emoji

| Situación | Color | Emoji | Función utils |
|-----------|-------|-------|----------------|
| Encabezado | Cyan + Bold | 🚀 | `print_header()` |
| Paso numerado | Yellow + Bold | [N/M] | `print_step()` |
| Información | Cyan | ℹ️ | `print_info()` |
| Éxito | Green | ✅ | `print_success()` |
| Advertencia | Yellow | ⚠️ | `print_warning()` |
| Error | Red | ❌ | `print_error()` |
| Confirmación | Cyan + Bold | 🤖 | `print_confirm()` |
| Progreso | Blue | ⏳ | `print_progress_status()` |

## 3. Funciones Disponibles en utils.py

### Encabezados y Títulos
```python
utils.print_header(title, subtitle=None)
# Crea un panel con estilo corporativo para inicio de proceso
```

### Mensajes Estructurados
```python
utils.print_step(step_num, total, message)     # [N/M] Mensaje
utils.print_info(message)                       # ℹ️ Información contextual
utils.print_success(message)                    # ✅ Éxito
utils.print_warning(message)                    # ⚠️ Advertencia
utils.print_error(message)                      # ❌ Error
utils.print_progress_status(message)            # ⏳ Estado en progreso
```

### Entrada de Usuario
```python
utils.prompt_required(prompt_text, default="")     # Solicita valor obligatorio
utils.prompt_optional(prompt_text, default="")     # Solicita valor opcional
utils.print_confirm(message, default=False)        # Pide confirmación sí/no
utils.seleccionar_opcion(lista, mensaje, icono)    # Selector interactivo con numeración
```

### Tablas y Listas
```python
utils.print_table(title, rows)                  # rows = [(clave, valor), ...]
utils.print_list(title, items)                  # items = [string, ...]
utils.console.print(Panel.fit(...))             # Acceso directo a Console si es necesario
```

### Utilidades
```python
utils.print_separator(char="─", width=80)       # Dibuja línea separadora
utils.print_blank()                              # Línea vacía
utils.console.input("[cyan]Prompt: [/]")        # Input directo si es necesario
utils.console.status(msg, spinner="dots")       # Barra de progreso con spinner
```

## 4. Patrones Recomendados

### Inicio de Script
```python
import config
import utils

def main():
    utils.print_header("NOMBRE DEL PROCESO", "Breve descripción")
    utils.print_step(1, 5, "Validando archivos...")
    # ... lógica ...
    utils.print_success("Paso 1 completado")
```

### Solicitud de Año/Mes
```python
# Usar la función centralizada
año, mes = utils.seleccionar_año_mes(config.RAIZ)
ruta_mes = os.path.join(config.RAIZ, año, mes)
```

### Errores Graves
```python
if not condition:
    utils.print_error("Descripción del error")
    return 1
```

### Flujo de Confirmación
```python
if utils.print_confirm("¿Deseas continuar?"):
    # ejecutar acción
    utils.print_success("Acción realizada")
else:
    utils.print_warning("Operación cancelada")
```

### Mostrar Tabla de Resultados
```python
resultado = [
    ("Campo 1", "Valor 1"),
    ("Campo 2", "Valor 2"),
]
utils.print_table("Título de Tabla", resultado)
```

## 5. NO Hacer - Antipatrones

❌ **No mezclar librerías**:
```python
# ❌ MAL
print(f"{Fore.GREEN}✅ OK{Style.RESET_ALL}")
console.print("[green]✅ OK[/green]")

# ✅ BIEN
utils.print_success("OK")
```

❌ **No crear Consoles nuevas**:
```python
# ❌ MAL
from rich.console import Console
console = Console()

# ✅ BIEN
utils.console.print(...)
```

❌ **No duplicar código de selección**:
```python
# ❌ MAL
años = os.listdir(raiz)
año = input("Seleccione: ")

# ✅ BIEN
año, mes = utils.seleccionar_año_mes(config.RAIZ)
```

## 6. Compatibilidad y Versiones

- Python 3.10+
- `pandas==3.0.2`
- `openpyxl==3.1.5`
- `rich==13.9.4`
- `colorama==0.4.6`
- `tqdm==4.67.0` (para barras de progreso en bucles)

## 7. Ejemplos de Scripts Refactorizados

Revisa `0.-generar_solicitud.py` como ejemplo completo de un script que sigue esta guía.

---
**Última actualización**: 29 de abril de 2026
