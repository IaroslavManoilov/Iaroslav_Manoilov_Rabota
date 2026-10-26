"""Verify the four local photo-track files structurally; visual review remains required."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

FILES = ('01_white_750.png', '02_application_750.png',
         '03_dimensions_750.png', '04_macro_750.png')


def check(folder: Path) -> dict:
    from PIL import Image
    checks = []
    for name in FILES:
        path = folder / name
        try:
            with Image.open(path) as im:
                actual_format, size = im.format, im.size
                im.verify()
            checks.append({'file': name, 'format': actual_format, 'size': list(size),
                           'ok': actual_format == 'PNG' and size == (750, 750)})
        except (OSError, ValueError, SyntaxError):
            checks.append({'file': name, 'ok': False, 'error': 'missing_or_invalid'})
    return {'structural_ok': all(c['ok'] for c in checks), 'checks': checks,
            'visual_review_required': True, 'workflow_completed': False}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('folder', type=Path)
    args = parser.parse_args()
    result = check(args.folder)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result['structural_ok'] else 1)


if __name__ == '__main__':
    main()
