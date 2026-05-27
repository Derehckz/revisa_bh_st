# Contrato CLI-first (scripts de etapas)

Los scripts en `etapas/` y `main.py` son la **interfaz operativa principal** del sistema.
El frontend y la API son **clientes opcionales** de la misma lógica Python.

Este documento es la regla de evolución del proyecto: **nada en la web puede romper la consola**.

---

## Reglas obligatorias

1. **Entrypoint permanente**  
   Cada etapa conserva su archivo `etapas/N.-*.py` ejecutable con:
   ```bash
   python etapas/N.-nombre.py --help
   python main.py --year 2026 --month Mayo --start-from N --end-at N
   ```

2. **Sin dependencia del frontend**  
   Los scripts no importan FastAPI, React, WebSockets ni código de `api/` o `frontend/`.
   La API, si usa lógica compartida, importa desde `lib/` o invoca el mismo entrypoint CLI — nunca al revés.

3. **Flags CLI estables**  
   No se renombran ni eliminan argumentos existentes sin compatibilidad (alias o deprecación documentada).
   Los flags nuevos son opcionales.

4. **Modo interactivo por defecto**  
   Sin `--yes` / sin `BH_NON_INTERACTIVE`, el comportamiento interactivo en terminal se mantiene.
   La web usa adaptadores o flags explícitos (`--send`, etc.), no sustituye el script.

5. **Migración a `lib/stages/`**  
   Si se extrae lógica a módulos compartidos, el script en `etapas/` sigue siendo el wrapper oficial:
   parsea `argparse` → construye contexto → llama al servicio con `CLIAdapter`.
   La API reutiliza el **mismo servicio**, no un fork distinto.

6. **Dos caminos en API (transición)**  
   - Jobs subprocess + log: etapas aún no migradas a sesión interactiva.  
   - Sesión WebSocket: etapas migradas, misma lógica in-process.  
   En ambos casos la consola directa (`python etapas/...`) sigue disponible y probada.

7. **Pruebas de regresión CLI**  
   `tests/test_cli_entrypoints.py` verifica que cada script responde a `--help` sin error.
   Cualquier PR que toque `etapas/` o `lib/stages/` debe pasar esos tests.

---

## Lo que NO haremos

- Eliminar scripts de `etapas/` “porque ya está la web”.
- Mover lógica de negocio solo a `api/` o solo al frontend.
- Hacer obligatorio levantar uvicorn para ejecutar un mes en producción.
- Cambiar el comportamiento por defecto del CLI sin test que lo documente.

---

## Checklist para cambios en una etapa

- [ ] `python etapas/X.-....py --help` funciona.
- [ ] `python main.py` puede invocar la etapa X (si aplica al tramo).
- [ ] Modo interactivo probado manualmente o con test de humo documentado.
- [ ] `pytest tests/test_cli_entrypoints.py` en verde.
- [ ] README / RUNBOOK actualizados solo si cambian flags o flujo visible.

---

## Sesión web vs script CLI

- `python etapas/1.-envia_correo_mensual_bh.py` sigue siendo el entrypoint oficial.
- La web usa `lib/stages/stageN/service.py` con `WebAdapter` (misma lógica).
- Etapas con servicio en `lib/stages/stageN/`: **1–4**, **5**, **7** (misma lógica CLI + web; 5/7 con `per_mail`).
- Etapas **0, 6, 8–10** usan *bridge* (`utils_bridge` + script legacy); la web supervisa vía WebSocket.
- En web **no** se envían correos en 5/7 (`send` bloqueado); envío real solo por consola con `--send`.
- El modo job (`POST /operations/stages/N/start`) es opcional y no reemplaza el script.

## Referencia

- Orquestador: `main.py`
- Catálogo de etapas: `lib/pipeline_stages.py`
- Comandos API (subprocess): `lib/stage_commands.py`
- UI terminal: `lib/terminal_ui.py`
