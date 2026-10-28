import SwiftUI
import AppKit

/// (0.14.0) What the pack's parts report says: `moblee-setup.py --parts`. The
/// parts every Moblee wiki comes with, each in place or not, and what the
/// checklist's own record last saw of each extra.
struct Parts: Equatable {
    struct Part: Identifiable, Equatable {
        let key: String
        let title: String
        let what: String
        let say: String
        let open: String
        let state: String          // in, missing, differs, unseen
        var id: String { key }
        var inPlace: Bool { state == "in" }
    }

    var assistant: String
    var checked: String?
    var core: [Part]
    var extras: [String: String]   // on, off, unseen, unknown

    /// The report, or nil when it is not the shape expected. A part or an extra
    /// that is not plain words is left out rather than drawn wrong.
    static func parse(_ data: Data) -> Parts? {
        guard let o = (try? JSONSerialization.jsonObject(with: data)) as? [String: Any],
              let core = o["core"] as? [[String: Any]], let extras = o["extras"] as? [String: Any] else { return nil }
        let parts = core.compactMap { p -> Part? in
            guard let key = p["key"] as? String, let title = p["title"] as? String,
                  // (0.16.0) "unreadable": a settings file that will not parse, so nobody can tell.
                  let state = p["state"] as? String, ["in", "missing", "differs", "unseen", "unreadable"].contains(state) else { return nil }
            return Part(key: key, title: title, what: p["what"] as? String ?? "", say: p["say"] as? String ?? "",
                        open: p["open"] as? String ?? "", state: state)
        }
        return Parts(assistant: o["assistant"] as? String ?? "claude",
                     checked: o["checked"] as? String,
                     core: parts,
                     extras: extras.compactMapValues { $0 as? String })
    }

    var missing: [Part] { core.filter { !$0.inPlace } }

    /// (0.16.0) The parts that need the owner: missing, or read from a file
    /// nobody can read. "differs" (an older or changed copy) and "unseen"
    /// (ChatGPT's hooks, which no file can show running) are not faults and
    /// stay quiet words on their rows, as in 0.15.2; the pack reports every
    /// ChatGPT hook as unseen, so counting them warned those owners for ever.
    var faults: [Part] { core.filter { Self.isFault($0.state) } }
    static func isFault(_ state: String) -> Bool { state == "missing" || state == "unreadable" }
}

/// (0.16.0) Which part of Add more is showing.
enum AddMoreSection: Hashable {
    case forYou
    case group(String)
    case inWiki
}

/// (0.14.0) Opening the two things a wiki carries that are pages in the browser.
@MainActor
enum AddMore {
    static let wayIn = "Add more"
    static let sentence = "Everything your wiki can have."
    static let updateWayIn = "See what else you can add"
    static let lookAgain = "Look again"
    static let comesWith = "Comes with every Moblee wiki"

    /// (0.16.0) The names on the left of Add more, and what each page says
    /// under its title.
    static let forYouTitle = "For you"
    static let inWikiTitle = "In your wiki"
    static let forYouLead = "Picked by Claude from how you use your wiki. Everything else is in the list on the left."
    static let forYouEmpty = "Claude has not suggested anything yet. Everything you can add is in the list on the left."
    static let inWikiAllIn = "Everything every Moblee wiki comes with is in place."
    static let inWikiLead = "What every Moblee wiki comes with."
    static let lookingNow = "Looking at everything on this Mac. This can take a minute; nothing you have set up is changed."

    /// What a part's state says on its row. (0.16.0: "In place", quietly, where
    /// it was "In your wiki" in green; the page is called In your wiki now.)
    static func partWord(_ part: Parts.Part, newerWiki: Bool = false) -> String {
        switch part.state {
        case "in": return "In place"
        // An older copy, or one the owner or their assistant changed. Not a
        // fault, and not something an update would change, so no button.
        case "differs": return "An older or changed copy"
        // Entered for ChatGPT, which runs it only once trusted.
        case "unseen": return "Moblee cannot see whether ChatGPT runs this"
        case "unreadable": return "Moblee cannot read the settings file to tell"
        default: return newerWiki ? "Missing. A newer Moblee puts it back" : "Missing"
        }
    }

    /// The words on a part's button, or nil for no button: Open for the two
    /// things the app opens, Put back for a part that is missing (the update
    /// puts it back), and nothing while an update could not run.
    static func partButton(_ part: Parts.Part, newerWiki: Bool, busy: Bool) -> String? {
        if part.state == "in" { return part.open.isEmpty ? nil : "Open" }
        if part.state == "missing" && !newerWiki && !busy { return "Put back" }
        return nil
    }

    /// (0.16.0) The one warning on the In your wiki page, naming what is not
    /// in place. Nil when everything is.
    static func banner(_ parts: Parts, newerWiki: Bool) -> String? {
        let off = parts.faults
        guard let first = off.first else { return nil }
        if off.count == 1 {
            switch first.state {
            case "unreadable": return "Moblee cannot read the settings file to tell whether \(first.title.lowercasedFirst) is in place."
            default: return "\(first.title) is missing." + (newerWiki ? " A newer Moblee puts it back." : "")
            }
        }
        return "\(off.count) parts are not as they should be: "
            + off.map(\.title.lowercasedFirst).joined(separator: ", ") + "."
    }

    /// (0.16.0) The banner's one button: Put back, when any part is missing and
    /// the update can put it back (the same rule as each part's own button);
    /// otherwise Check my wiki, when a part could not be read, since the
    /// check-up is what looks at the file and says what is wrong with it.
    static let checkWikiButton = "Check my wiki"
    static func bannerButton(_ parts: Parts, newerWiki: Bool, busy: Bool) -> String? {
        if parts.core.contains(where: { partButton($0, newerWiki: newerWiki, busy: busy) == "Put back" }) { return "Put back" }
        if parts.core.contains(where: { $0.state == "unreadable" }) { return checkWikiButton }
        return nil
    }

    /// (0.16.0) What "In your wiki" says on the left: the count of parts, with
    /// a tick when none needs the owner, or how many of them are as they should be.
    static func inWikiCount(_ parts: Parts?) -> String {
        guard let parts else { return "" }
        let n = parts.core.count
        return parts.faults.isEmpty ? "\(n)" : "\(n - parts.faults.count) of \(n)"
    }

    /// What an extra's state says on its row.
    static func extraWord(_ state: HomeModel.ExtraState) -> String {
        switch state {
        case .on: return "Set up"
        case .off: return "Not set up"
        case .unknown: return "Not looked at yet"
        case .unseen: return "Moblee cannot see whether this is set up"
        case .adding: return "Being added…"
        case .handedOver(let how): return how == .clicks ? "Finish it in Claude, then press Done" : "Finish it in the window that opened"
        case .failed(let why): return why.isEmpty ? "That did not work" : "That did not work: \(why)"
        }
    }

    /// The words on an extra's button, or nil for no button.
    static func extraButton(_ state: HomeModel.ExtraState) -> String? {
        switch state {
        case .off, .unknown: return "Add"
        case .unseen: return "Show me how"
        case .failed: return "Try again"
        case .handedOver(let how): return how == .clicks ? "Done" : "Open it again"
        case .on, .adding: return nil
        }
    }

    /// (0.16.0) The line under a row's title, where the row needs something
    /// done or says something the owner should know: a half-finished add, one
    /// that failed, or one Moblee cannot see. Nil for the rest, which say what
    /// they need to in the one quiet word or button at the end of the row.
    static func extraNote(_ state: HomeModel.ExtraState) -> String? {
        switch state {
        case .handedOver, .failed, .unseen: return extraWord(state)
        default: return nil
        }
    }

    /// What "Say … to Claude" reads like for a part.
    static func sayLine(_ part: Parts.Part, talksTo: String) -> String? {
        part.say.isEmpty ? nil : "Say \u{201C}\(part.say)\u{201D} to \(talksTo)."
    }

    static func buttonId(_ key: String) -> String { "addmore-" + key }
    static func rowId(_ key: String) -> String { "addmore-row-" + key }
    static let putBackId = "addmore-put-back"
    static let lookAgainId = "look-again"
    static func sectionId(_ section: AddMoreSection, index: Int = 0) -> String {
        switch section {
        case .forYou: return "addmore-for-you"
        case .group: return "addmore-group-\(index)"
        case .inWiki: return "addmore-in-wiki"
        }
    }

    /// (0.15.2) Whether Add more should look again by itself on opening: the
    /// checklist has never looked, its record is more than a day old, or an
    /// item is one it has never seen. Until 0.15.2 only the first applied, so
    /// something added another way stayed "Not set up" for good.
    static func needsFreshLook(_ parts: Parts, now: Date) -> Bool {
        if parts.extras.values.contains("unknown") { return true }
        guard let date = stampDate(parts.checked) else { return true }
        return now.timeIntervalSince(date) > 24 * 3600
    }

    /// (0.15.2) A Look again that did not finish: stopped or failed to start
    /// (any exit but 0, or 1 for "something is off"), or one that left the
    /// record's time as it was although something was off or broke.
    static func lookFailed(code: Int32, before: String?, after: String?) -> Bool {
        if code != 0 && code != 1 { return true }
        return code == 1 && after == before
    }

    /// The checklist's stamp as a date. (0.15.2) The pack writes it to the
    /// second (YYYYMMDD-HHMMSS); only the minute form was read before, so no
    /// real stamp was ever understood and "Last looked" never showed.
    static func stampDate(_ stamp: String?) -> Date? {
        guard let stamp, stamp.count == 13 || stamp.count == 15,
              stamp[stamp.index(stamp.startIndex, offsetBy: 8)] == "-" else { return nil }
        let f = DateFormatter()
        f.locale = Locale(identifier: "en_GB_POSIX")
        f.dateFormat = stamp.count == 15 ? "yyyyMMdd-HHmmss" : "yyyyMMdd-HHmm"
        return f.date(from: stamp)
    }

    static let couldNotLook = "Moblee could not look just now, so this is what it saw last time. Press Look again in a minute."

    /// "Looked 26 October, 17:00", from the checklist's own stamp
    /// (YYYYMMDD-HHMMSS, or YYYYMMDD-HHMM); nil for a stamp of any other shape.
    /// (0.16.0) Shorter, for the foot of Add more, where "Look again" follows it.
    static func lastLooked(_ stamp: String?) -> String? {
        guard let date = stampDate(stamp) else { return nil }
        let out = DateFormatter()
        out.locale = Locale(identifier: "en_GB")
        out.dateFormat = "d MMMM, HH:mm"
        return "Looked \(out.string(from: date))"
    }

    /// The whole screen, read aloud: the sentence, then each section in the
    /// words its rows show.
    static func speech(parts: Parts?, groups: [(String, [String])], word: (String) -> String,
                       title: (String) -> String) -> Speech {
        var said = sentence
        if let parts {
            let missing = parts.faults.count
            said += " \(comesWith): \(parts.core.count) parts, "
                + (missing == 0 ? "all in place." : "\(missing) of them not in place.")
            for (group, keys) in groups where !keys.isEmpty {
                let on = keys.filter { word($0) == "Set up" }.count
                said += " \(group): \(on) of \(keys.count) set up."
            }
        } else {
            said += " Looking at your wiki…"
        }
        return Speech(said)
    }

    /// (0.16.0) The page that is showing, read aloud: its title, the line
    /// under it, the warning if there is one, and each row in the words it
    /// shows, its state or its button included.
    static func pageSpeech(title: String, lead: String, banner: String?, rows: [(String, String)]) -> Speech {
        var said = "\(title). \(lead)"
        if let banner { said += " \(banner)" }
        for (name, word) in rows { said += word.isEmpty ? " \(name)." : " \(name): \(word)." }
        return Speech(said)
    }

    /// The galaxy, built afresh and opened, the way the galaxy skill does it.
    static func openGalaxy(vault: URL, home: URL, practice: Bool) {
        guard !practice else { return }
        EngineTask.output(of: "/usr/bin/python3",
                          [vault.appendingPathComponent("scripts/wiki-galaxy/build.py").path],
                          home: home) { code, _ in
            let page = vault.appendingPathComponent("outputs/galaxy/index.html")
            if code == 0, FileManager.default.fileExists(atPath: page.path) { NSWorkspace.shared.open(page) }
        }
    }

    /// The dashboard, started the way its README says, and opened in the
    /// browser. It stops by itself when its tab is closed. A second press while
    /// it is already running opens the same page: the second server cannot take
    /// the port and ends at once.
    static func openDashboard(vault: URL, home: URL, practice: Bool) {
        guard !practice else { return }
        let p = Process()
        p.executableURL = URL(fileURLWithPath: "/usr/bin/python3")
        p.arguments = [vault.appendingPathComponent("dashboard/server.py").path]
        p.currentDirectoryURL = vault
        p.environment = EngineTask.environment(home: home)
        p.standardInput = FileHandle.nullDevice
        p.standardOutput = FileHandle.nullDevice
        p.standardError = FileHandle.nullDevice
        try? p.run()
        DispatchQueue.main.asyncAfter(deadline: .now() + 1.5) {
            if let url = URL(string: "http://127.0.0.1:7373") { NSWorkspace.shared.open(url) }
        }
    }
}

private extension String {
    var lowercasedFirst: String {
        guard let first else { return self }
        return first.lowercased() + dropFirst()
    }
}

/// (0.16.0) Everything a wiki can have, as two panes inside the window.
///
/// On the left, the sections: Claude's own suggestions ("For you"), the
/// checklist's groups in its own order with how many of each are set up, and
/// what every wiki comes with ("In your wiki"). On the right, the one section
/// chosen: a title, one line under it, and one list. A row in a group shows its
/// title and one thing at its end, a small button or a quiet word; pressing the
/// row opens what it is and what adding it takes, in place, one row at a time.
/// Done, at the foot, is the screen's one big action.
///
/// Until 0.16.0 this was one long list of every part and every extra with a
/// line of state words beside each, which an owner had to read all of to find
/// the one thing that needed them.
struct AddMoreScreen: View {
    @EnvironmentObject var flow: Flow
    @EnvironmentObject var home: HomeModel
    @Environment(\.stillPicture) private var still
    @ObservedObject private var textSize = TextSize.shared
    @ObservedObject private var speaker = Speaker.shared

    /// The checklist's groups, in its own order, each with its items.
    private var groups: [(String, [String])] {
        var order: [String] = []
        var keys: [String: [String]] = [:]
        for key in home.catalogueOrder where home.itemTile(key, why: "") != nil {
            let g = home.itemGroup(key)
            if keys[g] == nil { order.append(g) }
            keys[g, default: []].append(key)
        }
        return order.map { ($0, keys[$0] ?? []) }
    }

    private var claudeExtras: Bool { home.assistant != .chatgpt }

    /// The section showing. A group the list no longer has (or a ChatGPT owner,
    /// who has none) falls back to For you.
    private var section: AddMoreSection {
        // A wiki for ChatGPT alone has only what it comes with.
        guard claudeExtras else { return .inWiki }
        if case .group(let g) = home.addMoreSection, !groups.contains(where: { $0.0 == g }) {
            return .forYou
        }
        return home.addMoreSection
    }

    private var busy: Bool { home.lookingAgain || home.somethingRunning || AppDelegate.busyWithWork }

    var body: some View {
        HStack(spacing: 0) {
            // At the biggest size the groups' names take two lines each, so the
            // left scrolls in the window (and is cut off at the foot in a
            // picture file) rather than push the window taller.
            Group {
                if still {
                    Color.clear.frame(maxWidth: .infinity, maxHeight: .infinity)
                        .overlay(alignment: .top) { sidebar.fixedSize(horizontal: false, vertical: true) }
                        .clipped()
                } else {
                    ScrollView { sidebar }
                }
            }
                .frame(width: Theme.pt(240))
                .frame(maxHeight: .infinity, alignment: .top)
                .background(Theme.card.opacity(0.35))
            Rectangle().fill(Theme.cardEdge).frame(width: 1)
            VStack(alignment: .leading, spacing: 0) {
                page
                    .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
                foot
            }
            .padding(.horizontal, Theme.pt(24))
            .padding(.top, Theme.pt(14))
            .padding(.bottom, Theme.pt(14))
        }
        .onAppear { if !still { home.loadParts() } }
        .onDisappear { speaker.stop() }
    }

    // MARK: the left

    private var sidebar: some View {
        VStack(alignment: .leading, spacing: Theme.pt(2)) {
            if claudeExtras {
                sideItem(.forYou, AddMore.forYouTitle, count: forYouCount)
                separator
                ForEach(Array(groups.enumerated()), id: \.element.0) { index, group in
                    sideItem(.group(group.0), group.0, count: groupCount(group.1), index: index + 1)
                }
                if home.assistant == .both { sideNote(HomeScreen.claudeOnly) }
            } else {
                // A wiki for ChatGPT alone: Claude's suggestions and the groups
                // are Claude's, so neither is offered, and their place says so,
                // as the old list did.
                sideNote(HomeScreen.claudeOnly)
            }
            separator
            sideItem(.inWiki, AddMore.inWikiTitle, count: AddMore.inWikiCount(home.parts),
                     tick: home.parts.map { $0.faults.isEmpty && !$0.core.isEmpty } ?? false)
        }
        .padding(.horizontal, Theme.pt(10))
        .padding(.vertical, Theme.pt(14))
    }

    private var separator: some View {
        Rectangle().fill(Theme.cardEdge).frame(height: 1)
            .padding(.vertical, Theme.pt(8)).padding(.horizontal, Theme.pt(6))
    }

    private func sideNote(_ words: String) -> some View {
        Text(words)
            .font(Theme.font(12, .medium))
            .foregroundStyle(.secondary)
            .fixedSize(horizontal: false, vertical: true)
            .padding(.horizontal, Theme.pt(10)).padding(.vertical, Theme.pt(4))
    }

    private var forYouCount: String {
        guard claudeExtras else { return "" }
        let n = home.forYou.filter { home.extraState($0.key) != .on }.count
        return n > 0 ? "\(n)" : ""
    }

    private func groupCount(_ keys: [String]) -> String {
        guard home.parts != nil else { return "" }
        return "\(keys.filter { home.extraState($0) == .on }.count) of \(keys.count)"
    }

    private func sideItem(_ target: AddMoreSection, _ title: String, count: String,
                          tick: Bool = false, index: Int = 0) -> some View {
        let chosen = section == target
        let choose = {
            withAnimation(.easeOut(duration: 0.12)) {
                home.addMoreSection = target
                home.addMoreOpenRow = nil
            }
        }
        return Button(action: choose) {
            HStack(spacing: Theme.pt(6)) {
                Text(title)
                    .font(Theme.font(14, chosen ? .semibold : .medium))
                    .lineLimit(2)
                    .fixedSize(horizontal: false, vertical: true)
                Spacer(minLength: Theme.pt(4))
                HStack(spacing: Theme.pt(3)) {
                    if tick {
                        Image(systemName: "checkmark")
                            .foregroundStyle(chosen ? Color.white : Theme.goodText)
                            .accessibilityHidden(true)
                    }
                    Text(count)
                }
                .font(Theme.font(12, .medium))
                .foregroundStyle(chosen ? Color.white.opacity(0.85) : Color.secondary)
                .fixedSize()
            }
            .foregroundStyle(chosen ? Color.white : Color.primary)
            .padding(.horizontal, Theme.pt(10)).padding(.vertical, Theme.pt(7))
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(RoundedRectangle(cornerRadius: Theme.pt(8), style: .continuous)
                .fill(chosen ? Theme.accent : Color.clear))
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .accessibilityLabel(count.isEmpty ? title : "\(title), \(count)")
        .accessibilityAddTraits(chosen ? .isSelected : [])
        .keyboardReachable(AddMore.sectionId(target, index: index), corner: 8, press: choose)
    }

    // MARK: the right

    private struct Row: Identifiable {
        let key: String
        let title: String
        var lines: [String] = []          // always shown under the title
        var note: String? = nil           // a line that needs the owner, in the warning colour
        var noteIsBad = false
        var detail: String? = nil         // shown when the row is opened
        var facts: HomeModel.Facts? = nil
        var end: End = .none
        var id: String { key }
        var opens: Bool { detail != nil || facts != nil }
    }

    private enum End {
        case none
        case word(String, warn: Bool)
        case button(String, id: String, action: () -> Void)

        var spoken: String {
            switch self {
            case .none: return ""
            case .word(let w, _): return w
            case .button(let b, _, _): return "button, \(b)"
            }
        }
    }

    private struct Page {
        var title: String
        var lead: String
        var banner: String? = nil
        var bannerButton: (String, () -> Void)? = nil
        var rows: [Row] = []
    }

    private var current: Page {
        switch section {
        case .forYou: return forYouPage
        case .group(let g): return groupPage(g, keys: groups.first { $0.0 == g }?.1 ?? [])
        case .inWiki: return inWikiPage
        }
    }

    /// One of the checklist's items as a row: the same state word, button and
    /// action whether it is shown under For you or in its own group, so the
    /// two can never say different things about the same item.
    private func extraRow(_ key: String, title: String, lines: [String] = []) -> Row {
        let state = home.extraState(key)
        var row = Row(key: key, title: title, lines: lines,
                      note: AddMore.extraNote(state), noteIsBad: { if case .failed = state { return true }; return false }(),
                      detail: home.itemWhat(key), facts: home.itemFacts(key))
        if home.lookingAgain || home.parts == nil {
            // (0.15.2) Until the report is read, an extra offers nothing.
            row.end = .none
        } else if let words = AddMore.extraButton(state) {
            row.end = .button(words, id: AddMore.buttonId(key)) {
                if case .handedOver(let how) = state, how == .clicks { home.doneFromList(key) }
                else { home.addFromList(key) }
            }
        } else {
            row.end = .word(AddMore.extraWord(state), warn: false)
        }
        return row
    }

    private var forYouPage: Page {
        guard claudeExtras else { return Page(title: AddMore.forYouTitle, lead: HomeScreen.claudeOnly) }
        let tiles = home.forYou
        guard !tiles.isEmpty else { return Page(title: AddMore.forYouTitle, lead: AddMore.forYouEmpty) }
        let rows = tiles.map { tile in
            extraRow(tile.key, title: tile.title, lines: [tile.note.isEmpty ? tile.why : ""])
        }
        return Page(title: AddMore.forYouTitle, lead: AddMore.forYouLead, rows: rows)
    }

    private func groupPage(_ group: String, keys: [String]) -> Page {
        let rows = keys.map { extraRow($0, title: home.itemTile($0, why: "")?.title ?? $0) }
        guard home.parts != nil else {
            return Page(title: group, lead: home.partsUnreadable
                        ? "Moblee could not read its list. Tell \(home.assistant.talksTo): run a check-up."
                        : "Looking at your wiki…",
                        rows: rows.map { Row(key: $0.key, title: $0.title) })
        }
        let on = keys.filter { home.extraState($0) == .on }.count
        return Page(title: group, lead: "\(on) of \(keys.count) set up.", rows: rows)
    }

    private var inWikiPage: Page {
        guard let parts = home.parts else {
            return Page(title: AddMore.inWikiTitle,
                        lead: home.partsUnreadable
                            ? "Moblee could not read its list. Tell \(home.assistant.talksTo): run a check-up."
                            : "Looking at your wiki…")
        }
        let newer = home.wikiIsNewerThanApp
        var page = Page(title: AddMore.inWikiTitle,
                        lead: parts.faults.isEmpty ? AddMore.inWikiAllIn : AddMore.inWikiLead)
        page.banner = AddMore.banner(parts, newerWiki: newer)
        if let words = AddMore.bannerButton(parts, newerWiki: newer, busy: busy) {
            if words == AddMore.checkWikiButton {
                // A part read from a file nobody can read: the check-up looks
                // at the file and says what is wrong with it.
                if flow.canBeginClinic {
                    page.bannerButton = (words, { home.addMoreOpen = false; flow.beginClinic() })
                }
            } else {
                // The updater puts back every part a wiki comes with that is
                // missing, and leaves the owner's pages alone.
                page.bannerButton = (words, { home.addMoreOpen = false; flow.beginUpdate() })
            }
        }
        page.rows = parts.core.map { part -> Row in
            var row = Row(key: part.key, title: part.title,
                          lines: [part.what, AddMore.sayLine(part, talksTo: home.assistant.talksTo) ?? ""])
            if AddMore.partButton(part, newerWiki: newer, busy: busy) == "Open", let vault = home.vault ?? (flow.isTestMode ? flow.home : nil) {
                row.end = .button("Open", id: AddMore.buttonId(part.key)) {
                    if part.open == "galaxy" { AddMore.openGalaxy(vault: vault, home: flow.home, practice: flow.isTestMode) }
                    else { AddMore.openDashboard(vault: vault, home: flow.home, practice: flow.isTestMode) }
                }
            } else {
                // Only a fault is in the warning colour; an older or changed
                // copy, or a hook ChatGPT cannot be seen to run, is said quietly.
                row.end = .word(AddMore.partWord(part, newerWiki: newer), warn: Parts.isFault(part.state))
            }
            return row
        }
        return page
    }

    private var screenSpeech: Speech {
        let p = current
        return AddMore.pageSpeech(title: p.title, lead: p.lead, banner: p.banner,
                                  rows: p.rows.map { ($0.title, $0.end.spoken) })
            + AddMore.speech(parts: home.parts, groups: claudeExtras ? groups : [],
                             word: { AddMore.extraWord(home.extraState($0)) },
                             title: { home.itemTile($0, why: "")?.title ?? $0 })
    }

    private var page: some View {
        let p = current
        return VStack(alignment: .leading, spacing: Theme.pt(4)) {
            HStack(alignment: .firstTextBaseline, spacing: Theme.pt(10)) {
                Text(p.title)
                    .font(Theme.font(21, .semibold))
                    .lineLimit(2)
                    .accessibilityAddTraits(.isHeader)
                Spacer(minLength: Theme.pt(4))
                // (0.16.0) One read-aloud for the whole screen, beside the title.
                ListenButton(id: "read-aloud", speech: screenSpeech, what: "this page", size: 20)
            }
            Text(p.lead)
                .font(Theme.font(13))
                .foregroundStyle(.secondary)
                .fixedSize(horizontal: false, vertical: true)
                .padding(.bottom, Theme.pt(10))
            if let banner = p.banner {
                HStack(spacing: Theme.pt(10)) {
                    Image(systemName: "exclamationmark.triangle.fill")
                        .foregroundStyle(Theme.waiting)
                        .accessibilityHidden(true)
                    Text(banner)
                        .font(Theme.font(13, .medium))
                        .foregroundStyle(Theme.waitingText)
                        .fixedSize(horizontal: false, vertical: true)
                    Spacer(minLength: Theme.pt(6))
                    if let pair = p.bannerButton {
                        Button(pair.0, action: pair.1)
                            .buttonStyle(SmallButtonStyle(tint: Theme.accent, filled: true))
                            .keyboardReachable(AddMore.putBackId, corner: 7, press: pair.1)
                    }
                }
                .padding(.horizontal, Theme.pt(12)).padding(.vertical, Theme.pt(9))
                .background(RoundedRectangle(cornerRadius: Theme.pt(10), style: .continuous)
                    .fill(Theme.waiting.opacity(0.12)))
                .overlay(RoundedRectangle(cornerRadius: Theme.pt(10), style: .continuous)
                    .strokeBorder(Theme.waiting.opacity(0.45), lineWidth: 1))
                .padding(.bottom, Theme.pt(12))
                .accessibilityElement(children: .contain)
            }
            if !p.rows.isEmpty {
                if still {
                    // A scrolling area cannot be drawn to a picture file: the top
                    // of the list is drawn at its own height, and the rest cut
                    // off. Drawn as an overlay on the room that is left, so a
                    // long list never pushes the page taller than the window.
                    Color.clear
                        .frame(maxWidth: .infinity, maxHeight: .infinity)
                        .overlay(alignment: .top) {
                            list(p.rows).fixedSize(horizontal: false, vertical: true)
                        }
                        .clipped()
                } else {
                    ScrollView { list(p.rows).padding(.bottom, Theme.pt(4)) }
                }
            }
        }
    }

    private func list(_ rows: [Row]) -> some View {
        VStack(spacing: 0) {
            ForEach(Array(rows.enumerated()), id: \.element.id) { index, row in
                if index > 0 { Rectangle().fill(Theme.cardEdge).frame(height: 1) }
                rowView(row)
            }
        }
        .background(CardBackground(corner: 12))
        .padding(.horizontal, 1)
    }

    private func rowView(_ row: Row) -> some View {
        let open = row.opens && home.addMoreOpenRow == row.key
        let toggle = {
            guard row.opens else { return }
            withAnimation(.easeOut(duration: 0.15)) { home.addMoreOpenRow = open ? nil : row.key }
        }
        return VStack(alignment: .leading, spacing: Theme.pt(6)) {
            HStack(alignment: .center, spacing: Theme.pt(12)) {
                Button(action: toggle) {
                    VStack(alignment: .leading, spacing: Theme.pt(2)) {
                        Text(row.title)
                            .font(Theme.font(14, .semibold))
                            .lineLimit(2)
                            .fixedSize(horizontal: false, vertical: true)
                        ForEach(row.lines.filter { !$0.isEmpty }, id: \.self) { line in
                            Text(line).font(Theme.font(12.5)).foregroundStyle(.secondary)
                                .fixedSize(horizontal: false, vertical: true)
                        }
                        if let note = row.note {
                            Text(note).font(Theme.font(12.5, .medium))
                                .foregroundStyle(row.noteIsBad ? Theme.badText : Theme.waitingText)
                                .fixedSize(horizontal: false, vertical: true)
                        }
                    }
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .contentShape(Rectangle())
                }
                .buttonStyle(.plain)
                .foregroundStyle(Color.primary)
                .accessibilityHint(row.opens ? (open ? "Closes what it is" : "Opens what it is and what adding it takes") : "")
                .keyboardReachable(AddMore.rowId(row.key), corner: 6, press: toggle)
                end(row.end)
            }
            if open {
                VStack(alignment: .leading, spacing: Theme.pt(6)) {
                    if let detail = row.detail, !detail.isEmpty {
                        Text(detail)
                            .font(Theme.font(12.5))
                            .foregroundStyle(Color.primary.opacity(0.85))
                            .fixedSize(horizontal: false, vertical: true)
                    }
                    if let facts = row.facts { factsLine(facts) }
                }
                .transition(.opacity)
            }
        }
        .padding(.horizontal, Theme.pt(14)).padding(.vertical, Theme.pt(10))
        .background(open ? Theme.accent.opacity(0.05) : Color.clear)
        .accessibilityElement(children: .contain)
    }

    /// How it is added, how long it takes, the room it takes, and whether it
    /// can cost money, which is said in the warning colour.
    private func factsLine(_ f: HomeModel.Facts) -> some View {
        let plain = ([f.how, f.minutes] + (f.size.map { [$0] } ?? [])).joined(separator: "  ·  ") + "  ·  "
        return (Text(plain).foregroundStyle(Color.secondary)
                + Text(f.paid ? "Can cost money" : "Free")
                    .foregroundStyle(f.paid ? Theme.waitingText : Color.secondary))
            .font(Theme.font(12, .medium))
            .fixedSize(horizontal: false, vertical: true)
    }

    @ViewBuilder
    private func end(_ e: End) -> some View {
        switch e {
        case .none:
            EmptyView()
        case .word(let words, let warn):
            let word = Text(words)
                .font(Theme.font(12.5, .medium))
                .foregroundStyle(warn ? Theme.waitingText : Color.secondary)
                .multilineTextAlignment(.trailing)
            // A short word takes exactly its own width and the title the rest;
            // a long one ("Moblee cannot see whether ChatGPT runs this") wraps
            // in a column of its own, never more than 150 wide.
            if words.count <= 24 {
                word.fixedSize()
            } else {
                word.frame(maxWidth: Theme.pt(150), alignment: .trailing)
                    .fixedSize(horizontal: false, vertical: true)
                    .layoutPriority(1)
            }
        case .button(let words, let id, let action):
            Button(words, action: action)
                .buttonStyle(SmallButtonStyle())
                .keyboardReachable(id, corner: 7, press: action)
        }
    }

    // MARK: the foot

    private var foot: some View {
        HStack(alignment: .center, spacing: Theme.pt(12)) {
            lookLine
                .font(Theme.font(12, .medium))
                .foregroundStyle(.secondary)
                .frame(maxWidth: .infinity, alignment: .leading)
            Button(action: { speaker.stop(); home.addMoreOpen = false }) {
                Text("Done")
                    .font(Theme.font(15, .semibold))
                    .frame(minWidth: Theme.pt(70), minHeight: Theme.pt(32))
            }
            .buttonStyle(BigButtonStyle(corner: 9, sidePadding: 14))
            // The screen's one primary action: Return presses it from anywhere,
            // as the big button does on every other screen, and the walk finds
            // it by the same name.
            .keyboardShortcut(.defaultAction)
            .accessibilityIdentifier("main-button")
            .background(DrawnAt(id: "main-button"))
        }
        .padding(.top, Theme.pt(10))
    }

    @ViewBuilder
    private var lookLine: some View {
        if home.lookingAgain {
            Text(AddMore.lookingNow).fixedSize(horizontal: false, vertical: true)
        } else {
            HStack(spacing: Theme.pt(4)) {
                if home.lookFailed {
                    Text(AddMore.couldNotLook).fixedSize(horizontal: false, vertical: true)
                } else if let looked = AddMore.lastLooked(home.parts?.checked) {
                    // The dot is a piece of its own, so it stays between the
                    // two when the row is mirrored.
                    Text(looked).fixedSize()
                    if home.canLookAgain { Text("·") }
                }
                if home.canLookAgain { lookAgainButton }
            }
        }
    }

    private var lookAgainButton: some View {
        Button(action: { home.lookAgain() }) {
            Text(AddMore.lookAgain)
                .font(Theme.font(12, .semibold))
                .padding(.horizontal, Theme.pt(4)).padding(.vertical, Theme.pt(2))
                .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .foregroundStyle(Theme.accent)
        .fixedSize()
        .keyboardReachable(AddMore.lookAgainId, corner: 6, press: { home.lookAgain() })
    }
}
