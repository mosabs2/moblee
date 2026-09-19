import SwiftUI
import AppKit

/// What a returning owner sees: the things they agreed with Claude, waiting as
/// tiles; an update, if this app carries a newer Moblee than their wiki has;
/// and a repair button if the safety layer is not as it should be.
///
/// The app reads the wiki's request list and never writes to the wiki. Claude
/// records what was added, after testing it.
@MainActor
final class HomeModel: ObservableObject {
    enum How: String { case silent, terminal, clicks, hidden }
    enum Kind: String { case item, skill, connection }
    enum TileState: Equatable { case waiting, running, done, failed, handedOver }

    struct Tile: Identifiable, Equatable {
        let kind: Kind
        let key: String
        var title: String
        var why: String
        var detail: String
        var how: How
        var paid: Bool
        var state: TileState = .waiting
        var id: String { kind.rawValue + ":" + key }

        var symbol: String {
            switch kind {
            case .skill: return "wand.and.stars"
            case .connection: return "link"
            case .item:
                switch how {
                case .silent: return "square.and.arrow.down.fill"
                case .terminal: return "terminal.fill"
                case .clicks: return "cursorarrow.click.2"
                case .hidden: return "questionmark"
                }
            }
        }
    }

    @Published var tiles: [Tile] = []
    @Published var wikiVersion: String = ""
    @Published var packVersion: String = ""
    @Published var needsRepair = false
    @Published var loaded = false
    @Published var explaining: Tile?

    private(set) var vault: URL?
    private var home: URL = FileManager.default.homeDirectoryForCurrentUser
    private var pack: URL?
    private var catalogue: [String: [String: Any]] = [:]
    private var timer: Timer?
    private var tasks: [String: EngineTask] = [:]

    var updateAvailable: Bool {
        !wikiVersion.isEmpty && !packVersion.isEmpty && Self.isNewer(packVersion, than: wikiVersion)
    }

    static func isNewer(_ a: String, than b: String) -> Bool {
        let pa = a.split(separator: ".").map { Int($0) ?? 0 }
        let pb = b.split(separator: ".").map { Int($0) ?? 0 }
        for i in 0..<max(pa.count, pb.count) {
            let x = i < pa.count ? pa[i] : 0, y = i < pb.count ? pb[i] : 0
            if x != y { return x > y }
        }
        return false
    }

    /// The wiki this Mac already has, if any.
    static func existingVault(home: URL) -> URL? {
        let record = home.appendingPathComponent(".config/moblee/vault-path")
        guard let text = try? String(contentsOf: record, encoding: .utf8) else { return nil }
        let url = URL(fileURLWithPath: text.trimmingCharacters(in: .whitespacesAndNewlines), isDirectory: true)
        let fm = FileManager.default
        guard fm.fileExists(atPath: url.appendingPathComponent("CLAUDE.md").path),
              fm.fileExists(atPath: url.appendingPathComponent("wiki").path) else { return nil }
        return url
    }

    func load(home: URL, bundledPack: URL?) {
        self.home = home
        vault = Self.existingVault(home: home)
        guard let vault else { loaded = true; return }

        wikiVersion = Self.read(vault.appendingPathComponent("VERSION"))
        if let bundledPack {
            packVersion = Self.read(bundledPack.appendingPathComponent("VERSION"))
            pack = try? InstallRun.settlePack(bundledPack, home: home)
        }
        needsRepair = !FileManager.default.fileExists(
            atPath: home.appendingPathComponent(".claude/hooks/bash-guard.py").path)

        guard let pack else { readRequests(); loaded = true; return }
        EngineTask.output(of: "/usr/bin/python3",
                          [pack.appendingPathComponent("scripts/moblee-setup.py").path, "--list", "--json"],
                          home: home) { [weak self] _, data in
            guard let self else { return }
            if let list = try? JSONSerialization.jsonObject(with: data) as? [[String: Any]] {
                for entry in list { if let k = entry["key"] as? String { self.catalogue[k] = entry } }
            }
            self.readRequests()
            self.loaded = true
        }
    }

    func startWatching() {
        timer = Timer.scheduledTimer(withTimeInterval: 4, repeats: true) { [weak self] _ in
            Task { @MainActor in self?.refreshStates() }
        }
    }

    func stopWatching() { timer?.invalidate(); timer = nil }

    private static func read(_ url: URL) -> String {
        ((try? String(contentsOf: url, encoding: .utf8)) ?? "").trimmingCharacters(in: .whitespacesAndNewlines)
    }

    private func readRequests() {
        guard let vault else { return }
        let url = vault.appendingPathComponent(".moblee/requests.json")
        guard let data = try? Data(contentsOf: url),
              let obj = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
              let list = obj["requests"] as? [[String: Any]] else { tiles = []; return }

        var made: [Tile] = []
        for r in list {
            guard (r["status"] as? String ?? "waiting") == "waiting",
                  let kind = Kind(rawValue: r["kind"] as? String ?? ""),
                  let key = r["key"] as? String, !key.isEmpty else { continue }
            let why = r["why"] as? String ?? ""
            switch kind {
            case .item:
                guard let c = catalogue[key] else { continue }
                let how = How(rawValue: c["how"] as? String ?? "terminal") ?? .terminal
                if how == .hidden { continue }
                let mb = c["space_mb"] as? Int ?? 0
                let size = mb >= 1000 ? String(format: "%.1f GB", Double(mb) / 1000) : "\(mb) MB"
                let paid = c["paid"] as? Bool ?? false
                let detail = "About \(c["minutes"] as? Int ?? 1) min · \(size) · " + (paid ? "can cost money" : "free")
                made.append(Tile(kind: .item, key: key, title: c["title"] as? String ?? key,
                                 why: why, detail: detail, how: how, paid: paid))
            case .skill:
                guard Self.safeName(key),
                      FileManager.default.fileExists(atPath: draft(of: key).appendingPathComponent("SKILL.md").path)
                else { continue }
                made.append(Tile(kind: .skill, key: key, title: "Made for you: \(key)",
                                 why: why, detail: "A new skill Claude wrote for you", how: .silent, paid: false))
            case .connection:
                made.append(Tile(kind: .connection, key: key, title: "Connect \(key)",
                                 why: why, detail: "A few clicks inside Claude", how: .clicks, paid: false))
            }
        }
        // keep the state of tiles already on screen
        for i in made.indices {
            if let old = tiles.first(where: { $0.id == made[i].id }) { made[i].state = old.state }
        }
        tiles = made
        refreshStates()
    }

    static func safeName(_ s: String) -> Bool {
        !s.isEmpty && s.count <= 60 && s.allSatisfy { $0.isLetter || $0.isNumber || $0 == "-" || $0 == "_" }
    }

    private func draft(of skill: String) -> URL {
        (vault ?? home).appendingPathComponent("made-for-you/skills/\(skill)", isDirectory: true)
    }

    /// An item added in a Terminal window finishes out of the app's sight, so
    /// the saved state is looked at every few seconds.
    private func refreshStates() {
        let stateURL = home.appendingPathComponent(".config/moblee/setup-state.json")
        let status = ((try? JSONSerialization.jsonObject(with: Data(contentsOf: stateURL))) as? [String: Any])?["status"] as? [String: Bool] ?? [:]
        for i in tiles.indices where tiles[i].state != .running {
            switch tiles[i].kind {
            case .item:
                if status[tiles[i].key] == true { tiles[i].state = .done }
            case .skill:
                let installed = home.appendingPathComponent(".claude/skills/\(tiles[i].key)/SKILL.md")
                if let a = try? Data(contentsOf: installed),
                   let b = try? Data(contentsOf: draft(of: tiles[i].key).appendingPathComponent("SKILL.md")), a == b {
                    tiles[i].state = .done
                }
            case .connection: break
            }
        }
    }

    private func setState(_ id: String, _ s: TileState) {
        if let i = tiles.firstIndex(where: { $0.id == id }) {
            withAnimation(.spring(response: 0.4, dampingFraction: 0.75)) { tiles[i].state = s }
        }
    }

    // MARK: pressing a tile's button

    func press(_ tile: Tile) {
        switch (tile.kind, tile.how) {
        case (.skill, _): addSkill(tile)
        case (.item, .silent): addSilently(tile)
        default: explaining = tile        // a Terminal window or clicks: explain first
        }
    }

    private func addSilently(_ tile: Tile) {
        guard let pack else { return }
        setState(tile.id, .running)
        let t = EngineTask()
        tasks[tile.id] = t
        var worked = false
        t.run("/usr/bin/python3",
              [pack.appendingPathComponent("scripts/moblee-setup.py").path,
               "--only", tile.key, "--yes", "--progress"],
              home: home,
              onEvent: { e in
                  if e["step"] as? String == tile.key, e["state"] as? String == "ok" { worked = true }
              },
              onEnd: { [weak self] code in
                  self?.tasks[tile.id] = nil
                  self?.setState(tile.id, (code == 0 && worked) ? .done : .failed)
              })
    }

    private func addSkill(_ tile: Tile) {
        let fm = FileManager.default
        let src = draft(of: tile.key)
        let skills = home.appendingPathComponent(".claude/skills", isDirectory: true)
        let dst = skills.appendingPathComponent(tile.key, isDirectory: true)
        do {
            try fm.createDirectory(at: skills, withIntermediateDirectories: true)
            if fm.fileExists(atPath: dst.path) {
                // never delete: the copy being replaced is moved to the backups folder
                let stamp = ISO8601DateFormatter().string(from: Date()).replacingOccurrences(of: ":", with: "")
                let keep = home.appendingPathComponent(".config/moblee/backups/\(stamp)/skills", isDirectory: true)
                try fm.createDirectory(at: keep, withIntermediateDirectories: true)
                try fm.moveItem(at: dst, to: keep.appendingPathComponent(tile.key))
            }
            try fm.copyItem(at: src, to: dst)
            setState(tile.id, .done)
        } catch {
            setState(tile.id, .failed)
        }
    }

    /// For an item that needs the owner at a Terminal window: write a small
    /// command file that runs the pack's own checklist for that one item, and
    /// open it. The checklist asks its usual questions there.
    func openTerminal(for tile: Tile) {
        guard let pack else { return }
        let dir = home.appendingPathComponent("Library/Application Support/Moblee/run", isDirectory: true)
        let file = dir.appendingPathComponent("add-\(tile.key).command")
        let script = """
        #!/bin/bash
        clear
        echo "Moblee: adding \(tile.title)"
        echo "If it asks for your Mac password, type it and press Return."
        echo "Nothing shows while you type. That is normal."
        echo ""
        cd "\(pack.path)" || exit 1
        python3 scripts/moblee-setup.py --only \(tile.key)
        echo ""
        echo "You can close this window now and go back to Moblee."
        """
        do {
            try FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
            try script.write(to: file, atomically: true, encoding: .utf8)
            try FileManager.default.setAttributes([.posixPermissions: 0o755], ofItemAtPath: file.path)
            if home == FileManager.default.homeDirectoryForCurrentUser {
                NSWorkspace.shared.open(file)       // a practice run never opens Terminal
            }
            setState(tile.id, .handedOver)
        } catch {
            setState(tile.id, .failed)
        }
    }

    func openClicks(for tile: Tile) {
        if home == FileManager.default.homeDirectoryForCurrentUser,
           let url = URL(string: "https://claude.ai/settings/connectors") {
            NSWorkspace.shared.open(url)
        }
        setState(tile.id, .handedOver)
    }

    func repair(then: @escaping @MainActor (Bool) -> Void) {
        guard let pack, let vault else { then(false); return }
        EngineTask.output(of: "/usr/bin/python3",
                          [pack.appendingPathComponent("safety/install-safety.py").path, "--vault", vault.path],
                          home: home) { [weak self] code, _ in
            guard let self else { return }
            self.needsRepair = !FileManager.default.fileExists(
                atPath: self.home.appendingPathComponent(".claude/hooks/bash-guard.py").path)
            then(code == 0)
        }
    }
}
