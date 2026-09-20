import SwiftUI
import AppKit

/// What a returning owner sees: the things Claude has asked for on their
/// behalf, waiting as tiles; an update, if this app carries a newer Moblee than
/// their wiki has; and a repair button if the safety layer is not as it should
/// be.
///
/// The request list is a file in the wiki, written by Claude. Claude reads web
/// pages, documents and messages, so that file is treated as untrusted: nothing
/// in it reaches a command line, item keys must match the pack's own list, and
/// a made-to-measure skill is checked by the pack's own script and shown to the
/// owner before it is added. The app never writes to the wiki.
@MainActor
final class HomeModel: ObservableObject {
    enum How: String { case silent, terminal, clicks, hidden }
    enum Kind: String { case item, skill, connection }
    enum TileState: Equatable { case waiting, running, done, failed, handedOver, blocked }

    struct Tile: Identifiable, Equatable {
        let kind: Kind
        let key: String
        var title: String
        var why: String
        var detail: String
        var how: How
        var paid: Bool
        var state: TileState = .waiting
        var note: String = ""          // why it failed or cannot be added, in the engine's own words
        var files: [String] = []       // for a made-to-measure skill: what is in it
        var body: String = ""          // and the whole of what Claude would be told to do
        var steps: [[String]] = []     // for clicks inside Claude: where to go, what to press, how to tell it worked
        var asked: String = ""         // the date on the request: the owner's Done answers this asking, not every later one
        var id: String { kind.rawValue + ":" + key }
        var doneKey: String { asked.isEmpty ? id : id + "@" + asked }

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
    @Published var repairFailed = false
    @Published var safetyOff = false
    @Published var listUnreadable = false
    @Published var updateSetAside = false
    @Published var loaded = false
    @Published var explaining: Tile?

    private(set) var vault: URL?
    private var home: URL = FileManager.default.homeDirectoryForCurrentUser
    private var pack: URL?
    private var catalogue: [String: [String: Any]] = [:]
    private var timer: Timer?
    private var activeObserver: NSObjectProtocol?
    private var tasks: [String: EngineTask] = [:]
    private var describing: Set<String> = []

    var updateAvailable: Bool {
        !updateSetAside && !wikiVersion.isEmpty && !packVersion.isEmpty
            && Self.isNewer(packVersion, than: wikiVersion)
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

    /// The wiki this Mac already has, if any. The record is written by the
    /// installer's last step, so a half-built wiki is never taken for one.
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
        if let bundledPack { packVersion = Self.read(bundledPack.appendingPathComponent("VERSION")) }
        checkSafety()

        guard let bundledPack else { readRequests(); loaded = true; return }
        // Copying the pack into place is file work, so it happens off the main thread.
        DispatchQueue.global(qos: .userInitiated).async { [weak self] in
            let settled = try? InstallRun.settlePack(bundledPack, home: home)
            DispatchQueue.main.async { MainActor.assumeIsolated { self?.packSettled(settled) } }
        }
    }

    private func packSettled(_ settled: URL?) {
        pack = settled
        checkSafety()      // now that the pack is known, the skills can be compared too
        guard let pack else { listUnreadable = true; loaded = true; return }
        EngineTask.output(of: "/usr/bin/python3",
                          [pack.appendingPathComponent("scripts/moblee-setup.py").path, "--list", "--json"],
                          home: home) { [weak self] code, data in
            guard let self else { return }
            let list = (try? JSONSerialization.jsonObject(with: data)) as? [[String: Any]]
            if code == 0, let list, !list.isEmpty {
                for entry in list { if let k = entry["key"] as? String { self.catalogue[k] = entry } }
                self.listUnreadable = false
            } else {
                // Usually Apple's tools needing a reinstall after a macOS upgrade.
                // Saying so beats an empty screen that claims nothing is waiting.
                self.listUnreadable = true
            }
            self.readRequests()
            self.loaded = true
        }
    }

    func startWatching() {
        timer?.invalidate()
        timer = Timer.scheduledTimer(withTimeInterval: 4, repeats: true) { [weak self] _ in
            Task { @MainActor in self?.readRequests() }
        }
        if activeObserver == nil {
            activeObserver = NotificationCenter.default.addObserver(
                forName: NSApplication.didBecomeActiveNotification, object: nil, queue: .main
            ) { [weak self] _ in
                Task { @MainActor in self?.checkSafety(); self?.readRequests() }
            }
        }
    }

    func stopWatching() { timer?.invalidate(); timer = nil }

    private static func read(_ url: URL) -> String {
        ((try? String(contentsOf: url, encoding: .utf8)) ?? "").trimmingCharacters(in: .whitespacesAndNewlines)
    }

    private static func json(_ url: URL) -> [String: Any]? {
        guard let data = try? Data(contentsOf: url) else { return nil }
        return (try? JSONSerialization.jsonObject(with: data)) as? [String: Any]
    }

    /// The same three tests the check-up makes: the guard is there, it is
    /// switched on in Claude's settings, and Moblee's permission rules are in
    /// the wiki's own settings.
    func checkSafety() {
        guard let vault else { return }
        let guardThere = FileManager.default.fileExists(
            atPath: home.appendingPathComponent(".claude/hooks/bash-guard.py").path)
        var switchedOn = false
        if let settings = Self.json(home.appendingPathComponent(".claude/settings.json")),
           let hooks = (settings["hooks"] as? [String: Any])?["PreToolUse"] as? [[String: Any]] {
            for entry in hooks {
                for h in (entry["hooks"] as? [[String: Any]] ?? []) {
                    if (h["command"] as? String ?? "").contains("bash-guard.py") { switchedOn = true }
                }
            }
        }
        var rules = 0
        for name in ["settings.local.json", "settings.json"] {
            if let s = Self.json(vault.appendingPathComponent(".claude/\(name)")),
               let allow = (s["permissions"] as? [String: Any])?["allow"] as? [Any] { rules += allow.count }
        }
        safetyOff = !(guardThere && switchedOn && rules >= 10)
        // While an update is pending the skills are expected to differ; the update brings them level.
        let versionsLevel = !Self.isNewer(packVersion, than: wikiVersion)
        needsRepair = safetyOff || (versionsLevel && !skillsAreMoblees())
    }

    /// Each of Moblee's skills must be there, and be Moblee's: a folder of the
    /// right name holding something else (an older copy, or the owner's own
    /// skill) means the companion is missing without anyone being told.
    private func skillsAreMoblees() -> Bool {
        guard let pack else { return true }      // not known yet; looked at again once the pack is settled
        let fm = FileManager.default
        let source = pack.appendingPathComponent("skills", isDirectory: true)
        guard let names = try? fm.contentsOfDirectory(atPath: source.path) else { return true }
        for name in names {
            let ours = source.appendingPathComponent("\(name)/SKILL.md")
            guard fm.fileExists(atPath: ours.path) else { continue }
            let theirs = home.appendingPathComponent(".claude/skills/\(name)/SKILL.md")
            guard let a = try? Data(contentsOf: ours), let b = try? Data(contentsOf: theirs), a == b else { return false }
        }
        return true
    }

    /// Plain words only on a tile: a request cannot put anything else there.
    static func plain(_ s: String, limit: Int) -> String {
        let kept = s.unicodeScalars.filter {
            CharacterSet.alphanumerics.contains($0) || " .,'!?-:()&".unicodeScalars.contains($0)
        }
        return String(String(String.UnicodeScalarView(kept)).prefix(limit))
    }

    static func safeName(_ s: String) -> Bool {
        guard let first = s.first, s.count <= 60, first.isASCII, first.isLetter || first.isNumber else { return false }
        return s.allSatisfy { $0.isASCII && ($0.isLetter || $0.isNumber || $0 == "-" || $0 == "_") }
    }

    private func readRequests() {
        guard let vault else { return }
        let list = (Self.json(vault.appendingPathComponent(".moblee/requests.json"))?["requests"] as? [[String: Any]]) ?? []

        var made: [Tile] = []
        var seen: Set<String> = []
        for r in list.prefix(40) {
            guard (r["status"] as? String ?? "waiting") == "waiting",
                  let kind = Kind(rawValue: r["kind"] as? String ?? ""),
                  let key = r["key"] as? String, !key.isEmpty else { continue }
            let why = Self.plain(r["why"] as? String ?? "", limit: 120)
            var tile: Tile?
            switch kind {
            case .item:
                guard let c = catalogue[key] else { continue }       // only the pack's own items
                let how = How(rawValue: c["how"] as? String ?? "terminal") ?? .terminal
                if how == .hidden { continue }
                let mb = c["space_mb"] as? Int ?? 0
                let size = mb >= 1000 ? String(format: "%.1f GB", Double(mb) / 1000) : "\(mb) MB"
                let paid = c["paid"] as? Bool ?? false
                // Something that takes no room (a connection) says nothing about room: "0 MB" is noise.
                let detail = "About \(c["minutes"] as? Int ?? 1) min · " + (mb > 0 ? "\(size) · " : "")
                    + (paid ? "can cost money" : "free")
                tile = Tile(kind: .item, key: key, title: c["title"] as? String ?? key,
                            why: why, detail: detail, how: how, paid: paid)
                // The pack's own words for the three cards; a list of any other shape is ignored.
                if let steps = c["steps"] as? [[String]], steps.count == 3, steps.allSatisfy({ $0.count == 2 }) {
                    tile?.steps = steps
                }
            case .skill:
                guard Self.safeName(key) else { continue }
                tile = Tile(kind: .skill, key: key, title: "A skill Claude wrote: \(key)",
                            why: why, detail: "Looking at it…", how: .silent, paid: false)
            case .connection:
                let name = Self.plain(key, limit: 30)
                guard !name.isEmpty else { continue }
                tile = Tile(kind: .connection, key: name, title: "Connect \(name)",
                            why: why, detail: "A few clicks inside Claude", how: .clicks, paid: false)
            }
            guard var t = tile, !seen.contains(t.id) else { continue }
            t.asked = Self.plain(r["asked"] as? String ?? "", limit: 20)
            seen.insert(t.id)
            if let old = tiles.first(where: { $0.id == t.id }) {      // keep what is already known
                t.state = old.state; t.note = old.note
                if t.kind == .skill { t.detail = old.detail; t.files = old.files; t.body = old.body }
            }
            made.append(t)
        }
        if made != tiles { tiles = made }
        for t in made where t.kind == .skill && t.files.isEmpty && t.state != .blocked { describe(t) }
        refreshStates()
    }

    /// Ask the pack's own script what a drafted skill says it does, what is in
    /// it, and whether there is any reason not to add it.
    private func describe(_ tile: Tile, then: (@MainActor () -> Void)? = nil) {
        guard let pack, let vault, !describing.contains(tile.id) else { return }
        describing.insert(tile.id)
        EngineTask.output(of: "/usr/bin/python3",
                          [pack.appendingPathComponent("scripts/add-made-skill.py").path, tile.key,
                           "--vault", vault.path, "--describe", "--json"],
                          home: home) { [weak self] _, data in
            guard let self else { return }
            self.describing.remove(tile.id)
            guard let i = self.tiles.firstIndex(where: { $0.id == tile.id }) else { return }
            guard let info = (try? JSONSerialization.jsonObject(with: data)) as? [String: Any] else {
                self.tiles[i].state = .blocked
                self.tiles[i].note = "Moblee could not look inside it."
                return
            }
            let problems = info["problems"] as? [String] ?? []
            self.tiles[i].detail = Self.plain(info["description"] as? String ?? "", limit: 400)
            self.tiles[i].files = (info["files"] as? [[String: Any]] ?? []).compactMap { $0["path"] as? String }
            self.tiles[i].body = info["body"] as? String ?? ""
            if let first = problems.first {
                self.tiles[i].state = .blocked
                self.tiles[i].note = first
            }
            then?()
        }
    }

    // MARK: things only the owner can say are done

    private var doneFile: URL { home.appendingPathComponent(".config/moblee/app-state.json") }

    private func ownerSaidDone() -> Set<String> {
        Set((Self.json(doneFile)?["done"] as? [String]) ?? [])
    }

    /// A connection is made by clicks inside Claude, where Moblee cannot see.
    /// So the owner says when it is done, and the tile gets out of the way.
    func markDone(_ tile: Tile) {
        var all = ownerSaidDone(); all.insert(tile.doneKey)
        if let data = try? JSONSerialization.data(withJSONObject: ["done": Array(all).sorted()], options: [.prettyPrinted]) {
            try? FileManager.default.createDirectory(at: doneFile.deletingLastPathComponent(), withIntermediateDirectories: true)
            try? data.write(to: doneFile, options: .atomic)
        }
        setState(tile.id, .done)
    }

    /// The tile the big button acts on: the first one that can simply be added.
    var nextTile: Tile? { tiles.first { $0.state == .waiting || $0.state == .failed } }

    /// An item added in a Terminal window finishes out of the app's sight, so
    /// the saved state is looked at every few seconds.
    private func refreshStates() {
        // Read value by value: one entry that is not a plain yes or no must not
        // make the whole record unreadable and every added tile forget it was added.
        let status = ((Self.json(home.appendingPathComponent(".config/moblee/setup-state.json"))?["status"]
                       as? [String: Any]) ?? [:]).compactMapValues { $0 as? Bool }
        for i in tiles.indices where tiles[i].state != .running {
            switch tiles[i].kind {
            case .item:
                if status[tiles[i].key] == true, tiles[i].state != .done { tiles[i].state = .done }
                // Clicks inside Claude happen where neither Moblee nor the pack's
                // check can see, so there the owner's word is what finishes it.
                if tiles[i].how == .clicks, tiles[i].state != .done,
                   ownerSaidDone().contains(tiles[i].doneKey) { tiles[i].state = .done }
            case .skill:
                let marker = home.appendingPathComponent(".claude/skills/\(tiles[i].key)/.made-for-you")
                let installed = home.appendingPathComponent(".claude/skills/\(tiles[i].key)/SKILL.md")
                let draft = (vault ?? home).appendingPathComponent("made-for-you/skills/\(tiles[i].key)/SKILL.md")
                if FileManager.default.fileExists(atPath: marker.path),
                   let a = try? Data(contentsOf: installed), let b = try? Data(contentsOf: draft), a == b,
                   tiles[i].state != .done {
                    tiles[i].state = .done
                }
            case .connection:
                if tiles[i].state != .done, ownerSaidDone().contains(tiles[i].doneKey) { tiles[i].state = .done }
            }
        }
    }

    private func setState(_ id: String, _ s: TileState, note: String = "") {
        if let i = tiles.firstIndex(where: { $0.id == id }) {
            withAnimation(.spring(response: 0.4, dampingFraction: 0.75)) {
                tiles[i].state = s
                tiles[i].note = note
            }
        }
    }

    // MARK: pressing a tile's button

    func press(_ tile: Tile) {
        switch (tile.kind, tile.how) {
        case (.item, .silent): addSilently(tile)
        case (.skill, _):
            // Look at the draft again at this moment, so that what the owner is
            // shown is what would be added, even if the draft changed since.
            describe(tile) { [weak self] in
                guard let self, let fresh = self.tiles.first(where: { $0.id == tile.id }),
                      fresh.state != .blocked else { return }
                self.explaining = fresh
            }
        default: explaining = tile        // a Terminal window or clicks: explain first
        }
    }

    private func addSilently(_ tile: Tile) {
        guard let pack else { return }
        setState(tile.id, .running)
        let t = EngineTask()
        tasks[tile.id] = t
        var worked = false
        var why = ""
        t.run("/usr/bin/python3",
              [pack.appendingPathComponent("scripts/moblee-setup.py").path,
               "--only", tile.key, "--yes", "--progress"],
              home: home,
              onEvent: { e in
                  guard e["step"] as? String == tile.key else { return }
                  if e["state"] as? String == "ok" { worked = true }
                  if e["state"] as? String == "fail" { why = Self.plain(e["detail"] as? String ?? "", limit: 160) }
                  if e["state"] as? String == "unseen" { why = "Moblee cannot see whether this worked. Ask Claude to try it." }
              },
              onEnd: { [weak self] code in
                  self?.tasks[tile.id] = nil
                  if code == 0 && worked { self?.setState(tile.id, .done) }
                  else { self?.setState(tile.id, .failed, note: why) }
              })
    }

    /// After the owner has seen what the skill says it does and pressed Add.
    func addSkill(_ tile: Tile) {
        guard let pack, let vault else { return }
        setState(tile.id, .running)
        EngineTask.output(of: "/usr/bin/python3",
                          [pack.appendingPathComponent("scripts/add-made-skill.py").path, tile.key,
                           "--vault", vault.path, "--yes"],
                          home: home) { [weak self] code, _ in
            if code == 0 { self?.setState(tile.id, .done) }
            else { self?.setState(tile.id, .failed, note: "It could not be added. Tell Claude.") }
        }
    }

    /// For an item that needs the owner at a Terminal window: write a small
    /// command file that runs the pack's own checklist for that one item, and
    /// open it. Only the item's key, which has matched the pack's own list,
    /// reaches the file.
    ///
    /// `--yes`: the owner has pressed Add and then Open it, so the checklist's
    /// "Start now?" would be a third asking of the same question, and one the
    /// companion never warned them about (install test, 20 September 2026).
    ///
    /// The last lines end this window's own shell before it can speak. Left to
    /// exit by itself, Apple's Terminal set-up prints "truncating history
    /// files" and "Deleting expired sessions", which read badly beside a
    /// promise that nothing is deleted. That shell is ended only when Terminal
    /// opened it for this file: the file notes, as its first act, whether the
    /// shell that started it is under ten seconds old. A shell someone was
    /// already working in (the file run by hand) is older, and is left alone.
    func openTerminal(for tile: Tile) {
        guard let pack, tile.kind == .item, catalogue[tile.key] != nil else { return }
        let dir = home.appendingPathComponent("Library/Application Support/Moblee/run", isDirectory: true)
        let file = dir.appendingPathComponent("add-\(tile.key).command")
        let script = """
        #!/bin/bash
        opened_for_this=no
        case "$(ps -o etime= -p "$PPID" 2>/dev/null | tr -d ' ')" in 00:0[0-9]) opened_for_this=yes ;; esac
        clear
        echo "Moblee: adding one item for your wiki."
        echo "If it asks for your Mac password, type it and press Return."
        echo "Nothing shows while you type. That is normal."
        echo ""
        cd '\(pack.path.replacingOccurrences(of: "'", with: "'\\''"))' || exit 1
        if python3 scripts/moblee-setup.py --only \(tile.key) --yes; then
          echo ""
          echo "Finished. Close this window and go back to Moblee."
        else
          echo ""
          echo "That did not finish. Nothing is broken. Close this window and tell Claude."
        fi
        echo ""
        if [ "$opened_for_this" = yes ] && [ "${TERM_PROGRAM:-}" = "Apple_Terminal" ]; then
          case "$(ps -o comm= -p "$PPID" 2>/dev/null)" in
            -zsh|zsh|*/zsh|-bash|bash|*/bash) kill -9 "$PPID" ;;
          esac
        fi
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
            setState(tile.id, .failed, note: "Moblee could not open the window.")
        }
    }

    func openClicks(for tile: Tile) {
        if home == FileManager.default.homeDirectoryForCurrentUser,
           let url = URL(string: "https://claude.ai/settings/connectors") {
            NSWorkspace.shared.open(url)
        }
        setState(tile.id, .handedOver)
    }

    func repair(then: @escaping @MainActor () -> Void) {
        guard let pack, let vault else { repairFailed = true; then(); return }
        // The safety layer first, then Moblee's own skills (whatever was sitting
        // under one of their names is moved to the backups folder, never deleted).
        EngineTask.output(of: "/usr/bin/python3",
                          [pack.appendingPathComponent("safety/install-safety.py").path, "--vault", vault.path],
                          home: home) { [weak self] code, _ in
            guard let self else { return }
            EngineTask.output(of: "/bin/bash",
                              [pack.appendingPathComponent("scripts/install-skills.sh").path, "--update"],
                              home: self.home) { [weak self] code2, _ in
                guard let self else { return }
                self.checkSafety()
                self.repairFailed = code != 0 || code2 != 0 || self.needsRepair
                then()
            }
        }
    }
}
