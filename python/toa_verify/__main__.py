"""CLI: python -m toa_verify path/to/toa.json"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .verify import verify_document


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify a toa/0.1 document")
    parser.add_argument("document", type=Path, help="Path to TOA JSON file")
    parser.add_argument(
        "--public-key",
        type=Path,
        default=None,
        help="Path to keys/*.json (default: bundled agentstatus-v1)",
    )
    parser.add_argument(
        "--require-emitter",
        default=None,
        help="Fail unless emitter.name matches (e.g. agentstatus)",
    )
    parser.add_argument(
        "--require-layer",
        action="append",
        default=[],
        metavar="LAYER=STATUS",
        help="Require layer status, e.g. functional=pass (repeatable)",
    )
    args = parser.parse_args(argv)

    doc = json.loads(args.document.read_text(encoding="utf-8"))
    result = verify_document(
        doc,
        public_key=args.public_key,
        require_emitter=args.require_emitter,
    )
    if not result.get("valid"):
        print(json.dumps(result, indent=2))
        return 1

    layers = result.get("layers") or {}
    for req in args.require_layer:
        if "=" not in req:
            print(json.dumps({"valid": False, "reason": f"bad_require_layer:{req}"}, indent=2))
            return 1
        layer, want = req.split("=", 1)
        got = layers.get(layer)
        if got != want:
            print(
                json.dumps(
                    {
                        "valid": False,
                        "reason": f"layer_mismatch:{layer}",
                        "expected": want,
                        "got": got,
                    },
                    indent=2,
                )
            )
            return 1

    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
