---
name: wiki-export
description: Compila y exporta el desarrollo técnico y decisiones de esta sesión a notas atómicas inmutables en la wiki personal, y actualiza los resúmenes compilados (synthesis/ e index.md).
---

# Wiki Export — Documentar Desarrollo

Documenta el desarrollo, features, bug fixes o descubrimientos de esta sesión en la base de conocimiento global.

## Pasos

1. **Obtener contexto y configuración:**
   - Lee `~/.config/context-wiki/config` (o `~/.config/llm-wiki/config`) para conocer `TOOL_DIR` y `DATA_DIR`.
   - Sincroniza cambios previos si aplica: `"${PYTHON:-python3}" "$TOOL_DIR/cli.py" sync pull`.
   - Revisa las notas existentes más recientes para enlazar hacia atrás:
     ```bash
     bash -c 'source ~/.config/context-wiki/config 2>/dev/null || source ~/.config/llm-wiki/config; "${PYTHON:-python3}" "$TOOL_DIR/cli.py" titles 6000'
     ```
   - Revisa el vocabulario controlado de topics en `$DATA_DIR/topics.json`.

2. **Resumir el desarrollo:**
   Analiza la conversación y los cambios realizados en el código (git diff/log si aplica): ¿qué se implementó, qué temas toca, hubo cambios de base de datos o contratos de API?

3. **Crear nota(s) atómica(s) (máximo 5):**
   - Genera el ID y nombre con:
     ```bash
     bash -c 'source ~/.config/context-wiki/config 2>/dev/null || source ~/.config/llm-wiki/config; "${PYTHON:-python3}" "$TOOL_DIR/cli.py" new-id <descripcion_del_tema>'
     ```
   - Crea el archivo en `$DATA_DIR/atomic/YYYYMMDDHHMM_<descripcion>.md`.
   - El eje es el **tema**, no el repo.
   - **Tags:** usa tags del vocabulario controlado en `topics.json`. Si es un topic genuinamente nuevo, agrégalo a `topics.json` con sus aliases.
   - Formato requerido:
     ```yaml
     ---
     id: YYYYMMDDHHMM
     created: YYYY-MM-DD HH:MM
     type: endpoint | feature | discovery | bug_fix
     status: stable | draft
     tags: [del-vocabulario-de-topics.json]
     scope: [repo]         # opcional
     ticket: PROJ-123      # si aplica
     ---

     # Título claro

     ## Qué cambió
     ## API/Endpoints (si aplica — URL, method, inputs, outputs, auth)
     ## Database changes (si aplica)
     ## Decisiones técnicas / Conflictos (⚠️)
     ## Links
     - Links to: [[YYYYMMDDHHMM_nombre_completo]]
     ```

4. **Enlazar hacia atrás (Prevenir islas):**
   - Conecta la nueva nota con al menos 1 nota existente previa relevante usando su stem completo: `[[YYYYMMDDHHMM_stem_completo]]`.
   - No enlaces únicamente notas de la misma sesión si no hay continuidad temática.
   - Si no hay candidatas obvias en `titles`, busca con `"${PYTHON:-python3}" "$TOOL_DIR/cli.py" search "<ticket o tema>"`.

5. **Actualizar synthesis/ e index.md:**
   - Actualiza los resúmenes compilados correspondientes en `$DATA_DIR/synthesis/` linkeando a las notas nuevas.
   - Actualiza `$DATA_DIR/index.md` con las nuevas notas.

6. **Sincronizar:**
   Ejecuta:
   ```bash
   bash -c 'source ~/.config/context-wiki/config 2>/dev/null || source ~/.config/llm-wiki/config; "${PYTHON:-python3}" "$TOOL_DIR/cli.py" sync push -m "export: <resumen corto>"'
   ```
   Si el push falla por estar offline, informa al usuario que quedó en local.

## Reglas de Oro
- **Notas atómicas y raw/ = INMUTABLES.** Jamás se editan una vez creadas; si algo cambió, crea una nota nueva que enlace a la vieja.
- **Synthesis = SIEMPRE ACTUALIZAR.**
- **Conflictos = MARCAR (⚠️)**, no resolver por cuenta propia.
