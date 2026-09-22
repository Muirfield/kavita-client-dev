'''Canary hooks: value-provider injection (docs/TODO-schemathesis.md, phase 2).

Loaded by Schemathesis through `hooks` in schemathesis.toml. Provider
values come from `kavita_providers.yaml` (parameter -> state key) and
the stack state written by `schemathesis_stack.py --populate`, whose path
arrives via the SCHEMATHESIS_STATE environment variable (set by
schemathesis_canary.py).
'''

from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from schemathesis import hook

REGISTRY = Path(__file__).with_name('kavita_providers.yaml')
STATE_ENV = 'SCHEMATHESIS_STATE'


@lru_cache(maxsize=1)
def _registry() -> dict[str, Any]:
  return yaml.safe_load(REGISTRY.read_text(encoding='utf-8'))


def _state() -> dict[str, Any]:
  path = os.environ.get(STATE_ENV)
  if not path or not Path(path).is_file():
    return {}
  try:
    return json.loads(Path(path).read_text(encoding='utf-8')).get('providers', {})
  except (OSError, json.JSONDecodeError):
    return {}


@hook
def before_call(ctx: object, case: object, **kwargs: object) -> None:  # noqa: ANN001, ANN003, ARG001
  state = _state()
  registry = _registry()
  for parameter, key in registry.get('values', {}).items():
    value = state.get(key)
    if value is None:
      continue
    _inject(case, parameter, value)
  for parameter, value in registry.get('static', {}).items():
    if value is not None:
      _inject(case, parameter, value)


def _inject(case: object, parameter: str, value: Any) -> None:
  query = getattr(case, 'query', None)
  if isinstance(query, dict) and parameter in query:
    query[parameter] = value
  path_parameters = getattr(case, 'path_parameters', None)
  if isinstance(path_parameters, dict) and parameter in path_parameters:
    path_parameters[parameter] = value
