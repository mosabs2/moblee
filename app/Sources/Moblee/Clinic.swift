import Foundation
import AppKit

/// (v0.9.6) The check-up an owner runs themselves, from one press.
///
/// A check-up used to mean the owner carrying out a clinic note by hand: put a
/// file in `raw/`, say an exact sentence to their assistant, answer a permission
/// prompt for every command, then find a file and send it. Several owners cannot
/// manage that, and what arrived instead was a message or a photograph of a
/// screen for somebody to read by eye. This runs the pack's own read-only
/// check-up and saves the report where the clinic process already looks for it,
/// so the owner presses one thing and sends one file.
///
/// WHAT IT RUNS. `scripts/moblee-doctor.py --card --json`, and nothing else. The
/// check-up is read-only and this must not make it otherwise: `--report` and
/// `--card-file` are the only two things it can write and neither is asked for,
/// `--prove-guard` is never asked for (it would spend the owner's allowance),
/// and no command of any kind is put together from anything the wiki contains.
/// `--card --json` is the interface the card was built to offer a program; see
/// `build_card` in the check-up itself.
///
/// REDACTION. Not a word of the report is written here from the check-up's own
/// findings: every line comes out of the card, which the check-up has already
/// passed through its own `anonymiser` (the home folder as `~`, the wiki's
/// folder name as `<wiki>`, page names replaced). Writing a second redaction in
/// the app would be a second thing to keep right. What this file adds to the
/// report is its own: dates, counts, and the owner's name, which the clinic note
/// allows.
///
/// WHAT IT WRITES. One report, in the wiki's own `raw/` folder, under the name
/// the clinic note gives (`raw/clinic-report-<owner>-checkup-2026-09-24.md`), so
/// that the folder the owner is told to look in is the folder it is in and a
/// later commit by their assistant picks it up. An earlier report of that name is
/// never overwritten: a number is added, as the check-up's own `--report` does
/// and as a dropped file's name does. Nothing under `wiki/` is touched, nothing
/// is committed, and one line goes into Moblee's own install diary, as a repair
/// and a drop already do.
@MainActor
final class Clinic: ObservableObject {
    /// The round this app carries out. The clinic note of 24 September 2026 names
    /// the report's file name and its sections, and the maintainer's process
    /// reads reports under that name, so both are written down here rather than
    /// made up at each call.
    static let round = "check-up, 24 September 2026"
    /// (v0.9.6) The day the check-up RAN goes into the file name, not the day
    /// the note was written. A report made in December and named 24 September
    /// told whoever read it the wrong thing about when it was made, and every
    /// later press only added a number to the same old date. The round the
    /// note belongs to is still named inside the report, on its `round:` line.
    static var roundStamp: String { stamp(for: Date()) }
    static func stamp(for date: Date) -> String { "checkup-" + fileDay.string(from: date) }
    private static let fileDay: DateFormatter = {
        let f = DateFormatter()
        f.locale = Locale(identifier: "en_US_POSIX")
        f.calendar = Calendar(identifier: .gregorian)
        f.dateFormat = "yyyy-MM-dd"
        return f
    }()

    /// How long the check-up is given. It takes about nine seconds on a wiki of
    /// 3,400 files, so this is roughly ten times the longest run seen. A limit
    /// matters because the owner is watching a screen: with none, a check-up that
    /// never ends leaves them in front of "Checking your wiki" for ever.
    /// `nonisolated`, because the run itself happens off the main thread and the
    /// limit is read there.
    nonisolated static let timeLimit: TimeInterval = 90

    /// Why the check-up could not say anything about the wiki. Never shown to the
    /// owner in these words; see `Clinic.sentence`.
    enum Trouble: Equatable {
        case noCheckup                  // this Moblee has no check-up inside it
        case didNotFinish(code: Int32)   // it ran and stopped, or said nothing a program can read
        case refusedByGuard             // the Mac's delete guard would not let it run
        case tookTooLong
    }

    struct Finished: Equatable {
        let card: Card
        /// The report's file name inside `raw/`, or nil when it could not be
        /// saved. Nil is not a failure of the check-up: the findings are on the
        /// screen and the owner can photograph it, which is what the card is for.
        let savedAs: String?
    }

    enum State: Equatable {
        case idle
        case running
        case finished(Finished)
        /// No wiki on this Mac: nothing to check, and nowhere to write a report.
        case noWiki
        /// The wiki is there but the check-up said nothing about it. A report
        /// saying exactly that is still written, as the clinic note asks, so the
        /// maintainer learns that the check-up is broken on this Mac.
        case couldNotCheck(Trouble, savedAs: String?)
    }

    @Published var state: State = .idle

    /// Where the report went, for the screen and for the Finder window.
    private var reportURL: URL?
    private var rawFolder: URL?

    // MARK: - the health card, as the check-up hands it over

    /// One screen of findings, redacted by the check-up itself, meant for
    /// whoever is helping the owner. Read from `--card --json` and never
    /// assembled here: the card is a way of printing the check-up's findings and
    /// not a second reading of them.
    struct Card: Equatable {
        struct Row: Equatable {
            var level: String = ""  // OK, LOOK, PROBLEM, CANNOT SEE, as the check-up says it
            var code: String        // its entry in the companion's field guide, or "" for none
            var line: String
        }
        var lines: [String] = []           // the card exactly as the check-up prints it
        var state: String = "healthy"      // healthy, unchecked or unwell
        var headline: String = ""
        var wrong: [Row] = []
        var wrongTotal: Int = 0
        var unchecked: [Row] = []
        var uncheckedTotal: Int = 0
        var actions: [String] = []
        /// (v0.9.6) Every finding the check-up made, redacted by the check-up
        /// itself, in the order it raised them.
        ///
        /// Empty with the pack as it stands today: the card is one screen and
        /// carries what needs attention, so the lines that were found to be right
        /// are not on it, and a long list of faults is cut to what fits. The
        /// report then says so in plain words rather than pretending to be whole.
        /// A `findings` list in `--card --json` is the one change to the check-up
        /// that would let a report carry the whole of it, and this reads it the
        /// moment the pack offers it; see the note in `report`.
        var findings: [Row] = []

        var healthy: Bool { state == "healthy" }

        /// The card as a program reads it. The output is looked for between the
        /// first `{` and the last `}` rather than parsed from the first byte,
        /// because both of the check-up's own streams are read together (which is
        /// what lets a refusal by the delete guard be seen at all) and a warning
        /// from Python on the way past must not make the findings unreadable.
        static func read(_ text: String) -> Card? {
            guard let start = text.firstIndex(of: "{"), let end = text.lastIndex(of: "}"),
                  start < end else { return nil }
            let body = String(text[start...end])
            guard let data = body.data(using: .utf8),
                  let json = (try? JSONSerialization.jsonObject(with: data)) as? [String: Any],
                  let lines = json["lines"] as? [String] else { return nil }
            func rows(_ key: String) -> [Row] {
                ((json[key] as? [[String: Any]]) ?? []).map {
                    Row(level: $0["level"] as? String ?? "",
                        code: $0["guide"] as? String ?? "",
                        line: $0["line"] as? String ?? "")
                }
            }
            var card = Card()
            card.lines = lines
            card.state = json["state"] as? String ?? "unwell"
            card.headline = json["headline"] as? String ?? ""
            card.wrong = rows("wrong")
            card.wrongTotal = json["wrong_total"] as? Int ?? card.wrong.count
            card.unchecked = rows("unchecked")
            card.uncheckedTotal = json["unchecked_total"] as? Int ?? card.unchecked.count
            card.actions = (json["actions"] as? [String]) ?? []
            card.findings = rows("findings")
            return card
        }
    }

    // MARK: - who the owner is

    /// The one sentence in a wiki's rules file that names its owner, read exactly
    /// as the clinic note reads it (`personal knowledge base for … where`). A
    /// wiki whose name was never filled in still says `[Your Name]`, which names
    /// nobody, so that counts as not found.
    static func ownerName(inRules text: String) -> String? {
        guard let r = text.range(of: "personal knowledge base for ") else { return nil }
        let rest = text[r.upperBound...]
        // Never past the end of that line, and never through a bold marker, which
        // is where the note's own pattern stops.
        guard let stop = rest.range(of: " where") else { return nil }
        let name = rest[..<stop.lowerBound]
        guard !name.contains("\n"), !name.contains("*") else { return nil }
        let tidy = name.trimmingCharacters(in: .whitespaces)
        return (tidy.isEmpty || tidy == "[Your Name]") ? nil : tidy
    }

    /// The wiki's rules file: `CLAUDE.md`, or `AGENTS.md` in a wiki laid down for
    /// ChatGPT alone. Read in the note's own order, and a link to the other one
    /// is followed, as reading a file does.
    static func ownerName(inWiki vault: URL) -> String? {
        for name in ["CLAUDE.md", "AGENTS.md"] {
            if let text = try? String(contentsOf: vault.appendingPathComponent(name), encoding: .utf8),
               let owner = ownerName(inRules: text) {
                return owner
            }
        }
        return nil
    }

    /// The owner's name turned into the word the report's file name carries, by
    /// the clinic note's own rule: the first word only, in lower case, with every
    /// character that is not a plain a-to-z letter replaced by a hyphen. So
    /// "Mary Ann" gives `mary`, "Zoë" gives `zo-`, "Ali & Noor" gives `ali`.
    /// A wiki that names nobody is filed under `owner`, and the report says so in
    /// words rather than leaving the line blank or inventing a name.
    static func ownerKey(from name: String?) -> String {
        guard let first = (name ?? "").split(separator: " ").first, !first.isEmpty else { return "owner" }
        let key = String(first).lowercased().map { c -> Character in
            ("a"..."z").contains(String(c)) ? c : "-"
        }
        // (v0.9.6) A name with no plain letter in it at all, a name written in
        // Arabic for one, left nothing but hyphens, so every such owner's report
        // had the same name. It is filed under `owner` instead, as a wiki that
        // names nobody is; the report's own `vault_owner:` line still carries
        // the name exactly as the owner wrote it.
        return key.contains(where: { ("a"..."z").contains(String($0)) }) ? String(key) : "owner"
    }

    static func reportName(ownerKey: String, on date: Date = Date()) -> String {
        "clinic-report-\(ownerKey)-\(stamp(for: date)).md"
    }

    /// A report already there is never written over. The number goes before the
    /// ending, the way the check-up's own `--report` numbers a second report of
    /// the same day, so every one of them still begins `clinic-report-` and the
    /// owner can find it by the name they were told to look for.
    static func freeReport(in folder: URL, named name: String) -> URL {
        let fm = FileManager.default
        let stem = name.hasSuffix(".md") ? String(name.dropLast(3)) : name
        var url = folder.appendingPathComponent(name)
        var n = 2
        while fm.fileExists(atPath: url.path) {
            url = folder.appendingPathComponent("\(stem)-\(n).md")
            n += 1
        }
        return url
    }

    // MARK: - the loose ends the app can measure itself

    /// One of Moblee's own clinic files still sitting in `raw/`. These names are
    /// Moblee's, not the owner's, so the note reports them as they are.
    struct ClinicFile: Equatable {
        var name: String
        var status: String      // the first word of its `status:` line, or "no status line"
    }

    /// The measurements of the clinic note's Sections 3 and 4 that the app can
    /// take: counts, dates and Moblee's own file names, and never one word from
    /// inside a page. Everything else the note asks for is said in the report to
    /// be missing rather than guessed at.
    ///
    /// Nothing here reads what an owner has written. The two dates are pulled out
    /// of a heading by a pattern that can match nothing but a date, and the
    /// counts are of directory entries.
    struct LooseEnds: Equatable {
        var waitingInRaw: Int = 0
        var waitingInClippings: Int = 0
        var placeholders: Int = 0            // files iCloud has moved off this Mac
        var clinicFiles: [ClinicFile] = []
        var coreFilesMissing: [String] = []
        var lastLogEntry: String?
        var contextRefreshed: String?
        var healthChecks: Int = 0
        var newestHealthCheck: String?
        var wikiPages: Int = 0
        var sourcesProcessed: Int = 0
        var jobs: [String] = []
        /// The wiki's history. Nil throughout when it was not read, with
        /// `historyWhy` saying why, so a blank is never taken for a zero.
        var uncommitted: Int?
        var lastSaved: String?
        var saves: Int?
        var historyWhy: String?
    }

    nonisolated static let coreFiles = ["wiki/Identity.md", "wiki/_context.md",
                                        "wiki/Index.md", "wiki/log.md"]

    /// Reads folders and two dates, and runs the wiki's history tool three times
    /// read-only. Never on the main thread: it walks the whole of `wiki/`.
    nonisolated static func looseEnds(vault: URL, home: URL, toolsInstalled: Bool) -> LooseEnds {
        let fm = FileManager.default
        var ends = LooseEnds()

        /// The clinic note's own rule for what is "waiting": the files at the top
        /// of an inbox, leaving out hidden ones and Moblee's own clinic files.
        /// Moblee's `HOW-TO-ADD-CONTENT.md` is counted, because the note counts
        /// it, and the report says so, so that this number can be compared with
        /// the numbers earlier rounds reported.
        func waiting(_ folder: String) -> Int {
            let names = (try? fm.contentsOfDirectory(atPath: vault.appendingPathComponent(folder).path)) ?? []
            return names.filter { name in
                if name.hasPrefix(".") || name.hasPrefix("clinic-") { return false }
                var isFolder: ObjCBool = false
                let there = fm.fileExists(atPath: vault.appendingPathComponent("\(folder)/\(name)").path,
                                          isDirectory: &isFolder)
                return there && !isFolder.boolValue
            }.count
        }
        ends.waitingInRaw = waiting("raw")
        ends.waitingInClippings = waiting("Clippings")

        // Clinic NOTES left in raw/, and the status each carries, which is how an
        // unstamped round shows up.
        //
        // (v0.9.6) Reports are left out, and that matters more each round. A
        // report is named `clinic-report-…`, it is written by this very code, and
        // the companion is told never to move one out of `raw/` — so by round
        // four every report would have listed the three before it as clinic notes
        // with no status line, and the one signal this line exists to give (was
        // the note stamped?) would be buried under Moblee's own output. The
        // report this run is about to write is not there yet either way, because
        // the counting happens first.
        //
        // The WHOLE status is kept, not its first word. The template's real
        // values are `pending-execution`, `EXECUTED <date>` and
        // `PARTIAL <what is left and why>`, and on a PARTIAL the reason is the
        // only part worth reading; taking the first word threw it away and left
        // the bare word "PARTIAL", which says nothing.
        let rawNames = ((try? fm.contentsOfDirectory(atPath: vault.appendingPathComponent("raw").path)) ?? [])
            .filter { $0.hasPrefix("clinic-") && !$0.hasPrefix("clinic-report-") }.sorted()
        for name in rawNames {
            var status = "no status line"
            if name.hasSuffix(".md"),
               let text = try? String(contentsOf: vault.appendingPathComponent("raw/\(name)"), encoding: .utf8) {
                for line in text.split(separator: "\n", omittingEmptySubsequences: false) where line.hasPrefix("status:") {
                    let said = line.dropFirst("status:".count).trimmingCharacters(in: .whitespaces)
                    status = said.isEmpty ? "empty" : said
                    break
                }
            }
            ends.clinicFiles.append(ClinicFile(name: name, status: status))
        }

        ends.coreFilesMissing = coreFiles.filter { !fm.fileExists(atPath: vault.appendingPathComponent($0).path) }
        ends.lastLogEntry = lastLogEntry(in: vault)
        ends.contextRefreshed = contextRefreshed(in: vault)

        let lint = ((try? fm.contentsOfDirectory(atPath: vault.appendingPathComponent("outputs/lint").path)) ?? [])
            .filter { !$0.hasPrefix(".") }.sorted()
        ends.healthChecks = lint.count
        ends.newestHealthCheck = lint.last.flatMap { firstDate(in: $0) }

        // Every page in the wiki, and everything already taken in, as counts.
        var pages = 0
        if let walk = fm.enumerator(at: vault.appendingPathComponent("wiki"),
                                    includingPropertiesForKeys: nil) {
            for case let url as URL in walk where url.pathExtension == "md" { pages += 1 }
        }
        ends.wikiPages = pages
        var processed = 0
        for folder in ["raw/processed", "Clippings/processed"] {
            if let walk = fm.enumerator(at: vault.appendingPathComponent(folder), includingPropertiesForKeys: nil) {
                for case let url as URL in walk {
                    var isFolder: ObjCBool = false
                    if fm.fileExists(atPath: url.path, isDirectory: &isFolder), !isFolder.boolValue { processed += 1 }
                }
            }
        }
        ends.sourcesProcessed = processed

        // Files iCloud has moved off this Mac leave a marker behind, and a wiki
        // half on a Mac reads as a wiki half missing.
        var placeholders = 0
        for folder in ["raw", "Clippings", "wiki"] {
            if let walk = fm.enumerator(at: vault.appendingPathComponent(folder), includingPropertiesForKeys: nil) {
                for case let url as URL in walk
                where url.lastPathComponent.hasPrefix(".") && url.lastPathComponent.hasSuffix(".icloud") {
                    placeholders += 1
                }
            }
        }
        ends.placeholders = placeholders

        ends.jobs = ((try? fm.contentsOfDirectory(atPath: home.appendingPathComponent("Library/LaunchAgents").path)) ?? [])
            .filter { $0.lowercased().contains("moblee") }.sorted()

        // The wiki's history, read and never written. Apple's tools are looked
        // for first, because `/usr/bin/git` on a Mac without them is a stand-in
        // that pops up Apple's install window — the very window the clinic note
        // tells owners to cancel. A check-up must not be the thing that opens it.
        if !toolsInstalled {
            ends.historyWhy = "Apple's tools are not on this Mac, so the wiki's history was not read"
        } else if let count = gitLines(["-C", vault.path, "status", "--porcelain"], home: home) {
            ends.uncommitted = count.lines
            ends.lastSaved = gitLines(["-C", vault.path, "log", "-1", "--format=%cd", "--date=short"],
                                      home: home).flatMap { firstDate(in: $0.text) }
            ends.saves = gitLines(["-C", vault.path, "rev-list", "--count", "HEAD"], home: home)
                .flatMap { Int($0.text.trimmingCharacters(in: .whitespacesAndNewlines)) }
        } else {
            ends.historyWhy = "this wiki keeps no history (git), so nothing was read from one"
        }
        return ends
    }

    /// The date on the last entry in the log, and nothing else from the log. The
    /// pattern can match a date and nothing else, so no words of the owner's can
    /// come out of this.
    nonisolated static func lastLogEntry(in vault: URL) -> String? {
        guard let text = try? String(contentsOf: vault.appendingPathComponent("wiki/log.md"), encoding: .utf8)
        else { return nil }
        var found: String?
        for line in text.split(separator: "\n", omittingEmptySubsequences: false) where line.hasPrefix("## [") {
            if let date = firstDate(in: String(line)) { found = date }
        }
        return found
    }

    /// When `_context.md` says it was last refreshed. Only the date is taken.
    nonisolated static func contextRefreshed(in vault: URL) -> String? {
        guard let text = try? String(contentsOf: vault.appendingPathComponent("wiki/_context.md"), encoding: .utf8)
        else { return nil }
        for line in text.split(separator: "\n", omittingEmptySubsequences: false) where line.contains("Last refreshed") {
            return firstDate(in: String(line)) ?? "a date Moblee could not read"
        }
        return nil
    }

    /// The first `YYYY-MM-DD` in a piece of text, or nothing.
    nonisolated static func firstDate(in text: String) -> String? {
        let digits = Array(text)
        guard digits.count >= 10 else { return nil }
        for start in 0...(digits.count - 10) {
            let window = digits[start..<(start + 10)]
            let shape = window.map { $0.isNumber ? "9" : String($0) }.joined()
            if shape == "9999-99-99" { return String(window) }
        }
        return nil
    }

    /// One read-only run of the wiki's history tool. Nothing it prints reaches
    /// the report except a count of its lines or a date, so a path or a page name
    /// in its output can never be sent on.
    nonisolated private static func gitLines(_ args: [String], home: URL) -> (lines: Int, text: String)? {
        let p = Process()
        p.executableURL = URL(fileURLWithPath: "/usr/bin/git")
        p.arguments = args
        p.environment = EngineTask.environment(home: home)
        p.standardInput = FileHandle.nullDevice
        let out = Pipe()
        p.standardOutput = out
        p.standardError = Pipe()
        do { try p.run() } catch { return nil }
        let data = out.fileHandleForReading.readDataToEndOfFile()
        p.waitUntilExit()
        guard p.terminationStatus == 0 else { return nil }
        let text = String(data: data, encoding: .utf8) ?? ""
        let lines = text.split(separator: "\n").filter { !$0.isEmpty }.count
        return (lines, text)
    }

    // MARK: - where the wiki lives, as a kind of place and never as a path

    /// The clinic note asks for the KIND of place only: the Desktop folder, the
    /// Documents folder, iCloud Drive, or somewhere else. The path itself is
    /// never written, here or anywhere in the report.
    ///
    /// Read from the path as the owner's Mac names it, not from a resolved one.
    /// With Desktop & Documents sync switched on, `~/Desktop` IS a link into
    /// iCloud, so a resolved path stops beginning with Desktop on exactly the
    /// Macs where the answer matters; the check-up learned that the hard way
    /// (v0.9.2, `VAULT_AS_NAMED`). Whether iCloud really copies the folder is a
    /// question this cannot answer, and the check-up's own findings do, so this
    /// says the folder and leaves the verdict to them.
    static func kindOfPlace(vault: URL, home: URL) -> String {
        let path = vault.path
        if path.contains("Mobile Documents") { return "iCloud Drive" }
        for (folder, said) in [("Desktop", "the Desktop folder"), ("Documents", "the Documents folder"),
                               ("Downloads", "the Downloads folder")] {
            if path.hasPrefix(home.appendingPathComponent(folder).path + "/") { return said }
        }
        if path.hasPrefix(home.path + "/") { return "the home folder, outside Desktop and Documents" }
        return "somewhere else on this Mac"
    }

    // MARK: - the report

    /// Everything the report carries that does not come out of the card.
    struct Facts {
        var owner: String?
        var wikiVersion: String
        var packVersion: String
        var appVersion: String
        /// The word on record in `~/.config/moblee/assistant`, or nil for no file.
        var assistantOnRecord: String?
        var place: String
        var ends: LooseEnds
        var today: Date
    }

    private static let day: DateFormatter = {
        let f = DateFormatter()
        f.dateFormat = "yyyy-MM-dd"
        f.locale = Locale(identifier: "en_GB_POSIX")
        return f
    }()

    /// The report, in the clinic note's own frontmatter and its own seven
    /// sections, in that order.
    ///
    /// Where the app cannot supply what an assistant would have supplied, the
    /// section says so in plain words. The owner's two answers are the big one:
    /// the app asks nobody anything, so there are none, and a report that made
    /// them up or left the heading bare would be worse than one that says it.
    /// `note_status` is therefore always PARTIAL, with what is missing named,
    /// which is what the note asks for when a section cannot be completed.
    static func report(card: Card?, trouble: Trouble?, facts: Facts) -> String {
        var out: [String] = []
        let key = ownerKey(from: facts.owner)
        let today = day.string(from: facts.today)
        let missing = partlyDone(card: card, trouble: trouble)

        out += ["---",
                "date: \(today)",
                "type: Moblee clinic report",
                "round: \(round)",
                "vault_owner: " + (facts.owner ?? "not named in this wiki's rules file; filed under \"\(key)\""),
                "executed_by: the Moblee app \(facts.appVersion), from its own button (no assistant was involved)",
                "pack_version_found: \(facts.packVersion.isEmpty ? "not known" : facts.packVersion)",
                "app_version_found: \(facts.appVersion)",
                "assistant_on_record: " + (facts.assistantOnRecord
                                           ?? "no record on this Mac (the pack treats that as Claude)"),
                "note_status: PARTIAL (\(missing))",
                "do_not_ingest: true",
                "---",
                ""]
        out += ["# Moblee check-up report, \(today)", ""]

        // 1. The summary. Six lines at most, in plain English, for the owner and
        // for whoever looks after Moblee for them. Something to fix is stated here
        // and never fixed: the check-up only reads, and so does this.
        out += ["## 1. Summary", ""]
        out.append("- This wiki belongs to " + (facts.owner ?? "somebody its rules file does not name") + ".")
        if let card {
            out.append("- " + card.headline)
        } else {
            out.append("- The wiki's health was not checked. " + reportLine(for: trouble))
        }
        out.append("- " + versionLine(facts))
        if let n = facts.ends.uncommitted, n > 0 {
            out.append("- " + Self.things(n, "change has", "changes have")
                       + " not been saved into the wiki's history.")
        }
        let waiting = facts.ends.waitingInRaw + facts.ends.waitingInClippings
        if waiting > 0 {
            out.append("- " + Self.things(waiting, "file is", "files are")
                       + " waiting in the inboxes to be taken in.")
        }
        out.append("- Nothing here has been fixed. Anything that needs attention is stated, not mended.")
        out.append("")

        // 2. The owner's answers, which the app cannot ask for.
        out += ["## 2. The owner's answers", "",
                "None. The clinic note asks the owner two questions in their own words, and "
                + "this check-up was run from a button in the Moblee app, which asks nobody "
                + "anything. Nothing has been put here in their place.", "",
                "To add them, the owner can say to their assistant: \"add my answers to the "
                + "clinic report in raw\".", ""]

        // 3. The note's Section 1.
        out += ["## 3. Versions and the assistant", "",
                "- The wiki is on version " + (facts.wikiVersion.isEmpty ? "(no VERSION file)" : facts.wikiVersion) + ".",
                "- The Moblee folder this Mac uses is version "
                + (facts.packVersion.isEmpty ? "not known" : facts.packVersion) + ".",
                "- The Moblee app that ran this is version \(facts.appVersion).",
                "- The assistant on record is " + (facts.assistantOnRecord
                                                   ?? "not recorded on this Mac (treated as Claude)") + ".",
                "- Which assistant ran this: none. The app ran the check-up itself.", ""]

        // 4. The note's Section 2: the check-up's own output. The card is the
        // redacted whole of what a program can be given, and it is copied in as
        // the check-up printed it.
        out += ["## 4. The check-up", ""]
        if let card {
            out += ["The pack's own read-only check-up was run as "
                    + "`moblee-doctor.py --vault <wiki> --card --json`. Its health card, "
                    + "exactly as it printed it:", "", "```"]
            out += card.lines
            out += ["```", ""]
            // Where the pack hands over every finding, the report carries every
            // finding, which is what an assistant carrying the note by hand
            // would have pasted in. Where it does not, the report says what is
            // missing and why, and never pretends the card is the whole of it.
            if card.findings.isEmpty {
                if card.wrongTotal > card.wrong.count || card.uncheckedTotal > card.unchecked.count {
                    out += ["The card holds one screen, so it does not list every finding: "
                            + "\(Self.things(card.wrongTotal)) \(card.wrongTotal == 1 ? "was" : "were") found wrong and \(card.uncheckedTotal) "
                            + "could not be checked. The whole list is on the owner's Mac; their "
                            + "assistant can print it with the check-up itself.", ""]
                }
                out += ["The lines that were found to be right are not on the card, which shows "
                        + "what needs attention. That is the one thing this report cannot give "
                        + "that an assistant carrying the note by hand would have pasted in whole.", ""]
            } else {
                out += ["And every line it found, in the order it found them:", ""]
                out += card.findings.map {
                    "- **\($0.level)** \($0.line)"
                        + ($0.code.isEmpty || $0.level == "OK" ? "" : " (field guide \($0.code))")
                }
                out.append("")
            }
        } else {
            out += [reportLine(for: trouble), "",
                    "No verdict is given on this wiki's health, because none was reached.", ""]
        }

        // 5. The note's Section 3.
        out += ["## 5. Loose ends", ""]
        out.append("- Waiting in `raw/`: \(facts.ends.waitingInRaw). Counted the way the clinic "
                   + "note counts it, so Moblee's own HOW-TO-ADD-CONTENT.md is in that number, "
                   + "and this report itself is not (it is written after the count). Anything "
                   + "whose name begins `clinic-` is left out, clinic notes and reports alike — "
                   + "which also means a file of the owner's own with that name would not be "
                   + "counted. Kept this way on purpose, so the number can be read beside the "
                   + "ones earlier rounds reported.")
        out.append("- Waiting in `Clippings/`: \(facts.ends.waitingInClippings).")
        out.append("- Files iCloud has moved off this Mac: \(facts.ends.placeholders).")
        if facts.ends.clinicFiles.isEmpty {
            out.append("- Moblee's own clinic files still in `raw/`: none.")
        } else {
            out.append("- Moblee's own clinic files still in `raw/`:")
            for f in facts.ends.clinicFiles { out.append("  - `\(f.name)`: status \(f.status)") }
        }
        if let why = facts.ends.historyWhy {
            out.append("- Work not yet saved into the wiki's history: not measured, because \(why).")
        } else {
            out.append("- Work not yet saved into the wiki's history: "
                       + Self.things(facts.ends.uncommitted ?? 0, "change", "changes") + ".")
            out.append("- The wiki was last saved on " + (facts.ends.lastSaved ?? "a date Moblee could not read") + ".")
        }
        out.append("- The last entry in the log is dated " + (facts.ends.lastLogEntry ?? "no entry Moblee could find") + ".")
        out.append("- `_context.md` was last refreshed " + (facts.ends.contextRefreshed ?? "on no date Moblee could find") + ".")
        out.append("- Health checks written by the weekly check: \(facts.ends.healthChecks)"
                   + (facts.ends.newestHealthCheck.map { ", the newest dated \($0)" } ?? "") + ".")
        out.append("- Moblee jobs scheduled on this Mac: "
                   + (facts.ends.jobs.isEmpty ? "none" : facts.ends.jobs.joined(separator: ", ")) + ".")
        out.append("- The files every Moblee wiki should have: "
                   + (facts.ends.coreFilesMissing.isEmpty
                      ? "all four are there"
                      : "missing " + facts.ends.coreFilesMissing.joined(separator: ", ")) + ".")
        out += ["", "Two of the note's measurements are not here. Whether the weekly check is "
                + "scheduled is answered by the job list above; whether each clinic note was "
                + "stamped is answered by the status beside each file above.", ""]

        // 6. The note's Section 4.
        out += ["## 6. Counts, and where the wiki lives", "",
                "- Pages in the wiki: \(facts.ends.wikiPages).",
                "- Sources already taken in: \(facts.ends.sourcesProcessed).",
                "- Saves in the wiki's history: " + (facts.ends.saves.map { "\($0)" } ?? "not measured") + ".",
                "- The wiki lives in \(facts.place). Whether iCloud copies it is in the "
                + "check-up's own findings above, which can see that where a folder's name cannot.",
                "- The log by kind and by month, and the Mac's own version and chip, are not "
                + "here: the app does not read the log's entries, and the Mac's details are in "
                + "the check-up's findings above.", ""]

        // 7. Where the note was wrong. This report's own honest answer, which is
        // that the note assumes an assistant is carrying it out.
        out += ["## 7. Where the note was wrong about this wiki", "",
                "The note is written for an assistant carrying it out by hand, and this round "
                + "was run by the Moblee app instead. So: nobody was asked the two questions "
                + "in Section 0; no commands were run in the wiki beyond the read-only "
                + "check-up and three read-only reads of its history; nothing was committed; "
                + "and this note was neither stamped nor moved, because there was no note in "
                + "`raw/` to stamp. Everything else above is what was actually found.", ""]

        return out.joined(separator: "\n") + "\n"
    }

    /// What `note_status` says is left undone, in the note's own spirit: the
    /// reason, not a bare word.
    static func partlyDone(card: Card?, trouble: Trouble?) -> String {
        card == nil
            ? "the owner was not asked the two questions, and the wiki's health was not checked"
            : "the owner was not asked the two questions, which the app cannot do"
    }

    /// How the report says the check-up said nothing. The clinic note names three
    /// of these outright, and they are written here in its own words so that a
    /// report can be read beside one an assistant wrote.
    static func reportLine(for trouble: Trouble?) -> String {
        switch trouble {
        case .noCheckup:
            return "health not checked: no check-up on this Mac (this Moblee could not find "
                + "`scripts/moblee-doctor.py` in the Moblee folder it is using)."
        case .didNotFinish(let code):
            return "health not checked: the check-up stopped with an error (it ended with code "
                + "\(code)). Its output is not copied here, because nothing outside the "
                + "check-up's own redaction may go into a report."
        case .refusedByGuard:
            return "REFUSED BY GUARD: this Mac's delete guard refused the check-up, so it "
                + "never ran. Nothing was looked for a way round."
        case .tookTooLong:
            return "health not checked: the check-up was still running after "
                + "\(Int(timeLimit)) seconds, so Moblee stopped it."
        case nil:
            return "health not checked."
        }
    }

    private static func versionLine(_ facts: Facts) -> String {
        guard !facts.wikiVersion.isEmpty, !facts.packVersion.isEmpty else {
            return "The wiki is on version "
                + (facts.wikiVersion.isEmpty ? "an unknown one (no VERSION file)" : facts.wikiVersion) + "."
        }
        if HomeModel.isNewer(facts.packVersion, than: facts.wikiVersion) {
            return "The wiki is on \(facts.wikiVersion) and has not yet been updated to "
                + "\(facts.packVersion), which this Mac has."
        }
        return "The wiki is on \(facts.wikiVersion), which is the version this Mac carries."
    }

    // MARK: - what the owner is told

    /// The sentence at the top of the screen, for every way the check-up can
    /// end. Plain words, no technical message, and never a silent failure: each
    /// one says what happened, whether anything changed, and what to do.
    /// Static, so every one of them can be read back in a check.
    static func sentence(for state: State) -> String {
        switch state {
        case .idle, .running:
            return "Checking your wiki. Nothing in it is changed."
        case .finished(let done):
            let where_ = done.savedAs == nil
                ? "The report could not be saved, so photograph this screen and send the photograph."
                : "The report is saved in your wiki's raw folder."
            switch done.card.state {
            case "healthy":
                return "Your wiki looks healthy. " + where_
            case "unchecked":
                return "Nothing looks wrong, but \(Self.things(done.card.uncheckedTotal)) could not be "
                    + "checked. " + where_
            default:
                return "Your wiki needs attention: \(Self.things(done.card.wrongTotal)) to look at. " + where_
            }
        case .noWiki:
            return "Moblee has not made your wiki yet, so there is nothing to check."
        case .couldNotCheck(let trouble, let savedAs):
            let kept = savedAs == nil ? "" : " A note is saved in your raw folder: "
                + "send it to whoever looks after Moblee for you."
            switch trouble {
            case .noCheckup:
                return "This Moblee cannot find its own check-up, so your wiki was not checked. "
                    + "Nothing has changed." + kept
            case .didNotFinish:
                return "The check-up did not finish, so your wiki was not checked. Nothing has "
                    + "changed." + kept
            case .refusedByGuard:
                // (v0.9.6) Kept short enough for three lines at the biggest text
                // size with the line about the note after it, as every sentence
                // on this screen now is; a longer one was cut off mid-word.
                return "Your Mac's safety guard stopped the check-up, so your wiki was not "
                    + "checked. Nothing has changed." + kept
            case .tookTooLong:
                return "The check-up took too long, so Moblee stopped it. Nothing has "
                    + "changed; try again later." + kept
            }
        }
    }

    /// `1 thing`, `4 things`. The same choice the check-up's own card makes (see
    /// `things` in `moblee-doctor.py`), for the same reason: the owner reading
    /// this screen is somebody who does not read much, and `4 thing(s)` is a
    /// programmer's shortcut for not choosing, which asks them to choose
    /// instead. The pack's rules file tells every assistant to use plain words.
    static func things(_ n: Int, _ one: String = "thing", _ many: String = "things") -> String {
        "\(n) \(n == 1 ? one : many)"
    }

    /// The small line under the card: what to do with the file. Nobody is named:
    /// Moblee is a public product and the person who looks after it differs.
    static let sendIt = "Send that file to whoever looks after Moblee for you."

    /// The quiet words under the big button, where there are any. Only a saved
    /// report has somewhere to go.
    static func quietWords(for state: State) -> String? {
        switch state {
        case .finished(let done): return done.savedAs == nil ? nil : "Show me the file"
        case .couldNotCheck(_, let savedAs): return savedAs == nil ? nil : "Show me the file"
        default: return nil
        }
    }

    /// Whether the big button can be pressed. A check-up still running has
    /// nothing to say yet, so Done waits for it.
    static func canGoOn(_ state: State) -> Bool {
        switch state {
        case .idle, .running: return false
        default: return true
        }
    }

    // MARK: - running it

    private var home: URL = FileManager.default.homeDirectoryForCurrentUser
    private var vault: URL?

    /// One press. Everything from here on happens without the owner being asked
    /// anything: no command typed, no permission prompt, no sentence to say.
    ///
    /// `limit` is only ever given by the windowless check, which proves the time
    /// limit against a stand-in check-up that never ends. An owner always gets
    /// `Clinic.timeLimit`.
    func begin(home: URL, vault: URL?, pack: URL?, wikiVersion: String, packVersion: String,
               limit: TimeInterval = Clinic.timeLimit) {
        guard state == .idle else { return }
        self.home = home
        self.vault = vault
        state = .running
        guard let vault else { state = .noWiki; return }
        rawFolder = vault.appendingPathComponent("raw", isDirectory: true)
        Diary.write("--- Moblee check-up ---", home: home, vault: vault)
        Diary.write("check-up: started; wiki version \(wikiVersion.isEmpty ? "unknown" : wikiVersion), "
                    + "pack version \(packVersion.isEmpty ? "unknown" : packVersion)",
                    home: home, vault: vault)

        let doctor = pack?.appendingPathComponent("scripts/moblee-doctor.py")
        guard let doctor, FileManager.default.isReadableFile(atPath: doctor.path) else {
            finish(card: nil, trouble: .noCheckup, wikiVersion: wikiVersion, packVersion: packVersion)
            return
        }
        Self.runCheckup(doctor: doctor, vault: vault, home: home, limit: limit) { [weak self] result in
            guard let self else { return }
            switch result {
            case .card(let card):
                self.finish(card: card, trouble: nil, wikiVersion: wikiVersion, packVersion: packVersion)
            case .trouble(let trouble):
                self.finish(card: nil, trouble: trouble, wikiVersion: wikiVersion, packVersion: packVersion)
            }
        }
    }

    enum Result { case card(Card); case trouble(Trouble) }

    /// The check-up as a program, with a time limit on it.
    ///
    /// Both of its streams are read together into one, for two reasons: a
    /// refusal by the delete guard is written to the error stream and would
    /// otherwise never be seen, and an error stream nobody reads can fill up and
    /// stop the program it belongs to. The card is then found inside whatever
    /// came out (see `Card.read`), so a stray line cannot make the findings
    /// unreadable.
    nonisolated static func runCheckup(doctor: URL, vault: URL, home: URL,
                                       limit: TimeInterval = Clinic.timeLimit,
                                       then: @escaping @MainActor (Result) -> Void) {
        DispatchQueue.global(qos: .userInitiated).async {
            let p = Process()
            p.executableURL = URL(fileURLWithPath: "/usr/bin/python3")
            // Nothing from inside the wiki reaches this line. The only thing that
            // varies is the wiki's own place, which the app holds itself.
            p.arguments = [doctor.path, "--vault", vault.path, "--card", "--json"]
            p.environment = EngineTask.environment(home: home)
            p.standardInput = FileHandle.nullDevice
            let out = Pipe()
            p.standardOutput = out
            p.standardError = out
            func hand(_ r: Result) { DispatchQueue.main.async { MainActor.assumeIsolated { then(r) } } }
            do { try p.run() } catch { hand(.trouble(.noCheckup)); return }
            let stopped = Stopwatch()
            let killer = DispatchWorkItem {
                guard p.isRunning else { return }
                stopped.mark()
                p.terminate()
            }
            DispatchQueue.global(qos: .utility).asyncAfter(deadline: .now() + limit, execute: killer)
            let data = out.fileHandleForReading.readDataToEndOfFile()
            p.waitUntilExit()
            killer.cancel()
            if stopped.marked { hand(.trouble(.tookTooLong)); return }
            let text = String(data: data, encoding: .utf8) ?? ""
            // The guard's own words, as `BLOCK_MSG` in safety/bash-guard.py writes
            // them. An app running the check-up itself is not what the guard
            // watches, so this is not expected to happen; it is here so that if it
            // ever does the owner is told the truth rather than "did not finish".
            if text.contains("Blocked by the vault safety gate") {
                hand(.trouble(.refusedByGuard)); return
            }
            guard p.terminationStatus == 0, let card = Card.read(text) else {
                hand(.trouble(.didNotFinish(code: p.terminationStatus))); return
            }
            hand(.card(card))
        }
    }

    /// One flag, set on one thread and read on another: whether the time limit
    /// was the thing that ended the check-up.
    final class Stopwatch: @unchecked Sendable {
        private let lock = NSLock()
        private var stopped = false
        func mark() { lock.lock(); stopped = true; lock.unlock() }
        var marked: Bool { lock.lock(); defer { lock.unlock() }; return stopped }
    }

    /// The measurements, the report, the diary line and the Finder window.
    private func finish(card: Card?, trouble: Trouble?, wikiVersion: String, packVersion: String) {
        guard let vault, let rawFolder else { state = .noWiki; return }
        let home = self.home
        let appVersion = Self.appVersion
        DispatchQueue.global(qos: .userInitiated).async {
            let tools = Checkup.developerToolsInstalled()
            let ends = Self.looseEnds(vault: vault, home: home, toolsInstalled: tools)
            DispatchQueue.main.async {
                MainActor.assumeIsolated {
                    let facts = Facts(owner: Self.ownerName(inWiki: vault),
                                      wikiVersion: wikiVersion, packVersion: packVersion,
                                      appVersion: appVersion,
                                      assistantOnRecord: Assistant.stored(home: home)?.rawValue,
                                      place: Self.kindOfPlace(vault: vault, home: home),
                                      ends: ends, today: Date())
                    let body = Self.report(card: card, trouble: trouble, facts: facts)
                    let name = Self.reportName(ownerKey: Self.ownerKey(from: facts.owner), on: facts.today)
                    var savedAs: String?
                    let url = Self.freeReport(in: rawFolder, named: name)
                    do {
                        try FileManager.default.createDirectory(at: rawFolder, withIntermediateDirectories: true)
                        try body.write(to: url, atomically: true, encoding: .utf8)
                        savedAs = url.lastPathComponent
                        self.reportURL = url
                    } catch {
                        savedAs = nil
                    }
                    Diary.write("check-up: " + (card.map { "the wiki is \($0.state); "
                                                    + "\(Self.things($0.wrongTotal)) wrong, "
                                                    + "\($0.uncheckedTotal) not checked" }
                                                ?? "the wiki's health was not checked"),
                                home: home, vault: vault)
                    Diary.write("check-up: " + (savedAs == nil
                                                ? "the report could not be saved"
                                                : "report written into the wiki's raw folder"),
                                home: home, vault: vault)
                    if let card {
                        self.state = .finished(Finished(card: card, savedAs: savedAs))
                    } else {
                        self.state = .couldNotCheck(trouble ?? .didNotFinish(code: -1), savedAs: savedAs)
                    }
                    // (v0.9.6) Finder is no longer opened by itself here. It came
                    // up over the card the owner had just waited for, so the first
                    // thing they saw was a Finder window. "Show me the file" under
                    // the card opens it, with the report picked out, when they ask.
                }
            }
        }
    }

    /// The app's own version, which the report names as what ran the check-up.
    static var appVersion: String {
        (Bundle.main.infoDictionary?["CFBundleShortVersionString"] as? String) ?? "unknown"
    }

    /// Opens the wiki's `raw` folder with the report picked out. A practice run
    /// opens nothing, as every other practice run does.
    func showTheFile() {
        guard home == FileManager.default.homeDirectoryForCurrentUser else { return }
        if let reportURL {
            NSWorkspace.shared.selectFile(reportURL.path, inFileViewerRootedAtPath: reportURL.deletingLastPathComponent().path)
        } else if let rawFolder {
            NSWorkspace.shared.open(rawFolder)
        }
    }

    /// Set aside for a fresh run: pressing the button again starts a new
    /// check-up rather than showing the last one's answer.
    func forget() {
        state = .idle
        reportURL = nil
        rawFolder = nil
    }
}
