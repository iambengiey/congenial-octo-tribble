# Contributing

1. Update data packs under `data/packs/<COUNTRY>/`.
2. Add sample datasets under `data/samples/` for offline builds.
3. Run `make sample` and verify the generated `/site` output.
4. Run `make test` and `make lint` before committing.

All changes must preserve the training-only disclaimer and avoid any GO/NO-GO decision output.
