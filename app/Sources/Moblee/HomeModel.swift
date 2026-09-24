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
    @Published var guardStale = false      // on, but an older copy than this Moblee's
    @Published var listUnreadable = false
    @Published var updateSetAside = false
    /// A newer Moblee published on GitHub than this app carries, if the daily
    /// look found one and the owner has not said Not now to it (see `NewerRelease`).
    @Published var newerRelease: String?
    @Published var loaded = false
    @Published var explaining: Tile?
    /// Which assistant this wiki is for, as the pack's scripts will read it:
    /// the word on record, and Claude when there is none.
    @Published var assistant: Assistant = .claude
    /// ChatGPT is still waiting for the owner to trust the guard (see `Trust`).
    @Published var trustPending = false
    /// The owner put the proof off ("Later") in this opening of the app.
    @Published var trustSetAside = false

    /// Only for an owner whose wiki is for ChatGPT, alone or with Claude: a
    /// note left from before a change to Claude alone is not theirs to answer.
    func refreshTrust(home: URL) {
        let now = Trust.pending(home: home, for: assistant)
        if now != trustPending { trustPending = now }
    }

    /// The Change control is there only when changing can be done safely: not
    /// on a wiki newer than this app (the change is made by this app's updater,
    /// which would put older files over newer ones), and not while something
    /// is being added (the updater and the checklist write the same settings).
    var canChangeAssistant: Bool {
        !wikiIsNewerThanApp && !tiles.contains { $0.state == .running }
    }

    /// The guard looks off, and the wiki is newer than this app. This app's
    /// copies are the older ones and its idea of "on" may be out of date, so it
    /// does not repair: the owner is sent for the newest Moblee.
    var repairIsForANewerMoblee: Bool { safetyOff && wikiIsNewerThanApp }

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

    nonisolated static func isNewer(_ a: String, than b: String) -> Bool {
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
        // The rules file is CLAUDE.md, AGENTS.md, or one of them with the other
        // a link to it (for ChatGPT alone: a real AGENTS.md, and CLAUDE.md a
        // link, so that a Moblee from before ChatGPT still sees a wiki here and
        // does not build a second one; for both: the other way round). Any of
        // these marks a wiki, and a link that some sync tool dropped changes
        // nothing. Which assistant the wiki is for is not read from this shape
        // but from the choice on record (see `Assistant.onRecord`).
        guard fm.fileExists(atPath: url.appendingPathComponent("CLAUDE.md").path)
                || fm.fileExists(atPath: url.appendingPathComponent("AGENTS.md").path),
              fm.fileExists(atPath: url.appendingPathComponent("wiki").path) else { return nil }
        return url
    }

    func load(home: URL, bundledPack: URL?) {
        self.home = home
        vault = Self.existingVault(home: home)
        assistant = Assistant.onRecord(home: home)
        refreshTrust(home: home)
        guard let vault else { loaded = true; return }

        wikiVersion = Self.read(vault.appendingPathComponent("VERSION"))
        if let bundledPack { packVersion = Self.read(bundledPack.appendingPathComponent("VERSION")) }
        checkSafety()
        lookForNewerRelease()

        guard let bundledPack else { readRequests(); loaded = true; return }
        // Copying the pack into place is file work, so it happens off the main thread.
        DispatchQueue.global(qos: .userInitiated).async { [weak self] in
            let settled = try? InstallRun.settlePack(bundledPack, home: home)
            DispatchQueue.main.async { MainActor.assumeIsolated { self?.packSettled(settled) } }
        }
    }

    /// Only ever reached with a wiki already in place: an install never asks.
    /// A practice run never goes to the network unless told to: `--latest <v>`
    /// pretends GitHub said v, `--release-url <url>` asks that address instead
    /// (a dead one proves the silent give-up), and `--live-release` asks GitHub
    /// itself. Without any of them a practice run asks nobody.
    func lookForNewerRelease() {
        let current = packVersion
        guard NewerRelease.isPlainVersion(current) else { return }
        let home = self.home
        let offer: (String?) -> Void = { [weak self] latest in
            guard let self else { return }
            self.newerRelease = NewerRelease.offer(latest: latest, current: current,
                                                   setAside: NewerRelease.setAside(home: home))
        }
        if Practice.on, let v = Flow.value(after: "--latest", in: Practice.args) {
            offer(NewerRelease.version(fromTag: v)); return
        }
        guard let source = NewerRelease.source(practice: Practice.on, args: Practice.args) else { return }
        let seen = NewerRelease.askedToday(home: home)
        if seen.asked, source == NewerRelease.latestURL { offer(seen.version); return }
        NewerRelease.fetch(from: source) { latest in
            DispatchQueue.main.async {
                MainActor.assumeIsolated {
                    if let latest, source == NewerRelease.latestURL { NewerRelease.note(home: home, version: latest) }
                    offer(latest)
                }
            }
        }
    }

    /// Whether the newer-Moblee line may be on the screen: never over an
    /// explanation, an update this app can make, or a repair. (The home screen
    /// also keeps it off the Trust steps, which are the screen's own state.)
    var newerReleaseLineAllowed: Bool {
        newerRelease != nil && explaining == nil && !updateAvailable && !needsRepair && !repairIsForANewerMoblee
    }

    /// Not now: this version is not offered again; a newer one will be.
    func setAsideNewerRelease() {
        if let v = newerRelease { NewerRelease.setAside(v, home: home) }
        newerRelease = nil
    }

    private func packSettled(_ settled: URL?) {
        pack = settled
        pointAtPack()
        checkSafety()      // now that the pack is known, the guard and the skills can be compared too
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
    ///
    /// For an owner who uses ChatGPT the same is asked of ChatGPT's own files,
    /// as the check-up asks it: the guard is there, and it is entered in
    /// ChatGPT's hooks file for both of the ways ChatGPT can delete. (Whether
    /// the owner has trusted it there cannot be seen in any file; that is what
    /// the Trust screen and the proof are for.) Claude's files are looked at
    /// only when Claude is used, since a wiki for ChatGPT alone has none.
    func checkSafety() {
        guard let vault else { return }
        let onRecord = Assistant.onRecord(home: home)
        if onRecord != assistant { assistant = onRecord }
        refreshTrust(home: home)
        var claudeOff = false, chatgptOff = false
        if assistant.wantsClaude {
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
            claudeOff = !(guardThere && switchedOn && rules >= 10)
        }
        if assistant.wantsChatGPT {
            let guardThere = FileManager.default.fileExists(
                atPath: home.appendingPathComponent(".codex/hooks/bash-guard.py").path)
            var entered = false
            if let file = Self.json(home.appendingPathComponent(".codex/hooks.json")),
               let hooks = (file["hooks"] as? [String: Any])?["PreToolUse"] as? [[String: Any]] {
                for entry in hooks where Self.coversBothWays(entry["matcher"] as? String) {
                    for h in (entry["hooks"] as? [[String: Any]] ?? []) {
                        if (h["command"] as? String ?? "").contains(".codex/hooks/bash-guard.py") { entered = true }
                    }
                }
            }
            chatgptOff = !(guardThere && entered)
        }
        safetyOff = claudeOff || chatgptOff
        // The guard and the skills are compared with this app's pack only when
        // the wiki and the pack are the SAME version. While an update is pending
        // they are expected to differ, and the update brings them level. And when
        // the wiki is NEWER than this app (the owner updated another way, then
        // opened an old copy of Moblee), this app's copies are the older ones:
        // offering to "repair" with them would put an older guard and older
        // skills over newer ones and call it bringing them up to date.
        let versionsLevel = wikiVersion == packVersion
            || (!Self.isNewer(packVersion, than: wikiVersion) && !Self.isNewer(wikiVersion, than: packVersion))
        guardStale = !safetyOff && versionsLevel && !guardIsMoblees() && !repairSetAside
        needsRepair = safetyOff || guardStale || (versionsLevel && !skillsAreMoblees() && !repairSetAside)
    }

    /// ChatGPT can delete in two ways, by a shell command (`Bash`) and with its
    /// file-editing tool (`apply_patch`), and the guard's entry must name both.
    /// This Moblee writes exactly `Bash|apply_patch`. A later one may name
    /// more tools beside them; that is still "on", and an app that called it
    /// "off" would press an older entry and an older guard on a newer wiki.
    static func coversBothWays(_ matcher: String?) -> Bool {
        let named = Set((matcher ?? "").split(separator: "|").map { $0.trimmingCharacters(in: .whitespaces) })
        return named.contains("Bash") && named.contains("apply_patch")
    }

    /// The owner said "Not now" to a Repair that is about copies differing, not
    /// about the guard being off (that one is never set aside). For this opening
    /// of the app only. An owner who changed their guard on purpose can then
    /// still reach their tiles.
    @Published var repairSetAside = false { didSet { if repairSetAside != oldValue { checkSafety() } } }

    /// True when the wiki was made or updated by a newer Moblee than this app.
    var wikiIsNewerThanApp: Bool { Self.isNewer(wikiVersion, than: packVersion) }

    /// `~/.config/moblee/package-path` is how Claude and the check-up find the
    /// Moblee folder. The app is what brings a newer folder to the Mac, so the
    /// app keeps that note pointing at the folder it is using. Left pointing at
    /// an older one, the check-up compared the guard and the skills with stale
    /// copies and raised two false alarms (second run on a fresh account,
    /// 20 September 2026). The older folder stays where it is; nothing is deleted.
    private func pointAtPack() {
        // Never towards an older folder: a wiki newer than this app keeps the
        // note its own, newer, Moblee wrote.
        guard let pack, !wikiIsNewerThanApp else { return }
        let note = home.appendingPathComponent(".config/moblee/package-path")
        if Self.read(note) == pack.path { return }
        try? FileManager.default.createDirectory(at: note.deletingLastPathComponent(), withIntermediateDirectories: true)
        try? (pack.path + "\n").write(to: note, atomically: true, encoding: .utf8)
    }

    /// The guard on the Mac must be this Moblee's guard, as the check-up also
    /// asks: an older copy does not know the newer pack's own scripts and would
    /// refuse Claude the pack's tools. Repair puts it level and keeps the old one.
    private func guardIsMoblees() -> Bool {
        guard let pack else { return true }      // not known yet; looked at again once the pack is settled
        guard let ours = try? Data(contentsOf: pack.appendingPathComponent("safety/bash-guard.py")) else { return true }
        // One copy for each assistant in use: Claude's, ChatGPT's, or both.
        var places: [String] = []
        if assistant.wantsClaude { places.append(".claude/hooks/bash-guard.py") }
        if assistant.wantsChatGPT { places.append(".codex/hooks/bash-guard.py") }
        return places.allSatisfy { (try? Data(contentsOf: home.appendingPathComponent($0))) == ours }
    }

    /// Each of Moblee's skills must be there, and be Moblee's: a folder of the
    /// right name holding something else (an older copy, or the owner's own
    /// skill) means the companion is missing without anyone being told.
    private func skillsAreMoblees() -> Bool {
        guard let pack else { return true }      // not known yet; looked at again once the pack is settled
        let fm = FileManager.default
        let source = pack.appendingPathComponent("skills", isDirectory: true)
        guard let names = try? fm.contentsOfDirectory(atPath: source.path) else { return true }
        // Claude keeps its skills in ~/.claude/skills and ChatGPT in ~/.agents/skills;
        // the same files go to each that is in use.
        var folders: [String] = []
        if assistant.wantsClaude { folders.append(".claude/skills") }
        if assistant.wantsChatGPT { folders.append(".agents/skills") }
        for name in names {
            let ours = source.appendingPathComponent("\(name)/SKILL.md")
            guard fm.fileExists(atPath: ours.path) else { continue }
            for folder in folders {
                let theirs = home.appendingPathComponent("\(folder)/\(name)/SKILL.md")
                guard let a = try? Data(contentsOf: ours), let b = try? Data(contentsOf: theirs), a == b else { return false }
            }
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
            // keep what is already known about this asking; the same thing asked again on a
            // later date is a new asking and starts as waiting, even while the app is open
            if let old = tiles.first(where: { $0.id == t.id && $0.asked == t.asked }) {
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
        // Never from this pack onto a wiki a newer Moblee made, whatever the
        // guard's state: the screen does not offer it, and this refuses it.
        guard !wikiIsNewerThanApp else { then(); return }
        guard let pack, let vault else { repairFailed = true; then(); return }
        // The assistant is named to both scripts as the app read it. Left to
        // read the record themselves they do not all read it alike (one takes
        // the first line, another the whole file; one minds capitals, another
        // does not), and a repair for a different assistant than the screen
        // checked would either not mend what was found or stop on a word it
        // does not know, every time, with no way past.
        let who = assistant.rawValue
        // The safety layer first, then Moblee's own skills (whatever was sitting
        // under one of their names is moved to the backups folder, never deleted).
        EngineTask.output(of: "/usr/bin/python3",
                          [pack.appendingPathComponent("safety/install-safety.py").path, "--vault", vault.path,
                           "--assistant", who],
                          home: home) { [weak self] code, data in
            guard let self else { return }
            // A repair that added the guard's entry to ChatGPT's hooks list says,
            // on a line of its own, that ChatGPT is waiting for the owner's trust.
            // A repair that only replaced the guard file prints no such line, and
            // the step is not set waiting: ChatGPT's trust follows the entry.
            let said = String(data: data, encoding: .utf8) ?? ""
            if Trust.saidNeeded(in: said) {
                Trust.setPending(true, home: self.home)
                self.trustSetAside = false
            }
            EngineTask.output(of: "/bin/bash",
                              [pack.appendingPathComponent("scripts/install-skills.sh").path, "--update",
                               "--assistant", who],
                              home: self.home) { [weak self] code2, _ in
                guard let self else { return }
                self.checkSafety()
                self.repairFailed = code != 0 || code2 != 0 || self.needsRepair
                then()
            }
        }
    }
}
