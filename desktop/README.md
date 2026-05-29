# Agentplane Desktop (Tauri)

This folder contains a **Tauri v2** desktop shell for Agentplane.
It is completely self-contained and can be removed at any time without affecting the Python backend.

## Architecture

```
desktop/
├── src/                   # Frontend (vanilla TypeScript + Vite)
├── src-tauri/             # Rust / Tauri application
│   ├── src/lib.rs         # Backend auto-start + API bridge
│   ├── tauri.conf.json    # Tauri configuration
│   └── capabilities/      # Permission manifests
├── package.json           # Node dependencies
└── vite.config.ts         # Frontend build tool
```

The desktop app acts as a **thin native wrapper** around the existing FastAPI backend:

- On launch it checks whether `http://127.0.0.1:3400` is already up.
- If not, it automatically spawns `uv run agentplane run` (or falls back to `python -m agentplane.cli.main run`).
- The frontend communicates with the Python API via standard `fetch` (CORS is already enabled in `src/agentplane/api/main.py`).
- When the Tauri window closes, the spawned backend process is terminated.

## Prerequisites

- [Node.js](https://nodejs.org/) (v20+)
- [pnpm](https://pnpm.io/) (or npm)
- [Rust](https://rustup.rs/) (latest stable)
- Python backend dependencies already installed (`uv sync` from the project root)

## Quick Start

From the project root:

```bash
cd desktop
pnpm install
pnpm tauri:dev
```

This will:
1. Start the Vite dev server on `http://localhost:1420`
2. Build the Rust Tauri app
3. Open a native window
4. Auto-launch the Python backend if it is not already running

## Production Build

```bash
cd desktop
pnpm install
pnpm tauri:build
```

The native binaries will be placed in:
- Windows: `src-tauri/target/release/Agentplane.exe`
- macOS: `src-tauri/target/release/bundle/macos/Agentplane.app`
- Linux: `src-tauri/target/release/bundle/deb/*.deb` (or AppImage)

> **Note:** Before building you must generate the application icons.
> Place a `icon.png` (≥1240×1240 px, with transparency) in `src-tauri/icons/source.png` and run:
> ```bash
> pnpm tauri icon src-tauri/icons/source.png
> ```

## How to Remove

Because everything lives inside `desktop/`, removing Tauri is trivial:

1. Delete the `desktop/` directory.
2. Remove the `desktop/` entries from the root `.gitignore` (optional).

The Python project continues to work exactly as before — `uv run agentplane run` still starts the API server and you can use any browser or HTTP client to interact with it.

## Customising the Frontend

The UI is intentionally lightweight (no React/Vue/Svelte) so you can swap it easily:

1. Scaffold a new frontend in `desktop/src/` with your framework of choice.
2. Update `desktop/vite.config.ts` and `desktop/index.html` accordingly.
3. Keep the `invoke("get_api_base")` call so the UI knows where the Python API lives.

The Rust layer (`src-tauri/src/lib.rs`) only exposes two public things:
- `get_api_base()` — returns the backend URL.
- Auto-start / auto-kill of the Python process.

You can extend `lib.rs` with extra Tauri commands (file system access, native notifications, system tray, etc.) without touching the Python codebase.
