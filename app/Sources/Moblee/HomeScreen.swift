import SwiftUI
import AppKit

/// The screen a returning owner sees.
struct HomeScreen: View {
    /// Drawn again when the owner presses "Bigger text". (v0.9.4)
    @ObservedObject private var textSize = TextSize.shared
    /// (v0.9.6) Watched for the count of drops still copying, which is what
    /// greys "Check my wiki" while one is. Not for the receipt: that is drawn
    /// over every screen by `RootView`, not by this one.
    @ObservedObject private var dropped = Dropped.shared
    @EnvironmentObject var flow: Flow
    @EnvironmentObject var home: HomeModel
    @Environment(\.stillPicture) private var still
    @State private var repairing = false

    private var waiting: [HomeModel.Tile] { home.tiles.filter { $0.state != .done } }
    /// Three at a time. The ones that can simply be added come first; ones the
    /// owner has been sent elsewhere to finish, or that cannot be added, come
    /// after them; the rest take their place as these are dealt with.
    private var shown: [HomeModel.Tile] { Self.shown(from: home.tiles) }

    /// Which three, and in which order. A function of the tiles alone, so the
    /// live walk can work out what the screen in front of it is showing and
    /// ask whether the keyboard really crosses it in that order. (v0.9.5)
    static func shown(from tiles: [HomeModel.Tile]) -> [HomeModel.Tile] {
        Array(tiles.sorted { HomeModel.rank($0.state) < HomeModel.rank($1.state) }.prefix(3))
    }

    /// The Trust screen is open: because the step is waiting, or because the
    /// owner pressed "Prove the guard" in the menu. It stays until the owner
    /// leaves it. (0.16.0: the model holds it; see `HomeModel.trustOpen`.)
    private var showsTrust: Bool { (home.trustPending && !home.trustSetAside) || home.trustOpen }

    var body: some View {
        ZStack {
            if let tile = home.explaining {
                ExplainScreen(tile: tile)
            } else if home.addMoreOpen {
                // (0.14.0) Everything the wiki can have. Over the repair and the
                // update prompts too: it is opened on purpose, and its own Put
                // back starts the same update.
                AddMoreScreen()
            } else if home.updateAvailable {
                updatePrompt
            } else if home.repairIsForANewerMoblee {
                newerMobleePrompt
            } else if home.needsRepair {
                repairPrompt
            } else if home.showsForeignSkills {
                foreignSkillPrompt
            } else if showsTrust {
                TrustScreen(start: home.trustPending ? Trust.firstStage : .offer, vault: home.vault?.path) {
                    home.trustOpen = false
                    home.trustSetAside = true
                }
                .onAppear { home.trustOpen = true }
            } else if home.assistant == .chatgpt {
                // (0.16.0) On this screen and the two below it there is one big
                // button and one quiet line, "Add more". Everything else that
                // was round the foot of the screen is in the corner menu
                // (`HomeMenu`), and the one read-aloud in that corner reads the
                // whole screen (`HomeScreen.speech`).
                // The tiles are extras that Moblee sets up for Claude only. An
                // owner who uses ChatGPT alone is told so once, plainly, in
                // their place, and is never offered something that would do
                // nothing for them.
                ScreenFrame(sentence: Self.sentence(home),
                            buttonTitle: "Open ChatGPT", showsBack: false,
                            quietTitle: AddMore.wayIn, quietAction: { home.openAddMore() },
                            listenInCorner: true, subline: unknownLine,
                            action: openChatGPT) {
                    Image(systemName: "bubble.left.and.bubble.right.fill")
                        .font(Theme.font(96, .regular, .default)).foregroundStyle(Theme.accent)
                        .accessibilityHidden(true)
                }
            } else if home.listUnreadable {
                ScreenFrame(sentence: Self.sentence(home),
                            buttonTitle: "Open Claude", showsBack: false,
                            listenInCorner: true, subline: unknownLine, action: openClaude) {
                    Image(systemName: "exclamationmark.triangle.fill")
                        .font(Theme.font(90, .regular, .default)).foregroundStyle(Theme.waiting)
                        .accessibilityHidden(true)
                }
            } else if waiting.isEmpty {
                ScreenFrame(sentence: Self.sentence(home),
                            buttonTitle: "Open Claude", showsBack: false,
                            quietTitle: AddMore.wayIn, quietAction: { home.openAddMore() },
                            listenInCorner: true, subline: unknownLine,
                            action: openClaude) {
                    Image(systemName: home.tiles.isEmpty ? "bubble.left.and.bubble.right.fill" : "checkmark.circle.fill")
                        .font(Theme.font(96, .regular, .default))
                        .foregroundStyle(home.tiles.isEmpty ? Theme.accent : Theme.good)
                        .accessibilityHidden(true)
                }
            } else {
                // (0.16.0) Each card carries its own small Add, so the big
                // button no longer adds "the first one": it is Open Claude, as
                // on every other home screen, and Add more is the quiet line.
                ScreenFrame(sentence: Self.sentence(home),
                            buttonTitle: "Open Claude", showsBack: false,
                            quietTitle: AddMore.wayIn, quietAction: { home.openAddMore() },
                            listenInCorner: true, subline: unknownLine,
                            action: openClaude) {
                    VStack(spacing: Theme.pt(8)) {
                        HStack(alignment: .top, spacing: Theme.pt(18)) {
                            ForEach(shown) { tile in
                                RequestTile(tile: tile, press: { home.press(tile) }, done: { home.markDone(tile) })
                            }
                        }
                        // These two short lines belong to the list above them, and
                        // are read with it by the one read-aloud in the corner.
                        if let more = Self.moreAfterThese(tiles: home.tiles.count, shown: shown.count) {
                            Text(more)
                                .font(Theme.font(13, .medium))
                                .foregroundStyle(.secondary)
                        }
                        if home.assistant == .both {
                            Text(Self.claudeOnly)
                                .font(Theme.font(13, .medium))
                                .foregroundStyle(.secondary)
                        }
                    }
                    .padding(.horizontal, Theme.pt(30))
                }
            }
        }
        .onAppear {
            guard !still else { return }
            home.startWatching()
        }
        .onDisappear {
            home.stopWatching()
            // As the screen's own state did before 0.16.0: leaving the home
            // screen leaves the Trust steps and the menu behind it.
            home.trustOpen = false
            home.menuOpen = false
        }
    }

    /// (0.16.0) The sentence at the top of the ordinary home screen, in each of
    /// its states. A function of the model alone, so that the read-aloud in the
    /// window's corner, which is drawn outside this screen, reads the screen's
    /// own words and not a second copy of them.
    static func sentence(_ home: HomeModel) -> String {
        if home.assistant == .chatgpt {
            return "Connections and other extras are set up for Claude. Moblee does not set them up for ChatGPT yet."
        }
        if home.listUnreadable { return "Moblee could not read its list. Tell \(home.assistant.talksTo): run a check-up." }
        let waiting = home.tiles.filter { $0.state != .done }
        if waiting.isEmpty {
            return home.tiles.isEmpty ? "Nothing is waiting. Talk to Claude." : "All added. Tell Claude it is done."
        }
        guard home.nextTile == nil else { return "Claude has these ready for you." }
        return waiting.contains { $0.state == .handedOver && $0.how == .clicks }
            ? "Finish these where they opened. Then press Done here."
            : "Finish these where they opened, then tell Claude."
    }

    /// (0.16.0) The one quiet line under the sentence when a settings file
    /// cannot be read, so Moblee cannot tell whether the guard is on. It does
    /// not claim the guard is off; it says what it cannot see, and offers the
    /// check-up, which looks at the file and says what is wrong with it.
    static func unknownSentence(_ home: HomeModel) -> String? {
        home.unreadableSettingsOf.map {
            "Moblee cannot read \($0)'s settings file, so it cannot tell whether the safety guard is on."
        }
    }
    static let unknownCheckId = "unknown-check-wiki"

    private var unknownLine: AnyView? {
        guard let line = Self.unknownSentence(home) else { return nil }
        let check = { if flow.canBeginClinic { flow.beginClinic() } }
        return AnyView(
            HStack(spacing: Theme.pt(10)) {
                Text(line)
                    .font(Theme.font(13, .medium))
                    .foregroundStyle(.secondary)
                    .fixedSize(horizontal: false, vertical: true)
                Button(Self.checkWiki, action: check)
                    .buttonStyle(SmallButtonStyle())
                    .disabled(!flow.canBeginClinic)
                    .keyboardReachable(Self.unknownCheckId, corner: 7, press: check)
            }
            .frame(maxWidth: Theme.pt(620))
        )
    }

    static func moreAfterThese(tiles: Int, shown: Int) -> String? {
        tiles > shown ? "and \(tiles - shown) more after these" : nil
    }

    /// (0.16.0) What the one read-aloud in the corner says: the whole screen,
    /// top to bottom. The sentence; each card in the words the card itself
    /// shows, cost and state included; the two short lines under the cards;
    /// then the two things that can be pressed below them.
    ///
    /// (v0.9.5) A skill Claude wrote wears the name the owner asked for, in
    /// their own words, so a list with one in it is read in pieces rather
    /// than in one voice; `RequestTile.speech` does that.
    static func speech(_ home: HomeModel) -> Speech {
        var said = Speech(sentence(home))
        if let line = unknownSentence(home) {
            said = said + Speech(line + " Press \(checkWiki) beside it.")
        }
        let onScreenTiles = home.assistant != .chatgpt && !home.listUnreadable
            && home.tiles.contains { $0.state != .done }
        if onScreenTiles {
            let shown = Self.shown(from: home.tiles)
            for tile in shown where tile.state != .done { said = said + RequestTile.speech(for: tile) }
            if let more = moreAfterThese(tiles: home.tiles.count, shown: shown.count) { said = said + Speech(more) }
            if home.assistant == .both { said = said + Speech(claudeOnly) }
        }
        let big = home.assistant == .chatgpt ? "Open ChatGPT" : "Open Claude"
        said = said + Speech(home.listUnreadable ? "The big button: \(big)."
                             : "The big button: \(big). Under it: \(AddMore.wayIn).")
        // (0.16.0) A newer Moblee is in the menu, which an owner who cannot
        // read would never open on the chance: 0.15.2 gave its line a speaker
        // of its own for exactly that reason, so it is said here.
        if home.newerReleaseLineAllowed, let v = home.newerRelease {
            said = said + Speech(newerReleaseSpoken(v))
        }
        return said
    }

    static func newerReleaseSpoken(_ version: String) -> String {
        "Moblee \(version) is out. Install it from the menu at the top of the window."
    }

    /// (v0.9.5) Every control the keyboard stops at on this screen, in the
    /// order Tab reaches them, written here beside the code that draws them.
    ///
    /// It is here and not in the check because a list of names typed out in a
    /// check is a list of what somebody believed the screen had on it. The live
    /// walk presses Tab round the real window and requires the real ring to be
    /// exactly this, so the two cannot drift apart.
    ///
    /// (0.16.0) Far shorter than it was. The corner comes first, at the top of
    /// the window: the one read-aloud and the one menu. Then each card's own
    /// buttons, card by card, and then the quiet "Add more" under the big
    /// button. The big button is not on the round and never has been: it is
    /// the window's default action, pressed by Return from anywhere. Every
    /// card's own speaker, the quiet words' speaker, and the two lines along
    /// the bottom with their three speakers have gone: the lines are inside the
    /// menu (`HomeMenu.stops`), and the corner's read-aloud reads it all.
    static func stops(shown: [HomeModel.Tile], addMore: Bool = true, unknownLine: Bool = false) -> [String] {
        var ring = ["read-aloud", HomeMenu.buttonId]
        // The quiet line under the sentence, when a settings file cannot be read.
        if unknownLine { ring.append(unknownCheckId) }
        for tile in shown { ring += RequestTile.stops(tile) }
        if addMore { ring.append("quiet") }
        return ring
    }

    /// The most controls this screen can ever have on it at once, which is the
    /// number the keyboard has to be able to cross.
    ///
    /// Worked out from `stops` rather than counted by eye: one tile still to
    /// be added, and two handed over by clicks (which is what grows a Done
    /// button each).
    static func busiestTiles() -> [HomeModel.Tile] {
        var waiting = HomeModel.Tile(kind: .item, key: "one", title: "", why: "", detail: "",
                                     how: .silent, paid: false)
        waiting.state = .waiting
        let handedOver: [HomeModel.Tile] = ["two", "three"].map {
            var tile = HomeModel.Tile(kind: .item, key: $0, title: "", why: "", detail: "",
                                      how: .clicks, paid: false)
            tile.state = .handedOver
            return tile
        }
        return [waiting] + handedOver
    }

    static func busiest() -> [String] { stops(shown: busiestTiles()) }

    static let claudeOnly = "These are set up for Claude. Moblee does not set them up for ChatGPT yet."

    private var updatePrompt: some View {
        ScreenFrame(sentence: "A newer Moblee is ready for your wiki. Your pages are not touched.",
                    buttonTitle: "Update", showsBack: false,
                    quietTitle: "Not now", quietAction: { home.updateSetAside = true },
                    // On a Mac with no choice of assistant on record, the update asks first.
                    action: { flow.beginUpdate() }) {
            VStack(spacing: Theme.pt(14)) {
                Image(systemName: "arrow.up.circle.fill")
                    .font(Theme.font(96, .regular, .default)).foregroundStyle(Theme.accent)
                    .accessibilityHidden(true)
                // (v0.9.4) The arrow is a letter inside a line of its own, and a
                // line keeps the direction of its own words whatever the layout
                // around it does, so it points the same way on a mirrored screen
                // as it does here. See `Layout.versionsArrow`.
                //
                // (v0.9.5) An arrow between two numbers cannot be read aloud as
                // an arrow, so the listen control beside it says what the line
                // means in words — the same words the screen reader is given.
                HStack(spacing: Theme.pt(8)) {
                    Text("\(home.wikiVersion)  \(Layout.versionsArrow)  \(home.packVersion)")
                        .font(Theme.font(20, .semibold))
                        .foregroundStyle(.secondary)
                        .accessibilityLabel(Self.versionsSaid(from: home.wikiVersion, to: home.packVersion))
                    ListenButton(id: "listen-versions",
                                 speech: Speech(Self.versionsSaid(from: home.wikiVersion, to: home.packVersion)),
                                 what: "the two versions", size: 15)
                }
            }
        }
    }

    static func versionsSaid(from: String, to: String) -> String {
        "From version \(from) to \(to)"
    }

    private var repairPrompt: some View {
        ScreenFrame(sentence: home.repairFailed ? "That did not work. Tell \(home.assistant.talksTo): run a check-up."
                        : (repairing ? "Putting it right…"
                           : (home.safetyOff ? "The safety guard is off. Switch it back on."
                              : home.guardStale ? "The safety guard is an older one. Bring it up to date."
                                             : "One of Moblee's skills is missing. Put it back.")),
                    buttonTitle: home.repairFailed ? "Open \(home.assistant.talksTo)" : "Repair",
                    buttonEnabled: !repairing, showsBack: false,
                    // A guard that is OFF is never waved through. Copies that merely
                    // differ can be: an owner who changed theirs on purpose, or a repair
                    // that cannot finish, must not be shut out of their tiles.
                    quietTitle: (!home.safetyOff && !repairing) ? "Not now" : nil,
                    quietAction: (!home.safetyOff && !repairing) ? { home.repairFailed = false; home.repairSetAside = true } : nil,
                    action: {
                        if home.repairFailed {
                            if home.assistant == .chatgpt { openChatGPT() } else { openClaude() }
                            return
                        }
                        repairing = true
                        home.repair { repairing = false }
                    }) {
            Image(systemName: home.safetyOff || home.guardStale ? "lock.shield.fill" : "graduationcap.fill")
                .font(Theme.font(96, .regular, .default)).foregroundStyle(home.repairFailed ? .red : Theme.waiting)
                .accessibilityHidden(true)
        }
    }

    /// (v0.9.4) Something else is wearing one of Moblee's skill names, and it
    /// is not a copy any Moblee left here. Moblee will not touch it, so there
    /// is no repair to offer: the screen names the skill and says what to do.
    /// The button opens the assistant, which is who can rename it. This used to
    /// be a Repair button that ran two scripts and changed nothing, on every
    /// opening of the app, for ever (a live failure, 24 September 2026).
    private var foreignSkillPrompt: some View {
        ScreenFrame(sentence: HomeModel.foreignSkillSentence(home.foreignSkills,
                                                             talksTo: home.assistant.talksTo),
                    buttonTitle: "Open \(home.assistant.talksTo)", showsBack: false,
                    quietTitle: "Not now",
                    quietAction: { home.foreignSkillsSetAside = true },
                    action: { if home.assistant == .chatgpt { openChatGPT() } else { openClaude() } }) {
            Image(systemName: "graduationcap.fill")
                .font(Theme.font(96, .regular, .default)).foregroundStyle(Theme.waiting)
                .accessibilityHidden(true)
        }
    }

    /// The guard looks off on a wiki that a newer Moblee made. This app's
    /// copies are older than the wiki's, so it does not offer Repair, and says
    /// why. There is nothing for it to do, so the button closes it.
    private var newerMobleePrompt: some View {
        ScreenFrame(sentence: Self.newerMobleeSentence,
                    buttonTitle: "Close Moblee", showsBack: false,
                    action: { if !flow.isTestMode { NSApplication.shared.terminate(nil) } }) {
            VStack(spacing: Theme.pt(14)) {
                Image(systemName: "arrow.down.app.fill")
                    .font(Theme.font(96, .regular, .default)).foregroundStyle(Theme.waiting)
                    .accessibilityHidden(true)
                HStack(spacing: Theme.pt(8)) {
                    Text("Your wiki: \(home.wikiVersion)   This Moblee: \(home.packVersion)")
                        .font(Theme.font(17, .semibold))
                        .foregroundStyle(.secondary)
                        .accessibilityLabel(Self.twoVersionsSaid(wiki: home.wikiVersion, app: home.packVersion))
                    // (v0.9.5) Two version numbers on one line, read as sentences.
                    ListenButton(id: "listen-versions",
                                 speech: Speech(Self.twoVersionsSaid(wiki: home.wikiVersion, app: home.packVersion)),
                                 what: "the two versions", size: 15)
                }
            }
        }
    }

    static func twoVersionsSaid(wiki: String, app: String) -> String {
        "Your wiki is version \(wiki). This Moblee is version \(app)."
    }

    static let newerMobleeSentence = "Your wiki is newer than this Moblee, so this one cannot repair its guard. Get the newest Moblee."
    static let changeNeedsNewest = "To change it, get the newest Moblee."

    private func openClaude() {
        if !flow.isTestMode,
           let url = NSWorkspace.shared.urlForApplication(withBundleIdentifier: "com.anthropic.claudefordesktop") {
            NSWorkspace.shared.openApplication(at: url, configuration: NSWorkspace.OpenConfiguration())
        }
    }

    private func openChatGPT() {
        ChatGPTApp.open(folder: home.vault?.path, practice: flow.isTestMode)
    }

    /// The words on the check-up's button. Plain, and about the owner's wiki
    /// rather than about a clinic or a check-up, which are the maintainer's
    /// words and not theirs. (v0.9.6)
    static let checkWiki = "Check my wiki"
}

/// In a practice run only: where a small control was drawn, in the window's
/// own coordinates (from the top left), so the self-drive walk can click the
/// control itself rather than where it is expected to be. A released app
/// records nothing.
@MainActor
enum DrawnPlaces {
    static var frames: [String: CGRect] = [:]

    /// (v0.9.4) Which view last reported each control's place. While one screen
    /// slides out and the next slides in, both are on the window at once and
    /// both carry a control of the same name — the big button, the way back —
    /// so the one leaving must not wipe the record the one arriving has just
    /// made. Telling them apart by the frame alone was not enough: the big
    /// button is in the SAME place on one screen as on the next, so the two
    /// frames matched and the one leaving cleared it after all, and the walk
    /// found nothing where the button plainly was (seen 26 September 2026).
    /// They are told apart by which view wrote the record instead.
    static var owners: [String: ObjectIdentifier] = [:]
}

struct DrawnAt: View {
    let id: String

    /// This particular view, as something that can be told from another view of
    /// the same name.
    private final class Mine {}
    @State private var mine = Mine()

    var body: some View {
        GeometryReader { g in
            Color.clear
                .onAppear { record(g.frame(in: .global)) }
                .onChange(of: g.frame(in: .global)) { _, f in record(f) }
                .onDisappear {
                    guard Practice.on, DrawnPlaces.owners[id] == ObjectIdentifier(mine) else { return }
                    DrawnPlaces.frames[id] = nil
                    DrawnPlaces.owners[id] = nil
                }
        }
    }

    private func record(_ f: CGRect) {
        guard Practice.on else { return }
        DrawnPlaces.frames[id] = f
        DrawnPlaces.owners[id] = ObjectIdentifier(mine)
    }
}

struct RequestTile: View {
    let tile: HomeModel.Tile
    let press: () -> Void
    let done: () -> Void
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @ObservedObject private var textSize = TextSize.shared

    /// (v0.9.4) The names the keyboard, and the self-drive walk, find these
    /// buttons by. Until now they could be reached by the mouse alone.
    static func buttonId(_ tile: HomeModel.Tile) -> String { "tile-" + tile.key }
    static func doneId(_ tile: HomeModel.Tile) -> String { "tile-" + tile.key + "-done" }
    /// Every control this tile puts on the keyboard's round, in the order it
    /// lays them out. Written here beside `body`, which is the only other place
    /// that decides which buttons a tile in a given state has. (0.16.0: the
    /// tile's own listen control has gone; the corner's read-aloud reads every
    /// card, in `HomeScreen.speech`.)
    static func stops(_ tile: HomeModel.Tile) -> [String] {
        switch tile.state {
        case .waiting, .failed:
            return [buttonId(tile)]
        case .handedOver:
            return tile.how == .clicks ? [doneId(tile), buttonId(tile)] : [buttonId(tile)]
        case .running, .done, .blocked:
            return []                               // words, not buttons
        }
    }

    /// (v0.9.5) Everything a tile says, read aloud: what it is, WHY Claude asked
    /// for it, what it costs in time and money, and where it has got to. The
    /// reason is the part an owner is actually deciding on, and it was silent.
    ///
    /// A skill Claude wrote wears the skill's own name, which the owner asked for
    /// in their own words and may be in their own script, so that name is read in
    /// a voice chosen for it.
    static func speech(for tile: HomeModel.Tile) -> Speech {
        var said = tile.title + ". " + (tile.note.isEmpty ? tile.why : tile.note)
        // A skill says its name and what it does, and has no minutes or megabytes.
        if tile.kind != .skill { said += ". " + tile.detail }
        said += ". " + stateWord(tile)
        return tile.kind == .skill ? Speech.sentence(said, theirs: tile.key) : Speech(said)
    }

    static func stateWord(_ tile: HomeModel.Tile) -> String {
        switch tile.state {
        case .waiting: return "waiting to be added"
        case .running: return "being added"
        case .handedOver: return "opened elsewhere, to be finished there"
        case .done: return "added"
        case .failed: return "did not work. \(tile.note)"
        case .blocked: return "cannot be added. \(tile.note)"
        }
    }

    var body: some View {
        VStack(spacing: Theme.pt(8)) {
            Image(systemName: tile.state == .done ? "checkmark.circle.fill" : tile.symbol)
                .font(Theme.font(40, .medium, .default))
                .foregroundStyle(tile.state == .done ? Theme.good
                                 : ((tile.state == .failed || tile.state == .blocked) ? .red : Theme.accent))
                .frame(height: Theme.pt(50))
                .symbolEffect(.pulse, options: .repeating, isActive: tile.state == .running && !reduceMotion)
                .accessibilityHidden(true)
            Text(tile.title)
                .font(Theme.font(15, .semibold))
                .multilineTextAlignment(.center).lineLimit(2).minimumScaleFactor(0.85)
            Text(tile.note.isEmpty ? tile.why : tile.note)
                .font(Theme.font(13))
                .foregroundStyle(tile.note.isEmpty ? Color.primary.opacity(0.85) : Theme.badText)
                .multilineTextAlignment(.center).lineLimit(3).minimumScaleFactor(0.85)
            if tile.kind != .skill {
                HStack(spacing: Theme.pt(4)) {
                    if tile.paid { Image(systemName: "creditcard.fill").accessibilityHidden(true) }
                    Text(tile.detail)
                }
                .font(Theme.font(13, .medium))
                .foregroundStyle(tile.paid ? Theme.waitingText : Color.secondary)
                .multilineTextAlignment(.center)
            }
            Spacer(minLength: Theme.pt(0))
            // (0.16.0) One small outlined button on each card, drawn by SwiftUI
            // so a picture file shows it, and no speaker beside it: the corner's
            // one read-aloud reads every card.
            Group {
                switch tile.state {
                case .waiting:
                    Button(tile.kind == .skill ? "Look" : (tile.kind == .job ? "Switch on" : "Add"), action: press)
                        .buttonStyle(SmallButtonStyle())
                        .keyboardReachable(Self.buttonId(tile), corner: 7, press: press)
                case .running:
                    Label(tile.kind == .job ? "Switching on…" : "Adding…", systemImage: "arrow.triangle.2.circlepath")
                        .foregroundStyle(Theme.waitingText)
                case .handedOver:
                    HStack(spacing: Theme.pt(8)) {
                        // Anything done by clicks inside Claude, whether it is on the
                        // pack's list (Google) or not, is finished by the owner's word:
                        // nothing outside Claude can see those connections.
                        if tile.how == .clicks {
                            Button("Done", action: done)
                                .buttonStyle(SmallButtonStyle(tint: Theme.good, filled: true))
                                .keyboardReachable(Self.doneId(tile), corner: 7, press: done)
                        }
                        Button("Again", action: press)
                            .buttonStyle(SmallButtonStyle())
                            .keyboardReachable(Self.buttonId(tile), corner: 7, press: press)
                    }
                case .done:
                    Text("Added").foregroundStyle(Theme.goodText)
                case .failed:
                    Button("Try again", action: press)
                        .buttonStyle(SmallButtonStyle())
                        .keyboardReachable(Self.buttonId(tile), corner: 7, press: press)
                case .blocked:
                    Text("Tell Claude").foregroundStyle(Theme.badText)
                }
            }
            .font(Theme.font(13, .semibold))
            .frame(height: Theme.pt(30))
        }
        .padding(.horizontal, Theme.pt(12)).padding(.vertical, Theme.pt(14))
        .frame(width: Theme.pt(200), height: Theme.pt(262))
        .background(CardBackground())
        .accessibilityElement(children: .contain)
        .accessibilityLabel("\(tile.title). \(tile.why)")
        .accessibilityValue(stateWord)
    }

    private var stateWord: String { Self.stateWord(tile) }
}

/// Shown before anything is added that the owner should see first: a skill
/// Claude wrote, a Terminal window, or clicks inside Claude.
struct ExplainScreen: View {
    @EnvironmentObject var home: HomeModel
    @Environment(\.stillPicture) private var still
    @ObservedObject private var textSize = TextSize.shared
    let tile: HomeModel.Tile

    private var isSkill: Bool { tile.kind == .skill }
    private var isTerminal: Bool { tile.kind == .item && tile.how == .terminal }

    /// (v0.9.4) The Terminal explanation used to put all three of its pictures
    /// on the screen at once, which is three things to read in one go for an
    /// owner who does not read much. They now come one at a time, in the same
    /// words, with where they are in the three said plainly, a way back, and
    /// the last one leading to the button that opens the Terminal window.
    static let terminalCards: [(symbol: String, title: String, detail: String)] = [
        ("terminal.fill", "It types for itself", "Press Return if it asks you to"),
        ("key.fill", "Your Mac password", "Nothing shows as you type. That is normal."),
        ("clock.fill", "Wait", "Downloads take a while. Then close it."),
    ]

    /// The big button moves on through the three, and opens the window at the
    /// last of them. Nothing is opened before the owner has seen all three.
    static func terminalButtonTitle(step: Int) -> String {
        step < terminalCards.count - 1 ? "Next" : "Open it"
    }

    static func terminalWhere(step: Int) -> String { "\(step + 1) of \(terminalCards.count)" }

    @State private var terminalStep = 0

    private var lastTerminalCard: Bool { terminalStep >= Self.terminalCards.count - 1 }

    var body: some View {
        ScreenFrame(
            sentence: isSkill ? "Claude wrote this skill for you. It will work in every Claude session on this Mac."
                : (isTerminal ? "A black window opens and types for itself. Follow it, then come back."
                              : "Do these three in Claude. Then come back and press Done."),
            buttonTitle: isSkill ? "Add it"
                : (isTerminal ? Self.terminalButtonTitle(step: terminalStep) : "Show me"),
            showsBack: false,
            quietTitle: "Not now", quietAction: { home.explaining = nil },
            spoken: isSkill ? "Claude wrote this skill for you. It says: \(tile.detail)" : nil,
            action: {
                if isTerminal && !lastTerminalCard {
                    withAnimation(.easeInOut(duration: 0.2)) { terminalStep += 1 }
                    return
                }
                if isSkill { home.addSkill(tile) }
                else if isTerminal { home.openTerminal(for: tile) }
                else { home.openClicks(for: tile) }
                home.explaining = nil
            }
        ) {
            if isSkill {
                skillPreview
            } else if isTerminal {
                terminalPicture
            } else if tile.steps.count == 3 {
                // The pack's own three cards for this item: where to go, what to
                // switch on by name, and how to tell it worked. Without them an
                // owner lands in Claude with nothing to look for.
                HStack(alignment: .top, spacing: Theme.pt(18)) {
                    HandoffCard(number: 1, symbol: "gearshape.fill", title: tile.steps[0][0], detail: tile.steps[0][1])
                    HandoffCard(number: 2, symbol: "link", title: tile.steps[1][0], detail: tile.steps[1][1])
                    HandoffCard(number: 3, symbol: "text.bubble.fill", title: tile.steps[2][0], detail: tile.steps[2][1])
                }
                .padding(.horizontal, Theme.pt(30))
            } else {
                HStack(alignment: .top, spacing: Theme.pt(18)) {
                    HandoffCard(number: 1, symbol: "gearshape.fill", title: "Connectors",
                                detail: "The page opens. If it says moved: Customise, then Connectors")
                    HandoffCard(number: 2, symbol: "link", title: "Connect \(tile.key)",
                                detail: tile.paid ? "Press Connect and sign in. Paying is your choice"
                                                  : "Find it, press Connect, sign in with your own account")
                    HandoffCard(number: 3, symbol: "text.bubble.fill", title: "Check it worked",
                                detail: "Ask Claude to use it. If it answers, it is connected")
                }
                .padding(.horizontal, Theme.pt(30))
            }
        }
        // A picture file is drawn at whichever of the three it was asked for;
        // an owner always begins at the first.
        .onAppear { if still { terminalStep = home.explainTerminalStep } }
    }

    /// One picture at a time: the card, then where the owner is in the three,
    /// with Back beside it once there is somewhere to go back to. Forward is
    /// the big button below, which is the same button on every screen.
    private var terminalPicture: some View {
        let card = Self.terminalCards[min(terminalStep, Self.terminalCards.count - 1)]
        return VStack(spacing: Theme.pt(16)) {
            HandoffCard(number: terminalStep + 1, symbol: card.symbol,
                        title: card.title, detail: card.detail,
                        width: Theme.pt(300))
            ZStack {
                Text(Self.terminalWhere(step: terminalStep))
                    .font(Theme.font(14, .semibold))
                    .foregroundStyle(.secondary)
                    .accessibilityLabel("Picture \(Self.terminalWhere(step: terminalStep))")
                HStack(spacing: Theme.pt(0)) {
                    if terminalStep > 0 {
                        QuietButton(title: "Back", id: "explain-back",
                                    action: { withAnimation(.easeInOut(duration: 0.2)) { terminalStep -= 1 } })
                    }
                    Spacer()
                }
                .frame(width: Theme.pt(300))
            }
        }
    }

    /// The one line the skill says about itself, then the whole of what Claude
    /// would be told to do, so that the owner is never adding words unseen.
    ///
    /// (v0.9.4) This card is a window onto a file, not a sentence of Moblee's,
    /// so it is not mirrored with the rest of the screen: a file's words are
    /// written left to right and its lines begin on the left, and right-aligning
    /// them would take every line's beginning away from where it is. The card
    /// itself still sits where the mirrored screen puts it.
    private var skillPreview: some View {
        let whole = Self.preview(tile)
        return VStack(alignment: .leading, spacing: Theme.pt(8)) {
            Label(tile.key, systemImage: "wand.and.stars")
                .font(Theme.font(18, .semibold))
            Group {
                if still {
                    // a scrolling area cannot be drawn to a picture file
                    Text(whole).frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
                } else {
                    ScrollView { Text(whole).frame(maxWidth: .infinity, alignment: .leading).textSelection(.enabled) }
                }
            }
            .font(Theme.font(13))
        }
        .padding(Theme.pt(16))
        .frame(width: Theme.pt(600), height: Theme.pt(270), alignment: .topLeading)
        .environment(\.layoutDirection, .leftToRight)
        .background(CardBackground(corner: 20))
        // (v0.9.5) The whole of what the owner is about to add, read aloud. This
        // is the screen that asks somebody to agree to words they have not
        // written, and the words were only ever on the card to be read: the
        // headline's own control says what the skill claims to do, this one says
        // the whole of it. The skill's name is the owner's own — they asked for it
        // in their own words — so it is read in a voice chosen for that name.
        .overlay(alignment: .topTrailing) {
            ListenButton(id: "listen-skill", speech: Self.skillSpeech(tile), what: "the whole skill")
                .padding(Theme.pt(10))
        }
    }

    /// The whole of what the card shows, in one place, so that what is drawn and
    /// what is read cannot drift apart. (v0.9.5)
    static func preview(_ tile: HomeModel.Tile) -> String {
        "WHAT IT SAYS IT DOES\n\(tile.detail.isEmpty ? "It does not say." : tile.detail)\n\n"
            + "EVERYTHING CLAUDE WOULD BE TOLD (\(tile.files.count) file\(tile.files.count == 1 ? "" : "s"): "
            + tile.files.prefix(6).joined(separator: ", ") + ")\n\(tile.body)"
    }

    static func skillSpeech(_ tile: HomeModel.Tile) -> Speech {
        Speech.sentence(tile.key + ". " + preview(tile), theirs: tile.key)
    }
}

/// The update, shown the same way as the first build.
struct UpdateScreen: View {
    /// Drawn again when the owner presses "Bigger text". (v0.9.4)
    @ObservedObject private var textSize = TextSize.shared
    @EnvironmentObject var flow: Flow
    @EnvironmentObject var home: HomeModel
    @EnvironmentObject var install: InstallRun
    @Environment(\.stillPicture) private var still
    /// (v0.13.0) The two short films, offered once the update has finished, in
    /// place of the tiles while open, as at the end of an install.
    @State private var showingFilms = false
    @State private var filmChosen: Films.Film?

    private var failed: Bool { if case .failed = install.phase { return true }; return false }
    private var done: Bool { install.phase == .finished || install.phase == .needsCommit }

    var body: some View {
        ScreenFrame(
            // (v0.9.1) `needsCommit` is its own sentence. The files all landed,
            // so "the update stopped" would be wrong; the closing commit was
            // refused, so "up to date" would be a lie — and it was the one the
            // owner used to be told, over a wiki whose update was never saved
            // into its history and whose own next commit would be refused too.
            sentence: showingFilms ? (filmChosen?.title ?? HandoffScreen.filmsSentence)
                : install.phase == .needsCommit
                ? "Your wiki is updated, but the change was not saved into its history. Open your assistant and say: the Moblee update did not commit, please look and commit it."
                // (v0.9.2) A step can finish while one part inside it does not,
                // and the run used to end on a flat "up to date" over exactly
                // that. What was skipped is in the diary, which is one press away.
                : (install.phase == .finished
                    ? (install.partial
                        ? "Your wiki is up to date, but one or two things in the update did not finish. Press Show what happened."
                        : "Your wiki is up to date.")
                : (failed ? "The update stopped. Your pages were not touched." : "Updating your wiki…")),
            buttonTitle: showingFilms ? "Back" : (failed ? "Try again" : "Done"),
            buttonEnabled: install.phase == .finished || install.phase == .needsCommit || failed,
            showsBack: false,
            // (0.14.0) Once it has finished, the way to everything else the wiki
            // can have, which an update used to offer only as a question in a
            // Terminal window.
            // Not when the update has just asked for ChatGPT's trust: that
            // screen comes first, and this one must not open over it.
            quietTitle: failed ? "Not now" : (install.phase == .finished && !showingFilms && !install.trustNeeded ? AddMore.updateWayIn : nil),
            quietAction: failed ? { home.updateSetAside = true; backHome() }
                : (install.phase == .finished && !showingFilms && !install.trustNeeded ? { backHome(); home.openAddMore() } : nil),
            // Nine small pictures need a little less room than the six large
            // ones a first build shows, and giving back what they do not need
            // is what keeps this screen — which has the longest sentence in
            // the app — inside the window at the biggest size. (v0.9.4)
            pictureHeight: install.items.count > 6 ? 268 : 280,
            action: {
                if showingFilms {
                    withAnimation(.easeInOut(duration: 0.25)) {
                        if filmChosen != nil { filmChosen = nil } else { showingFilms = false }
                    }
                    return
                }
                if failed { start(); return }
                backHome()
            }
        ) {
            if showingFilms {
                FilmsPanel(chosen: $filmChosen)
            } else {
            VStack(spacing: Theme.pt(8)) {
                LazyVGrid(columns: Array(repeating: GridItem(.fixed(Theme.pt(150)), spacing: Theme.pt(16)), count: 3), spacing: Theme.pt(8)) {
                    ForEach(install.items) { item in BuildTile(item: item, small: true) }
                }
                // The diary is where the refusal is written out in full, so it is
                // offered whenever there is something to read about, not only on
                // a failure. Before v0.9.1 a refused commit reached the owner as
                // a green screen with no way through to the one file that said so.
                if failed || install.phase == .needsCommit || install.partial || done {
                    HStack(spacing: Theme.pt(6)) {
                        if failed || install.phase == .needsCommit || install.partial {
                            QuietButton(title: "Show what happened", action: { install.showDiary() })
                            ListenButton(id: "listen-show-what-happened",
                                         speech: Speech("Show what happened"),
                                         what: "the small button", size: 13)
                        }
                        // (v0.13.0) Every owner who updates is offered the two
                        // films, as a new owner is at the end of the install.
                        if done {
                            QuietButton(title: Films.offerTitle, id: "watch-films-update") {
                                withAnimation(.easeInOut(duration: 0.25)) { showingFilms = true }
                            }
                            .padding(.leading, Theme.pt(8))
                            ListenButton(id: "listen-watch-films-update", speech: Speech(Films.offerSaid),
                                         what: "the small button", size: 13)
                        }
                    }
                }
            }
            // (v0.9.5) The nine small tiles, read as one list, for the reason
            // given in `BuildScreen`: nine speakers on nine 76-point tiles would
            // crowd them, and this screen is the tightest in the window.
            .overlay(alignment: .top) {
                ListenButton(id: BuildScreen.listenId, speech: BuildScreen.listSpeech(install),
                             what: "the list")
                    .frame(width: Theme.pt(BuildScreen.stripWidth), alignment: .trailing)
            }
            }
        }
        .onAppear {
            guard !still, install.phase == .idle else { return }
            start()
        }
    }

    private func start() {
        guard let vault = home.vault, let pack = flow.bundledPack else { return }
        // The answer, if this update asked which assistant first; nothing if it did not.
        install.startUpdate(home: flow.home, vault: vault, bundledPack: pack, answered: flow.updateAssistant)
    }

    private func backHome() {
        // An update that said ChatGPT is waiting for the owner's trust (it added
        // the guard's entry to ChatGPT's hooks list) shows the Trust screen even
        // if the owner put it off earlier in this opening of the app: that was
        // an answer about the entry as it was. An update that only replaced the
        // guard file says no such thing, and nothing is shown.
        if install.trustNeeded { home.trustSetAside = false }
        home.load(home: flow.home, bundledPack: flow.bundledPack)
        flow.mode = .home
    }
}
