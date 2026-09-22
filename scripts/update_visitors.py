"""Update the shields.io visitor-count badge file as a monotonic high-water mark.

Called by the "Update visitor count" workflow with the count freshly queried
from Application Insights. The stored value never decreases, so the badge does
not decay when telemetry ages out of the retention window.

Usage:
    python scripts/update_visitors.py <queried-count>
"""

import json
import sys
from pathlib import Path
from typing import Any

BADGE_FILE = Path(__file__).resolve().parent.parent / 'visitors.json'

# shields.io endpoint schema keys
ALLOWED_KEYS = {'schemaVersion', 'label', 'message', 'color', 'labelColor',
                'isError', 'namedLogo', 'logoSvg', 'logoColor', 'logoSize', 'style'}


def next_badge(previous_json_text: str, queried: int) -> tuple[dict[str, Any], bool]:
    """Return (badge, changed): the badge dict for max(previous, queried).

    Raises ValueError for a malformed badge file or a non-integer/negative
    queried count - callers must fail loudly rather than commit a bad value.
    """
    if isinstance(queried, bool) or not isinstance(queried, int) or queried < 0:
        raise ValueError(f'Invalid queried visitor count: {queried!r}')
    previous = json.loads(previous_json_text)
    if not isinstance(previous, dict):
        raise TypeError(f'Badge file must contain a JSON object, got {type(previous).__name__}')
    message = previous.get('message')
    if not isinstance(message, str) or not message.isdigit():
        raise ValueError(f'Badge file has no plain-integer message: {message!r}')

    badge = {key: val for key, val in previous.items() if key in ALLOWED_KEYS}
    badge['schemaVersion'] = 1
    badge.setdefault('label', 'visitors')
    badge.setdefault('color', 'green')
    badge['message'] = str(max(int(message), queried))
    return badge, badge['message'] != message


def main(argv: list[str] | None = None) -> None:
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 1:
        sys.exit(f'Usage: {Path(__file__).name} <queried-count>')
    try:
        queried = int(argv[0])
    except ValueError:
        sys.exit(f'Not an integer: {argv[0]!r}')

    badge, changed = next_badge(BADGE_FILE.read_text(encoding='utf-8'), queried)
    if not changed:
        print(f'Visitor count unchanged at {badge["message"]}; nothing to commit.')
        return
    BADGE_FILE.write_text(json.dumps(badge) + '\n', encoding='utf-8')
    print(f'Visitor count updated to {badge["message"]}.')


if __name__ == '__main__':
    main()
