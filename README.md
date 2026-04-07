# Generate Stars

GTK4 desktop app for generating clustered star coordinates.

## Bundles

The project uses PyInstaller to build self-contained desktop bundles. With GTK4 and PyGObject this means a portable
bundle directory plus an archive, not a single fully static executable.

## Config

The app loads `config.toml` from the runtime directory:

- packaged bundle: next to the bundle entry executable
- source run: project root, next to `generate_stars_launcher.py`

If `config.toml` does not exist, the app creates it from the packaged `default_config.toml` on first launch.

Local build:

```bash
python3 -m pip install --user pyinstaller
python3 scripts/build_bundle.py --target linux
```

Windows build on a native Windows or MSYS2 environment:

```powershell
python scripts/build_bundle.py --target windows
```

Generated archives are written to `dist/`:

- `generate-stars-linux-<arch>.tar.gz`
- `generate-stars-windows-<arch>.zip`

The checked-in GitHub Actions workflow at `.github/workflows/build-bundles.yml` builds both artifacts on native Linux
and Windows runners.
