import Foundation
import AppKit

/// Utility to detect Asta installation on the system
final class AstaInstaller {
    /// Common paths to check for Asta installation
    static let searchPaths: [String] = [
        NSHomeDirectory() + "/asta",               // ~/asta (primary)
        NSHomeDirectory(),                          // ~
        NSHomeDirectory() + "/Projects",            // ~/Projects
        NSHomeDirectory() + "/Developer",          // ~/Developer
        NSHomeDirectory() + "/Code",              // ~/Code
        NSHomeDirectory() + "/Development",        // ~/Development
    ]
    
    /// File/folder indicators that suggest Asta is installed
    static let indicators = ["asta.sh", "backend/", "app/", "frontend/"]
    
    /// Result of installation detection
    struct DetectionResult {
        let path: String
        let hasBackend: Bool
        let hasFrontend: Bool
        let hasStartScript: Bool
        
        var startCommand: String {
            let path = self.path
            if FileManager.default.fileExists(atPath: "\(path)/asta.sh") {
                return "cd \(path) && ./asta.sh start"
            }
            return "cd \(path)/backend && uvicorn app.main:app --port 8010"
        }
    }
    
    /// Check if Asta is installed in any of the common paths
    static func detectInstallation() -> DetectionResult? {
        for basePath in searchPaths {
            if let result = checkPath(basePath) {
                return result
            }
        }
        return nil
    }
    
    /// Check a specific path for Asta installation
    private static func checkPath(_ path: String) -> DetectionResult? {
        let fm = FileManager.default
        
        // Check if directory exists
        var isDir: ObjCBool = false
        guard fm.fileExists(atPath: path, isDirectory: &isDir), isDir.boolValue else {
            return nil
        }
        
        // Look for Asta indicators
        var hasBackend = false
        var hasFrontend = false
        var hasStartScript = false
        
        if let contents = try? fm.contentsOfDirectory(atPath: path) {
            for item in contents {
                if item == "asta.sh" || item == "backend" || item == "app" {
                    hasBackend = true
                }
                if item == "frontend" || item == "index.html" {
                    hasFrontend = true
                }
                if item == "asta.sh" {
                    hasStartScript = true
                }
            }
        }
        
        // Must have at least backend to be considered installed
        guard hasBackend else { return nil }
        
        return DetectionResult(
            path: path,
            hasBackend: hasBackend,
            hasFrontend: hasFrontend,
            hasStartScript: hasStartScript
        )
    }
    
    /// Try to start Asta backend if installation detected
    static func startBackend(at path: String) async -> Bool {
        let script: String
        if FileManager.default.fileExists(atPath: "\(path)/asta.sh") {
            script = """
            cd "\(path)"
            if [ -f "./asta.sh" ]; then
                ./asta.sh start &
                echo "Started via asta.sh"
            else
                echo "asta.sh not found"
                exit 1
            fi
            """
        } else {
            script = """
            cd "\(path)/backend"
            nohup uvicorn app.main:app --port 8010 > ~/asta-backend.log 2>&1 &
            echo "Started via uvicorn"
            """
        }
        
        return await withCheckedContinuation { continuation in
            let task = Process()
            task.executableURL = URL(fileURLWithPath: "/bin/zsh")
            task.arguments = ["-l", "-c", script]
            
            do {
                try task.run()
                task.waitUntilExit()
                continuation.resume(returning: task.terminationStatus == 0)
            } catch {
                continuation.resume(returning: false)
            }
        }
    }
}

/// Utility for copying text to clipboard
final class ClipboardUtil {
    static func copy(_ text: String) {
        let pasteboard = NSPasteboard.general
        pasteboard.clearContents()
        pasteboard.setString(text, forType: .string)
    }
}
