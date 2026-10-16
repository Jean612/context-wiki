#!/usr/bin/env python3
"""
Wiki CLI — base de conocimiento multi-repo para sesiones de LLM.

La herramienta (este CLI) y los datos (tus notas) viven en carpetas separadas:
  ~/.config/context-wiki/config  →  apunta a ambas
  DATA_DIR                       →  atomic/ synthesis/ raw/ index.md renames.json

Por default la wiki es **local**: vive en tu disco y no habla con ningún
servidor. Publicarla en un repo propio es opcional (`cli.py publish <url>`).

El nombre de un repo se deriva siempre de su git remote (o del nombre de la
carpeta si no tiene remote). No hay registro ni claves canónicas: cualquier
repo nuevo funciona sin configurar nada.

renames.json (opcional) sólo hace falta si renombraste un repo y querés que la
búsqueda encuentre también las notas escritas con el nombre anterior.

Uso: python3 cli.py <comando> [argumentos]

Comandos:
  status                     Estado del wiki (notas, sync, rutas)
  resolve <path>             Nombre del repo de esa carpeta
  detect                     Repos git encontrados en la carpeta de proyecto
  search <términos>          Busca notas por palabra clave (expande renombres)
  lint                       Verifica integridad del wiki
  sync [pull|push|full]      Sincroniza con el repo de datos, si está publicado
  publish <url>              Publica la wiki en un repo propio (opcional)
  titles [tope]              Notas existentes como 'stem — título' (default 8000 chars)
  new-id [slug]              Genera ID + nombre de archivo para nota atómica
  raw [archivo]              Sin argumento: archivos de raw/ que ninguna nota cita.
                             Con archivo: lo copia a raw/ (si no está) para /wiki-ingest
  raw --subir <nombre>       Sube igual un archivo de raw/ que pasa de 5 MB
  raw <url>                  Dice si el link ya se guardó y con qué nombre guardarlo
  context <modo> [arg]       Contexto inicial de cada slash command
                             (ingest, load, export, import, lint, status, sync)
  extract-sessions <repo|all> [max]
                             Extrae conocimiento de sesiones históricas de Claude Code.
                             'all' procesa todos los repos locales. Busca en TODOS los
                             perfiles ~/.claude* (personal, empresa, etc.) automáticamente.

Variables de entorno:
  CLAUDE_DIR   Fuerza un único perfil de Claude Code (default: autodetectar ~/.claude*)
"""

import json
import os
import platform
import re
import shutil
import unicodedata
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote_plus, urlsplit

# Windows redirige la salida con el codepage local y los ✓/⚠️ revientan con
# UnicodeEncodeError — justo cuando los comandos capturan la salida.
for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")

TOOL_ROOT = Path(__file__).parent.resolve()        # donde vive este CLI
CONFIG_DIR = Path.home() / ".config" / "context-wiki"
CONFIG_FILE = CONFIG_DIR / "config"
# config de instalaciones previas (llm-wiki)
LEGACY_CONFIG_FILES = [
    Path.home() / ".config" / "llm-wiki" / "config",
]


# Lo que es contenido del wiki (y por tanto se versiona y se publica).
# Todo lo demás que aparezca en la carpeta de datos se ignora.
# Un archivo de raw/ más pesado que esto no se sube salvo que se pida
# (`cli.py raw --subir`): git lo guarda para siempre, aunque después se borre.
RAW_MAX_BYTES = 5 * 1024 * 1024

CONTENT_PATHS = ["atomic", "synthesis", "raw", "templates",
                 "index.md", "renames.json", "topics.json",
                 "CLAUDE.md", "AGENTS.md", "GEMINI.md", "README.md"]


# ---------------------------------------------------------------- helpers

def run_git(args, cwd, check=False):
    """Ejecuta git y retorna (exit_code, stdout+stderr)."""
    try:
        r = subprocess.run(
            ["git"] + args, cwd=str(cwd), capture_output=True, text=True, timeout=60
        )
        return r.returncode, (r.stdout + r.stderr).strip()
    except FileNotFoundError:
        return 127, "git no encontrado"
    except subprocess.TimeoutExpired:
        return 124, "git timeout (¿sin conexión?)"


def _native_path(p: str, windows: bool = os.name == "nt") -> str:
    """Git Bash escribe la config con rutas /c/Users/...; el Python nativo de
    Windows no las entiende. Bash sí las necesita así, por eso la conversión va
    de este lado, al leer, y no al escribir."""
    m = re.match(r"^/([a-zA-Z])(/.*)?$", p)
    if windows and m:
        return f"{m.group(1).upper()}:{m.group(2) or '/'}"
    return p


def _claude_slug(path: str) -> str:
    """Nombre de la carpeta donde Claude Code guarda las sesiones de `path`."""
    # Regla (todo lo no alfanumérico → "-"): /home/x → -home-x;
    # D:\context-wiki → D--context-wiki en Windows.
    return re.sub(r"[^a-zA-Z0-9]", "-", path)


def read_config():
    """Lee ~/.config/context-wiki/config (KEY=VALUE por línea), con fallback legacy."""
    cfg = {}
    path = next((p for p in [CONFIG_FILE] + LEGACY_CONFIG_FILES if p.exists()), None)
    if path:
        for line in path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                v = v.strip().strip('"')
                # SESSION_PROFILES es una lista separada por ":" — se convierte
                # por ítem al partirla, no acá (C: rompería la separación)
                cfg[k.strip()] = v if k.strip() == "SESSION_PROFILES" else _native_path(v)
    return cfg


class Wiki:
    def __init__(self):
        cfg = read_config()
        # Los datos viven aparte de la herramienta. WIKI_DIR es el nombre que
        # usaban las instalaciones anteriores al split.
        data_dir = cfg.get("DATA_DIR") or cfg.get("WIKI_DIR")
        if not data_dir:
            sys.exit(
                "❌ No encuentro la configuración.\n"
                f"   Ejecutá primero:  bash {TOOL_ROOT}/install.sh\n"
                "   (define dónde guardar tus notas y instala los comandos)"
            )
        self.root = Path(data_dir).expanduser()
        if self.root == TOOL_ROOT or str(self.root).startswith(f"{TOOL_ROOT}/"):
            sys.exit(
                f"❌ DATA_DIR apunta dentro de la herramienta ({TOOL_ROOT}).\n"
                "   Tus notas tienen que vivir en otra carpeta. Corregí "
                f"DATA_DIR en {CONFIG_FILE} o volvé a correr install.sh"
            )
        self.atomic = self.root / "atomic"
        self.synthesis = self.root / "synthesis"
        self.raw = self.root / "raw"
        for d in (self.atomic, self.synthesis, self.raw):
            d.mkdir(parents=True, exist_ok=True)

        # Grupos de nombres equivalentes (un repo que fue renombrado). Opcional:
        # si el archivo no existe, cada repo es simplemente su nombre actual.
        # Legacy del modelo repo-céntrico: las notas nuevas se organizan por
        # topics, pero las viejas conservan el nombre del repo en el archivo.
        renames_file = self.root / "renames.json"
        self.name_groups = []
        if renames_file.exists():
            data = json.loads(renames_file.read_text()).get("renames", {})
            self.name_groups = [
                {n.lower() for n in [current] + list(olds)}
                for current, olds in data.items()
            ]

        # Vocabulario controlado de tags (topic canónico + aliases). Mismo
        # mecanismo que renames.json: grupos de términos equivalentes, para
        # que "auth" y "autenticación" encuentren las mismas notas.
        topics_file = self.root / "topics.json"
        self.topic_groups = []
        self.topic_canonico = {}
        # Las notas anteriores al vocabulario son inmutables: no se pueden
        # corregir, así que avisar por ellas sería ruido permanente.
        self.topics_desde = None
        if topics_file.exists():
            raw = json.loads(topics_file.read_text())
            self.topics_desde = raw.get("vigente_desde")
            data = raw.get("topics", {})
            self.topic_groups = [
                {t.lower() for t in [canonical] + list(aliases)}
                for canonical, aliases in data.items()
            ]
            canonicos = {c.lower() for c in data}
            self.topic_canonico = {
                a.lower(): canonical
                for canonical, aliases in data.items() for a in aliases
                if a.lower() not in canonicos
            }

        # Carpeta donde viven los repos clonados. Prioridad:
        # config > padre de la carpeta de datos
        self.project_root = Path(cfg.get("PROJECT_DIR", str(self.root.parent))).expanduser()

        # Perfiles de Claude Code para minar sesiones. Prioridad:
        # 1. CLAUDE_DIR (env) — fuerza un único perfil
        # 2. SESSION_PROFILES (config) — lista separada por ':' de nombres
        #    (ej. ".claude-work") o rutas; permite excluir el perfil personal
        # 3. autodetectar todos los ~/.claude* con sesiones
        env_dir = os.environ.get("CLAUDE_DIR")
        session_profiles = cfg.get("SESSION_PROFILES", "").strip()
        if env_dir:
            p = Path(env_dir).expanduser()
            self.claude_projects_dirs = [(p.name, p / "projects")]
        elif session_profiles:
            self.claude_projects_dirs = []
            for item in session_profiles.split(":"):
                item = _native_path(item.strip())
                if not item:
                    continue
                p = Path(item).expanduser() if "/" in item else Path.home() / item
                if (p / "projects").is_dir():
                    self.claude_projects_dirs.append((p.name, p / "projects"))
        else:
            self.claude_projects_dirs = [
                (d.name, d / "projects")
                for d in sorted(Path.home().glob(".claude*"))
                if d.is_dir() and (d / "projects").is_dir()
            ]

    # ------------------------------------------------------------ resolve

    def _slug_from_remote(self, path: Path):
        """Extrae el slug (nombre de repo) del remote origin de un clone."""
        code, out = run_git(["remote", "get-url", "origin"], cwd=path)
        if code != 0 or not out:
            return None
        # git@github.com:Org/nombre.git | https://github.com/Org/nombre
        m = re.search(r"[:/]([^/:]+?)(?:\.git)?$", out.strip())
        return m.group(1) if m else None

    def expand_term(self, term: str):
        """
        Todos los términos equivalentes a uno dado (renombres de repo y
        aliases de topics). Sin renames.json ni topics.json, devuelve sólo
        el término mismo.
        """
        low = (term or "").lower()
        for group in self.name_groups + self.topic_groups:
            if low in group:
                return set(group)
        return {low}

    def expand_name(self, name: str):
        """Compat: nombre de repo → todos sus equivalentes (ver expand_term)."""
        return self.expand_term(name)

    def resolve(self, token: str):
        """
        Nombre de un repo a partir de un path: el slug de su remote, o el
        nombre de la carpeta si no tiene remote. Retorna (nombre, cómo).

        No hay registro ni claves canónicas: el nombre se deriva siempre.
        """
        path = Path(token or ".").expanduser()
        if not (path.exists() and path.is_dir()):
            return None, None
        code, top = run_git(["rev-parse", "--show-toplevel"], cwd=path)
        if code != 0 or not top:
            return None, None
        repo_dir = Path(top)
        slug = self._slug_from_remote(repo_dir)
        if slug:
            return slug, "remote origin"
        return repo_dir.name, "nombre de carpeta (sin remote)"

    def detect_local(self):
        """Repos git clonados en project_root, con su nombre derivado."""
        results = []
        if not self.project_root.exists():
            return results
        for child in sorted(self.project_root.iterdir()):
            if not child.is_dir() or child.name.startswith(".") or child == self.root:
                continue
            if not (child / ".git").exists():
                continue
            name, how = self.resolve(str(child))
            results.append((child.name, name or child.name, how or "carpeta"))
        return results

    def local_paths_for(self, name: str):
        """Carpetas locales que corresponden a un nombre (expandiendo renombres)."""
        p = Path(name).expanduser()
        if p.is_dir() and (p / ".git").exists():
            return [p.resolve()]
        wanted = self.expand_name(name)
        paths = [
            self.project_root / folder
            for folder, n, _ in self.detect_local()
            if n.lower() in wanted or folder.lower() in wanted
        ]
        if not paths and (TOOL_ROOT.name.lower() in wanted or TOOL_ROOT.name.lower() == name.lower()):
            paths.append(TOOL_ROOT)
        return paths

    # ------------------------------------------------------------ search

    def search(self, terms: str):
        """Busca en atomic/, synthesis/ y raw/. Expande aliases (repos y topics)."""
        words = [w for w in re.split(r"\s+", terms.strip()) if w]
        expanded = set(w.lower() for w in words)
        for w in words:
            expanded.update(self.expand_term(w))

        def score(text):
            t = text.lower()
            return sum(1 for w in expanded if w in t)

        results = []
        for d, kind in ((self.atomic, "atomic"), (self.synthesis, "synthesis"), (self.raw, "raw")):
            for f in d.glob("*.md"):
                s = score(f.name) * 2 + score(f.read_text(errors="ignore"))
                if s > 0:
                    results.append((s, kind, f))
        results.sort(key=lambda r: -r[0])
        return results, sorted(expanded)

    # ------------------------------------------------------------ sync

    def is_published(self):
        """True si la carpeta de datos es un repo git con remote configurado."""
        code, out = run_git(["remote"], cwd=self.root)
        return code == 0 and bool(out.strip())

    def _exclude_file(self):
        return self.root / ".git" / "info" / "exclude"

    @staticmethod
    def _patron_exclude(rel):
        # anclado a la raíz y con los comodines de gitignore escapados
        return "/" + re.sub(r"([\\\[\]*?!#])", r"\\\1", rel)

    def excluir_pesados(self):
        """Deja fuera de git, sólo en esta máquina (.git/info/exclude no se
        versiona), lo que esté en raw/ sin trackear y pese más de RAW_MAX_BYTES.
        Lo ya trackeado o stageado con `raw --subir` no se toca."""
        if not (self.root / ".git").is_dir():
            return
        _, out = run_git(["-c", "core.quotePath=false", "ls-files", "--others",
                          "--exclude-standard", "--", "raw"], cwd=self.root)
        for rel in filter(None, out.splitlines()):
            tam = (self.root / rel).stat().st_size
            if tam <= RAW_MAX_BYTES:
                continue
            ex = self._exclude_file()
            ex.parent.mkdir(parents=True, exist_ok=True)
            with ex.open("a") as f:
                f.write(self._patron_exclude(rel) + "\n")
            mb = f"{tam / 1024 / 1024:.1f} MB"
            print(f"⚠️  {rel} ({mb}) no se sube: pasa de {RAW_MAX_BYTES // 1024 // 1024} MB. "
                  f"Queda sólo en esta máquina.")
            print(f"    Para subirlo igual (el repo crece {mb} para siempre): "
                  f"cli.py raw --subir {Path(rel).name}")

    def sync(self, mode="full", message=None):
        """
        pull --rebase y/o commit+push. Tolerante a offline.

        Si la wiki no está publicada (sin remote) no hace nada: el modo por
        default es local, y publicarla es una decisión explícita (cli.py publish).
        """
        if not self.is_published():
            print("· Wiki local (sin remote) — nada que sincronizar")
            print("  Para publicarla en un repo propio: python3 cli.py publish <url>")
            return True

        ok = True
        if mode in ("pull", "full"):
            code, out = run_git(["pull", "--rebase", "--autostash"], cwd=self.root)
            if code == 0:
                print(f"✓ pull: {out.splitlines()[-1] if out else 'ok'}")
            else:
                ok = False
                print(f"⚠️  pull falló (¿offline?): {out.splitlines()[-1] if out else code}")
                print("   El wiki sigue funcionando en local; sincroniza después con /wiki-sync")

        if mode in ("push", "full"):
            # Sólo el contenido del wiki: nunca barrer la carpeta entera
            # (state de Obsidian, __pycache__, archivos sueltos).
            self.excluir_pesados()
            paths = [p for p in CONTENT_PATHS if (self.root / p).exists()]
            code, out = run_git(["status", "--porcelain", "--"] + paths, cwd=self.root)
            if out:
                run_git(["add", "--"] + paths, cwd=self.root)
                msg = message or f"wiki: update {datetime.now().strftime('%Y-%m-%d %H:%M')}"
                host = platform.node()
                code, out = run_git(["commit", "-m", f"{msg} [{host}]"], cwd=self.root)
                if code == 0:
                    print("✓ commit creado")
                else:
                    print(f"⚠️  commit: {out}")
            # push de todo lo pendiente (incluye commits de sesiones offline)
            code, out = run_git(["push"], cwd=self.root)
            if code == 0:
                print("✓ push")
            else:
                ok = False
                low = out.lower()
                if any(s in low for s in ("permission", "denied", "403", "not have access",
                                          "authentication", "could not read")):
                    print(f"❌ push rechazado — no tenés permiso de escritura en este remote:")
                    print(f"   {out.splitlines()[-1] if out else code}")
                    print("   Si el wiki es de otra persona, publicá el tuyo:"
                          " python3 cli.py publish <url-de-tu-repo>")
                else:
                    print(f"⚠️  push falló (¿offline?): {out.splitlines()[-1] if out else code}")
                    print("   Los commits quedan en local; sincroniza después con /wiki-sync")
        return ok

    def sync_status(self):
        """Estado de sync vs remoto, o 'local' si la wiki no está publicada."""
        if not self.is_published():
            return "local (sin publicar)"
        run_git(["fetch", "--quiet"], cwd=self.root)
        code, out = run_git(["status", "-sb"], cwd=self.root)
        return out.splitlines()[0] if out else "?"

    # ------------------------------------------------------------ misc

    def counts(self):
        return {
            "atomic": len(list(self.atomic.glob("*.md"))),
            "synthesis": len(list(self.synthesis.glob("*.md"))),
            "raw": len(list(self.raw.glob("*.md"))),
        }


# ---------------------------------------------------------------- comandos

def cmd_status(wiki, _args):
    c = wiki.counts()
    print("\n📊 WIKI")
    print("=" * 60)
    print(f"Notas atómicas: {c['atomic']}")
    print(f"Síntesis:       {c['synthesis']}")
    print(f"Raw (sources):  {c['raw']}")
    print(f"Datos:          {wiki.root}")
    print(f"Herramienta:    {TOOL_ROOT}")
    print(f"Repos:          {wiki.project_root}")
    print(f"Estado:         {wiki.sync_status()}")
    if wiki.is_published():
        paths = [p for p in CONTENT_PATHS if (wiki.root / p).exists()]
        dirty = run_git(["status", "--porcelain", "--"] + paths, cwd=wiki.root)[1]
        if dirty:
            print(f"⚠️  Sin commitear: {len(dirty.splitlines())} archivo(s) — usa /wiki-sync")
    print()


def cmd_publish(wiki, args):
    """Conecta la carpeta de datos a un repo propio y sube todo por primera vez."""
    if wiki.is_published():
        code, out = run_git(["remote", "get-url", "origin"], cwd=wiki.root)
        print(f"Esta wiki ya está publicada en: {out}")
        print("Para sincronizar: python3 cli.py sync")
        return
    if not args:
        print("Uso: cli.py publish <url-del-repo>")
        print("\nCreá primero un repo VACÍO y PRIVADO en GitHub (sin README), y pasá su URL.")
        print("Ej: cli.py publish git@github.com:tuusuario/mi-wiki.git")
        return
    url = args[0]

    # Un destino con historia suele ser un typo en la URL (apuntar a una wiki
    # ya publicada): el push fallaría por non-fast-forward y el remote quedaría
    # mal configurado. Mejor cortar antes de tocar nada.
    code, out = run_git(["ls-remote", url], cwd=wiki.root)
    if code != 0:
        print(f"❌ No pude contactar el repo: {out.splitlines()[-1] if out else code}")
        print("   Revisá la URL y que tengas acceso (¿clave SSH en esta máquina?).")
        return
    if out.strip():
        print("❌ Ese repo ya tiene contenido — publish es para un repo VACÍO.")
        print("   ¿Es la URL correcta? Si querés usar una wiki ya publicada, clonala")
        print("   y apuntá DATA_DIR a ella en ~/.config/context-wiki/config.")
        return

    if not (wiki.root / ".git").exists():
        code, out = run_git(["init"], cwd=wiki.root)
        if code != 0:
            print(f"❌ git init falló: {out}")
            return
        # 'main' es lo que espera GitHub; symbolic-ref funciona en cualquier
        # versión de git y es inocuo en un repo recién inicializado.
        run_git(["symbolic-ref", "HEAD", "refs/heads/main"], cwd=wiki.root)
        print("✓ git init (rama main)")

    code, out = run_git(["remote", "add", "origin", url], cwd=wiki.root)
    if code != 0:
        print(f"❌ No pude agregar el remote: {out}")
        return
    print(f"✓ remote → {url}")

    wiki.excluir_pesados()
    paths = [p for p in CONTENT_PATHS if (wiki.root / p).exists()]
    run_git(["add", "--"] + paths, cwd=wiki.root)
    run_git(["commit", "-m", f"wiki: publicación inicial desde {platform.node()}"],
            cwd=wiki.root)

    code, out = run_git(["push", "-u", "origin", "HEAD"], cwd=wiki.root)
    if code == 0:
        print("✓ Wiki publicada. A partir de ahora /wiki-sync la mantiene al día.")
    else:
        print(f"⚠️  El push falló: {out.splitlines()[-1] if out else code}")
        print("   El remote quedó configurado; reintentá con: python3 cli.py sync push")


def cmd_resolve(wiki, args):
    token = args[0] if args else "."
    name, how = wiki.resolve(token)
    if not name:
        print(f"❌ '{token}' no es un repo git.")
        sys.exit(1)
    print(f"repo: {name}")
    print(f"via: {how}")
    others = wiki.expand_name(name) - {name.lower()}
    if others:
        print(f"nombres anteriores: {', '.join(sorted(others))}")


def cmd_detect(wiki, _args):
    print(f"\n🗺️  REPOS LOCALES en {wiki.project_root}")
    print("=" * 60)
    found = wiki.detect_local()
    if not found:
        print("(no encontré repos git aquí)")
    sin_registrar = 0
    for folder, name, _how in found:
        if folder.lower() == name.lower():
            print(f"· {name}")
        elif folder.lower() in wiki.expand_name(name):
            # renombrado, pero ya está en renames.json: no hay nada que hacer
            print(f"· {name}  (carpeta local: {folder})")
        else:
            sin_registrar += 1
            print(f"⚠️  {name:30} (carpeta local: {folder})")
    if sin_registrar:
        print(f"\n{sin_registrar} carpeta(s) con nombre distinto al del remote y sin registrar.")
        print("Para que la búsqueda cruce ambos nombres, agregalos a renames.json")
    print()


def cmd_search(wiki, args):
    if not args:
        print("Uso: cli.py search '<términos>'")
        return
    terms = " ".join(args)
    results, expanded = wiki.search(terms)
    print(f"\n🔍 BÚSQUEDA: {terms}")
    print(f"(términos expandidos: {', '.join(expanded)})")
    print("=" * 60)
    if not results:
        print("Sin resultados.")
        return
    for score, kind, f in results[:15]:
        print(f"[{score:3}] {kind:9} {f.relative_to(wiki.root)}")
    if len(results) > 15:
        print(f"... y {len(results) - 15} más")
    print()

def cmd_lint(wiki, _args):
    print("\n🔧 LINT WIKI")
    print("=" * 60)
    c = wiki.counts()
    print(f"Notas: {c['atomic']} atomic, {c['synthesis']} synthesis, {c['raw']} raw")

    # notas huérfanas (sin links salientes ni entrantes)
    all_content = {}
    for f in wiki.atomic.glob("*.md"):
        all_content[f.stem] = f.read_text(errors="ignore")
    linked = set()
    for stem, content in all_content.items():
        for m in re.finditer(r"\[\[(\d{12,13}[^\]]*)\]\]", content):
            linked.add(m.group(1).strip())
    orphans = [
        stem for stem, content in all_content.items()
        if "[[" not in content and stem not in linked
    ]
    if orphans:
        print(f"\n⚠️  Notas huérfanas (sin links en ninguna dirección): {len(orphans)}")
        for o in orphans[:8]:
            print(f"  - {o}")
        if len(orphans) > 8:
            print(f"  ... y {len(orphans) - 8} más")
    else:
        print("✓ Sin notas huérfanas")

    # links rotos
    broken = []
    stems = set(all_content.keys())
    for stem, content in all_content.items():
        for m in re.finditer(r"\[\[(\d{12,13}[^\]|#]*)\]\]", content):
            target = m.group(1).strip()
            if target not in stems and not any(s.startswith(target) for s in stems):
                broken.append(f"{stem} → [[{target}]]")
    if broken:
        print(f"\n⚠️  Links rotos: {len(broken)}")
        for b in broken[:8]:
            print(f"  - {b}")
    else:
        print("✓ Sin links rotos")

    # notas sin links salientes (regla: toda nota enlaza al menos 1 otra;
    # previene huérfanas futuras en vez de sólo detectarlas)
    sin_salientes = [
        stem for stem, content in all_content.items()
        if "[[" not in content
    ]
    if sin_salientes:
        print(f"\n⚠️  Notas sin links salientes: {len(sin_salientes)}")
        for s in sin_salientes[:8]:
            print(f"  - {s}")
        print("  → al crear una nota, enlaza al menos 1 relacionada (paso 2.5 de /wiki-export)")

    # notas muy largas: cuestan tokens en cada /wiki-load que las abre
    largas = [
        (stem, len(content.split()))
        for stem, content in all_content.items()
        if len(content.split()) > 1200
    ]
    if largas:
        print(f"\n⚠️  Notas sobre 1200 palabras: {len(largas)}")
        for stem, n in largas[:8]:
            print(f"  - {stem} ({n} palabras)")
        print("  → dividir en notas enlazadas: una nueva referencia a la vieja, nunca se edita")

    # tags fuera del vocabulario controlado (topics.json, si existe)
    if wiki.topic_groups:
        known = set().union(*wiki.topic_groups)
        unknown = {}
        # Un alias funciona igual en la búsqueda, pero el vocabulario existe
        # para que cada tema tenga un solo nombre. Sólo se avisa en las notas
        # de hoy: las anteriores son inmutables y el aviso sería ruido.
        hoy = datetime.now().strftime("%Y%m%d")
        con_alias = {}
        for stem, content in all_content.items():
            if wiki.topics_desde and stem[:12] < wiki.topics_desde:
                continue   # nota anterior al vocabulario: inmutable, no se avisa
            m = re.search(r"^tags:\s*\[([^\]]*)\]", content, re.M)
            if not m:
                continue
            tags = [t.strip().strip("\"'") for t in m.group(1).split(",") if t.strip()]
            fuera = [t for t in tags if t.lower() not in known]
            if fuera:
                unknown[stem] = fuera
            alias = [f"{t} → {wiki.topic_canonico[t.lower()]}" for t in tags
                     if t.lower() in wiki.topic_canonico]
            if alias and stem.startswith(hoy):
                con_alias[stem] = alias
        if unknown:
            print(f"\n⚠️  Tags fuera de topics.json: {len(unknown)} nota(s)")
            for stem, tags in list(unknown.items())[:8]:
                print(f"  - {stem}: {', '.join(tags)}")
            print("  → agregalos como topic canónico o como alias de uno existente")
        else:
            desde = f" (desde {wiki.topics_desde})" if wiki.topics_desde else ""
            print(f"✓ Todos los tags están en el vocabulario{desde}")
        if con_alias:
            print(f"\n⚠️  Notas de hoy con un alias en vez del tag canónico: {len(con_alias)}")
            for stem, alias in con_alias.items():
                print(f"  - {stem}: {', '.join(alias)}")
            print("  → son de hoy: cambialas al canónico antes de subirlas")

    # las notas viejas usan el nombre que el repo tenía ese día — es correcto
    print("\n(Nota: nombres de repo viejos en notas antiguas son válidos — ver renames.json)")
    print()


def cmd_sync(wiki, args):
    mode = args[0] if args and args[0] in ("pull", "push", "full") else "full"
    message = None
    if "-m" in args:
        i = args.index("-m")
        if i + 1 < len(args):
            message = args[i + 1]
    wiki.sync(mode, message)



def cmd_titles(wiki, args):
    """
    Lista las notas existentes como 'stem — título', de la más nueva a la más
    vieja, con tope de caracteres. Se le pasa al LLM antes de escribir una nota
    nueva: si ve lo que ya existe, enlaza hacia atrás en vez de enlazar sólo las
    notas de su propia sesión.
    """
    tope = int(args[0]) if args and args[0].isdigit() else 8000
    usado = 0
    for f in sorted(wiki.atomic.glob("*.md"), reverse=True):
        titulo = ""
        for linea in f.read_text(errors="ignore").splitlines():
            if linea.startswith("# "):
                titulo = linea[2:].strip()
                break
        fila = f"{f.stem} — {titulo}" if titulo else f.stem
        if usado + len(fila) > tope:
            print(f"... ({len(list(wiki.atomic.glob('*.md')))} notas en total; "
                  f"usá cli.py search para el resto)")
            break
        print(fila)
        usado += len(fila) + 1


def cmd_new_id(wiki, args):
    now = datetime.now().strftime("%Y%m%d%H%M")
    slug = re.sub(r"[^a-z0-9_]+", "_", "_".join(args).lower()).strip("_") if args else "descripcion"
    print(f"id: {now}")
    print(f"file: {wiki.atomic}/{now}_{slug}.md")


def _session_dirs_for(wiki, local: Path):
    """Encuentra los directorios de sesiones de un repo en TODOS los perfiles de Claude."""
    slug = _claude_slug(str(local.resolve()))
    return [(profile, projects_dir / slug)
            for profile, projects_dir in wiki.claude_projects_dirs
            if (projects_dir / slug).exists()]


def _detect_antigravity_workspace(transcript_file: Path):
    """Detecta el workspace al que pertenece una conversación de Antigravity."""
    try:
        with open(transcript_file, encoding="utf-8", errors="ignore") as f:
            for i, line in enumerate(f):
                if i > 25:
                    break
                if not line.strip():
                    continue
                try:
                    obj = json.loads(line)
                    m = re.search(r"Command Working Directory:\s*([^\n\r]+)", str(obj.get("content", "")))
                    if m:
                        return m.group(1).strip()
                    for tc in obj.get("tool_calls", []):
                        cwd = tc.get("args", {}).get("Cwd")
                        if cwd:
                            return cwd.strip("\"'")
                except (json.JSONDecodeError, KeyError):
                    continue
    except OSError:
        pass
    return None


def _antigravity_sessions_for(local: Path):
    """Encuentra sesiones de Google Antigravity para un repo local."""
    brain = Path.home() / ".gemini" / "antigravity" / "brain"
    if not brain.exists():
        return []
    local_resolved = local.resolve()
    found = []
    for d in brain.iterdir():
        if not d.is_dir():
            continue
        transcript = d / ".system_generated" / "logs" / "transcript.jsonl"
        if not transcript.exists():
            continue
        ws = _detect_antigravity_workspace(transcript)
        if ws:
            try:
                # comparar Paths, no strings: en Windows el separador es la barra invertida
                # y las mayúsculas de la unidad no importan
                ws_resolved = Path(ws).resolve()
                if ws_resolved == local_resolved or local_resolved in ws_resolved.parents:
                    found.append(("antigravity", transcript))
            except OSError:
                pass
    return found


def _parse_antigravity_session(session_file: Path):
    """Parsea una transcripción de Google Antigravity en intercambios user/assistant."""
    exchanges = []
    try:
        with open(session_file, encoding="utf-8", errors="ignore") as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    obj = json.loads(line)
                except (json.JSONDecodeError, KeyError):
                    continue

                if obj.get("type") == "USER_INPUT" and obj.get("source") == "USER_EXPLICIT":
                    c = obj.get("content", "")
                    m_req = re.search(r"<USER_REQUEST>(.*?)</USER_REQUEST>", c, re.DOTALL)
                    text = m_req.group(1).strip() if m_req else c.strip()
                    if len(text) > 10 and not text.startswith("<"):
                        exchanges.append({"role": "user", "text": text[:500]})
                elif obj.get("type") == "PLANNER_RESPONSE" and obj.get("source") == "MODEL":
                    c = obj.get("content", "").strip()
                    if len(c) > 30:
                        exchanges.append({"role": "assistant", "text": c[:800]})
    except OSError as e:
        print(f"  ⚠️  Error leyendo {session_file}: {e}")
    return exchanges


def _extract_repo_sessions(wiki, key, locals_, max_s):
    """
    Extrae sesiones de un repo canónico (puede tener varias carpetas locales),
    combinando Claude Code y Google Antigravity. Retorna Path del resumen o None.
    """
    session_files = []  # (profile, file)
    for local in locals_:
        # 1. Claude Code
        for profile, d in _session_dirs_for(wiki, local):
            session_files += [(profile, f) for f in d.glob("*.jsonl")]
        # 2. Antigravity
        session_files += _antigravity_sessions_for(local)

    if not session_files:
        return None
    session_files.sort(key=lambda pf: pf[1].stat().st_mtime, reverse=True)

    print(f"\n📚 {key} — {len(session_files)} sesiones encontradas "
          f"(fuentes: {', '.join(sorted({p for p, _ in session_files}))})")

    summaries = []
    for profile, sf in session_files[:max_s]:
        mtime = datetime.fromtimestamp(sf.stat().st_mtime)
        if profile == "antigravity" or sf.name == "transcript.jsonl":
            exchanges = _parse_antigravity_session(sf)
            file_id = sf.parent.parent.parent.name[:8] if sf.name == "transcript.jsonl" else sf.name[:8]
        else:
            exchanges = _parse_session(sf)
            file_id = sf.name[:8]
        if exchanges:
            summaries.append({
                "file": file_id, "profile": profile,
                "date": mtime.strftime("%Y-%m-%d %H:%M"),
                "exchanges": exchanges[:15],
            })
            print(f"  ✓ {mtime.strftime('%Y-%m-%d')} [{profile}] — {len(exchanges)} intercambios")
    if not summaries:
        print("  (sin conversaciones procesables)")
        return None

    out = wiki.raw / f"sessions_{key}_{datetime.now().strftime('%Y%m%d')}.md"
    lines = [f"# Sesiones Históricas — {key}", "",
             f"**Generado:** {datetime.now().strftime('%Y-%m-%d %H:%M')} en {platform.node()}",
             f"**Sesiones procesadas:** {len(summaries)} (de {len(session_files)} encontradas)",
             "", "---", ""]
    for i, s in enumerate(summaries, 1):
        lines += [f"## Sesión {i} — {s['date']} [{s['profile']}]", f"*ID: {s['file']}*", ""]
        for e in s["exchanges"]:
            prefix = "**👤 Usuario:**" if e["role"] == "user" else ("**🤖 Antigravity:**" if s["profile"] == "antigravity" else "**🤖 Claude:**")
            text = e["text"] if e["role"] == "user" else e["text"].split("\n")[0]
            lines += [f"{prefix} {text}", ""]
        lines += ["---", ""]
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"  → {out.name}")
    return out


def cmd_extract_sessions(wiki, args):
    if not args:
        print("Uso: cli.py extract-sessions <repo|all> [max_sesiones_por_repo]")
        return
    max_s = int(args[1]) if len(args) > 1 and args[1].isdigit() else 10

    has_claude = bool(wiki.claude_projects_dirs)
    has_antigravity = (Path.home() / ".gemini" / "antigravity" / "brain").is_dir()
    if not has_claude and not has_antigravity:
        print("❌ No encontré sesiones de Claude Code (~/.claude*/projects) ni de Antigravity (~/.gemini/antigravity/brain)")
        print("   Define CLAUDE_DIR si tu config de Claude está en otra ruta.")
        return

    sources = []
    if has_claude:
        sources.append(f"Claude ({', '.join(p for p, _ in wiki.claude_projects_dirs)})")
    if has_antigravity:
        sources.append("Google Antigravity (~/.gemini/antigravity/brain)")
    print(f"Fuentes de sesiones detectadas: {'; '.join(sources)}")

    # Agrupar carpetas locales por nombre de repo
    targets = {}  # nombre -> [paths]
    if args[0].lower() == "all":
        for folder, name, _how in wiki.detect_local():
            targets.setdefault(name, []).append(wiki.project_root / folder)
    else:
        name = args[0]
        locals_ = wiki.local_paths_for(name)
        if not locals_:
            print(f"❌ No encontré '{name}' clonado en {wiki.project_root}")
            print("   Repos disponibles: " +
                  ", ".join(n for _f, n, _h in wiki.detect_local()))
            return
        targets[name] = locals_

    outputs = []
    for key, locals_ in targets.items():
        out = _extract_repo_sessions(wiki, key, locals_, max_s)
        if out:
            outputs.append(out)

    print("\n" + "=" * 60)
    if not outputs:
        print("No se generó ningún resumen (sin sesiones procesables).")
        return
    print(f"✓ {len(outputs)} resumen(es) generado(s) en raw/:")
    for o in outputs:
        print(f"  - {o.name}")
    print("\nSiguiente paso: ejecuta /wiki-import para convertirlos en notas atómicas.")


def _parse_session(session_file):
    exchanges = []
    skip = [r"^<local-command", r"^<command-name>", r"^<command-message>", r"^\s*$"]
    try:
        with open(session_file, encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                    msg = obj.get("message", {})
                    role, content = msg.get("role", ""), msg.get("content", "")
                    text = ""
                    if isinstance(content, str):
                        text = content.strip()
                    elif isinstance(content, list):
                        for c in content:
                            if isinstance(c, dict) and c.get("type") == "text":
                                text = c.get("text", "").strip()
                                break
                    if role == "user":
                        if len(text) < 15 or any(re.match(p, text) for p in skip):
                            continue
                        if text.startswith("<") and text.endswith(">"):
                            continue
                        exchanges.append({"role": "user", "text": text[:500]})
                    elif role == "assistant" and len(text) > 30:
                        exchanges.append({"role": "assistant", "text": text[:800]})
                except (json.JSONDecodeError, KeyError):
                    continue
    except OSError as e:
        print(f"  ⚠️  Error leyendo {session_file.name}: {e}")
    return exchanges


def _nombre_de_link(url, tope=60):
    """Nombre legible para la copia de una página: el sitio y el final de la
    ruta, que es lo más específico (el título en Confluence o Medium).
    Cortar host+ruta a 60 caracteres partía el ID de la página a la mitad
    y nunca llegaba al título."""
    def slug(t):
        t = unicodedata.normalize("NFKD", unquote_plus(t)).encode("ascii", "ignore").decode()
        return re.sub(r"[^a-z0-9]+", "-", t.lower()).strip("-")
    partes = urlsplit(url)
    sitio = slug(re.sub(r"^www\.", "", partes.netloc.lower()).split(".")[0]) or "pagina"
    tramos = []
    for seg in reversed([slug(x) for x in partes.path.split("/") if slug(x)]):
        if tramos and len("-".join([seg] + tramos)) > tope:
            break
        tramos.insert(0, seg)
    ruta = "-".join(tramos)
    if len(ruta) > tope:   # un solo tramo larguísimo: cortar en un guión
        ruta = ruta[:tope].rsplit("-", 1)[0]
    return f"{sitio}-{ruta}" if ruta else sitio


def cmd_raw(wiki, args):
    """Prepara un archivo para /wiki-ingest. Un archivo está ingerido si alguna
    nota atómica lo menciona como `raw/<nombre>`: las nuevas lo llevan en el
    frontmatter (`source:`), las anteriores a /wiki-ingest en el cuerpo
    (`Source: raw/...`). Sin registro aparte."""
    def citado_por(nombre):
        return [f.stem for f in sorted(wiki.atomic.glob("*.md"))
                if f"raw/{nombre}" in f.read_text(errors="ignore")]

    if args[:1] == ["--subir"]:
        rel = f"raw/{' '.join(args[1:]).strip()}"
        if not (wiki.root / rel).is_file():
            sys.exit(f"❌ No existe: {rel}")
        if not (wiki.root / ".git").is_dir():
            sys.exit("❌ La wiki es local (sin repo): no hay adónde subirlo")
        # -f pasa por encima de .git/info/exclude, y una vez trackeado el
        # exclude ya no lo afecta: no hace falta limpiar la línea
        run_git(["add", "-f", "--", rel], cwd=wiki.root)
        mb = (wiki.root / rel).stat().st_size / 1024 / 1024
        print(f"✓ {rel} se sube en el próximo /wiki-sync (+{mb:.1f} MB al repo)")
        return

    arg = " ".join(args).strip()
    if not arg:
        pendientes = [f.name for f in sorted(wiki.raw.iterdir())
                      if f.is_file() and not f.name.startswith("sessions_")
                      and f.suffix != ".template"   # plantillas, no fuentes
                      and not citado_por(f.name)]
        print("Pendientes en raw/ (ninguna nota los cita):")
        print("\n".join(f"  raw/{n}" for n in pendientes) or "  (ninguno)")
        return

    if re.match(r"https?://", arg):
        # Una página no se copia: la lee el agente con sus herramientas y guarda
        # el texto acá. Esto sólo dice si ya se guardó y con qué nombre.
        url = arg.split()[0].split("#")[0].rstrip("/")
        previas = [f for f in sorted(wiki.raw.glob("*.md"))
                   if f"url: {url}\n" in f.read_text(errors="ignore")]
        for f in previas:
            print(f"⚠️  ya guardada en raw/{f.name}")
            for stem in citado_por(f.name):
                print(f"⚠️  ya ingerido en: {stem}")
        if previas:
            return
        base = _nombre_de_link(url)
        nombre, n = f"{base}.md", 2
        while (wiki.raw / nombre).exists():
            nombre, n = f"{base}-{n}.md", n + 1
        print(f"link nuevo: guarda el texto en {wiki.raw / nombre}")
        print(f"con este encabezado:\n---\nurl: {url}\nfecha: {datetime.now():%Y-%m-%d}\n---")
        return

    origen = Path(_native_path(arg)).expanduser()
    if not origen.is_file():
        sys.exit(f"❌ No existe: {origen}")
    destino = wiki.raw / origen.name
    if origen.resolve() != destino.resolve():
        if destino.exists():
            sys.exit(f"❌ Ya hay otro raw/{origen.name} — renombrá el archivo para no pisarlo")
        shutil.copy2(origen, destino)
        print(f"✓ copiado a raw/{origen.name}")
    print(f"archivo: {destino} ({destino.stat().st_size // 1024} KB)")
    wiki.excluir_pesados()
    for stem in citado_por(destino.name):
        print(f"⚠️  ya ingerido en: {stem}")


def cmd_context(wiki, args):
    """Todo el contexto inicial de un slash command en una sola línea.

    Los comandos pre-aprobaban `Bash(bash -c:*)` para sus líneas `!`, y eso
    le aprobaba al modelo cualquier comando escrito dentro de las comillas —
    también lo que le pidiera un documento malicioso. Ahora cada comando tiene
    una sola línea (`cli.py context <modo>`) y una regla exacta."""
    modo = args[0] if args else ""
    # el argumento llega en un solo string ("$ARGUMENTS"): separar palabras
    resto = " ".join(args[1:]).split()

    def datos(w, a):
        print(w.root)

    def topics(w, a):
        f = w.root / "topics.json"
        print(f.read_text() if f.exists() else "sin topics.json")

    def cambios(w, a):
        for g in (["log", "--oneline", "-10"], ["status", "-s"]):
            code, out = run_git(g, cwd=Path.cwd())
            if code != 0:
                print("(la carpeta actual no es un repo git)")
                return
            print("\n".join(out.splitlines()[:20]))

    pull = ("Sync", cmd_sync, ["pull"])
    nuevo_id = ("ID para nota nueva", cmd_new_id, [])
    carpeta = ("Carpeta de datos", datos, [])
    vocabulario = ("Vocabulario de topics", topics, [])
    existentes = ("Notas que ya existen (las más recientes)", cmd_titles, ["6000"])
    modos = {
        "ingest": [pull, ("Archivo o link", cmd_raw, resto), nuevo_id, carpeta,
                   vocabulario, existentes],
        "load": [pull, ("Repo actual", cmd_resolve, ["."]),
                 ("Resultados de búsqueda", cmd_search, resto), carpeta],
        "export": [pull, ("Repo actual (metadato opcional)", cmd_resolve, resto[:1] or ["."]),
                   nuevo_id, carpeta, vocabulario, existentes,
                   ("Cambios de la sesión", cambios, [])],
        "import": [pull, ("Extracción", cmd_extract_sessions, resto or ["all"]), carpeta],
        "lint": [("Lint automático", cmd_lint, []), carpeta],
        "status": [("Estado", cmd_status, []), ("Repos locales detectados", cmd_detect, [])],
        "sync": [("Resultado del sync", cmd_sync, resto or ["full"]), carpeta],
    }
    if modo not in modos:
        sys.exit(f"Uso: cli.py context {'|'.join(modos)} [argumento]")
    for titulo, fn, a in modos[modo]:
        print(f"\n### {titulo}")
        try:
            fn(wiki, a)
        except SystemExit as e:
            # Claude Code aborta el slash command entero si la línea falla:
            # un error en una sección no puede salir de acá
            if e.code not in (None, 0):
                print(e.code if isinstance(e.code, str) else f"(terminó con código {e.code})")


COMMANDS = {
    "status": cmd_status,
    "resolve": cmd_resolve,
    "detect": cmd_detect,
    "search": cmd_search,
    "check-context": cmd_search,  # compat v1
    "lint": cmd_lint,
    "lint-wiki": cmd_lint,  # compat v1
    "sync": cmd_sync,
    "publish": cmd_publish,
    "titles": cmd_titles,
    "new-id": cmd_new_id,
    "raw": cmd_raw,
    "context": cmd_context,
    "extract-sessions": cmd_extract_sessions,
}


def main():
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help", "help"):
        print(__doc__)
        return
    cmd = sys.argv[1]
    if cmd not in COMMANDS:
        print(f"Comando desconocido: {cmd}")
        print(f"Disponibles: {', '.join(sorted(set(COMMANDS)))}")
        sys.exit(1)
    COMMANDS[cmd](Wiki(), sys.argv[2:])


if __name__ == "__main__":
    main()
