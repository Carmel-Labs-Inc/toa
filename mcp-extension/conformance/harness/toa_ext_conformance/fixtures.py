"""Load golden documents / keys from ``conformance/fixtures/`` when present.

Layout (owned by the fixtures / ``toa_ext`` workstream):

```text
fixtures/
  pass_functional.json
  fail_functional.json
  ...
  keys/toa-conformance-test-v1.json
```

Also accepts legacy ``fixtures/documents/*.json`` and ``keys/toa-conformance.json``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from .constants import FIXTURES_ROOT, KEYS_DIR


class FixturesMissing(Exception):
    """Required fixture file(s) are not present yet."""

    def __init__(self, names: List[str]):
        self.names = names
        super().__init__("fixtures_missing:" + ",".join(names))


def document_path(name: str) -> Path:
    if not name.endswith(".json"):
        name = f"{name}.json"
    # Preferred: fixtures/<name>.json (current pack)
    direct = FIXTURES_ROOT / name
    if direct.is_file():
        return direct
    # Legacy / alternate: fixtures/documents/<name>.json
    nested = FIXTURES_ROOT / "documents" / name
    return nested if nested.is_file() else direct


def key_path() -> Path:
    preferred = KEYS_DIR / "toa-conformance-test-v1.json"
    if preferred.is_file():
        return preferred
    legacy = KEYS_DIR / "toa-conformance.json"
    return legacy if legacy.is_file() else preferred


def load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def try_load_document(name: str) -> Optional[Dict[str, Any]]:
    path = document_path(name)
    if not path.is_file():
        return None
    return load_json(path)


def try_load_key() -> Optional[Dict[str, Any]]:
    path = key_path()
    if not path.is_file():
        return None
    return load_json(path)


def require_documents(*names: str) -> Dict[str, Dict[str, Any]]:
    missing: List[str] = []
    loaded: Dict[str, Dict[str, Any]] = {}
    for name in names:
        doc = try_load_document(name)
        if doc is None:
            missing.append(name if name.endswith(".json") else f"{name}.json")
        else:
            key = name[:-5] if name.endswith(".json") else name
            loaded[key] = doc
    if missing:
        raise FixturesMissing(missing)
    return loaded


def require_key() -> Dict[str, Any]:
    key = try_load_key()
    if key is None:
        raise FixturesMissing(["keys/toa-conformance-test-v1.json"])
    return key


def fixture_status() -> Dict[str, Any]:
    expected_docs = [
        "pass_functional.json",
        "fail_functional.json",
        "expired.json",
        "wrong_tool.json",
        "server_role.json",
        "bad_signature.json",
    ]
    present_docs = [n for n in expected_docs if document_path(n).is_file()]
    key_file = key_path().is_file()
    return {
        "fixtures_root": str(FIXTURES_ROOT),
        "key_path": str(key_path()),
        "key_present": key_file,
        "documents_present": present_docs,
        "documents_missing": [n for n in expected_docs if n not in present_docs],
        "ready_for_crypto_scenarios": key_file and len(present_docs) == len(expected_docs),
    }


def missing_fixture_reason(*doc_names: str, need_key: bool = True) -> Optional[str]:
    """Return a ``fixtures_missing:...`` reason, or None if all present."""
    missing: List[str] = []
    if need_key and try_load_key() is None:
        missing.append("keys/toa-conformance-test-v1.json")
    for name in doc_names:
        fname = name if name.endswith(".json") else f"{name}.json"
        if try_load_document(name) is None:
            missing.append(fname)
    if missing:
        return "fixtures_missing:" + ",".join(missing)
    return None


def default_document_store() -> Dict[str, Dict[str, Any]]:
    """Map ``fixture:<stem>`` and bare stem → document (for reference mode)."""
    store: Dict[str, Dict[str, Any]] = {}
    if not FIXTURES_ROOT.is_dir():
        return store
    for path in FIXTURES_ROOT.glob("*.json"):
        try:
            doc = load_json(path)
        except (OSError, json.JSONDecodeError):
            continue
        store[f"fixture:{path.stem}"] = doc
        store[path.stem] = doc
    return store
