---
description: Exporta el desarrollo de esta sesión a notas atómicas de la wiki global
argument-hint: [repo opcional — por defecto se detecta el repo actual]
allowed-tools: Bash(__PYTHON__ "__TOOL_DIR__/cli.py" context export *), Bash(__PYTHON__ "__TOOL_DIR__/cli.py" sync push -m *), Read, Grep, Glob, Edit(/__DATA_DIR__/**)
---

## Contexto (generado automáticamente)

!`__PYTHON__ "__TOOL_DIR__/cli.py" context export "$ARGUMENTS"`

## Tu tarea

Documentar el desarrollo de esta sesión en la wiki global.

### 1. Resumir el desarrollo
Analiza la conversación y los cambios (git diff/log si hace falta): ¿qué se implementó, qué temas toca, hubo cambios de base de datos?

### 2. Crear notas atómicas (máximo 5)
Archivos en `atomic/` de la carpeta de datos (arriba), con nombre `YYYYMMDDHHMM_<descripción_del_tema>.md` (usa el ID generado arriba; si creas varias notas, incrementa el minuto para que cada ID sea único). El eje es el **tema**, no el repo.

**Tags del vocabulario controlado:** revisa `topics.json` (arriba) antes de etiquetar. Si el tema existe como canónico o alias, usa el canónico. Solo crea un topic nuevo si es genuinamente nuevo — y agrégalo a `topics.json` con sus aliases (incluye el otro idioma si aplica: `auth` ↔ `autenticación`).

```yaml
---
id: YYYYMMDDHHMM
created: YYYY-MM-DD HH:MM
type: endpoint | feature | discovery | bug_fix
status: stable | draft
tags: [del-vocabulario-de-topics.json]
scope: [repo]         # OPCIONAL, solo si la nota es claramente de un repo
ticket: PROJ-123      # si aplica
---

# Título claro

## Qué cambió
## API/Endpoints (si aplica — URL, method, inputs, outputs, auth)
## Database changes (si aplica)
## Decisiones técnicas / Conflictos (⚠️)
## Links
- Links to: [[YYYYMMDDHHMM_nombre]]
```

### 2.5. Enlazar hacia atrás, no sólo entre las notas de esta sesión
Arriba tienes la lista de notas que ya existen. **Léela antes de escribir**: el riesgo real no es que la nota quede huérfana, es que las notas de esta sesión se enlacen sólo entre sí y formen una isla sin puentes al resto de la wiki. Una isla densa es tan poco navegable como una nota suelta.

Si ninguna nota previa aparece como candidata obvia en esa lista, busca con Grep en la carpeta de datos el ticket y los tags/tema (ej. `PROJ-123` o `n+1`). Si aparece una nota existente que trata el mismo ticket, mismo bug/feature, o el mismo subsistema:
- Agrega un link real en formato `[[YYYYMMDDHHMM_scope_descripcion]]` (el **nombre completo del archivo sin extensión**). Ejemplo:
  - ❌ `[[202605110900]]` — Obsidian no lo resuelve (busca un archivo llamado exactamente `202605110900.md`, que no existe) y crea una nota fantasma vacía.
  - ❌ `[[202605110900]](202605110900_web_feat_....md)` — híbrido roto, tampoco resuelve.
  - ✅ `[[202605110900_web_feat_auth_jwt_refresh_technical_design]]` — el stem completo del archivo.
  - En `synthesis/` (donde también se linkea desde fuera de Obsidian, ej. GitHub) el patrón correcto es `[[stem_completo]](../atomic/stem_completo.md)` — ambas partes con el nombre completo.
- No fabriques la relación: solo enlaza si el contenido realmente se refiere a lo mismo (mismo ticket, mismo bug, o una nota que este desarrollo modifica/corrige/continúa). Compartir tags no basta por sí solo. **"Misma sesión" tampoco cuenta como justificación por sí sola.**
- Esto es lo que evita que la nota quede huérfana en el grafo de Obsidian — la nota atómica original nunca se edita retroactivamente para esto; el link se agrega ahora, al crear la nota nueva.

### 3. Actualizar synthesis/ e index.md
- Agrega/actualiza las entradas correspondientes en los synthesis por tema, siempre linkeando a las notas atómicas nuevas.
- Actualiza `index.md` con las notas nuevas.

### 4. Sincronizar
Al terminar, ejecuta:
```bash
__PYTHON__ "__TOOL_DIR__/cli.py" sync push -m "export: <resumen corto>"
```
Si el push falla por estar offline, avísale al usuario que quedó en local y que corra `/wiki-sync` cuando tenga conexión.

### Reglas de oro
- Notas atómicas y raw/ existentes = INMUTABLES. Nunca editarlas; si algo cambió, crea nota nueva que linkee a la vieja.
- Synthesis = siempre actualizar.
- Conflictos entre notas: márcalos con ⚠️ en synthesis, no los resuelvas tú.
