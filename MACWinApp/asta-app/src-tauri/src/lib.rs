use tauri::{
    menu::{Menu, MenuItem},
    tray::{MouseButton, MouseButtonState, TrayIconBuilder, TrayIconEvent},
    Manager, Runtime, WindowEvent,
};
use std::process::Command;

#[tauri::command]
fn get_backend_url() -> String {
    "http://localhost:8010".to_string()
}

// ── Tailscale commands ──────────────────────────────────────────────────────

/// Find the tailscale binary on this machine.
fn find_tailscale() -> Option<String> {
    let candidates = [
        "/usr/local/bin/tailscale",
        "/opt/homebrew/bin/tailscale",
        "/Applications/Tailscale.app/Contents/MacOS/Tailscale",
    ];
    for path in &candidates {
        if std::path::Path::new(path).exists() {
            return Some(path.to_string());
        }
    }
    // Try PATH
    if let Ok(output) = Command::new("which").arg("tailscale").output() {
        if output.status.success() {
            let p = String::from_utf8_lossy(&output.stdout).trim().to_string();
            if !p.is_empty() {
                return Some(p);
            }
        }
    }
    None
}

fn run_tailscale(args: &[&str]) -> Result<(String, i32), String> {
    let bin = find_tailscale().ok_or("Tailscale not installed")?;
    let output = Command::new(&bin)
        .args(args)
        .output()
        .map_err(|e| format!("Failed to run tailscale: {}", e))?;
    let stdout = String::from_utf8_lossy(&output.stdout).to_string();
    let stderr = String::from_utf8_lossy(&output.stderr).to_string();
    let combined = if stderr.is_empty() { stdout } else { format!("{}\n{}", stdout, stderr) };
    let code = output.status.code().unwrap_or(-1);
    Ok((combined, code))
}

#[tauri::command]
fn tailscale_status() -> Result<serde_json::Value, String> {
    let bin = find_tailscale();
    if bin.is_none() {
        return Ok(serde_json::json!({
            "installed": false,
            "status": "not_installed"
        }));
    }
    let (output, code) = run_tailscale(&["status", "--json"])?;
    if code != 0 {
        // Not logged in or other error
        if output.contains("not logged in") || output.contains("NeedsLogin") {
            return Ok(serde_json::json!({
                "installed": true,
                "status": "not_logged_in"
            }));
        }
        return Ok(serde_json::json!({
            "installed": true,
            "status": "disconnected",
            "error": output.trim()
        }));
    }
    // Parse JSON output
    let parsed: serde_json::Value = serde_json::from_str(&output)
        .unwrap_or(serde_json::json!({"raw": output}));

    let backend_state = parsed["BackendState"].as_str().unwrap_or("");
    let status = match backend_state {
        "Running" => "connected",
        "Starting" => "connecting",
        "Stopped" => "disconnected",
        "NeedsLogin" | "NeedsMachineAuth" => "not_logged_in",
        _ => "disconnected",
    };

    let ip = parsed["Self"]["TailscaleIPs"]
        .as_array()
        .and_then(|arr| arr.first())
        .and_then(|v| v.as_str())
        .unwrap_or("")
        .to_string();

    let dns_name = parsed["Self"]["DNSName"]
        .as_str()
        .unwrap_or("")
        .trim_end_matches('.')
        .to_string();

    Ok(serde_json::json!({
        "installed": true,
        "status": status,
        "ip": ip,
        "dns_name": dns_name,
    }))
}

#[tauri::command]
fn tailscale_serve_status() -> Result<serde_json::Value, String> {
    let (output, _code) = run_tailscale(&["serve", "status"])?;
    let enabled = !output.contains("No serve config") && !output.trim().is_empty();
    Ok(serde_json::json!({
        "enabled": enabled,
        "raw": output.trim()
    }))
}

#[tauri::command]
fn tailscale_serve_enable(port: u16) -> Result<serde_json::Value, String> {
    let target = format!("http://localhost:{}", port);
    let (output, code) = run_tailscale(&["serve", "--bg", &target])?;
    Ok(serde_json::json!({
        "ok": code == 0,
        "output": output.trim()
    }))
}

#[tauri::command]
fn tailscale_serve_disable() -> Result<serde_json::Value, String> {
    let (output, code) = run_tailscale(&["serve", "--https=443", "off"])?;
    Ok(serde_json::json!({
        "ok": code == 0,
        "output": output.trim()
    }))
}

#[tauri::command]
fn tailscale_connect() -> Result<serde_json::Value, String> {
    let (output, code) = run_tailscale(&["up"])?;
    Ok(serde_json::json!({
        "ok": code == 0,
        "output": output.trim()
    }))
}

#[tauri::command]
fn tailscale_disconnect() -> Result<serde_json::Value, String> {
    let (output, code) = run_tailscale(&["down"])?;
    Ok(serde_json::json!({
        "ok": code == 0,
        "output": output.trim()
    }))
}

#[tauri::command]
fn tailscale_login() -> Result<serde_json::Value, String> {
    let (output, code) = run_tailscale(&["login"])?;
    // Parse login URL from output
    let login_url = output.lines()
        .find(|line| line.contains("https://"))
        .and_then(|line| {
            line.split_whitespace()
                .find(|w| w.starts_with("https://"))
        })
        .map(|s| s.to_string());
    Ok(serde_json::json!({
        "ok": code == 0,
        "output": output.trim(),
        "login_url": login_url,
    }))
}

// ── App update check (GitHub releases) ──────────────────────────────────────

#[tauri::command]
fn check_app_update(current_version: String) -> Result<serde_json::Value, String> {
    let url = "https://api.github.com/repos/helloworldxdwastaken/asta/releases/latest";
    let output = Command::new("curl")
        .args(&["-sL", "-H", "Accept: application/vnd.github+json", "-H", "User-Agent: Asta-App", url])
        .output()
        .map_err(|e| format!("Failed to check updates: {}", e))?;
    let body = String::from_utf8_lossy(&output.stdout).to_string();
    let parsed: serde_json::Value = serde_json::from_str(&body)
        .unwrap_or(serde_json::json!({"error": "Failed to parse response"}));

    let tag = parsed["tag_name"].as_str().unwrap_or("").trim_start_matches('v').to_string();
    let has_update = !tag.is_empty() && tag != current_version;

    // Find DMG or MSI asset URL
    let assets = parsed["assets"].as_array();
    let download_url = assets.and_then(|arr| {
        arr.iter().find_map(|a| {
            let name = a["name"].as_str().unwrap_or("");
            if name.ends_with(".dmg") || name.ends_with(".msi") {
                a["browser_download_url"].as_str().map(|s| s.to_string())
            } else {
                None
            }
        })
    });

    Ok(serde_json::json!({
        "has_update": has_update,
        "latest_version": tag,
        "current_version": current_version,
        "release_url": parsed["html_url"].as_str().unwrap_or(""),
        "download_url": download_url,
        "release_notes": parsed["body"].as_str().unwrap_or(""),
    }))
}

// ── Window management ───────────────────────────────────────────────────────

/// Bring the window to the front, activating the app on macOS.
fn show_window<R: Runtime>(app: &tauri::AppHandle<R>) {
    if let Some(window) = app.get_webview_window("main") {
        let _ = window.unminimize();
        let _ = window.show();

        // macOS: activate the application so the window actually comes to front
        #[cfg(target_os = "macos")]
        {
            use cocoa::appkit::NSApplication;
            use cocoa::base::nil;
            unsafe {
                let ns_app = NSApplication::sharedApplication(nil);
                ns_app.activateIgnoringOtherApps_(true);
            }
        }

        let _ = window.set_focus();
    }
}

fn hide_window<R: Runtime>(app: &tauri::AppHandle<R>) {
    if let Some(window) = app.get_webview_window("main") {
        let _ = window.hide();
    }
}

fn toggle_window<R: Runtime>(app: &tauri::AppHandle<R>) {
    if let Some(window) = app.get_webview_window("main") {
        let visible = window.is_visible().unwrap_or(false);
        let focused = window.is_focused().unwrap_or(false);

        if visible && focused {
            // Window is visible AND focused → hide it
            hide_window(app);
        } else {
            // Window is hidden, or visible but behind other apps → bring to front
            show_window(app);
        }
    }
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_global_shortcut::Builder::new().build())
        .plugin(tauri_plugin_http::init())
        .plugin(tauri_plugin_autostart::init(
            tauri_plugin_autostart::MacosLauncher::LaunchAgent,
            Some(vec![]),
        ))
        .setup(|app| {
            // Build tray context menu
            let show = MenuItem::with_id(app, "show", "Open", true, None::<&str>)?;
            let quit = MenuItem::with_id(app, "quit", "Quit", true, None::<&str>)?;
            let menu = Menu::with_items(app, &[&show, &quit])?;

            // Create tray icon (built entirely in code — not via tauri.conf.json)
            // Left click → show/focus app, Right click → context menu (Open/Quit)
            TrayIconBuilder::new()
                .icon(tauri::image::Image::from_bytes(include_bytes!("../icons/tray-icon.png"))?)
                .icon_as_template(true)
                .tooltip("Asta")
                .menu(&menu)
                .show_menu_on_left_click(false)
                .on_tray_icon_event(|tray, event| {
                    match event {
                        TrayIconEvent::Click {
                            button: MouseButton::Left,
                            button_state: MouseButtonState::Up,
                            ..
                        } => {
                            let app = tray.app_handle();
                            show_window(app);
                        }
                        _ => {}
                    }
                })
                .on_menu_event(|app, event| match event.id.as_ref() {
                    "show" => show_window(app),
                    "quit" => app.exit(0),
                    _ => {}
                })
                .build(app)?;

            // Register global shortcut CmdOrCtrl+Alt+Space
            use tauri_plugin_global_shortcut::{Code, GlobalShortcutExt, Modifiers, Shortcut};
            let shortcut = Shortcut::new(
                Some(Modifiers::ALT | Modifiers::SUPER),
                Code::Space,
            );
            let app_handle = app.handle().clone();
            app.handle()
                .global_shortcut()
                .on_shortcut(shortcut, move |_app, _shortcut, _event| {
                    toggle_window(&app_handle);
                })?;

            // Close-to-tray: hide instead of quit when user closes the window
            if let Some(window) = app.get_webview_window("main") {
                let win = window.clone();
                window.on_window_event(move |event| {
                    if let WindowEvent::CloseRequested { api, .. } = event {
                        api.prevent_close();
                        let _ = win.hide();
                    }
                });

                // Show window on initial launch
                let _ = window.show();
                let _ = window.set_focus();
            }

            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            get_backend_url,
            check_app_update,
            tailscale_status,
            tailscale_serve_status,
            tailscale_serve_enable,
            tailscale_serve_disable,
            tailscale_connect,
            tailscale_disconnect,
            tailscale_login,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
