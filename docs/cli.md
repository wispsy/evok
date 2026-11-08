# Evok CLI Reference (`ev` / `evok`)

Evok provides a unified command-line tool accessible via `ev` or `evok`.

---

## Commands

### `ev init [directory]`
Initialize a clean Python project scaffold with `pyproject.toml`, `README.md`, `src/`, and `tests/`.

```bash
# Initialize in current directory
ev init

# Initialize in a specific directory with custom name
ev init my-project --name my-project
```

### `ev build [directory]`
Build standard PEP 427 pure-Python wheels (`.whl`), PEP 625 source distributions (`.tar.gz`), and standalone `.pyz` executables.

```bash
# Build wheel and sdist into dist/
ev build

# Also generate single-file standalone zipapp (.pyz)
ev build --zipapp
```

### `ev scan [directory]`
Audit your project's codebase using AST analysis to check for missing and dead dependencies.

```bash
ev scan
```

Output:
```
AST Scan Results for: /path/to/project
  Total Imported Modules: 14
  Inferred PyPI Packages: ['pyyaml', 'requests']
  Declared Dependencies:  ['pyyaml', 'rich']

  [!] Missing Dependencies (imported but not declared):
      + requests

  [-] Unused / Dead Dependencies (declared but not imported):
      - rich
```

### `ev prune [directory]`
Automatically prune declared dependencies that are not imported anywhere in your source code.

```bash
ev prune
```

### `ev resolve <requirements...>`
Resolve dependency constraints in-memory and print the resolved dependency graph.

```bash
ev resolve "requests>=2.28" "rich>=13.0"
```

### `ev run <script.py>`
Execute a Python script inside an in-process ephemeral zero-venv environment.

```bash
ev run main.py
```

### `ev info`
Display system details, Python runtime version, global cache path, and active reflink filesystem capability (`clonefile`, `ficlone`, or `hardlink`).

```bash
ev info
```
