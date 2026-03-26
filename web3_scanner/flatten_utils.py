from web3_scanner.setting import PRAGMA_SOLIDITY_RE, PRAGMA_OTHER_RE, SPDX_RE, IMPORT_RE
import pathlib
import json
import re

def normalize_sources(row: dict) -> dict:
    """
    Normalize SourceCode variations into dict[str filename]->str content.
    Etherscan can return:
    - single file: SourceCode is plain solidity string
    - multi-file: stringified JSON with "sources" or a map of files
      Sometimes wrapped with leading/trailing braces "{{ ... }}" legacy.
    """
    src = row["SourceCode"]
    # Trim legacy double-brace wrap: {{ ... }}
    def strip_wrappers(s: str) -> str:
        s = s.strip()
        if s.startswith("{{") and s.endswith("}}"):
            s = s[1:-1]  # remove one layer to get {...}
        return s

    def try_parse_json(s: str):
        try:
            return json.loads(s)
        except Exception:
            return None

    # 1) try parse JSON directly
    j = try_parse_json(src)
    if j is None:
        # 2) try strip legacy wrapper then parse
        j = try_parse_json(strip_wrappers(src))

    files = {}

    if j is None:
        # Single-file source (string)
        name = row.get("ContractName") or "Contract.sol"
        if not name.endswith(".sol"):
            name += ".sol"
        files[name] = src
        return files

    # JSON case:
    # Case A: {"language":"Solidity","sources":{"path.sol":{"content":"..."}}, ...}
    if isinstance(j, dict) and "sources" in j and isinstance(j["sources"], dict):
        for path, meta in j["sources"].items():
            if isinstance(meta, dict) and "content" in meta:
                files[path] = meta["content"]
            elif isinstance(meta, str):
                files[path] = meta
        return files

    # Case B: {"File1.sol":{"content":"..."}, "File2.sol":{"content":"..."}}
    # or {"File1.sol":"code", ...}
    if isinstance(j, dict):
        for k, v in j.items():
            if isinstance(v, dict) and "content" in v:
                files[k] = v["content"]
            elif isinstance(v, str):
                files[k] = v
    if files:
        return files

    # Fallback: treat as single file
    name = row.get("ContractName") or "Contract.sol"
    if not name.endswith(".sol"):
        name += ".sol"
    files[name] = src if isinstance(src, str) else str(src)
    return files

def norm_path(p: str) -> str:
    # Normalize Solidity import-like paths (handle ./, ../)
    return str(pathlib.PurePosixPath(p)).lstrip("./")

def extract_imports(content: str) -> list:
    """Return list of import paths as written (normalized)."""
    paths = []
    for m in IMPORT_RE.finditer(content):
        # group1 or group2 or group3 or group4 depending on syntax
        g = next((g for g in m.groups() if g), None)
        if g:
            paths.append(g)
    return [norm_path(x) for x in paths]

# ---------- Core: detect_root_file & topo DFS

def detect_root_file(files: dict, preferred_contract_name: str | None = None) -> str:
    """
    Detect the root file:
    - a file that is NOT imported by any other file
    - if multiple, prefer file that contains the preferred contract name
    - else, prefer file containing 'constructor'
    - else, pick the lexicographically last (often main contract resides deeper)
    """
    all_files = set(files.keys())
    imported = set()

    for fname, content in files.items():
        for imp in extract_imports(content):
            # try to resolve to a file key
            resolved = resolve_import_key(files, fname, imp)
            if resolved:
                imported.add(resolved)
            else:
                # if cannot resolve, still mark something to avoid false root?
                # We skip; unresolved will be reported later during DFS.
                pass

    candidates = list(all_files - imported)
    if not candidates:
        # fallback: if cycle or everything imported, choose best guess
        candidates = list(all_files)

    # Prefer by contract name
    if preferred_contract_name:
        pat = re.compile(rf'\bcontract\s+{re.escape(preferred_contract_name)}\b')
        for c in candidates:
            if pat.search(files[c]):
                return c
    # Prefer file containing 'constructor'
    for c in candidates:
        if re.search(r'\bconstructor\s*\(', files[c]):
            return c

    # Otherwise pick a stable choice
    candidates.sort()
    return candidates[-1]  # pick last for 'main-ish' tendency

def resolve_import_key(files: dict, current_file: str, import_path: str) -> str | None:
    """
    Resolve an import path to an exact key in `files`.
    Try:
    - relative to current_file's directory
    - normalized absolute match
    - basename unique match
    """
    cur_dir = str(pathlib.PurePosixPath(current_file).parent)
    rel = norm_path(str(pathlib.PurePosixPath(cur_dir, import_path)))
    if rel in files:
        return rel
    # Try normalized path directly
    imp_norm = norm_path(import_path)
    if imp_norm in files:
        return imp_norm
    # Try basename unique match
    base = pathlib.PurePosixPath(import_path).name
    candidates = [k for k in files.keys() if pathlib.PurePosixPath(k).name == base]
    if len(candidates) == 1:
        return candidates[0]
    return None

def build_graph(files: dict) -> dict:
    """
    Return adjacency list: file -> list of resolved dependency file keys.
    """
    g = {}
    for fname, content in files.items():
        deps = []
        for imp in extract_imports(content):
            resolved = resolve_import_key(files, fname, imp)
            if resolved:
                deps.append(resolved)
            else:
                # leave unresolved; we'll error later if needed
                pass
        g[fname] = deps
    return g

def topological_order_dfs(files: dict, root: str) -> list:
    """
    DFS with cycle detection:
    states: 0 unset, 1 temp (in stack), 2 perm (done)
    Return post-order list (deps first, then node)
    """
    graph = build_graph(files)
    state = {k: 0 for k in files.keys()}
    order = []
    unresolved_imports = []

    def dfs(u: str):
        if state[u] == 1:
            raise RuntimeError(f"Cycle detected at {u}")
        if state[u] == 2:
            return
        state[u] = 1
        # traverse dependencies
        for imp in extract_imports(files[u]):
            v = resolve_import_key(files, u, imp)
            if v is None:
                unresolved_imports.append((u, imp))
                continue
            if v not in graph:
                # should not happen, but guard
                unresolved_imports.append((u, imp))
                continue
            dfs(v)
        state[u] = 2
        order.append(u)
    dfs(root)
    # Might be disconnected (libraries not referenced by root): add remaining
    for k in files.keys():
        if state[k] == 0:
            dfs(k)

    # if unresolved_imports:
    #     # Warn but continue; often OZ imports are bundled and resolved by basename
    #     missing = "\n".join([f"- {u} imports {imp}" for (u, imp) in unresolved_imports])
    #     raise RuntimeError("Unresolved imports:\n" + missing)

    # order is deps-first then node (post-order)
    # To be safe, de-duplicate keeping first occurrence
    seen = set()
    final = []
    for f in order:
        if f not in seen:
            seen.add(f)
            final.append(f)
    return final, unresolved_imports

def strip_import_lines(content: str) -> str:
    return IMPORT_RE.sub("", content)

def remove_comments(code: str) -> str:
    """Xóa tất cả comment (block, NatSpec, inline) trong Solidity, không giữ SPDX"""
    # Xóa tất cả block comment /* ... */
    code = re.sub(r'/\*.*?\*/', '', code, flags=re.S)
    # Xóa inline comment // (trừ URL, trừ SPDX vì sẽ xử lý riêng)
    code = re.sub(r'//(?!https?://| SPDX-License-Identifier).*$', '', code, flags=re.M)
    # Xóa dòng trống
    code = '\n'.join(filter(str.strip, code.splitlines()))
    return code

def flatten_sources(files: dict, order: list,unresolved_imports=None ) -> str:
    """
    Build a single file:
    - Keep a single SPDX (first found) at very top
    - Keep a single `pragma solidity ...;` (first found)
    - Keep each non-solidity pragma (abicoder/experimental) once
    - Remove all import lines
    - Remove comments (inline, block, NatSpec)
    - Preserve the rest in dependency order
    """
    spdx = None
    pragma_solidity = None
    seen_other_pragmas = set()
    body_parts = []
    for fname in order:
        src = files[fname]
        # capture SPDX
        if spdx is None:
            m = SPDX_RE.search(src)
            if m:
                spdx = m.group(0)
        # capture pragma solidity
        if pragma_solidity is None:
            m = PRAGMA_SOLIDITY_RE.search(src)
            if m:
                pragma_solidity = m.group(0)
        # capture other pragmas
        for m in PRAGMA_OTHER_RE.finditer(src):
            seen_other_pragmas.add(m.group(0))
        # remove SPDX + pragmas + imports
        s = SPDX_RE.sub("", src)
        s = PRAGMA_SOLIDITY_RE.sub("", s)
        s = PRAGMA_OTHER_RE.sub("", s)
        s = strip_import_lines(s)
        # remove all comments
        s = remove_comments(s)
        body_parts.append(s.strip())
    # build header
    header = []
    if spdx:
        header.append(spdx)
    if pragma_solidity:
        header.append(pragma_solidity)
    header.extend(sorted(seen_other_pragmas))
     # unresolved imports section
    if unresolved_imports:
        unresolved_lines = [
            f'import "{imp}";' for (_, imp) in unresolved_imports
        ]
        header.extend(unresolved_lines)  # stable order
    # join body
    combined = "\n\n".join([*header, *body_parts]).strip()
    combined = re.sub(r'\n{3,}', '\n\n', combined)  # collapse blank lines
    return combined + "\n"