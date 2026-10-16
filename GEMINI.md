# GEMINI.md — Herramienta de wiki de contexto

> Aplica cuando Google Antigravity o Gemini trabajan en la wiki.
> Ver directrices canónicas completas en [AGENTS.md](AGENTS.md).

## Reglas Principales

1. **Notas atómicas = INMUTABLES**: Archivos bajo `DATA_DIR/atomic/` con nombre `YYYYMMDDHHMM_<tema>.md`. Jamás se editan; cambios generan notas nuevas enlazando a las anteriores.
2. **Synthesis = SIEMPRE ACTUALIZAR**: Mantener actualizados los resúmenes compilados en `DATA_DIR/synthesis/` e `index.md`.
3. **raw/ = SOLO LECTURA**: Fuentes originales de verdad.
4. **Vocabulario controlado**: Tags siempre validados contra `DATA_DIR/topics.json`.
5. **Enlazar hacia atrás**: Toda nota nueva debe enlazar con al menos una nota previa relevante (ver `python3 cli.py titles`).
6. **Skills disponibles**: `wiki-load`, `wiki-export`, `wiki-sync`, `wiki-status`, `wiki-lint`.
