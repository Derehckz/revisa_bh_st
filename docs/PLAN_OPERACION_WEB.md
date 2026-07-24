# Plan de Operación Web (pasos 0–4)

**Producto:** Boletas Honorarios  
**Audiencia:** usuario de oficina (Excel + Outlook), no técnico  
**Objetivo:** que el cierre mensual se haga con **un botón claro por paso**, sin cacería de confirms ni F5.

---

## 1. Problemas observados (conversación real)

| Dolor | Efecto en el usuario |
|-------|----------------------|
| Confirms uno por uno / muchos “Continuar” | Proceso engorroso; parece que el sistema no confía |
| Correos con idempotencia sin explicación | “Omitido…” confunde; no sabe si falló |
| Excel “termina” en log pero no se guarda hasta el último Sí | Cree que falló; reabre Excel vacío de cambios |
| Sesión activa / 409 / WebSocket caído (int64) | “Apreto Sí y no pasa nada” |
| Paso 2 no toca Excel (solo PDF/XML) | Busca cambios en el Excel y no los ve |
| Hay que F5 para ver estados/KPIs | No se siente una app moderna |
| Jerga: sesión, job, dry-run, idempotencia, hoja | Barrera para usuario normal |
| Dos caminos (supervisado vs modo rápido) | No sabe cuál es “el” correcto |

---

## 2. Principios del sistema profesional

1. **Un CTA primario por paso** (ver tabla abajo).
2. **Defaults inteligentes** — carpeta/mes/Excel/hoja ya resueltos; opciones avanzadas ocultas.
3. **Confirmar solo lo irreversible** — envío real de correo; sobrescribir datos ya OK.
4. **Guardar la planilla automáticamente** en pasos 3 y 4 (con backup existente).
5. **Progreso visible** — “listo / en curso / falta X” sin leer logs.
6. **Recuperación** — Retomar o Cancelar sesión en *todos* los pasos.
7. **Lenguaje de oficina** — nada de IDs hex ni términos de consola en la UI principal.
8. **Una sola vía recomendada** — el modo job/rápido queda como “Avanzado”.

### Happy path (CTA)

| Paso | CTA | Resultado esperado |
|------|-----|--------------------|
| 0 | Generar Solicitud del mes | `Solicitud.xlsx` listo |
| 1 | Enviar solicitudes (o Solo vista previa) | Correos enviados / simulados |
| 2 | Bajar boletas del mes | PDF+XML en carpeta del mes |
| 3 | Marcar recibidos en la planilla | Excel actualizado y guardado |
| 4 | Completar datos desde las boletas | Columnas XML en Excel guardado |

---

## 3. Reglas técnicas

- Parámetro web `streamlined=true` (default en API interactiva): omite confirms redundantes (Continuar / Procesar) y **auto-guarda Excel** en 3/4.
- Envío real (paso 1/5/7): **sí** exige confirmación explícita de producción.
- `supervision_mode=batch` por defecto en envíos.
- Al terminar sesión: invalidar overview / jobs / options / boletas (sin F5).
- Payloads WebSocket siempre JSON-safe (sin `numpy.int64`).
- Sesión trabada: banner Retomar / Cancelar en paneles 0–4.

---

## 4. Backlog

### Hecho / en curso (esta entrega)

- [x] Auto-refresh UI (polling + invalidate al terminar sesión)
- [x] Batch send + fix WS int64
- [x] `streamlined` backend pasos 1–4
- [x] Auto-guardar Excel 3/4 (sin confirm extra en web)
- [x] Banner sesión activa en paneles 1–4
- [x] Copy/CTA de oficina + opciones avanzadas
- [x] Resumen de éxito con “Ir al siguiente paso”
- [x] Plan documentado en este archivo

### P1 (siguiente)

- [ ] Auto-attach de sesión pendiente al abrir el paso
- [ ] Stepper visual Analizando → Guardando → Listo
- [ ] Log detrás de “Ver detalle”
- [ ] Un solo confirm de período por sesión (no por cada click)

### P2

- [ ] Unificar completamente job vs sesión en una sola experiencia
- [ ] Toggle explícito “revisar correo a correo” (power user)

---

## 5. Criterios de aceptación (usuario normal)

1. Cierra Julio 0→4 sin F5 y sin reabrir Excel “a ver si guardó”.
2. En paso 3/4, al terminar, `Solicitud.xlsx` ya tiene los cambios (cerrado en Excel durante el guardado).
3. Si queda una sesión a medias, ve “Continuar lo pendiente” / “Cancelar y empezar de nuevo”.
4. Entiende el botón principal sin leer documentación técnica.
5. Envío real sigue pidiendo un “sí, estoy enviando a producción”.

---

## UI compacta (julio 2026)

- Pantalla Operación: mes + sugerencia + lista corta de pasos + un panel de acción.
- Sin “modo job” duplicado en Ejecutar; bitácora/historial detrás de detalles.
- Sidebar con nombres cortos (Generar Solicitud, Enviar correos, …).
- Paso 1: plazos/Excel bajo “Opciones”.
