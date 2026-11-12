# Contributing

Issues and pull requests are welcome.

By submitting a contribution you agree that it is licensed under the
Apache License 2.0 (see [LICENSE](LICENSE)), the same license as the project.

## Checks

```
python3 tools/build_showcases.py && node tools/validate_showcases.mjs
python3 tools/shot.py --port 8231 --out /tmp/shots   # all showcases; needs Chrome or Chromium
```

Third-party code lives only in `third_party/` (see `third_party/a2ui_bundle/README.md`).
