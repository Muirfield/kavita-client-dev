'''Shared test configuration.

Makes the repo root (for `fix_spec`) and the generated client importable.
The generated client is imported from an *installed* package when present, so
a release can be verified against the exact built artifact; otherwise the
generated source tree in the repository is used.
'''

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent

if str(ROOT) not in sys.path:
  sys.path.insert(0, str(ROOT))

try:
  import kavita_client  # noqa: F401  (installed package wins)
except ImportError:
  # Fall back to a generated source tree: the patched build first, then the
  # raw (nightly) build.
  for pattern in ('*-fixed/kavita-client', '*/kavita-client'):
    matches = sorted(ROOT.glob(pattern))
    if matches:
      sys.path.insert(0, str(matches[0]))
      break
