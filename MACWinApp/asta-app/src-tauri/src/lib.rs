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

// ── File download (curl from Rust → ~/Downloads, no bytes over IPC) ──────────

#[tauri::command]
fn download_to_file(url: String, filename: String, auth_header: Option<String>) -> Result<String, String> {
    // Resolve ~/Downloads, fall back to ~/.asta-downloads
    let home = std::env::var("HOME").unwrap_or_else(|_| "/tmp".to_string());
    let downloads = std::path::PathBuf::from(&home).join("Downloads");
    let dir = if downloads.is_dir() {
        downloads
    } else {
        let fallback = std::path::PathBuf::from(&home).join(".asta-downloads");
        let _ = std::fs::create_dir_all(&fallback);
        fallback
    };

    // Sanitize filename — strip any path separators
    let safe_name = std::path::Path::new(&filename)
        .file_name()
        .and_then(|n| n.to_str())
        .unwrap_or("download")
        .to_string();

    let out_path = dir.join(&safe_name);
    let path_str = out_path.to_string_lossy().to_string();

    // Build curl args: download directly to disk, no bytes cross the IPC boundary.
    // -k: allow self-signed certs (Cloudflare Tunnel / local HTTPS backends)
    let mut args: Vec<String> = vec![
        "-sLk".into(),
        "-o".into(), path_str.clone(),
        "--write-out".into(), "%{http_code}".into(),
    ];
    if let Some(header) = auth_header {
        args.push("-H".into());
        args.push(header);
    }
    args.push(url);

    let output = Command::new("curl")
        .args(&args)
        .output()
        .map_err(|e| format!("curl failed: {}", e))?;

    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr).to_string();
        return Err(format!("Download failed: {}", stderr));
    }
    // Check HTTP status code written to stdout by --write-out
    let http_code = String::from_utf8_lossy(&output.stdout).trim().to_string();
    if !http_code.starts_with('2') && !http_code.is_empty() {
        return Err(format!("Server returned HTTP {}", http_code));
    }

    // Reveal in Finder (macOS) / Explorer (Windows)
    let _ = tauri_plugin_opener::reveal_item_in_dir(&path_str);
    Ok(path_str)
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

    // Find the best asset for this platform/architecture
    let assets = parsed["assets"].as_array();
    let download_url = assets.and_then(|arr| {
        let names_urls: Vec<(&str, &str)> = arr.iter().filter_map(|a| {
            let name = a["name"].as_str()?;
            let url = a["browser_download_url"].as_str()?;
            Some((name, url))
        }).collect();

        #[cfg(target_os = "macos")]
        {
            // Prefer matching architecture, fall back to any DMG
            let arch = std::env::consts::ARCH; // "aarch64" or "x86_64"
            names_urls.iter()
                .find(|(n, _)| n.ends_with(".dmg") && n.contains(arch))
                .or_else(|| names_urls.iter().find(|(n, _)| n.ends_with(".dmg")))
                .map(|(_, u)| u.to_string())
        }
        #[cfg(target_os = "windows")]
        {
            names_urls.iter()
                .find(|(n, _)| n.ends_with(".msi"))
                .or_else(|| names_urls.iter().find(|(n, _)| n.ends_with(".exe")))
                .map(|(_, u)| u.to_string())
        }
        #[cfg(not(any(target_os = "macos", target_os = "windows")))]
        {
            names_urls.iter()
                .find(|(n, _)| n.ends_with(".dmg") || n.ends_with(".msi"))
                .map(|(_, u)| u.to_string())
        }
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
            use cocoa::base::{nil, YES};
            unsafe {
                let ns_app = NSApplication::sharedApplication(nil);
                ns_app.activateIgnoringOtherApps_(YES);
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

            // Register global shortcut Alt+Space
            use tauri_plugin_global_shortcut::{Code, GlobalShortcutExt, Modifiers, Shortcut, ShortcutState};
            let shortcut = Shortcut::new(
                Some(Modifiers::ALT),
                Code::Space,
            );
            let app_handle = app.handle().clone();
            app.handle()
                .global_shortcut()
                .on_shortcut(shortcut, move |_app, _shortcut, event| {
                    if event.state == ShortcutState::Pressed {
                        toggle_window(&app_handle);
                    }
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
            download_to_file,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
