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
        let rank: (HomeModel.Tile) -> Int = { t in
            switch t.state {
            case .running: return 0
            case .waiting, .failed: return 1
            case .handedOver: return 2
            case .blocked: return 3
            case .done: return 4
            }
        }
        return Array(tiles.sorted { rank($0) < rank($1) }.prefix(3))
    }

    /// The Trust screen is open: because the step is waiting, or because the
    /// owner pressed "Prove the guard". It stays until the owner leaves it.
    @State private var trustOpen = false

    private var showsTrust: Bool { (home.trustPending && !home.trustSetAside) || trustOpen }
    private var showsMain: Bool {
        home.explaining == nil && !home.updateAvailable && !home.needsRepair
            && !home.showsForeignSkills && !showsTrust
    }

    var body: some View {
        ZStack {
            if let tile = home.explaining {
                ExplainScreen(tile: tile)
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
                    trustOpen = false
                    home.trustSetAside = true
                }
                .onAppear { trustOpen = true }
            } else if home.assistant == .chatgpt {
                // (v0.9.6) On this screen and the two below it, the second big
                // button opens the example wiki; see `exampleTitle`.
                // The tiles are extras that Moblee sets up for Claude only. An
                // owner who uses ChatGPT alone is told so once, plainly, in
                // their place, and is never offered something that would do
                // nothing for them.
                ScreenFrame(sentence: "Connections and other extras are set up for Claude. "
                                + "Moblee does not set them up for ChatGPT yet.",
                            buttonTitle: "Open ChatGPT", showsBack: false,
                            secondTitle: exampleTitle, secondAction: exampleAction,
                            action: openChatGPT) {
                    Image(systemName: "bubble.left.and.bubble.right.fill")
                        .font(Theme.font(96, .regular, .default)).foregroundStyle(Theme.accent)
                        .accessibilityHidden(true)
                }
            } else if home.listUnreadable {
                ScreenFrame(sentence: "Moblee could not read its list. Tell \(home.assistant.talksTo): run a check-up.",
                            buttonTitle: "Open Claude", showsBack: false, action: openClaude) {
                    Image(systemName: "exclamationmark.triangle.fill")
                        .font(Theme.font(90, .regular, .default)).foregroundStyle(Theme.waiting)
                        .accessibilityHidden(true)
                }
            } else if waiting.isEmpty {
                ScreenFrame(sentence: home.tiles.isEmpty ? "Nothing is waiting. Talk to Claude."
                                                         : "All added. Tell Claude it is done.",
                            buttonTitle: "Open Claude", showsBack: false,
                            secondTitle: exampleTitle, secondAction: exampleAction,
                            action: openClaude) {
                    Image(systemName: home.tiles.isEmpty ? "bubble.left.and.bubble.right.fill" : "checkmark.circle.fill")
                        .font(Theme.font(96, .regular, .default))
                        .foregroundStyle(home.tiles.isEmpty ? Theme.accent : Theme.good)
                        .accessibilityHidden(true)
                }
            } else {
                // The big button does the job the screen is for: it adds the next
                // thing. Going back to Claude is the quiet one underneath.
                ScreenFrame(sentence: waitingSentence,
                            buttonTitle: home.nextTile.map { $0.kind == .skill ? "Look at the first one" : "Add the first one" } ?? "Open Claude",
                            showsBack: false,
                            quietTitle: home.nextTile == nil ? nil : "Open Claude",
                            quietAction: home.nextTile == nil ? nil : openClaude,
                            secondTitle: exampleTitle, secondAction: exampleAction,
                            // (v0.9.5) A skill Claude wrote wears the name the
                            // owner asked for, in their own words, so the list is
                            // read in pieces rather than in one voice.
                            //
                            // No `spoken` beside it: `Headline.speech` gives the
                            // `speech` back before it looks at `spoken`, so the
                            // `listSpeech.plain` that used to sit here was a
                            // flattened second copy of these same words that
                            // nothing could ever read.
                            speech: listSpeech,
                            action: { if let t = home.nextTile { home.press(t) } else { openClaude() } }) {
                    VStack(spacing: Theme.pt(8)) {
                        HStack(alignment: .top, spacing: Theme.pt(18)) {
                            ForEach(shown) { tile in
                                RequestTile(tile: tile, press: { home.press(tile) }, done: { home.markDone(tile) })
                            }
                        }
                        // (v0.9.5) These two short lines belong to the list above
                        // them rather than standing on their own, so they are read
                        // by the list's own control at the top of the screen
                        // instead of growing two more buttons on a screen that
                        // already carries one for each of the three tiles.
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
        // The bottom corner the reading ends at. The window has no title bar of
        // its own, so its top strip is where the window is dragged by, and a
        // small control put there may not take a click at all; the top is also
        // where a two-line sentence reaches. The big button and the quiet one
        // under it sit in the middle of the bottom, and this corner is free on
        // every home screen.
        //
        // (v0.9.4) The two corners are named in `Layout` and are SwiftUI's own,
        // so they swap over when the layout is mirrored and the two lines never
        // land in the same corner.
        .overlay(alignment: Layout.assistantCorner) {
            if showsMain && !repairing { assistantControl }
        }
        // The other bottom corner, the one the assistant control leaves free: a
        // newer Moblee is out. Only on the ordinary home screen, never over an
        // update, a repair or the Trust steps, and never in an install.
        .overlay(alignment: Layout.newerReleaseCorner) {
            if showsMain && !repairing && home.newerReleaseLineAllowed, let v = home.newerRelease { newerReleaseLine(v) }
        }
        .onAppear {
            guard !still else { return }
            home.startWatching()
        }
        .onDisappear { home.stopWatching() }
    }

    /// The sentence at the top of the home screen when something is waiting.
    /// Named, so that the listen control beside it reads the screen's own words
    /// and not a second copy of them. (v0.9.5)
    private var waitingSentence: String {
        guard home.nextTile == nil else { return "Claude has these ready for you." }
        return waiting.contains { $0.state == .handedOver && $0.how == .clicks }
            ? "Finish these where they opened. Then press Done here."
            : "Finish these where they opened, then tell Claude."
    }

    static func moreAfterThese(tiles: Int, shown: Int) -> String? {
        tiles > shown ? "and \(tiles - shown) more after these" : nil
    }

    /// (v0.9.5) Every control the keyboard stops at on this screen, in the
    /// order Tab reaches them, written here beside the code that draws them.
    ///
    /// It is here and not in the check because a list of names typed out in a
    /// check is a list of what somebody believed the screen had on it. The one
    /// that used to stand there was sixteen strings long and was asserted to
    /// have no repeats and to be no longer than sixteen — both of which are
    /// true of any list of sixteen different strings, so neither could ever
    /// have failed. It also left out the Done button that each handed-over
    /// tile grows, which is three more stops than anybody had counted.
    ///
    /// The live walk presses Tab round the real window and requires the real
    /// ring to be exactly this, so the two cannot drift apart: a control added
    /// to the screen and not to this fails the walk, and a control here that
    /// the screen does not draw fails it too.
    ///
    /// The order is the one the keyboard really takes, which on this Mac is row
    /// by row down the window and, within a row, from the reading edge across —
    /// so the bottom row is the newer-Moblee line in the near corner, then the
    /// quiet words in the middle, then the line about the assistant in the far
    /// corner. Each listen control is inside its own group and never between
    /// two of another's; see `newerReleaseLine` for the one that had to move.
    static func stops(shown: [HomeModel.Tile], nextTileWaiting: Bool,
                      canChangeAssistant: Bool, wantsChatGPT: Bool,
                      newerRelease: Bool, showsExample: Bool = false) -> [String] {
        var ring = ["bigger-text", "read-aloud"]
        for tile in shown { ring += RequestTile.stops(tile) }
        // (v0.9.6) "See an example wiki" is the second big button, in the row of
        // big buttons, which the keyboard reaches after the cards above it and
        // before the three quiet lines along the bottom. The first big button is
        // not on this round at all and never has been: it is the window's default
        // action, pressed by Return from anywhere. The second one is not, so it
        // takes the keyboard like every other control.
        if showsExample { ring.append("second-button") }
        if nextTileWaiting { ring += ["quiet", "listen-quiet"] }
        // (v0.9.6) The check-up the owner runs themselves, in the corner with
        // the line about the assistant and on the line above it. It is read by
        // that line's own listen control rather than growing one of its own,
        // which is why it adds one stop and not two. Being on a line of its own
        // above the bottom row, the keyboard reaches it before anything on that
        // row: before the newer-Moblee line, "Change" and "Prove the guard".
        // (First written after them; the live-window walk of 27 September 2026
        // measured the real round and put it here.)
        ring.append("check-wiki")
        if newerRelease { ring += ["listen-newer-line", "download-newer", "newer-not-now"] }
        if canChangeAssistant { ring.append("change-assistant") }
        if wantsChatGPT { ring.append("prove-guard") }
        ring.append("listen-assistant-line")
        return ring
    }

    /// The most controls this screen can ever have on it at once, which is the
    /// number the keyboard has to be able to cross.
    ///
    /// Worked out from `stops` rather than counted by eye: one tile still to
    /// be added (which is what puts the quiet words under the big button) and
    /// two handed over by clicks (which is what grows a Done button each),
    /// with both corner lines showing and an owner who uses both assistants.
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

    static func busiest() -> [String] {
        stops(shown: busiestTiles(), nextTileWaiting: true,
              canChangeAssistant: true, wantsChatGPT: true, newerRelease: true,
              // (v0.9.6) A released Moblee always carries the example, so the
              // busiest screen always has the way into it on it.
              showsExample: true)
    }

    /// (v0.9.6) The second big button on the ordinary home screen: the way into
    /// the example wiki for an owner who already HAS a wiki. It is the same four
    /// words as the way in on the welcome screen, and it is here as well as there
    /// because knowing what a wiki is for is not something an install teaches. A
    /// build with no pack behind it has no example, and then there is no button.
    private var exampleTitle: String? { flow.hasExample ? ExampleReader.wayIn : nil }
    private var exampleAction: (() -> Void)? { flow.hasExample ? { flow.openExample() } : nil }

    static let claudeOnly = "These are set up for Claude. Moblee does not set them up for ChatGPT yet."

    /// (v0.9.5) The whole of what is waiting, read from the top of the screen:
    /// the sentence, then each tile in the words the tile itself shows, then the
    /// two short lines under the tiles. It was the sentence and the tiles' titles
    /// and reasons only, in one voice, and it left out what each thing costs,
    /// where each had got to, how many more there were, and the line saying these
    /// are for Claude alone.
    private var listSpeech: Speech {
        var said = Speech(waitingSentence)
        for tile in shown where tile.state != .done { said = said + RequestTile.speech(for: tile) }
        if let more = Self.moreAfterThese(tiles: home.tiles.count, shown: shown.count) {
            said = said + Speech(more)
        }
        if home.assistant == .both { said = said + Speech(Self.claudeOnly) }
        return said
    }

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

    /// Small and quiet, in the corner: which assistant the wiki is for, a way
    /// to change it (the question, then the updater with the answer), and, for
    /// an owner who uses ChatGPT, a way to put the guard to the test.
    ///
    /// Change is made by this app's updater, so it is not offered on a wiki a
    /// newer Moblee made (the words say where to go instead), nor while
    /// something is being added.
    private var assistantControl: some View {
        VStack(alignment: .trailing, spacing: Theme.pt(0)) {
            if home.wikiIsNewerThanApp {
                Text(Self.changeNeedsNewest)
                    .font(Theme.font(12, .medium))
                    .foregroundStyle(.secondary)
                    .padding(.trailing, Theme.pt(9))
            }
            // (v0.9.6) One press, and the pack's own read-only check-up runs and
            // saves its report where whoever looks after Moblee expects it. It
            // used to take a file dropped in `raw/`, an exact sentence said to an
            // assistant, a permission prompt for every command and then a hunt
            // through Finder, and several owners could not do it.
            //
            // On a line of its own above the assistant's, not beside it. On the
            // line, an owner who uses both assistants had "Assistant: Both",
            // "Change", "Prove the guard" and this one in a row long enough to
            // run under the quiet words in the middle of the window, and the two
            // touched. Above, it sits at the same height as those quiet words and
            // well clear of them, in the corner the reading ends at.
            cornerButton(Self.checkWiki, id: "check-wiki",
                         enabled: flow.canBeginClinic) { flow.beginClinic() }
            HStack(spacing: Theme.pt(2)) {
                Text("Assistant: \(home.assistant.name)")
                    .foregroundStyle(.secondary)
                    .padding(.trailing, home.canChangeAssistant || home.assistant.wantsChatGPT ? 6 : 9)
                if home.canChangeAssistant {
                    cornerButton("Change", id: "change-assistant") { flow.beginUpdate(changingAssistant: true) }
                }
                if home.assistant.wantsChatGPT {
                    cornerButton("Prove the guard", id: "prove-guard") { trustOpen = true }
                }
                // (v0.9.5) One control for the whole quiet line, its own small
                // buttons included: their words are the only thing saying what
                // they do, and an owner who would rather be told than read had no
                // way to find out. One rather than one each, because the line is
                // read as a line — "Assistant: Claude. Change. Prove the guard."
                ListenButton(id: "listen-assistant-line", speech: assistantLineSpeech,
                             what: "the line about your assistant", size: 13)
                    .padding(.leading, Theme.pt(4))
            }
        }
        .font(Theme.font(12, .semibold))
        // Low enough that the upper line clears the big button, and far enough
        // right that the lower one clears the quiet button in the middle.
        .padding(.trailing, Theme.pt(12)).padding(.bottom, Theme.pt(4))
    }

    /// What the quiet line in the other bottom corner says, its own two small
    /// buttons included. (v0.9.5)
    private var assistantLineSpeech: Speech {
        var said = "Assistant: \(home.assistant.name)."
        if home.wikiIsNewerThanApp { said += " " + Self.changeNeedsNewest }
        if home.canChangeAssistant { said += " There is a button beside it: Change." }
        if home.assistant.wantsChatGPT { said += " And a button: Prove the guard." }
        // (v0.9.6) The check-up is on this line too, and this is the only thing
        // on the screen that says what its words do.
        said += " And a button: \(Self.checkWiki). It looks at your wiki and saves a report you can send."
        return Speech(said)
    }

    /// The words on the check-up's button. Plain, and about the owner's wiki
    /// rather than about a clinic or a check-up, which are the maintainer's
    /// words and not theirs. (v0.9.6)
    static let checkWiki = "Check my wiki"

    static func newerReleaseSaid(_ version: String) -> String {
        "Moblee \(version) is out. There are two buttons beside it: Download, and Not now."
    }

    /// "Moblee 0.9.3 is out." with Download (the app itself, opened in the
    /// browser; nothing is downloaded or run by this app) and Not now (this
    /// version is not offered again).
    private func newerReleaseLine(_ version: String) -> some View {
        HStack(spacing: Theme.pt(2)) {
            // (v0.9.5) One control for the whole line, as the other corner has.
            // An owner who cannot read this line will never press Download, and
            // Download is the only way a newer Moblee reaches them.
            //
            // It stands at the START of this line and not at the end of it, and
            // the reason is the keyboard. Tab crosses a row of controls from
            // the reading edge across, and this line ends close to where the
            // quiet words under the big button begin: with the speaker at the
            // end, the keyboard went Download, Not now, the quiet words, THIS,
            // and then the quiet words' own speaker — so neither line's speaker
            // stood beside the words it reads. At the start of the line the
            // three of them are one run with nothing of another corner's inside
            // it, whichever way round the screen is laid out.
            ListenButton(id: "listen-newer-line", speech: Speech(Self.newerReleaseSaid(version)),
                         what: "the line about a newer Moblee", size: 13)
                .padding(.leading, Theme.pt(9)).padding(.trailing, Theme.pt(4))
            Text("Moblee \(version) is out.")
                .foregroundStyle(.secondary)
                .padding(.trailing, Theme.pt(6))
            cornerButton("Download", id: "download-newer") {
                if !flow.isTestMode, let url = NewerRelease.downloadURL(for: version) {
                    NSWorkspace.shared.open(url)
                }
            }
            .accessibilityLabel("Download Moblee \(version)")
            cornerButton("Not now", id: "newer-not-now") { home.setAsideNewerRelease() }
                .accessibilityLabel("Not now, do not offer Moblee \(version) again")
        }
        .font(Theme.font(12, .semibold))
        .padding(.leading, Theme.pt(12)).padding(.bottom, Theme.pt(4))
        .accessibilityElement(children: .contain)
    }

    /// Small words, but a target a finger on a trackpad does not miss: the
    /// whole padded box takes the click, not the letters alone.
    /// (v0.9.6) `enabled: false` greys the words and stops both roads into the
    /// action, the click and the keyboard's own press. A corner button that can
    /// be pressed and does nothing is worse than one that shows it cannot be.
    private func cornerButton(_ title: String, id: String, enabled: Bool = true,
                              action: @escaping () -> Void) -> some View {
        Button(action: { if enabled { action() } }) {
            Text(title)
                .padding(.horizontal, Theme.pt(9)).padding(.vertical, Theme.pt(6))
                .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .foregroundStyle(enabled ? Theme.accent : Color.secondary)
        .disabled(!enabled)
        // (v0.9.4) Reachable by the keyboard, with a ring that can be seen,
        // and still where it says it is drawn for the self-drive walk.
        .keyboardReachable(id, corner: 8, press: { if enabled { action() } })
    }
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
    /// (v0.9.5) And the tile's own listen control.
    static func listenId(_ tile: HomeModel.Tile) -> String { "listen-tile-" + tile.key }

    /// (v0.9.5) Every control this tile puts on the keyboard's round, in the
    /// order it lays them out: its buttons, and then its own listen control
    /// beside them. Written here beside `body`, which is the only other place
    /// that decides which buttons a tile in a given state has.
    static func stops(_ tile: HomeModel.Tile) -> [String] {
        var ring: [String] = []
        switch tile.state {
        case .waiting, .failed:
            ring.append(buttonId(tile))
        case .handedOver:
            if tile.how == .clicks { ring.append(doneId(tile)) }
            ring.append(buttonId(tile))
        case .running, .done, .blocked:
            break                                   // words, not buttons
        }
        ring.append(listenId(tile))
        return ring
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
            // (v0.9.5) The tile's own listen control sits in this row, beside
            // the tile's own buttons, and no longer in the card's top corner.
            //
            // The corner was the tidier place to draw it and the wrong place to
            // reach it from. The keyboard crosses this screen in the order the
            // controls are laid out down the window, so three speakers in three
            // top corners came as a run of three, one after another, before any
            // of the three Add buttons: an owner pressing Tab met "listen,
            // listen, listen, Add, Add, Add" and could not tell from where they
            // were which speaker belonged to which tile. Beside the button it
            // belongs to, the keyboard goes tile by tile, which is how the
            // screen reads.
            HStack(spacing: Theme.pt(8)) {
            Group {
                switch tile.state {
                case .waiting:
                    // The words are given their size on the label itself. A
                    // bordered button keeps its own font and pays no attention
                    // to one set on everything around it, so at the biggest
                    // size these were the only small words left on the screen.
                    // (v0.9.4)
                    Button(action: press) {
                        Text(tile.kind == .skill ? "Look" : "Add").font(Theme.font(14, .semibold))
                    }
                    .buttonStyle(.borderedProminent).tint(Theme.accent).controlSize(.large)
                    .keyboardReachable(Self.buttonId(tile), corner: 6, press: press)
                case .running:
                    Label("Adding…", systemImage: "arrow.triangle.2.circlepath")
                        .foregroundStyle(Theme.waitingText)
                case .handedOver:
                    HStack(spacing: Theme.pt(8)) {
                        // Anything done by clicks inside Claude, whether it is on the
                        // pack's list (Google) or not, is finished by the owner's word:
                        // nothing outside Claude can see those connections.
                        if tile.how == .clicks {
                            Button(action: done) { Text("Done").font(Theme.font(14, .semibold)) }
                                .buttonStyle(.borderedProminent).tint(Theme.good)
                                .keyboardReachable(Self.doneId(tile), corner: 6, press: done)
                        }
                        Button(action: press) { Text("Again").font(Theme.font(14, .semibold)) }
                            .buttonStyle(.bordered)
                            .keyboardReachable(Self.buttonId(tile), corner: 6, press: press)
                    }
                    .controlSize(.regular)
                case .done:
                    Text("Added").foregroundStyle(Theme.goodText)
                case .failed:
                    Button(action: press) { Text("Try again").font(Theme.font(14, .semibold)) }
                        .buttonStyle(.bordered).controlSize(.large)
                        .keyboardReachable(Self.buttonId(tile), corner: 6, press: press)
                case .blocked:
                    Text("Tell Claude").foregroundStyle(Theme.badText)
                }
            }
            .font(Theme.font(14, .semibold))
                ListenButton(id: Self.listenId(tile), speech: Self.speech(for: tile),
                             what: tile.title, size: 16)
            }
            .frame(height: Theme.pt(34))
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

    private var failed: Bool { if case .failed = install.phase { return true }; return false }

    var body: some View {
        ScreenFrame(
            // (v0.9.1) `needsCommit` is its own sentence. The files all landed,
            // so "the update stopped" would be wrong; the closing commit was
            // refused, so "up to date" would be a lie — and it was the one the
            // owner used to be told, over a wiki whose update was never saved
            // into its history and whose own next commit would be refused too.
            sentence: install.phase == .needsCommit
                ? "Your wiki is updated, but the change was not saved into its history. Open your assistant and say: the Moblee update did not commit, please look and commit it."
                // (v0.9.2) A step can finish while one part inside it does not,
                // and the run used to end on a flat "up to date" over exactly
                // that. What was skipped is in the diary, which is one press away.
                : (install.phase == .finished
                    ? (install.partial
                        ? "Your wiki is up to date, but one or two things in the update did not finish. Press Show what happened."
                        : "Your wiki is up to date.")
                : (failed ? "The update stopped. Your pages were not touched." : "Updating your wiki…")),
            buttonTitle: failed ? "Try again" : "Done",
            buttonEnabled: install.phase == .finished || install.phase == .needsCommit || failed,
            showsBack: false,
            quietTitle: failed ? "Not now" : nil,
            quietAction: failed ? { home.updateSetAside = true; backHome() } : nil,
            // Nine small pictures need a little less room than the six large
            // ones a first build shows, and giving back what they do not need
            // is what keeps this screen — which has the longest sentence in
            // the app — inside the window at the biggest size. (v0.9.4)
            pictureHeight: install.items.count > 6 ? 268 : 280,
            action: {
                if failed { start(); return }
                backHome()
            }
        ) {
            VStack(spacing: Theme.pt(8)) {
                LazyVGrid(columns: Array(repeating: GridItem(.fixed(Theme.pt(150)), spacing: Theme.pt(16)), count: 3), spacing: Theme.pt(8)) {
                    ForEach(install.items) { item in BuildTile(item: item, small: true) }
                }
                // The diary is where the refusal is written out in full, so it is
                // offered whenever there is something to read about, not only on
                // a failure. Before v0.9.1 a refused commit reached the owner as
                // a green screen with no way through to the one file that said so.
                if failed || install.phase == .needsCommit || install.partial {
                    HStack(spacing: Theme.pt(6)) {
                        QuietButton(title: "Show what happened", action: { install.showDiary() })
                        ListenButton(id: "listen-show-what-happened",
                                     speech: Speech("Show what happened"),
                                     what: "the small button", size: 13)
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
