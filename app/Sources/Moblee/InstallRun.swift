import SwiftUI
import AppKit

/// Runs the pack's own installer (scripts/install.sh) or updater
/// (scripts/update.sh) and follows its progress lines. The app never installs
/// anything by another route: the engine that a Terminal user runs is the
/// engine this runs.
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

    @Published var items: [Item] = InstallRun.installItems()
    @Published var phase: Phase = .idle
    @Published var vaultPath: String?

    /// Steps whose failure the engine itself carries on past.
    private var softSteps: Set<String> = ["skills"]
    private var task: EngineTask?
    var diaryURL: URL?

    static func installItems() -> [Item] {
        [
            Item(key: "folder", symbol: "folder.fill", label: "Your wiki"),
            Item(key: "tools", symbol: "wrench.adjustable.fill", label: "Its tools"),
            Item(key: "history", symbol: "clock.arrow.circlepath", label: "Its history"),
            Item(key: "safety", symbol: "lock.shield.fill", label: "The guard"),
            Item(key: "skills", symbol: "graduationcap.fill", label: "Claude's skills"),
            Item(key: "finish", symbol: "checkmark.seal.fill", label: "Finishing"),
        ]
    }

    static func updateItems() -> [Item] {
        [
            Item(key: "tools", symbol: "wrench.adjustable.fill", label: "Tools"),
            Item(key: "gate", symbol: "checkmark.shield.fill", label: "The gate"),
            Item(key: "skills", symbol: "graduationcap.fill", label: "Skills"),
            Item(key: "safety", symbol: "lock.shield.fill", label: "The guard"),
            Item(key: "rules", symbol: "list.bullet.rectangle.fill", label: "The rules"),
            Item(key: "pages", symbol: "doc.text.fill", label: "New pages"),
            Item(key: "weekly", symbol: "calendar", label: "Weekly check"),
            Item(key: "lessons", symbol: "lightbulb.fill", label: "Lessons"),
            Item(key: "finish", symbol: "checkmark.seal.fill", label: "Finishing"),
        ]
    }

    func start(home: URL, ownerName: String, wikiName: String, location: URL, bundledPack: URL) {
        guard phase != .running else { return }
        items = InstallRun.installItems()
        softSteps = ["skills"]
        begin(home: home, bundledPack: bundledPack, fallbackVault: location.path) { pack in
            [pack.appendingPathComponent("scripts/install.sh").path,
             "--name", ownerName, "--vault-name", wikiName,
             "--location", location.path, "--progress"]
        }
    }

    func startUpdate(home: URL, vault: URL, bundledPack: URL) {
        guard phase != .running else { return }
        items = InstallRun.updateItems()
        softSteps = []
        begin(home: home, bundledPack: bundledPack, fallbackVault: vault.path) { pack in
            [pack.appendingPathComponent("scripts/update.sh").path, vault.path, "--progress"]
        }
    }

    private func begin(home: URL, bundledPack: URL, fallbackVault: String,
                       arguments: (URL) -> [String]) {
        phase = .running
        vaultPath = nil
        diaryURL = home.appendingPathComponent(".config/moblee/install-diary.txt")

        let pack: URL
        do {
            pack = try Self.settlePack(bundledPack, home: home)
        } catch {
            phase = .failed(why: "pack-copy")
            return
        }
        let t = EngineTask()
        task = t
        t.run("/bin/bash", arguments(pack), home: home,
              onEvent: { [weak self] e in self?.handle(e) },
              onEnd: { [weak self] code in self?.ended(code: code, fallbackVault: fallbackVault) })
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

        // "The same pack" is judged by the scripts that do the work, and a copy
        // only counts once its last file, the marker, is there: a copy that was
        // interrupted part-way is never used.
        let judged = ["scripts/install.sh", "scripts/update.sh", "scripts/moblee-setup.py",
                      "scripts/add-made-skill.py", "safety/bash-guard.py"]
        func fingerprint(_ root: URL) -> [Data?] { judged.map { try? Data(contentsOf: root.appendingPathComponent($0)) } }
        let wanted = fingerprint(bundled)
        let marker = ".settled"

        var n = 0
        while true {
            let name = n == 0 ? "pack-\(version)" : "pack-\(version)-\(n)"
            let candidate = base.appendingPathComponent(name, isDirectory: true)
            if !fm.fileExists(atPath: candidate.path) {
                let incoming = base.appendingPathComponent(".incoming-\(UUID().uuidString)", isDirectory: true)
                try fm.copyItem(at: bundled, to: incoming)
                try Data().write(to: incoming.appendingPathComponent(marker))
                try fm.moveItem(at: incoming, to: candidate)
                return candidate
            }
            // An earlier run left the same pack here: use it, never overwrite it.
            if fm.fileExists(atPath: candidate.appendingPathComponent(marker).path),
               fingerprint(candidate) == wanted {
                return candidate
            }
            n += 1
        }
    }

    private func handle(_ obj: EngineTask.Event) {
        guard let step = obj["step"] as? String, let state = obj["state"] as? String else { return }
        if step == "done" {
            if let v = obj["vault"] as? String { vaultPath = v }
            return
        }
        withAnimation(.spring(response: 0.45, dampingFraction: 0.75)) {
            switch state {
            case "start": set(step, .running)
            case "ok": set(step, .done)
            case "fail":
                set(step, .failed)
                if !softSteps.contains(step) { phase = .failed(why: (obj["why"] as? String) ?? "stopped") }
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

    private func ended(code: Int32, fallbackVault: String) {
        task = nil
        if case .failed = phase { return }
        withAnimation(.easeInOut(duration: 0.4)) {
            if code == 0 {
                if vaultPath == nil { vaultPath = fallbackVault }   // the updater, or a hand-over to it
                for i in items.indices where items[i].state != .failed { items[i].state = .done }
                phase = .finished
            } else {
                phase = .failed(why: code == -1 ? "could-not-start" : "stopped")
            }
        }
    }

    func showDiary() {
        guard let diaryURL, FileManager.default.fileExists(atPath: diaryURL.path) else { return }
        NSWorkspace.shared.activateFileViewerSelecting([diaryURL])
    }
}
