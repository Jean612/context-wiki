#!/usr/bin/env bash
# install.sh — Instala/actualiza la wiki de contexto en esta máquina.
#
# La herramienta (este CLI) y los datos (tus notas) van en carpetas separadas.
# Por default la wiki es LOCAL: no se sube a ningún lado hasta que ejecutes
# `cli.py publish <url>`.
#
# Uso (máquina nueva):
#   git clone <repo-de-la-herramienta> ~/code/context-wiki
#   bash ~/code/context-wiki/install.sh
#
# Uso (actualizar): volver a ejecutarlo. Es idempotente.
#
# Variables opcionales:
#   WIKI_DATA_DIR    Carpeta de datos (default: se pregunta)
#   WIKI_PROJECT_DIR Carpeta donde viven tus repos (default: se pregunta)
#   WIKI_CLONE_DIR   Dónde clonar, si WIKI_DATA_DIR es una URL (default: se pregunta)
#   WIKI_CLAUDE_DIRS Lista separada por ':' de config dirs de Claude Code

set -euo pipefail

TOOL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_DIR="$HOME/.config/context-wiki"
CONFIG_FILE="$CONFIG_DIR/config"
LEGACY_CONFIG="$HOME/.config/llm-wiki/config"

# --check-updates: lo corre el hook de SessionStart. Mira si hay commits
# nuevos y lo dice; no baja ni ejecuta nada. `fetch` no toca el working tree,
# así que el código que alguien publique sólo corre cuando pedís el update a
# mano. Es la diferencia entre avisar y ejecutar por tu cuenta.
if [[ "${1:-}" == "--check-updates" ]]; then
  git -C "$TOOL_DIR" fetch --quiet 2>/dev/null || exit 0
  nuevos="$(git -C "$TOOL_DIR" rev-list --count HEAD..@{u} 2>/dev/null || echo 0)"
  if [[ "${nuevos:-0}" -gt 0 ]]; then
    echo "context-wiki: hay $nuevos commit(s) nuevos en la herramienta."
    echo "  ver qué cambió:  git -C $TOOL_DIR log --oneline HEAD..@{u}"
    echo "  actualizar:      bash $TOOL_DIR/install.sh"
  fi
  exit 0
fi

# lee un valor de la config existente (nueva o vieja)
# Un backup de una config de Claude tiene projects/, settings.json y commands/,
# así que pasa cualquier validación de contenido: hay que excluirlo por nombre.
# Escribir ahí ensucia respaldos, y minar sus sesiones duplica las notas.
es_backup() {
  case "$(basename "$1")" in
    *.bak|*.backup|*.old|*.orig|*~|*.save) return 0 ;;
  esac
  return 1
}

cfg_get() {
  local key="$1" f v
  for f in "$CONFIG_FILE" "$LEGACY_CONFIG"; do
    [[ -f "$f" ]] || continue
    v="$(grep -E "^${key}=" "$f" | cut -d= -f2- | tr -d '"' || true)"
    [[ -n "$v" ]] && { echo "$v"; return 0; }
  done
  return 0   # no encontrado no es un error (set -e mataría el script)
}

echo ""
echo "════════════════════════════════════════════"
echo "  Wiki de contexto — Instalador"
echo "════════════════════════════════════════════"
echo ""
echo "Herramienta: $TOOL_DIR"

# Python: el primero que *ejecute* de verdad. En Windows, python.org instala
# `python` (no `python3`) y el atajo de la Microsoft Store existe pero no corre.
# Se guarda en la config para que los comandos usen el mismo.
PYTHON=""
for cand in python3 python; do
  if "$cand" -c "import sys; sys.exit(sys.version_info < (3, 8))" &>/dev/null; then
    PYTHON="$cand"
    break
  fi
done

# ─── 1. Actualizar la herramienta (si viene de un repo) ─────────────────
if git -C "$TOOL_DIR" rev-parse --git-dir &>/dev/null; then
  antes="$(git -C "$TOOL_DIR" rev-parse HEAD 2>/dev/null || true)"
  if GIT_TERMINAL_PROMPT=0 GIT_SSH_COMMAND="ssh -o BatchMode=yes" git -C "$TOOL_DIR" pull --rebase --autostash --quiet 2>/dev/null; then
    echo "✓ Herramienta actualizada"
  else
    echo "· No se pudo hacer pull (¿offline o cambios locales?) — continuando"
  fi
  despues="$(git -C "$TOOL_DIR" rev-parse HEAD 2>/dev/null || true)"

  # Bash mantiene abierto el archivo con el que arrancó: si el pull cambió
  # este script, lo que sigue ejecutándose es la versión vieja. Hay que
  # reiniciar para que el fix recién bajado tenga efecto en esta corrida.
  if [[ -n "$antes" && "$antes" != "$despues" && -z "${WIKI_REEXEC:-}" ]]; then
    echo "· Se actualizó el instalador — reiniciando con la versión nueva"
    echo ""
    WIKI_REEXEC=1 exec bash "$TOOL_DIR/install.sh" "$@"
  fi
fi

# ─── 1b. Carpeta de datos ───────────────────────────────────────────────
DATA_DIR="${WIKI_DATA_DIR:-$(cfg_get DATA_DIR)}"
[[ -z "$DATA_DIR" ]] && DATA_DIR="$(cfg_get WIKI_DIR)"   # instalaciones pre-split
if [[ -z "$DATA_DIR" ]]; then
  default_data="$HOME/context-wiki-data"
  if [[ -t 0 ]]; then
    echo ""
    echo "Si ya tenés una wiki publicada, pegá la URL del repo y la clono."
    read -erp "¿Dónde guardo tus notas? (ruta o URL) [$default_data]: " DATA_DIR
  fi
  DATA_DIR="${DATA_DIR:-$default_data}"
fi

# Si respondió con una URL de git, clonarla en vez de crear una carpeta con
# ese nombre literal. Cubre https://, ssh:// y el formato git@host:user/repo.
if [[ "$DATA_DIR" == *"://"* || "$DATA_DIR" == *@*:* ]]; then
  url="$DATA_DIR"
  nombre="$(basename "$url")"; nombre="${nombre%.git}"
  destino="${WIKI_CLONE_DIR:-$HOME/$nombre}"
  # La URL no dice dónde querés el clon; preguntarlo en vez de decidirlo.
  if [[ -t 0 ]]; then
    echo "  (podés dar la carpeta contenedora — dentro creo '$nombre')"
    read -erp "¿Dónde lo clono? [$destino]: " respuesta
    destino="${respuesta:-$destino}"
    destino="${destino/#\~/$HOME}"
    destino="${destino%/}"
  fi

  # Si apunta a una carpeta que ya existe y tiene cosas, se interpreta como
  # la contenedora: es lo que uno espera al escribir "~/code".
  if [[ -d "$destino" && ! -d "$destino/.git" ]] && [[ -n "$(ls -A "$destino" 2>/dev/null)" ]]; then
    destino="$destino/$nombre"
  fi

  if [[ -d "$destino/.git" ]]; then
    echo "· Ya existe $destino — lo uso tal cual (no vuelvo a clonar)"
  elif [[ -e "$destino" && ! -d "$destino" ]]; then
    echo "❌ $destino existe y es un archivo. Elegí otra ruta."
    exit 1
  else
    echo "· Clonando $url"
    if ! git clone --quiet "$url" "$destino"; then
      echo "❌ No pude clonar $url"
      echo "   Revisá la URL y que tengas acceso (¿clave SSH en esta máquina?)."
      exit 1
    fi
    echo "✓ Clonado en $destino"
  fi
  DATA_DIR="$destino"
fi

DATA_DIR="${DATA_DIR/#\~/$HOME}"
DATA_DIR="${DATA_DIR%/}"   # readline agrega '/' al completar con Tab: se
                           # normaliza para que la config quede limpia

# Las notas NO pueden vivir dentro del repo de la herramienta: es justamente
# lo que la separación evita (actualizar la herramienta tocaría tus notas, y
# compartirla implicaría compartirlas).
if [[ "$DATA_DIR" == "$TOOL_DIR" || "$DATA_DIR" == "$TOOL_DIR"/* ]]; then
  echo ""
  echo "❌ Esa carpeta está dentro de la herramienta ($TOOL_DIR)."
  echo "   Tus notas tienen que vivir aparte. Probá con: $HOME/context-wiki-data"
  exit 1
fi

mkdir -p "$DATA_DIR"/{atomic,synthesis,raw}
echo "✓ Datos: $DATA_DIR"

# ─── 2. Carpeta que contiene tus repos ──────────────────────────────────
# Cualquier carpeta con varios repos git dentro. No importa cómo se llame
# ni de qué organización sean.
PROJECT_DIR="${WIKI_PROJECT_DIR:-$(cfg_get PROJECT_DIR)}"
[[ -d "${PROJECT_DIR:-}" ]] || PROJECT_DIR=""

# Autodetección: carpetas del home con 2+ repos git como hijos directos.
if [[ -z "$PROJECT_DIR" ]]; then
  # while+read en vez de mapfile: macOS trae bash 3.2, donde mapfile no existe.
  candidates=()
  while IFS= read -r cand; do
    [[ -n "$cand" ]] && candidates+=("$cand")
  done < <(
    for d in "$HOME"/*/ "$HOME"/*/*/; do
      [[ -d "$d" ]] || continue
      n=0
      for child in "$d"*/; do
        [[ -d "$child/.git" ]] && n=$((n+1))
        [[ $n -ge 2 ]] && break
      done
      [[ $n -ge 2 ]] && echo "${d%/}"
    done 2>/dev/null | head -8
  )
  if [[ ${#candidates[@]} -gt 1 && -t 0 ]]; then
    echo ""
    echo "Carpetas con varios repos git:"
    for i in "${!candidates[@]}"; do echo "  $((i+1))) ${candidates[$i]}"; done
    read -rp "¿Cuál usar? [1-${#candidates[@]}]: " choice
    PROJECT_DIR="${candidates[$((choice-1))]:-}"
  elif [[ ${#candidates[@]} -eq 1 ]]; then
    PROJECT_DIR="${candidates[0]}"   # sugerencia, se confirma abajo
  fi

  # Siempre confirmar: la detección es una sugerencia, no una decisión.
  if [[ -t 0 ]]; then
    read -erp "¿Dónde están tus repos?${PROJECT_DIR:+ [$PROJECT_DIR]}: " answer
    PROJECT_DIR="${answer:-$PROJECT_DIR}"
    PROJECT_DIR="${PROJECT_DIR/#\~/$HOME}"
    PROJECT_DIR="${PROJECT_DIR%/}"
  fi
fi

if [[ ! -d "${PROJECT_DIR:-}" ]]; then
  echo "❌ No existe: ${PROJECT_DIR:-(vacío)}"
  exit 1
fi
echo "✓ Repos: $PROJECT_DIR"

# ─── 3. Escribir config global ──────────────────────────────────────────
# Perfiles de Claude Code con sesiones: si hay varios, preguntar cuáles
# usar para minar conversaciones (/wiki-import). Ej: solo el de empresa.
declare -a session_profiles=()
for d in "$HOME"/.claude*/; do
  es_backup "${d%/}" && continue
  [[ -d "$d/projects" ]] && session_profiles+=("$(basename "${d%/}")")
done

SESSION_PROFILES="$(cfg_get SESSION_PROFILES)"   # conservar elección previa
if [[ -z "$SESSION_PROFILES" && ${#session_profiles[@]} -gt 1 && -t 0 ]]; then
  echo ""
  echo "Detecté varios perfiles de Claude Code con conversaciones:"
  for i in "${!session_profiles[@]}"; do echo "  $((i+1))) ~/${session_profiles[$i]}"; done
  echo "  a) todos"
  read -rp "¿Cuál(es) usar para minar sesiones con /wiki-import? (ej. 2, o '1 2', o a): " sel
  if [[ "$sel" != "a" && "$sel" != "A" && -n "$sel" ]]; then
    chosen=()
    for num in $sel; do
      idx=$((num - 1))
      [[ $idx -ge 0 && $idx -lt ${#session_profiles[@]} ]] && chosen+=("${session_profiles[$idx]}")
    done
    # el :- evita "unbound variable" si no eligió ninguno válido
    # (bash <4.4 con set -u falla al expandir un array vacío)
    SESSION_PROFILES="$(IFS=:; echo "${chosen[*]:-}")"
  fi
fi

# ─── 4. Detección y selección de agentes ────────────────────────────────
has_claude=false
for d in "$HOME"/.claude*/; do
  [[ -d "$d" ]] || continue
  es_backup "${d%/}" && continue
  if [[ -d "$d/projects" || -f "$d/settings.json" || -d "$d/commands" ]]; then
    has_claude=true
    break
  fi
done

has_antigravity=false
if [[ -d "$HOME/.gemini" ]] || command -v agy &>/dev/null; then
  has_antigravity=true
fi

selected_agents="${WIKI_AGENTS:-$(cfg_get ACTIVE_AGENTS)}"
if [[ -z "$selected_agents" && -t 0 ]]; then
  echo ""
  echo "Agentes compatibles en esta máquina:"
  echo "  1) Claude Code $( $has_claude && echo "[detectado]" || echo "[no detectado]" )"
  echo "  2) Google Antigravity / Gemini $( $has_antigravity && echo "[detectado]" || echo "[no detectado]" )"
  echo "  a) Todos los detectados"
  read -rp "¿Para qué agente(s) deseas configurar la wiki? [a]: " ag_choice
  ag_choice="${ag_choice:-a}"
  if [[ "$ag_choice" =~ [aA] ]]; then
    chosen_ag=()
    $has_claude && chosen_ag+=("claude")
    $has_antigravity && chosen_ag+=("antigravity")
    [[ ${#chosen_ag[@]} -eq 0 ]] && chosen_ag=("claude" "antigravity")
    selected_agents="$(IFS=:; echo "${chosen_ag[*]}")"
  else
    chosen_ag=()
    [[ "$ag_choice" == *"1"* ]] && chosen_ag+=("claude")
    [[ "$ag_choice" == *"2"* ]] && chosen_ag+=("antigravity")
    selected_agents="$(IFS=:; echo "${chosen_ag[*]}")"
  fi
fi

if [[ -z "$selected_agents" ]]; then
  chosen_ag=()
  $has_claude && chosen_ag+=("claude")
  $has_antigravity && chosen_ag+=("antigravity")
  [[ ${#chosen_ag[@]} -eq 0 ]] && chosen_ag=("claude")
  selected_agents="$(IFS=:; echo "${chosen_ag[*]}")"
fi

mkdir -p "$CONFIG_DIR"
cat > "$CONFIG_FILE" <<EOF
# Generado por install.sh — $(date '+%Y-%m-%d %H:%M') en $(hostname)
# Herramienta (este CLI) y datos (tus notas) viven separados.
TOOL_DIR="$TOOL_DIR"
DATA_DIR="$DATA_DIR"
# Carpeta que contiene tus repos de código
PROJECT_DIR="$PROJECT_DIR"
# Perfiles de Claude Code a minar con /wiki-import (vacío = todos los ~/.claude*)
SESSION_PROFILES="$SESSION_PROFILES"
# Agentes activos configurados (claude, antigravity)
ACTIVE_AGENTS="$selected_agents"
# Intérprete de Python que funciona en esta máquina (python3 o python)
PYTHON="$PYTHON"
EOF
echo "✓ Config: $CONFIG_FILE"
[[ -n "$SESSION_PROFILES" ]] && echo "  · Sesiones se minan solo de: $SESSION_PROFILES"
echo "  · Agentes activos: $selected_agents"

# ─── 5. Instalación por Agente ──────────────────────────────────────────

# A. Claude Code
if [[ ":$selected_agents:" == *":claude:"* ]]; then
  declare -a claude_dirs=()
  if [[ -n "${WIKI_CLAUDE_DIRS:-}" ]]; then
    IFS=':' read -ra claude_dirs <<< "$WIKI_CLAUDE_DIRS"
  else
    for d in "$HOME"/.claude*/; do
      [[ -d "$d" ]] || continue
      es_backup "${d%/}" && continue
      if [[ -d "$d/projects" || -f "$d/settings.json" || -d "$d/commands" ]]; then
        claude_dirs+=("${d%/}")
      fi
    done
  fi

  if [[ ${#claude_dirs[@]} -eq 0 ]]; then
    echo "⚠️  [Claude Code] No encontré config (~/.claude). Instala Claude Code primero."
  else
    for cd_dir in "${claude_dirs[@]}"; do
      mkdir -p "$cd_dir/commands"
      # Rutas reales en los comandos, en vez de `bash -c 'source config...'`:
      # - __PYTHON__ y __TOOL_DIR__: la línea de contexto llama a cli.py directo,
      #   y su regla en allowed-tools es exacta. `Bash(bash -c:*)` le aprobaba
      #   al modelo cualquier comando, y con "${PYTHON}" + "$*" Claude Code
      #   bloquea la línea aunque esté aprobada.
      # - __DATA_DIR__: /wiki-ingest sólo tiene pre-aprobado escribir ahí.
      data_abs="$(cd "$DATA_DIR" 2>/dev/null && pwd -P || echo "$DATA_DIR")"
      esc() { printf '%s' "$1" | sed 's/[&|\\]/\\&/g'; }
      for cmd_file in "$TOOL_DIR/claude-commands/"*.md; do
        sed -e "s|__DATA_DIR__|$(esc "$data_abs")|g" \
            -e "s|__TOOL_DIR__|$(esc "$TOOL_DIR")|g" \
            -e "s|__PYTHON__|$(esc "${PYTHON:-python3}")|g" \
            "$cmd_file" > "$cd_dir/commands/$(basename "$cmd_file")"
      done
      rm -f "$cd_dir/commands/wiki-register.md"
      echo "✓ [Claude Code] Comandos instalados en $cd_dir/commands/"
      mkdir -p "$cd_dir/agents"
      cp "$TOOL_DIR/claude-agents/"*.md "$cd_dir/agents/"
      echo "✓ [Claude Code] Agentes instalados en $cd_dir/agents/"

      if [[ -n "$PYTHON" ]]; then
        "$PYTHON" - "$cd_dir/settings.json" "$TOOL_DIR" <<'PYEOF'
import json, sys
from pathlib import Path

settings_path, tool_dir = Path(sys.argv[1]), sys.argv[2]
cfg = json.loads(settings_path.read_text()) if settings_path.exists() else {}

command = f"bash {tool_dir}/install.sh --check-updates  # context-wiki-autoupdate"
session_start = cfg.setdefault("hooks", {}).setdefault("SessionStart", [])

for entry in session_start:
    entry["hooks"] = [
        h for h in entry.get("hooks", [])
        if not (h.get("type") == "command"
                and ("context-wiki-autoupdate" in h.get("command", "")
                     or "llm-wiki-autoupdate" in h.get("command", "")
                     or (("context-wiki" in h.get("command", "")
                          or "llm-wiki" in h.get("command", ""))
                         and "install.sh" in h.get("command", ""))))
    ]
session_start[:] = [e for e in session_start if e.get("hooks")]
session_start.append({"hooks": [{"type": "command", "command": command,
                                 "timeout": 10}]})

settings_path.write_text(json.dumps(cfg, indent=2, ensure_ascii=False) + "\n")
PYEOF
        echo "✓ [Claude Code] Hook de aviso de actualizaciones en $cd_dir/settings.json"
      else
        echo "⚠️  Python 3.8+ no encontrado — el hook de aviso queda sin instalar"
      fi
    done
  fi
fi

# B. Google Antigravity / Gemini
if [[ ":$selected_agents:" == *":antigravity:"* ]]; then
  agy_skills_dir="$HOME/.gemini/config/skills"
  mkdir -p "$agy_skills_dir"
  if [[ -d "$TOOL_DIR/antigravity-skills" ]]; then
    for sk in "$TOOL_DIR/antigravity-skills/"*/; do
      [[ -d "$sk" ]] || continue
      sk_name="$(basename "$sk")"
      mkdir -p "$agy_skills_dir/$sk_name"
      cp -r "$sk"* "$agy_skills_dir/$sk_name/"
    done
    echo "✓ [Antigravity] Skills instalados en $agy_skills_dir"
  fi

  for doc in AGENTS.md GEMINI.md; do
    if [[ -f "$TOOL_DIR/$doc" && ! -f "$DATA_DIR/$doc" ]]; then
      cp "$TOOL_DIR/$doc" "$DATA_DIR/$doc"
      echo "✓ [Antigravity] $doc copiado a $DATA_DIR/"
    fi
  done
fi

# ─── 6. Verificación: repos detectados en la carpeta de proyecto ────────
echo ""
if [[ -n "$PYTHON" ]]; then
  "$PYTHON" "$TOOL_DIR/cli.py" detect || true
else
  echo "⚠️  Python 3.8+ no encontrado — el CLI lo necesita"
fi

echo "════════════════════════════════════════════"
echo "  Listo. Wiki configurada con éxito."
if [[ ":$selected_agents:" == *":claude:"* ]]; then
  echo ""
  echo "  Comandos para Claude Code:"
  echo "  /wiki-load <búsqueda>   carga contexto"
  echo "  /wiki-export [repo]     exporta desarrollo"
  echo "  /wiki-status            estado del wiki"
  echo "  /wiki-lint              salud del wiki"
  echo "  /wiki-sync              sincroniza (si publicaste la wiki)"
fi
if [[ ":$selected_agents:" == *":antigravity:"* ]]; then
  echo ""
  echo "  Skills para Google Antigravity (~/.gemini/config/skills/):"
  echo "  wiki-load, wiki-export, wiki-import, wiki-sync, wiki-status, wiki-lint"
fi
echo ""
if git -C "$DATA_DIR" remote 2>/dev/null | grep -q .; then
  echo "  Wiki publicada en: $(git -C "$DATA_DIR" remote get-url origin 2>/dev/null)"
else
  echo "  Tu wiki es LOCAL — vive sólo en $DATA_DIR"
  echo "  Para publicarla en un repo propio (opcional):"
  echo "    python3 $TOOL_DIR/cli.py publish <url-de-tu-repo>"
fi
echo ""
echo "  (reinicia Claude Code o abre Antigravity para que los detecten)"
echo "════════════════════════════════════════════"
