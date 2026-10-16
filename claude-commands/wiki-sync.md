---
description: Sincroniza la wiki global con GitHub (pull + commit + push)
argument-hint: [pull | push | full (default)]
allowed-tools: Bash(__PYTHON__ "__TOOL_DIR__/cli.py" context sync *), Read, Grep, Glob, Edit(/__DATA_DIR__/**)
---

## Resultado del sync

!`__PYTHON__ "__TOOL_DIR__/cli.py" context sync "$ARGUMENTS"`

## Tu tarea

Reporta al usuario el resultado del sync de arriba en una línea o dos. Si falló el pull o el push (offline, conflicto de rebase, auth), explica qué pasó y qué hacer:
- **Offline:** los cambios quedan en local, reintentar `/wiki-sync` con conexión.
- **Conflicto de rebase:** casi siempre es en `synthesis/` o `index.md` (las notas atómicas nunca chocan porque son inmutables y con ID único). Resuélvelo tú: revisa `git -C <carpeta de datos> status`, edita los archivos en conflicto fusionando ambas versiones, y completa con `git rebase --continue` + push.
- **Auth:** verifica `gh auth status` o las llaves SSH.
