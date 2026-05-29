use std::process::{Child, Command, Stdio};
use std::sync::{Arc, Mutex};
use tauri::Manager;

const BACKEND_PORT: u16 = 3400;

#[derive(Clone)]
struct BackendState {
    process: Arc<Mutex<Option<Child>>>,
}

impl Default for BackendState {
    fn default() -> Self {
        Self {
            process: Arc::new(Mutex::new(None)),
        }
    }
}

/// Check whether the backend port is open (health check by TCP connect).
async fn is_backend_ready() -> bool {
    match tokio::time::timeout(
        tokio::time::Duration::from_secs(2),
        tokio::net::TcpStream::connect(format!("127.0.0.1:{}", BACKEND_PORT)),
    )
    .await
    {
        Ok(Ok(_)) => true,
        _ => false,
    }
}

/// Discover the project root by looking for `pyproject.toml` in ancestors of the current dir.
fn find_project_root() -> Option<std::path::PathBuf> {
    let mut dir = std::env::current_dir().ok()?;
    loop {
        if dir.join("pyproject.toml").exists() {
            return Some(dir);
        }
        if !dir.pop() {
            return None;
        }
    }
}

/// Start the Python backend if it is not already running.
async fn ensure_backend(state: &BackendState) {
    if is_backend_ready().await {
        return;
    }

    let root = match find_project_root() {
        Some(r) => r,
        None => {
            eprintln!("[agentplane-desktop] Could not find project root (pyproject.toml).");
            return;
        }
    };

    // Prefer `uv run`. Fallback to plain `python` / `python3` if uv is missing.
    let (cmd, args): (&str, Vec<&str>) = if Command::new("uv").arg("--version").output().is_ok() {
        ("uv", vec!["run", "agentplane", "run"])
    } else if Command::new("python").arg("--version").output().is_ok() {
        ("python", vec!["-m", "agentplane.cli.main", "run"])
    } else if Command::new("python3").arg("--version").output().is_ok() {
        ("python3", vec!["-m", "agentplane.cli.main", "run"])
    } else {
        eprintln!("[agentplane-desktop] Neither `uv` nor `python` found in PATH.");
        return;
    };

    let child = Command::new(cmd)
        .args(&args)
        .current_dir(&root)
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .spawn();

    match child {
        Ok(c) => {
            println!("[agentplane-desktop] Started backend process ({}).", cmd);
            let _ = state.process.lock().map(|mut g| {
                *g = Some(c);
            });
        }
        Err(e) => {
            eprintln!("[agentplane-desktop] Failed to start backend: {}", e);
        }
    }
}

#[tauri::command]
fn get_api_base() -> String {
    format!("http://127.0.0.1:{}", BACKEND_PORT)
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let state = BackendState::default();

    let app = tauri::Builder::default()
        .manage(state.clone())
        .plugin(tauri_plugin_shell::init())
        .setup(|_app| {
            let state_clone = state.clone();
            tauri::async_runtime::spawn(async move {
                ensure_backend(&state_clone).await;
            });
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![get_api_base])
        .build(tauri::generate_context!())
        .expect("error while building tauri application");

    app.run(move |_app_handle, event| {
        if let tauri::RunEvent::Exit = event {
            if let Ok(mut guard) = state.process.lock() {
                if let Some(mut child) = guard.take() {
                    let _ = child.kill();
                    println!("[agentplane-desktop] Backend process terminated.");
                }
            }
        }
    });
}
