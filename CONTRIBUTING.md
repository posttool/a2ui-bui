# Contributing

Issues and pull requests are welcome.

By submitting a contribution you agree that it is licensed under the license of the files you change: the BUI renderer
in `renderer/` is GPL-3.0-or-later (see [renderer/LICENSE](renderer/LICENSE)); everything else is Apache-2.0 (see
[LICENSE](LICENSE)).

## Setup

```
python3 -m venv venv && venv/bin/pip install -e renderer/ pytest
```

The renderer needs a BUI (`blenderui`) with the Python additions described in the README ("BUI changes"); build it from a
BUI checkout until they are released.

## Checks

```
python3 tools/build_showcases.py && node tools/validate_showcases.mjs     # payloads vs. the catalog spec
venv/bin/python -m pytest renderer/tests -q                              # renderer end to end (headless)
venv/bin/a2ui-bui --showcase all --screenshot /tmp/shots --strict        # look at every showcase
venv/bin/python tools/icon_names.py                                      # prompt icon list vs. BUI's icons
```

Run Python from outside the repo root or with the venv's entry points: the repo's `bui/` folder (the catalog spec) is
not the `bui` package.
