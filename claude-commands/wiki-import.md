---
description: Importa conversaciones históricas de Claude Code (todos los perfiles y repos) como notas atómicas
argument-hint: [repo | all (default)] [max sesiones por repo, default 10]
allowed-tools: Bash(__PYTHON__ "__TOOL_DIR__/cli.py" context import *), Bash(__PYTHON__ "__TOOL_DIR__/cli.py" sync push -m *), Read, Grep, Glob, Edit(/__DATA_DIR__/**), Agent
---

## Extracción (generada automáticamente)

!`__PYTHON__ "__TOOL_DIR__/cli.py" context import "$ARGUMENTS"`

## Tu tarea

Orquestar la conversión de los resúmenes de sesiones (`raw/sessions_*.md`) en notas atómicas. **No proceses los archivos tú mismo** — cada uno puede ser largo y llenaría tu contexto.

1. Lista los archivos `raw/sessions_*.md` generados arriba (Glob en la carpeta de datos).
2. **Lanza UN agente `wiki-session-processor` por archivo, todos en paralelo** (una sola tanda de llamadas a la herramienta Agent). Cada prompt debe incluir:
   - El path completo del archivo `sessions_*.md` a procesar.
   - El path de la carpeta de datos (mostrada arriba).
3. Cada agente devuelve solo: notas creadas, temas omitidos por duplicado, y topics nuevos propuestos (si necesitó alguno que no está en `topics.json`).
4. Con los resultados de TODOS los agentes:
   - Actualiza `topics.json` con los topics genuinamente nuevos (canónico + aliases; si dos agentes propusieron sinónimos, unifícalos en un solo grupo).
   - Actualiza `synthesis/` e `index.md` con las notas nuevas (esto lo haces tú, que tienes la visión global — los agentes no tocan synthesis ni topics).
5. Muéstrale al usuario un resumen: cuántas notas por repo, qué se omitió por duplicado, qué archivos no produjeron nada.
6. Sincroniza:
```bash
__PYTHON__ "__TOOL_DIR__/cli.py" sync push -m "import: sesiones históricas"
```

Reglas de oro: notas atómicas existentes son INMUTABLES; los archivos `raw/sessions_*.md` quedan como fuente (no los borres ni edites).
