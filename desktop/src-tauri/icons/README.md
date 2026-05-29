# App Icons

Before running `pnpm tauri:build` you must provide application icons.

1. Create a square PNG (≥1240×1240 px) with transparency.
2. Save it as `source.png` inside this folder.
3. Run:

```bash
cd desktop
pnpm tauri icon src-tauri/icons/source.png
```

This will generate all required sizes/formats (`32x32.png`, `128x128.png`, `icon.ico`, `icon.icns`, …) automatically.

If you skip this step, `cargo tauri dev` still works, but the release bundle will fail.
