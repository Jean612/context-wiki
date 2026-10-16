#!/usr/bin/env python3
"""
Self-check del CLI y del instalador. Correr:  python3 test_cli.py

Sin frameworks a propósito: son subprocesos reales contra carpetas temporales.
Cada caso reproduce un bug que YA ocurrió — si alguno vuelve, esto falla.
"""

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

TOOL = Path(__file__).parent.resolve()

GIT_ENV = {
    "GIT_AUTHOR_NAME": "test", "GIT_AUTHOR_EMAIL": "test@test",
    "GIT_COMMITTER_NAME": "test", "GIT_COMMITTER_EMAIL": "test@test",
    "GIT_CONFIG_GLOBAL": "/dev/null",
}


def run(args, home, cwd=None):
    """Corre cli.py con un HOME aislado. Retorna (exit_code, salida)."""
    env = {**os.environ, **GIT_ENV, "HOME": str(home)}
    r = subprocess.run([sys.executable, str(TOOL / "cli.py")] + args,
                       capture_output=True, text=True, env=env, cwd=cwd)
    return r.returncode, r.stdout + r.stderr


def write_config(home, **values):
    d = Path(home) / ".config" / "context-wiki"
    d.mkdir(parents=True, exist_ok=True)
    (d / "config").write_text(
        "".join(f'{k}="{v}"\n' for k, v in values.items()))


def git(args, cwd):
    env = {**os.environ, **GIT_ENV}
    return subprocess.run(["git"] + args, cwd=str(cwd), capture_output=True,
                          text=True, env=env)


def fake_repo(path, remote_slug):
    """Un repo git con un remote, para probar la derivación de nombres."""
    path.mkdir(parents=True, exist_ok=True)
    git(["init", "-q"], path)
    git(["remote", "add", "origin",
         f"git@github.com:org/{remote_slug}.git"], path)


# ─────────────────────────────────────────────────────────── casos

def test_sin_config_no_contamina_la_herramienta(home, data):
    """El CLI sin config creaba atomic/ raw/ synthesis/ dentro de sí mismo."""
    copia = Path(home) / "tool"
    shutil.copytree(TOOL, copia, ignore=shutil.ignore_patterns(".git", "__pycache__"))
    env = {**os.environ, "HOME": str(home)}
    r = subprocess.run([sys.executable, str(copia / "cli.py"), "status"],
                       capture_output=True, text=True, env=env)
    assert r.returncode != 0, "debería fallar sin config"
    assert "install.sh" in (r.stdout + r.stderr), "debería decir cómo instalar"
    for d in ("atomic", "raw", "synthesis"):
        assert not (copia / d).exists(), f"creó {d}/ dentro de la herramienta"


def test_data_dir_dentro_de_la_herramienta_se_rechaza(home, data):
    write_config(home, DATA_DIR=str(TOOL / "notas"), PROJECT_DIR=str(data))
    code, out = run(["status"], home)
    assert code != 0 and "dentro de la herramienta" in out, out


def test_wiki_local_sin_git_funciona(home, data):
    """Offline por default: sin remote, sync no hace red y no es un error."""
    write_config(home, DATA_DIR=str(data), PROJECT_DIR=str(data))
    code, out = run(["status"], home)
    assert code == 0 and "local (sin publicar)" in out, out

    code, out = run(["sync"], home)
    assert code == 0, "sync no debe fallar en una wiki local"
    assert "nada que sincronizar" in out, out


def test_publish_sube_solo_contenido(home, data):
    """`sync push` hacía `git add -A` y barría basura junto con las notas."""
    remote = Path(home) / "remote.git"
    git(["init", "--bare", "-q", str(remote)], home)

    (data / "atomic").mkdir(parents=True, exist_ok=True)
    (data / "atomic" / "202601010000_repo_nota.md").write_text("# nota\n")
    (data / "basura.tmp").write_text("ruido\n")
    (data / ".obsidian").mkdir(exist_ok=True)
    (data / ".obsidian" / "workspace.json").write_text("{}\n")

    write_config(home, DATA_DIR=str(data), PROJECT_DIR=str(data))
    code, out = run(["publish", str(remote)], home)
    assert code == 0, out

    # el HEAD del bare apunta al default de git local (puede ser master);
    # lo que importa es la rama a la que publish realmente subió.
    subido = git(["ls-tree", "-r", "--name-only", "main"], remote).stdout.split()
    assert "atomic/202601010000_repo_nota.md" in subido, subido
    assert "basura.tmp" not in subido, f"subió basura: {subido}"
    assert not any(".obsidian" in f for f in subido), f"subió estado local: {subido}"

    ramas = git(["branch", "--format=%(refname:short)"], remote).stdout.split()
    assert ramas == ["main"], f"esperaba main, hay {ramas}"

    code, out = run(["publish", str(remote)], home)
    assert "ya está publicada" in out, "publish debería ser idempotente"


def test_publish_rechaza_un_repo_con_contenido(home, data):
    """Typo en la URL apuntando a una wiki ya publicada: publish no debe
    configurar el remote si el repositorio remoto ya tiene contenido."""
    ocupado = Path(home) / "wiki-ajena"
    (ocupado / "atomic").mkdir(parents=True)
    (ocupado / "atomic" / "202601010000_repo_nota.md").write_text("# nota\n")
    git(["init", "-q"], ocupado)
    git(["add", "-A"], ocupado)
    git(["commit", "-q", "-m", "inicial"], ocupado)

    write_config(home, DATA_DIR=str(data), PROJECT_DIR=str(data))
    code, out = run(["publish", f"file://{ocupado}"], home)
    assert "ya tiene contenido" in out, out

    # no configuró el remote ni tocó nada
    remotes = git(["remote"], data).stdout.split()
    assert remotes == [], f"configuró remote a pesar del rechazo: {remotes}"

    # un repo vacío sigue funcionando
    (data / "atomic").mkdir(parents=True, exist_ok=True)
    (data / "atomic" / "202601010000_repo_propia.md").write_text("# nota\n")
    vacio = Path(home) / "vacio.git"
    git(["init", "--bare", "-q", str(vacio)], home)
    code, out = run(["publish", str(vacio)], home)
    assert code == 0 and "Wiki publicada" in out, out


def test_nombre_de_repo_sale_del_remote(home, data):
    """Sin registro: el nombre se deriva, y la carpeta puede llamarse distinto."""
    repos = Path(home) / "repos"
    fake_repo(repos / "carpeta-con-otro-nombre", "api-backend")
    write_config(home, DATA_DIR=str(data), PROJECT_DIR=str(repos))

    code, out = run(["resolve", str(repos / "carpeta-con-otro-nombre")], home)
    assert code == 0 and "repo: api-backend" in out, out


def test_renames_cruzan_la_busqueda(home, data):
    """Una nota vieja con el nombre anterior tiene que aparecer igual."""
    (data / "atomic").mkdir(parents=True, exist_ok=True)
    (data / "atomic" / "202601010000_NombreViejo_algo.md").write_text(
        "---\nid: 202601010000\n---\n# Algo en NombreViejo\n")
    (data / "renames.json").write_text(
        '{"renames": {"nombre-nuevo": ["NombreViejo"]}}\n')
    write_config(home, DATA_DIR=str(data), PROJECT_DIR=str(data))

    code, out = run(["search", "nombre-nuevo"], home)
    assert code == 0 and "202601010000_NombreViejo_algo.md" in out, out


def test_topics_expanden_la_busqueda(home, data):
    """"auth" y "autenticación" deben encontrar las mismas notas mediante el
    vocabulario controlado de topics.json."""
    (data / "atomic").mkdir(parents=True, exist_ok=True)
    (data / "atomic" / "202601010000_login_con_tokens.md").write_text(
        "---\nid: 202601010000\ntags: [auth]\n---\n# Flujo de autenticación\n")
    (data / "topics.json").write_text(
        '{"topics": {"auth": ["autenticación", "login"]}}\n')
    write_config(home, DATA_DIR=str(data), PROJECT_DIR=str(data))

    code, out = run(["search", "autenticación"], home)
    assert code == 0 and "202601010000_login_con_tokens.md" in out, out
    assert "auth" in out, "el alias canónico debería aparecer en la expansión"


def test_lint_avisa_notas_sin_links_y_muy_largas(home, data):
    """Regla de wikilinks salientes y límite de tamaño de página: las notas
    largas cuestan tokens en cada /wiki-load."""
    (data / "atomic").mkdir(parents=True, exist_ok=True)
    (data / "atomic" / "202601010000_sin_links.md").write_text(
        "---\nid: 202601010000\n---\n# Aislada\nSin links.\n")
    (data / "atomic" / "202601010001_con_links.md").write_text(
        "---\nid: 202601010001\n---\n# Enlazada\nVer [[202601010000_sin_links]].\n")
    (data / "atomic" / "202601010002_larga.md").write_text(
        "---\nid: 202601010002\n---\n# Larga\n" + "palabra " * 1300
        + "\n[[202601010000_sin_links]]\n")
    write_config(home, DATA_DIR=str(data), PROJECT_DIR=str(data))

    code, out = run(["lint"], home)
    assert code == 0, out
    assert "sin links salientes" in out and "202601010000_sin_links" in out, out
    assert "sobre 1200 palabras" in out and "202601010002_larga" in out, out
    assert "202601010001_con_links" not in out, "acusó a la nota enlazada"


def test_titles_lista_notas_con_titulo_y_respeta_el_tope(home, data):
    """El escritor necesita ver qué ya existe, o enlaza sólo su propia sesión."""
    (data / "atomic").mkdir(parents=True, exist_ok=True)
    for i in range(5):
        (data / "atomic" / f"20260101000{i}_nota_{i}.md").write_text(
            f"---\nid: 20260101000{i}\n---\n# Título de la nota {i}\n\ncuerpo\n")
    write_config(home, DATA_DIR=str(data), PROJECT_DIR=str(data))

    code, out = run(["titles"], home)
    assert code == 0, out
    assert "202601010004_nota_4 — Título de la nota 4" in out, out
    # más nueva primero: el escritor ve lo reciente aunque se corte la lista
    assert out.index("nota_4") < out.index("nota_0"), "no ordenó de nueva a vieja"

    code, out = run(["titles", "60"], home)
    assert "notas en total" in out, "no avisó que truncó"
    assert len([l for l in out.splitlines() if " — " in l]) < 5, "ignoró el tope"


def test_raw_copia_lista_pendientes_y_no_pisa(home, data):
    """/wiki-ingest se apoya en `cli.py raw`: copiar a raw/ sin pisar otro
    archivo con el mismo nombre, y saber qué falta ingerir mirando el
    `source:` de las notas, sin un registro aparte."""
    (data / "atomic").mkdir(parents=True, exist_ok=True)
    (data / "raw").mkdir(parents=True, exist_ok=True)
    (data / "raw" / "sessions_web_20260101.md").write_text("x")  # de /wiki-import
    (data / "raw" / "api.md.template").write_text("x")           # plantilla
    (data / "raw" / "viejo.md").write_text("x")
    (data / "atomic" / "202501010000_vieja.md").write_text(       # convención previa
        "# Vieja\n\n- Source: `raw/viejo.md`\n")
    write_config(home, DATA_DIR=str(data), PROJECT_DIR=str(data))

    afuera = Path(home) / "Descargas" / "paper.pdf"
    afuera.parent.mkdir()
    afuera.write_bytes(b"%PDF-1.4 uno")

    code, out = run(["raw", str(afuera)], home)
    assert code == 0, out
    assert (data / "raw" / "paper.pdf").read_bytes() == b"%PDF-1.4 uno", "no copió"

    code, out = run(["raw"], home)
    assert "raw/paper.pdf" in out, f"no lo listó como pendiente: {out}"
    assert "sessions_" not in out, "listó un archivo de /wiki-import"
    assert "template" not in out, "listó una plantilla"
    assert "viejo.md" not in out, "no reconoció la cita en el cuerpo de una nota vieja"

    (data / "atomic" / "202601010000_de_paper.md").write_text(
        "---\nid: 202601010000\nsource: raw/paper.pdf\n---\n# Del paper\n")
    code, out = run(["raw"], home)
    assert "raw/paper.pdf" not in out, "sigue pendiente aunque una nota lo cita"
    code, out = run(["raw", str(data / "raw" / "paper.pdf")], home)
    assert "ya ingerido en: 202601010000_de_paper" in out, out

    afuera.write_bytes(b"%PDF-1.4 otro distinto")
    code, out = run(["raw", str(afuera)], home)
    assert code != 0, "pisó raw/paper.pdf con otro archivo"
    assert (data / "raw" / "paper.pdf").read_bytes() == b"%PDF-1.4 uno"


def test_raw_pesado_no_se_sube_salvo_que_se_pida(home, data):
    """Git guarda cada archivo para siempre: un PDF de 20 MB en raw/ engorda
    la wiki en todas las máquinas aunque después se borre. Lo que pasa de 5 MB
    queda local, con aviso, y se sube sólo con `raw --subir`."""
    grande = 5 * 1024 * 1024 + 1
    remote = Path(home) / "remote.git"
    git(["init", "--bare", "-q", str(remote)], home)
    (data / "atomic").mkdir(parents=True, exist_ok=True)
    (data / "atomic" / "202601010000_nota.md").write_text("# nota\n")
    (data / "raw").mkdir(parents=True, exist_ok=True)
    (data / "raw" / "chico.md").write_text("apunte\n")
    (data / "raw" / "manual.pdf").write_bytes(b"x" * grande)
    write_config(home, DATA_DIR=str(data), PROJECT_DIR=str(data))

    def subido():
        return git(["ls-tree", "-r", "--name-only", "main"], remote).stdout.split()

    code, out = run(["publish", str(remote)], home)
    assert code == 0, out
    assert "raw/chico.md" in subido(), "no subió el archivo chico"
    assert "raw/manual.pdf" not in subido(), "subió el pesado al publicar"
    assert "raw --subir manual.pdf" in out, f"no dijo cómo subirlo: {out}"

    # copiado con `raw` (lo que hace /wiki-ingest): avisa en el momento
    afuera = Path(home) / "paper.pdf"
    afuera.write_bytes(b"y" * grande)
    code, out = run(["raw", str(afuera)], home)
    assert "raw/paper.pdf" in out and "no se sube" in out, out
    for _ in range(2):
        run(["sync", "push", "-m", "x"], home)
    assert "raw/paper.pdf" not in subido(), "sync subió el pesado"
    exclude = (data / ".git" / "info" / "exclude").read_text()
    assert exclude.count("/raw/paper.pdf") == 1, f"exclude duplicado: {exclude}"

    # copiado a mano a raw/, sin pasar por ningún comando: lo frena sync
    (data / "raw" / "a_mano.pdf").write_bytes(b"z" * grande)
    code, out = run(["sync", "push", "-m", "x"], home)
    assert "raw/a_mano.pdf" not in subido(), "sync subió un pesado copiado a mano"
    assert "raw/a_mano.pdf" in out and "no se sube" in out, f"no avisó: {out}"

    code, out = run(["raw", "--subir", "manual.pdf"], home)
    assert code == 0, out
    code, out = run(["sync", "push", "-m", "subo el manual"], home)
    assert "raw/manual.pdf" in subido(), f"--subir no lo subió: {out}"
    assert "raw/paper.pdf" not in subido(), "--subir de uno subió también el otro"


def test_raw_con_link_sugiere_nombre_y_detecta_lo_ya_guardado(home, data):
    """/wiki-ingest con un link: el agente guarda el texto en raw/ con la URL
    en el encabezado. `raw <url>` dice dónde guardarlo, y la segunda vez que
    ya se guardó, para no volver a leer la página."""
    (data / "atomic").mkdir(parents=True, exist_ok=True)
    (data / "raw").mkdir(parents=True, exist_ok=True)
    write_config(home, DATA_DIR=str(data), PROJECT_DIR=str(data))
    url = "https://medium.com/@ana/zettelkasten-para-devs-9f1"

    code, out = run(["raw", url + "/#comentarios"], home)
    assert code == 0, out
    assert "raw/medium-ana-zettelkasten-para-devs-9f1.md" in out, out
    assert f"url: {url}\n" in out, "el encabezado no normalizó la URL"

    snap = data / "raw" / "medium-ana-zettelkasten-para-devs-9f1.md"
    snap.write_text(f"---\nurl: {url}\nfecha: 2026-10-13\n---\n# Artículo\n")
    code, out = run(["raw", url], home)
    assert "ya guardada en raw/" + snap.name in out, out
    assert "ya ingerido" not in out, "lo marcó ingerido sin notas que lo citen"

    (data / "atomic" / "202610130000_zettel.md").write_text(
        f"---\nsource: raw/{snap.name}\n---\n# Zettel\n")
    code, out = run(["raw", url], home)
    assert "ya ingerido en: 202610130000_zettel" in out, out

    code, out = run(["raw", "https://medium.com/@ana/otro"], home)
    snap2 = data / "raw" / "medium-ana-otro.md"
    snap2.write_text("---\nurl: https://medium.com/@ana/otro-distinto\n---\n")
    code, out = run(["raw", "https://medium.com/@ana/otro"], home)
    assert "medium-ana-otro-2.md" in out, f"pisaría otro archivo: {out}"

    # el nombre sale del final de la ruta: cortar host+ruta a 60 caracteres
    # partía el ID de la página de Confluence y nunca llegaba al título
    code, out = run(["raw", "https://acme.atlassian.net/wiki/spaces/DEV/pages/2426404881/"
                            "Setup+asistido+para+perfiles+no-dev+propuesta+inicial"], home)
    assert "raw/acme-setup-asistido-para-perfiles-no-dev-propuesta-inicial.md" in out, out
    code, out = run(["raw", "https://docs.ejemplo.org/guia/configuraci%C3%B3n"], home)
    assert "raw/docs-guia-configuracion.md" in out, f"no limpió el acento: {out}"


def test_context_junta_todo_y_un_error_no_lo_aborta(home, data):
    """Los slash commands pre-aprobaban `Bash(bash -c:*)` para sus líneas de
    contexto, y eso aprobaba cualquier comando. Ahora cada uno tiene una sola
    línea (`cli.py context`) y una regla exacta. Si esa línea falla, Claude
    Code aborta el comando entero: un error en una sección no puede salir."""
    (data / "atomic").mkdir(parents=True, exist_ok=True)
    (data / "atomic" / "202601010000_auth.md").write_text("# Auth\ntokens jwt\n")
    write_config(home, DATA_DIR=str(data), PROJECT_DIR=str(data))

    code, out = run(["context", "ingest", "/no/existe.pdf"], home)
    assert code == 0, f"un archivo inexistente abortó el contexto: {out}"
    for titulo in ("### Archivo o link", "No existe", "### ID para nota nueva",
                   "### Vocabulario de topics", "202601010000_auth — Auth"):
        assert titulo in out, f"falta {titulo!r}: {out}"

    code, out = run(["context", "load", "jwt"], home)
    assert code == 0, out
    assert "202601010000_auth" in out, f"no buscó: {out}"

    for modo in ("export", "import", "lint", "status", "sync"):
        code, out = run(["context", modo], home)
        assert code == 0 and "### " in out, f"context {modo} falló: {out}"

    for f in sorted((TOOL / "claude-commands").glob("*.md")):
        cmd, texto = f.stem, f.read_text()
        assert "bash -c" not in texto, f"{cmd} volvió a usar bash -c (aprobaba cualquier comando)"
        assert "Bash(git:*)" not in texto, f"{cmd} aprueba cualquier git (git -c corre comandos)"
        assert "Write" not in texto.split("---")[1], f"{cmd} aprueba escribir en cualquier ruta"
        # Claude Code reemplaza "$0" por la primera palabra del argumento antes
        # de ejecutar: la regla exacta deja de coincidir y la búsqueda pierde
        # el resto de las palabras. "$*" no lo toca.
        assert '"$0"' not in texto, f'{cmd} usa "$0", que Claude Code reemplaza'


def test_lint_no_acusa_notas_anteriores_al_vocabulario(home, data):
    """Las notas viejas son inmutables: avisar por ellas es ruido permanente."""
    (data / "atomic").mkdir(parents=True, exist_ok=True)
    (data / "atomic" / "202501010000_vieja.md").write_text(
        "---\nid: 202501010000\ntags: [tag-raro-de-antes]\n---\n# Vieja\n")
    (data / "atomic" / "202612310000_nueva.md").write_text(
        "---\nid: 202612310000\ntags: [otro-tag-raro]\n---\n# Nueva\n")
    (data / "topics.json").write_text(
        '{"vigente_desde": "202606010000", "topics": {"auth": ["login"]}}\n')
    write_config(home, DATA_DIR=str(data), PROJECT_DIR=str(data))

    code, out = run(["lint"], home)
    assert code == 0, out
    assert "otro-tag-raro" in out, "no avisó por la nota posterior al vocabulario"
    assert "tag-raro-de-antes" not in out, "acusó a una nota anterior al vocabulario"


def test_lint_avisa_tags_fuera_del_vocabulario(home, data):
    """Sin aviso, los sinónimos se acumulan en silencio entre sesiones."""
    (data / "atomic").mkdir(parents=True, exist_ok=True)
    (data / "atomic" / "202601010000_nota_ok.md").write_text(
        "---\nid: 202601010000\ntags: [auth]\n---\n# Bien\n")
    (data / "atomic" / "202601010001_nota_mal.md").write_text(
        "---\nid: 202601010001\ntags: [graphql, auth]\n---\n# Mal\n")
    (data / "topics.json").write_text('{"topics": {"auth": ["login"]}}\n')
    write_config(home, DATA_DIR=str(data), PROJECT_DIR=str(data))

    code, out = run(["lint"], home)
    assert code == 0, out
    assert "fuera de topics.json" in out and "graphql" in out, out
    assert "nota_ok" not in out.split("fuera de topics.json")[1].split("✓")[0], \
        "acusó a la nota que sí está en el vocabulario"

    # sin topics.json no hay vocabulario que violar: el chequeo no corre
    (data / "topics.json").unlink()
    code, out = run(["lint"], home)
    assert code == 0 and "topics.json" not in out, out


def test_lint_avisa_aliases_solo_en_las_notas_de_hoy(home, data):
    """Un alias pasaba el lint como "en el vocabulario": una nota se etiquetó
    `prompts` en vez de `claude-code`. Se avisa sólo en las notas de hoy,
    porque las anteriores son inmutables y no se pueden corregir."""
    from datetime import datetime
    hoy = datetime.now().strftime("%Y%m%d")
    (data / "atomic").mkdir(parents=True, exist_ok=True)
    (data / "atomic" / f"{hoy}0900_con_alias.md").write_text(
        "---\ntags: [prompts, claude-code]\n---\n# Hoy\n")
    (data / "atomic" / f"{hoy}0901_canonica.md").write_text(
        "---\ntags: [claude-code]\n---\n# Hoy bien\n")
    (data / "atomic" / "202601010000_vieja_con_alias.md").write_text(
        "---\ntags: [prompts]\n---\n# Vieja\n")
    (data / "topics.json").write_text(
        '{"topics": {"claude-code": ["prompts", "claude-code"]}}\n')
    write_config(home, DATA_DIR=str(data), PROJECT_DIR=str(data))

    code, out = run(["lint"], home)
    assert code == 0, out
    assert "alias en vez del tag canónico" in out, out
    seccion = out.split("alias en vez del tag canónico")[1].split("→ son de hoy")[0]
    assert f"{hoy}0900_con_alias: prompts → claude-code" in seccion, seccion
    assert "canonica" not in seccion, "acusó a la nota que usa el canónico"
    assert "vieja_con_alias" not in seccion, "avisó por una nota vieja, que no se puede corregir"
    assert "claude-code → claude-code" not in seccion, "trató al canónico como alias de sí mismo"


def test_detect_no_avisa_por_renames_ya_registrados(home, data):
    """El aviso pedía agregar a renames.json algo que ya estaba ahí."""
    repos = Path(home) / "repos"
    fake_repo(repos / "nombre-viejo", "nombre-nuevo")       # ya registrado
    fake_repo(repos / "otra-carpeta", "otro-nombre")        # sin registrar
    (data / "renames.json").write_text(
        '{"renames": {"nombre-nuevo": ["nombre-viejo"]}}\n')
    write_config(home, DATA_DIR=str(data), PROJECT_DIR=str(repos))

    code, out = run(["detect"], home)
    assert code == 0, out
    # el registrado se muestra, pero sin ⚠️ ni pedir acción
    assert "· nombre-nuevo  (carpeta local: nombre-viejo)" in out, out
    # el no registrado sí avisa
    assert "⚠️" in out and "otro-nombre" in out, out
    assert "1 carpeta(s)" in out, f"debería contar sólo el no registrado:\n{out}"


def test_instalador_acepta_una_url_y_clona(home, data):
    """Pegar la URL del repo de notas debe clonarlo, no crear una carpeta así."""
    copia = Path(home) / "tool"
    shutil.copytree(TOOL, copia, ignore=shutil.ignore_patterns(".git", "__pycache__"))
    repos = Path(home) / "repos"
    fake_repo(repos / "uno", "uno")
    fake_repo(repos / "dos", "dos")
    (Path(home) / ".claude" / "projects").mkdir(parents=True)

    # una wiki "ya publicada" con una nota dentro
    origen = Path(home) / "origen"
    (origen / "atomic").mkdir(parents=True)
    (origen / "atomic" / "202601010000_repo_vieja.md").write_text("# nota previa\n")
    git(["init", "-q"], origen)
    git(["add", "-A"], origen)
    git(["commit", "-q", "-m", "inicial"], origen)

    url = f"file://{origen}"
    env = {**os.environ, **GIT_ENV, "HOME": str(home),
           "WIKI_PROJECT_DIR": str(repos), "WIKI_DATA_DIR": url}
    r = subprocess.run(["bash", str(copia / "install.sh")], capture_output=True,
                       text=True, env=env, stdin=subprocess.DEVNULL)
    assert r.returncode == 0, f"{r.stdout}{r.stderr}"

    destino = Path(home) / "origen"  # basename de la URL
    assert not any(p.name.startswith("file:") for p in Path(home).iterdir()), \
        "creó una carpeta con la URL como nombre"

    cfg = (Path(home) / ".config" / "context-wiki" / "config").read_text()
    assert f'DATA_DIR="{destino}"' in cfg, cfg
    assert (destino / "atomic" / "202601010000_repo_vieja.md").exists(), \
        "las notas previas no quedaron disponibles"


def test_clon_dentro_de_una_carpeta_existente(home, data):
    """Responder '~/code' significa 'metelo ahí adentro', no 'esa es la ruta'."""
    copia = Path(home) / "tool"
    shutil.copytree(TOOL, copia, ignore=shutil.ignore_patterns(".git", "__pycache__"))
    repos = Path(home) / "repos"
    fake_repo(repos / "uno", "uno")
    fake_repo(repos / "dos", "dos")

    origen = Path(home) / "mis-notas"
    (origen / "atomic").mkdir(parents=True)
    (origen / "atomic" / "202601010000_repo_x.md").write_text("# nota\n")
    git(["init", "-q"], origen)
    git(["add", "-A"], origen)
    git(["commit", "-q", "-m", "i"], origen)

    # carpeta contenedora que ya existe y tiene contenido (como ~/code)
    contenedora = Path(home) / "code"
    (contenedora / "otro-proyecto").mkdir(parents=True)

    env = {**os.environ, **GIT_ENV, "HOME": str(home),
           "WIKI_PROJECT_DIR": str(repos),
           "WIKI_DATA_DIR": f"file://{origen}",
           "WIKI_CLONE_DIR": str(contenedora)}
    r = subprocess.run(["bash", str(copia / "install.sh")], capture_output=True,
                       text=True, env=env, stdin=subprocess.DEVNULL)
    assert r.returncode == 0, f"{r.stdout}{r.stderr}"

    esperado = contenedora / "mis-notas"
    assert (esperado / "atomic" / "202601010000_repo_x.md").exists(), \
        f"no clonó dentro de la contenedora:\n{r.stdout}{r.stderr}"
    assert (contenedora / "otro-proyecto").exists(), "pisó la carpeta contenedora"


def test_instalador_ignora_backups_de_configs_de_claude(home, data):
    """Escribía dentro de ~/.claude-*.bak: son respaldos, y minarlos duplica notas."""
    copia = Path(home) / "tool"
    shutil.copytree(TOOL, copia, ignore=shutil.ignore_patterns(".git", "__pycache__"))
    repos = Path(home) / "repos"
    fake_repo(repos / "uno", "uno")
    fake_repo(repos / "dos", "dos")

    # una config viva y dos respaldos indistinguibles por contenido
    for nombre in (".claude", ".claude-empresa.bak", ".claude-personal.old"):
        (Path(home) / nombre / "projects").mkdir(parents=True)
        (Path(home) / nombre / "settings.json").write_text("{}\n")

    env = {**os.environ, **GIT_ENV, "HOME": str(home),
           "WIKI_PROJECT_DIR": str(repos), "WIKI_DATA_DIR": str(data)}
    r = subprocess.run(["bash", str(copia / "install.sh")], capture_output=True,
                       text=True, env=env, stdin=subprocess.DEVNULL)
    assert r.returncode == 0, f"{r.stdout}{r.stderr}"

    assert (Path(home) / ".claude" / "commands" / "wiki-load.md").exists(), \
        "no instaló en la config viva"
    for backup in (".claude-empresa.bak", ".claude-personal.old"):
        assert not (Path(home) / backup / "commands").exists(), \
            f"escribió dentro del respaldo {backup}"


def test_instalador_rechaza_la_herramienta_con_barra_final(home, data):
    """El autocompletado con Tab deja '/' al final; el guard debe verlo igual.

    Hoy pasa porque el glob "$TOOL_DIR"/* matchea la cadena vacía. Queda como
    red por si alguien reescribe esa comparación usando sólo igualdad.
    """
    copia = Path(home) / "tool"
    shutil.copytree(TOOL, copia, ignore=shutil.ignore_patterns(".git", "__pycache__"))
    repos = Path(home) / "repos"
    fake_repo(repos / "uno", "uno")
    fake_repo(repos / "dos", "dos")

    env = {**os.environ, **GIT_ENV, "HOME": str(home),
           "WIKI_PROJECT_DIR": str(repos), "WIKI_DATA_DIR": f"{copia}/"}
    r = subprocess.run(["bash", str(copia / "install.sh")], capture_output=True,
                       text=True, env=env, stdin=subprocess.DEVNULL)
    assert r.returncode != 0, "aceptó una ruta dentro de la herramienta"
    assert "dentro de la herramienta" in r.stdout + r.stderr, r.stdout + r.stderr


def test_instalador_registra_hook_de_autoactualizacion(home, data):
    """install.sh debe registrar el hook de SessionStart una sola vez, sin
    pisar el resto del settings.json."""
    copia = Path(home) / "tool"
    shutil.copytree(TOOL, copia, ignore=shutil.ignore_patterns(".git", "__pycache__"))
    repos = Path(home) / "repos"
    fake_repo(repos / "uno", "uno")
    fake_repo(repos / "dos", "dos")
    claude = Path(home) / ".claude"
    (claude / "projects").mkdir(parents=True)
    (claude / "settings.json").write_text('{"theme": "dark"}\n')

    env = {**os.environ, **GIT_ENV, "HOME": str(home),
           "WIKI_PROJECT_DIR": str(repos), "WIKI_DATA_DIR": str(data)}
    for _ in range(2):  # dos corridas: el hook no debe duplicarse
        r = subprocess.run(["bash", str(copia / "install.sh")], capture_output=True,
                           text=True, env=env, stdin=subprocess.DEVNULL)
        assert r.returncode == 0, f"{r.stdout}{r.stderr}"

    import json
    cfg = json.loads((claude / "settings.json").read_text())
    assert cfg["theme"] == "dark", "pisó settings existentes"
    comandos = [
        h["command"]
        for entry in cfg["hooks"]["SessionStart"]
        for h in entry["hooks"]
        if h.get("type") == "command"
    ]
    assert len(comandos) == 1, f"hook duplicado: {comandos}"
    ingest = (claude / "commands" / "wiki-ingest.md").read_text()
    assert "__" not in ingest.split("## Tu tarea")[0], f"quedó una plantilla sin reemplazar: {ingest[:400]}"
    assert f"Edit(/{data.resolve()}/**)" in ingest, "la regla de escritura no apunta a las notas"
    linea = f'"{copia}/cli.py" context ingest "$ARGUMENTS"'
    assert linea in ingest and f'"{copia}/cli.py" context ingest *)' in ingest, \
        "la línea de contexto y su regla exacta no apuntan a la herramienta"
    assert "install.sh" in comandos[0] and "context-wiki-autoupdate" in comandos[0]


def test_instalador_no_pone_las_notas_dentro_de_la_herramienta(home, data):
    """El default no debe coincidir con el clon de la herramienta."""
    copia = Path(home) / "context-wiki"
    shutil.copytree(TOOL, copia, ignore=shutil.ignore_patterns(".git", "__pycache__"))
    repos = Path(home) / "repos"
    fake_repo(repos / "uno", "uno")
    fake_repo(repos / "dos", "dos")

    env = {**os.environ, **GIT_ENV, "HOME": str(home),
           "WIKI_PROJECT_DIR": str(repos)}
    r = subprocess.run(["bash", str(copia / "install.sh")],
                       capture_output=True, text=True, env=env, stdin=subprocess.DEVNULL)
    assert r.returncode == 0, f"el instalador falló:\n{r.stdout}{r.stderr}"
    # cfg_get mataba el script con set -e antes de escribir la config
    cfg = Path(home) / ".config" / "context-wiki" / "config"
    assert cfg.exists(), "no escribió la config (¿murió antes de terminar?)"
    for d in ("atomic", "raw", "synthesis"):
        assert not (copia / d).exists(), f"creó {d}/ dentro de la herramienta"


# ─────────────────────────────────────────────────────────── runner

def test_el_hook_avisa_pero_no_ejecuta_lo_que_baja(home, data):
    """El hook de SessionStart sólo hace `git fetch` y avisa si hay commits
    nuevos, sin hacer `git pull` ni ejecutar código recién bajado."""
    origen = Path(home) / "origen"
    shutil.copytree(TOOL, origen, ignore=shutil.ignore_patterns(".git", "__pycache__"))
    git(["init", "-q", "-b", "main"], origen)
    git(["add", "-A"], origen)
    git(["commit", "-qm", "inicial"], origen)

    clon = Path(home) / "clon"
    git(["clone", "-q", str(origen), str(clon)], home)

    # Alguien con push publica un instalador con payload.
    marcador = Path(home) / "EJECUTADO"
    inst = origen / "install.sh"
    inst.write_text(inst.read_text().replace(
        "set -euo pipefail\n", f"set -euo pipefail\ntouch {marcador}\n", 1))
    git(["commit", "-qam", "payload"], origen)

    env = {**os.environ, **GIT_ENV, "HOME": str(home)}
    r = subprocess.run(["bash", str(clon / "install.sh"), "--check-updates"],
                       capture_output=True, text=True, env=env,
                       stdin=subprocess.DEVNULL)
    assert r.returncode == 0, f"{r.stdout}{r.stderr}"
    assert "1 commit" in r.stdout, f"no avisó del commit nuevo: {r.stdout!r}"
    assert str(marcador) not in (clon / "install.sh").read_text(), \
        "bajó el código nuevo al working tree en vez de sólo avisar"


def test_instalador_soporta_antigravity(home, data):
    """Instala skills de Antigravity en ~/.gemini/config/skills/ y copia AGENTS.md."""
    copia = Path(home) / "tool"
    shutil.copytree(TOOL, copia, ignore=shutil.ignore_patterns(".git", "__pycache__"))
    repos = Path(home) / "repos"
    fake_repo(repos / "uno", "uno")

    # Simulamos presencia de ~/.gemini
    (Path(home) / ".gemini").mkdir(parents=True)

    env = {**os.environ, **GIT_ENV, "HOME": str(home),
           "WIKI_PROJECT_DIR": str(repos), "WIKI_DATA_DIR": str(data),
           "WIKI_AGENTS": "antigravity"}
    r = subprocess.run(["bash", str(copia / "install.sh")], capture_output=True,
                       text=True, env=env, stdin=subprocess.DEVNULL)
    assert r.returncode == 0, f"install.sh falló:\n{r.stdout}{r.stderr}"

    skills_dir = Path(home) / ".gemini" / "config" / "skills"
    assert (skills_dir / "wiki-load" / "SKILL.md").exists(), "no instaló skill wiki-load"
    assert (skills_dir / "wiki-export" / "SKILL.md").exists(), "no instaló skill wiki-export"
    assert (skills_dir / "wiki-import" / "SKILL.md").exists(), "no instaló skill wiki-import"
    assert (skills_dir / "wiki-status" / "SKILL.md").exists(), "no instaló skill wiki-status"
    assert (data / "AGENTS.md").exists(), "no copió AGENTS.md a DATA_DIR"


def test_extract_sessions_antigravity(home, data):
    """extract-sessions extrae transcripciones de Antigravity y genera el resumen en raw/."""
    repos = Path(home) / "repos"
    fake_repo(repos / "mi-app", "mi-app")
    write_config(home, TOOL_DIR=str(TOOL), DATA_DIR=str(data), PROJECT_DIR=str(repos))

    # Crear una sesión simulada de Antigravity
    ses_dir = Path(home) / ".gemini" / "antigravity" / "brain" / "test-session-123" / ".system_generated" / "logs"
    ses_dir.mkdir(parents=True)
    transcript = ses_dir / "transcript.jsonl"
    lines = [
        {"type": "USER_INPUT", "source": "USER_EXPLICIT", "content": f"<USER_REQUEST>Implementar autenticación JWT en mi-app</USER_REQUEST>\nCommand Working Directory: {repos / 'mi-app'}"},
        {"type": "PLANNER_RESPONSE", "source": "MODEL", "content": "Entendido, voy a configurar los endpoints de login y registro usando tokens JWT."}
    ]
    import json
    transcript.write_text("\n".join(json.dumps(l) for l in lines) + "\n")

    code, out = run(["extract-sessions", "mi-app"], home)
    assert code == 0, f"falló extract-sessions:\n{out}"
    assert "Fuentes de sesiones detectadas" in out
    assert "Google Antigravity" in out
    assert "1 resumen(es) generado(s) en raw/:" in out

    raw_files = list((data / "raw").glob("sessions_mi-app_*.md"))
    assert len(raw_files) == 1, f"no se creó el archivo en raw/: {list((data / 'raw').glob('*'))}"
    content = raw_files[0].read_text()
    assert "Implementar autenticación JWT" in content
    assert "Antigravity" in content


def test_rutas_y_sesiones_de_windows(home, data):
    """Git Bash escribe la config con /c/Users/... y el Python nativo de
    Windows no lo entiende; y el slug de sesiones reemplazaba sólo "/", así que
    D:\\context-wiki nunca coincidía con la carpeta D--context-wiki de Claude Code."""
    sys.path.insert(0, str(TOOL))
    import cli
    nat = cli._native_path
    assert nat("/c/Users/ana/notas", windows=True) == "C:/Users/ana/notas"
    assert nat("/d", windows=True) == "D:/"
    assert nat("C:/ya/nativa", windows=True) == "C:/ya/nativa"
    assert nat("/home/ana", windows=True) == "/home/ana", "convirtió algo que no es una unidad"
    assert nat("/c/Users/ana", windows=False) == "/c/Users/ana", "convirtió fuera de Windows"
    assert cli._claude_slug("D:\\context-wiki") == "D--context-wiki"
    assert cli._claude_slug("/home/ana/mi_repo.v2") == "-home-ana-mi-repo-v2"


def test_instalador_usa_python_si_python3_es_el_atajo_de_la_store(home, data):
    """El atajo de la Microsoft Store pasa `command -v python3` y falla al
    ejecutarse; python.org instala `python`. El instalador debe elegir el que
    corre y dejarlo en la config para que los comandos usen el mismo."""
    copia = Path(home) / "tool"
    shutil.copytree(TOOL, copia, ignore=shutil.ignore_patterns(".git", "__pycache__"))
    repos = Path(home) / "repos"
    fake_repo(repos / "uno", "uno")
    fake_repo(repos / "dos", "dos")
    claude = Path(home) / ".claude"
    (claude / "projects").mkdir(parents=True)

    bin_ = Path(home) / "bin"
    bin_.mkdir()
    (bin_ / "python3").write_text("#!/bin/sh\nexit 9009\n")  # el atajo de la Store
    (bin_ / "python3").chmod(0o755)
    (bin_ / "python").symlink_to(sys.executable)

    env = {**os.environ, **GIT_ENV, "HOME": str(home),
           "PATH": f"{bin_}:{os.environ['PATH']}",
           "WIKI_PROJECT_DIR": str(repos), "WIKI_DATA_DIR": str(data)}
    r = subprocess.run(["bash", str(copia / "install.sh")], capture_output=True,
                       text=True, env=env, stdin=subprocess.DEVNULL)
    assert r.returncode == 0, f"{r.stdout}{r.stderr}"
    config = (Path(home) / ".config" / "context-wiki" / "config").read_text()
    assert 'PYTHON="python"' in config, f"no eligió python: {config}"
    assert "context-wiki-autoupdate" in (claude / "settings.json").read_text(), \
        "el hook no se registró: el instalador se cortó en el atajo"


def main():
    casos = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    fallos = 0
    for caso in casos:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            data = Path(tmp) / "datos"
            home.mkdir()
            data.mkdir()
            try:
                caso(home, data)
                print(f"  ✓ {caso.__name__}")
            except AssertionError as e:
                fallos += 1
                print(f"  ✗ {caso.__name__}\n      {e}")
            except Exception as e:  # noqa: BLE001
                fallos += 1
                print(f"  ✗ {caso.__name__} — error inesperado: {e!r}")

    print(f"\n{len(casos) - fallos}/{len(casos)} pasaron")
    return 1 if fallos else 0


if __name__ == "__main__":
    sys.exit(main())
