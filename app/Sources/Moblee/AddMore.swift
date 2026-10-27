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
                  let state = p["state"] as? String, ["in", "missing", "differs", "unseen"].contains(state) else { return nil }
            return Part(key: key, title: title, what: p["what"] as? String ?? "", say: p["say"] as? String ?? "",
                        open: p["open"] as? String ?? "", state: state)
        }
        return Parts(assistant: o["assistant"] as? String ?? "claude",
                     checked: o["checked"] as? String,
                     core: parts,
                     extras: extras.compactMapValues { $0 as? String })
    }

    var missing: [Part] { core.filter { !$0.inPlace } }
}

/// (0.14.0) Opening the two things a wiki carries that are pages in the browser.
@MainActor
enum AddMore {
    static let wayIn = "Add more"
    static let sentence = "Everything your wiki can have."
    static let updateWayIn = "See what else you can add"
    static let lookAgain = "Look again"
    static let comesWith = "Comes with every Moblee wiki"

    /// What a part's state says on its row.
    static func partWord(_ part: Parts.Part, newerWiki: Bool = false) -> String {
        switch part.state {
        case "in": return "In your wiki"
        // An older copy, or one the owner or their assistant changed. Not a
        // fault, and not something an update would change, so no button.
        case "differs": return "An older or changed copy"
        // Entered for ChatGPT, which runs it only once trusted.
        case "unseen": return "Moblee cannot see whether ChatGPT runs this"
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

    /// What "Say … to Claude" reads like for a part.
    static func sayLine(_ part: Parts.Part, talksTo: String) -> String? {
        part.say.isEmpty ? nil : "Say \u{201C}\(part.say)\u{201D} to \(talksTo)."
    }

    static func buttonId(_ key: String) -> String { "addmore-" + key }

    /// "Last looked: 26 October, 17:00", from the checklist's own stamp
    /// (YYYYMMDD-HHMM); nil for a stamp of any other shape.
    static func lastLooked(_ stamp: String?) -> String? {
        guard let stamp, stamp.count == 13, stamp[stamp.index(stamp.startIndex, offsetBy: 8)] == "-" else { return nil }
        let f = DateFormatter()
        f.locale = Locale(identifier: "en_GB_POSIX")
        f.dateFormat = "yyyyMMdd-HHmm"
        guard let date = f.date(from: stamp) else { return nil }
        let out = DateFormatter()
        out.locale = Locale(identifier: "en_GB")
        out.dateFormat = "d MMMM, HH:mm"
        return "Last looked: \(out.string(from: date))."
    }

    /// The whole screen, read aloud: the sentence, then each section in the
    /// words its rows show.
    static func speech(parts: Parts?, groups: [(String, [String])], word: (String) -> String,
                       title: (String) -> String) -> Speech {
        var said = sentence
        if let parts {
            let missing = parts.missing.count
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

/// (0.14.0) Everything a wiki can have, in one list: the parts every wiki comes
/// with, and the checklist's extras in its own four groups, each with where it
/// stands and the one button that moves it on.
struct AddMoreScreen: View {
    @EnvironmentObject var flow: Flow
    @EnvironmentObject var home: HomeModel
    @Environment(\.stillPicture) private var still
    @ObservedObject private var textSize = TextSize.shared

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

    var body: some View {
        ScreenFrame(sentence: AddMore.sentence,
                    buttonTitle: "Done", showsBack: false,
                    quietTitle: home.canLookAgain ? AddMore.lookAgain : nil,
                    quietAction: home.canLookAgain ? { home.lookAgain() } : nil,
                    // (0.14.0) The example wiki, which was the home screen's second
                    // big button until this screen took its place there.
                    secondTitle: flow.hasExample ? ExampleReader.wayIn : nil,
                    secondAction: flow.hasExample ? { flow.openExample() } : nil,
                    speech: AddMore.speech(parts: home.parts, groups: claudeExtras ? groups : [],
                                           word: { AddMore.extraWord(home.extraState($0)) },
                                           title: { home.itemTile($0, why: "")?.title ?? $0 }),
                    pictureHeight: 330,
                    action: { home.addMoreOpen = false }) {
            VStack(spacing: Theme.pt(6)) {
                if home.lookingAgain {
                    Text("Looking at everything on this Mac. This can take a minute; nothing you have set up is changed.")
                        .font(Theme.font(13, .medium)).foregroundStyle(.secondary)
                } else if let last = AddMore.lastLooked(home.parts?.checked) {
                    Text(last).font(Theme.font(13, .medium)).foregroundStyle(.secondary)
                }
                if still {
                    // A scrolling area cannot be drawn to a picture file: the top of
                    // the list is drawn at its own height, and the rest cut off.
                    list.fixedSize(horizontal: false, vertical: true)
                        .frame(height: Theme.pt(300), alignment: .top)
                        .clipped()
                } else {
                    ScrollView { list.padding(.vertical, Theme.pt(4)) }
                }
            }
            .frame(maxWidth: Theme.pt(720), maxHeight: Theme.pt(330), alignment: .top)
            .padding(.horizontal, Theme.pt(24))
            // The list is longer than the room it is given: the window scrolls it,
            // and a picture file shows its top, never the list spilling over the
            // sentence and the big button.
            .clipped()
        }
        .onAppear { if !still { home.loadParts() } }
    }

    private var list: some View {
        VStack(alignment: .leading, spacing: Theme.pt(14)) {
            section(AddMore.comesWith) {
                if let parts = home.parts {
                    ForEach(parts.core) { part in partRow(part) }
                } else {
                    Text(home.partsUnreadable ? "Moblee could not read its list. Tell \(home.assistant.talksTo): run a check-up."
                                              : "Looking at your wiki…")
                        .font(Theme.font(13)).foregroundStyle(.secondary)
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .padding(.horizontal, Theme.pt(14)).padding(.vertical, Theme.pt(9))
                }
            }
            if claudeExtras {
                ForEach(groups, id: \.0) { group in
                    section(group.0) {
                        ForEach(group.1, id: \.self) { key in extraRow(key) }
                    }
                }
                if home.assistant == .both {
                    Text(HomeScreen.claudeOnly).font(Theme.font(13, .medium)).foregroundStyle(.secondary)
                }
            } else {
                Text(HomeScreen.claudeOnly).font(Theme.font(14, .medium)).foregroundStyle(.secondary)
            }
        }
    }

    private func section<Rows: View>(_ title: String, @ViewBuilder rows: () -> Rows) -> some View {
        VStack(alignment: .leading, spacing: Theme.pt(6)) {
            Text(title.uppercased())
                .font(Theme.font(12, .bold)).tracking(1.2).foregroundStyle(.secondary)
                .accessibilityAddTraits(.isHeader)
            VStack(spacing: 0) { rows() }
                .background(CardBackground(corner: 14))
        }
    }

    private func row<Trailing: View>(title: String, lines: [String], word: String, good: Bool, warn: Bool,
                                     @ViewBuilder trailing: () -> Trailing) -> some View {
        HStack(alignment: .center, spacing: Theme.pt(12)) {
            VStack(alignment: .leading, spacing: Theme.pt(2)) {
                Text(title).font(Theme.font(15, .semibold))
                ForEach(lines.filter { !$0.isEmpty }, id: \.self) { line in
                    Text(line).font(Theme.font(13)).foregroundStyle(.secondary)
                        .fixedSize(horizontal: false, vertical: true)
                }
            }
            Spacer(minLength: Theme.pt(8))
            HStack(spacing: Theme.pt(4)) {
                if good { Image(systemName: "checkmark.circle.fill").foregroundStyle(Theme.good).accessibilityHidden(true) }
                Text(word).font(Theme.font(13, .medium))
                    .foregroundStyle(good ? Theme.good : (warn ? Theme.badText : Color.secondary))
                    .multilineTextAlignment(.trailing)
            }
            .frame(maxWidth: Theme.pt(200), alignment: .trailing)
            trailing()
        }
        .padding(.horizontal, Theme.pt(14)).padding(.vertical, Theme.pt(9))
        .accessibilityElement(children: .combine)
    }

    private func partRow(_ part: Parts.Part) -> some View {
        row(title: part.title,
            lines: [part.what, AddMore.sayLine(part, talksTo: home.assistant.talksTo) ?? ""],
            word: AddMore.partWord(part, newerWiki: home.wikiIsNewerThanApp), good: part.inPlace,
            warn: part.state == "missing") {
            if let words = AddMore.partButton(part, newerWiki: home.wikiIsNewerThanApp,
                                               busy: home.lookingAgain || home.somethingRunning || AppDelegate.busyWithWork),
               let vault = home.vault {
                rowButton(words, id: AddMore.buttonId(part.key)) {
                    if words == "Open" {
                        if part.open == "galaxy" { AddMore.openGalaxy(vault: vault, home: flow.home, practice: flow.isTestMode) }
                        else { AddMore.openDashboard(vault: vault, home: flow.home, practice: flow.isTestMode) }
                    } else {
                        // The updater puts back every part a wiki comes with that is
                        // missing, and leaves the owner's pages alone.
                        home.addMoreOpen = false
                        flow.beginUpdate()
                    }
                }
            }
        }
    }

    private func extraRow(_ key: String) -> some View {
        let state = home.extraState(key)
        let tile = home.itemTile(key, why: "")
        let failed: Bool = { if case .failed = state { return true }; return false }()
        return row(title: tile?.title ?? key,
                   lines: [home.itemWhat(key), tile?.detail ?? ""],
                   word: AddMore.extraWord(state), good: state == .on, warn: failed) {
            if let words = AddMore.extraButton(state), !home.lookingAgain {
                rowButton(words, id: AddMore.buttonId(key)) {
                    if case .handedOver(let how) = state, how == .clicks { home.doneFromList(key) }
                    else { home.addFromList(key) }
                }
            }
        }
    }

    private func rowButton(_ title: String, id: String, action: @escaping () -> Void) -> some View {
        Button(action: action) { Text(title).font(Theme.font(14, .semibold)) }
            .buttonStyle(.borderedProminent).tint(Theme.accent).controlSize(.regular)
            .keyboardReachable(id, corner: 6, press: action)
    }
}
