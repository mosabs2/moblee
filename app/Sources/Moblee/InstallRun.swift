import SwiftUI
import AppKit

/// Runs the pack's own installer (scripts/install.sh) and follows its progress
/// lines. The app never installs anything by another route: the engine that a
/// Terminal user runs is the engine this runs.
@MainActor
final class InstallRun: ObservableObject {
    enum StepState { case waiting, running, done, failed }

    struct Item: Identifiable {
        let key: String
        let symbol: String
        let label: String
        var state: StepState = .waiting
        var id: String { key }
    }

    enum Phase: Equatable {
        case idle
        case running
        case finished
        case failed(why: String)
    }

    @Published var items: [Item] = InstallRun.freshItems()
    @Published var phase: Phase = .idle
    @Published var vaultPath: String?

    private var process: Process?
    private var buffer = Data()

    static func freshItems() -> [Item] {
        [
            Item(key: "folder", symbol: "folder.fill", label: "Your wiki"),
            Item(key: "tools", symbol: "wrench.adjustable.fill", label: "Its tools"),
            Item(key: "history", symbol: "clock.arrow.circlepath", label: "Its history"),
            Item(key: "safety", symbol: "lock.shield.fill", label: "The guard"),
            Item(key: "skills", symbol: "graduationcap.fill", label: "Claude's skills"),
            Item(key: "finish", symbol: "checkmark.seal.fill", label: "Finishing"),
        ]
    }

    var diaryURL: URL?

    func start(home: URL, ownerName: String, wikiName: String, location: URL, bundledPack: URL) {
        guard phase != .running else { return }
        items = InstallRun.freshItems()
        phase = .running
        vaultPath = nil
        buffer = Data()
        diaryURL = home.appendingPathComponent(".config/moblee/install-diary.txt")

        let pack: URL
        do {
            pack = try Self.settlePack(bundledPack, home: home)
        } catch {
            phase = .failed(why: "pack-copy")
            return
        }

        let p = Process()
        p.executableURL = URL(fileURLWithPath: "/bin/bash")
        p.arguments = [pack.appendingPathComponent("scripts/install.sh").path,
                       "--name", ownerName,
                       "--vault-name", wikiName,
                       "--location", location.path,
                       "--progress"]
        var env = ProcessInfo.processInfo.environment
        env["HOME"] = home.path
        // The Mac's own tools only, so every owner's install runs the same way.
        env["PATH"] = "/usr/bin:/bin:/usr/sbin:/sbin"
        p.environment = env
        p.standardInput = FileHandle.nullDevice

        let out = Pipe()
        p.standardOutput = out
        p.standardError = out
        out.fileHandleForReading.readabilityHandler = { [weak self] handle in
            let data = handle.availableData
            guard !data.isEmpty else { return }
            Task { @MainActor in self?.take(data) }
        }
        p.terminationHandler = { [weak self] proc in
            let code = proc.terminationStatus
            Task { @MainActor in
                out.fileHandleForReading.readabilityHandler = nil
                self?.ended(code: code, location: location)
            }
        }
        do {
            try p.run()
            process = p
        } catch {
            phase = .failed(why: "could-not-start")
        }
    }

    /// The pack travels inside the app, but the app may be run from Downloads
    /// and thrown away afterwards, and the wiki's tools need the pack later
    /// (the checklist, the updater). So it is copied once to a lasting place.
    static func settlePack(_ bundled: URL, home: URL) throws -> URL {
        let fm = FileManager.default
        let version = (try? String(contentsOf: bundled.appendingPathComponent("VERSION"), encoding: .utf8))?
            .trimmingCharacters(in: .whitespacesAndNewlines) ?? "unknown"
        let base = home.appendingPathComponent("Library/Application Support/Moblee", isDirectory: true)
        try fm.createDirectory(at: base, withIntermediateDirectories: true)

        let wanted = try Data(contentsOf: bundled.appendingPathComponent("scripts/install.sh"))
        var n = 0
        while true {
            let name = n == 0 ? "pack-\(version)" : "pack-\(version)-\(n)"
            let candidate = base.appendingPathComponent(name, isDirectory: true)
            if !fm.fileExists(atPath: candidate.path) {
                try fm.copyItem(at: bundled, to: candidate)
                return candidate
            }
            // An earlier run left the same pack here: use it, never overwrite it.
            if let have = try? Data(contentsOf: candidate.appendingPathComponent("scripts/install.sh")),
               have == wanted {
                return candidate
            }
            n += 1
        }
    }

    private func take(_ data: Data) {
        buffer.append(data)
        while let nl = buffer.firstIndex(of: 0x0A) {
            let lineData = buffer.subdata(in: buffer.startIndex..<nl)
            buffer.removeSubrange(buffer.startIndex...nl)
            guard let line = String(data: lineData, encoding: .utf8) else { continue }
            handle(line)
        }
    }

    private func handle(_ line: String) {
        let marker = "@@moblee "
        guard line.hasPrefix(marker),
              let json = line.dropFirst(marker.count).data(using: .utf8),
              let obj = try? JSONSerialization.jsonObject(with: json) as? [String: Any],
              let step = obj["step"] as? String,
              let state = obj["state"] as? String else { return }

        if step == "done" {
            vaultPath = obj["vault"] as? String
            return
        }
        withAnimation(.spring(response: 0.45, dampingFraction: 0.75)) {
            switch state {
            case "start": set(step, .running)
            case "ok": set(step, .done)
            case "fail":
                set(step, .failed)
                // A skills hiccup is not fatal to the engine, so it is not fatal here.
                if step != "skills" { phase = .failed(why: (obj["why"] as? String) ?? "stopped") }
            case "stopped":
                set(step, .failed)
                if case .failed = phase {} else { phase = .failed(why: "stopped") }
            default: break
            }
        }
    }

    private func set(_ key: String, _ state: StepState) {
        if let i = items.firstIndex(where: { $0.key == key }) { items[i].state = state }
    }

    private func ended(code: Int32, location: URL) {
        process = nil
        if case .failed = phase { return }
        withAnimation(.easeInOut(duration: 0.4)) {
            if code == 0 {
                if vaultPath == nil { vaultPath = location.path }   // handed to the updater
                for i in items.indices where items[i].state != .failed { items[i].state = .done }
                phase = .finished
            } else {
                phase = .failed(why: "stopped")
            }
        }
    }

    func showDiary() {
        guard let diaryURL, FileManager.default.fileExists(atPath: diaryURL.path) else { return }
        NSWorkspace.shared.activateFileViewerSelecting([diaryURL])
    }
}
