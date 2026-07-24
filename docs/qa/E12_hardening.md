# QA — Épica E12 — Hardening

## 1. API key: eliminar valor por defecto que autentica en silencio

### Problema
`frontend/src/app/app-config.tsx` usaba, como *fallback* cuando no había nada
en `localStorage`:

```ts
const defaultApiKey = localStorage.getItem("bh_api_key") || "boletas_api_local_2026_change_me";
```

Ese valor de ejemplo (copiado de la documentación/`.env.example`) quedaba
"funcionando en silencio" para cualquier instalación que no hubiera cambiado
`BH_API_KEY` en el backend — es decir, el frontend autenticaba exitosamente
contra un backend mal configurado sin que nadie lo notara, y cualquier persona
con el código fuente podía adivinar la key por defecto.

### Cambio
```ts
// E12: nunca cachear una API key "por defecto" que funcione en silencio. Si no
// hay nada guardado en localStorage, arranca vacía y obliga a configurarla en
// Ajustes; evita que un valor de ejemplo del repo termine autenticando en prod.
const defaultApiKey = localStorage.getItem("bh_api_key") || "";
```

- Si el usuario nunca configuró una key, el frontend arranca con
  `apiKey === ""`.
- Todas las llamadas autenticadas (`usePeriods`, `useHealth` no la requiere,
  etc.) fallarán con 401/503 de forma visible, y la pantalla de
  **Configuración** (`frontend/src/features/settings/page.tsx`) ya muestra el
  estado de conectividad (`ErrorState` + bloque "Conectividad API key") para
  guiar al usuario a pegar su key real.
- `setApiKey(...)` sigue guardando en `localStorage` igual que antes: una vez
  configurada, persiste entre sesiones del navegador.
- No se tocó `.env.example` (`BH_API_KEY=define_una_clave_larga_y_unica`) ni
  `api/security.py` (que ya rechaza con 503 si el backend no tiene ninguna key
  configurada, y con 401 si la key no coincide) — el hardening es puramente
  del lado del cliente, para no esconder un backend mal configurado.

### QA
- [ ] Borrar `localStorage` (`bh_api_key`) y recargar el frontend → el campo
      "x-api-key" en Configuración aparece vacío, no con un valor mágico.
- [ ] Sin key configurada, cualquier pantalla que dependa de datos
      autenticados muestra el estado de error (no un 200 silencioso).
- [ ] Pegar la key real del backend en Configuración → guarda en
      `localStorage` y las pantallas cargan datos con normalidad.
- [ ] Backends nuevos que no cambiaron `BH_API_KEY` del `.env.example` ya no
      pueden ser "usados sin querer" solo porque el frontend trae una key
      hardcodeada que coincide.

## 2. Cobertura de tests para `lib/mail_ledger.py`

`lib/mail_ledger.py` es la fachada única de correo (outbox + idempotencia) que
usan las etapas 1/5/7 para no reenviar correos duplicados. No tenía tests
propios (solo cobertura indirecta vía `idempotency_store`/`email_outbox`).

Se agregó `tests/test_mail_ledger.py` (usa el fixture `bh_raiz_tmp` de
`tests/conftest.py`, que aísla `config.RAIZ` en un directorio temporal para no
tocar el estado SQLite real del proyecto):

- `was_sent` devuelve `False` por defecto para una clave nunca marcada.
- `mark_sent` + `was_sent` → `True` tras marcar.
- El estado está *scoped* por `(stage, item_key)`: marcar `stage5/docente-1`
  no afecta a `stage7/docente-1` ni a `stage5/docente-2`.
- `clear_sent` revierte una marca de éxito (permite forzar reenvío puntual).
- `record_pending` + `mark_outbox_sent` reflejan cambios en
  `stats_by_status()`.

### QA
- [ ] `pytest tests/test_mail_ledger.py -q` → 5 passed.
- [ ] Los tests no dejan artefactos fuera de `tmp_path` (usan
      `bh_raiz_tmp`, que apunta `config.RAIZ` a un directorio temporal).

## Regresión general
- [ ] `pytest tests/ -q` — sin nuevas fallas atribuibles a este cambio (ver
      nota abajo sobre un fallo preexistente no relacionado).
- [ ] `npx tsc --noEmit -p frontend/tsconfig.app.json` — sin nuevos errores en
      `app-config.tsx`.

### Nota sobre fallo preexistente no relacionado
Al correr la suite completa aparece 1 falla en
`tests/test_stage5_stage7_service.py::TestStageContexts::test_stage5_modo_prueba_confirm_not_inverted`,
reproducible también sin ninguno de los cambios de E3/E5/E6/E11/E12 (viene de
una sesión de trabajo previa, relacionada con un `MagicMock` sin resolver en
`resolve_año_mes` al escribir un Excel de prueba). No se tocó ese archivo en
esta pasada; se deja registrado para una épica de limpieza de tests aparte.

## Veredicto
PASS — cambio de frontend de una línea + doc, respaldado por
`tests/test_mail_ledger.py` (5/5 verdes).
