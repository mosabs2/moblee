import SwiftUI
import AppKit

/// The screen a returning owner sees.
struct HomeScreen: View {
    @EnvironmentObject var flow: Flow
    @EnvironmentObject var home: HomeModel
    @Environment(\.stillPicture) private var still
    @State private var repairing = false

    private var waiting: [HomeModel.Tile] { home.tiles.filter { $0.state != .done } }
    /// Three at a time. The ones that can simply be added come first; ones the
    /// owner has been sent elsewhere to finish, or that cannot be added, come
    /// after them; the rest take their place as these are dealt with.
    private var shown: [HomeModel.Tile] {
        let rank: (HomeModel.Tile) -> Int = { t in
            switch t.state {
            case .running: return 0
            case .waiting, .failed: return 1
            case .handedOver: return 2
            case .blocked: return 3
            case .done: return 4
            }
        }
        return Array(home.tiles.sorted { rank($0) < rank($1) }.prefix(3))
    }

    /// The Trust screen is open: because the step is waiting, or because the
    /// owner pressed "Prove the guard". It stays until the owner leaves it.
    @State private var trustOpen = false

    private var showsTrust: Bool { (home.trustPending && !home.trustSetAside) || trustOpen }
    private var showsMain: Bool {
        home.explaining == nil && !home.updateAvailable && !home.needsRepair && !showsTrust
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
            } else if showsTrust {
                TrustScreen(start: home.trustPending ? .steps : .offer, vault: home.vault?.path) {
                    trustOpen = false
                    home.trustSetAside = true
                }
                .onAppear { trustOpen = true }
            } else if home.assistant == .chatgpt {
                // The tiles are extras that Moblee sets up for Claude only. An
                // owner who uses ChatGPT alone is told so once, plainly, in
                // their place, and is never offered something that would do
                // nothing for them.
                ScreenFrame(sentence: "Connections and other extras are set up for Claude. "
                                + "Moblee does not set them up for ChatGPT yet.",
                            buttonTitle: "Open ChatGPT", showsBack: false, action: openChatGPT) {
                    Image(systemName: "bubble.left.and.bubble.right.fill")
                        .font(.system(size: 96)).foregroundStyle(Theme.accent)
                        .accessibilityHidden(true)
                }
            } else if home.listUnreadable {
                ScreenFrame(sentence: "Moblee could not read its list. Tell Claude: run a check-up.",
                            buttonTitle: "Open Claude", showsBack: false, action: openClaude) {
                    Image(systemName: "exclamationmark.triangle.fill")
                        .font(.system(size: 90)).foregroundStyle(Theme.waiting)
                        .accessibilityHidden(true)
                }
            } else if waiting.isEmpty {
                ScreenFrame(sentence: home.tiles.isEmpty ? "Nothing is waiting. Talk to Claude."
                                                         : "All added. Tell Claude it is done.",
                            buttonTitle: "Open Claude", showsBack: false, action: openClaude) {
                    Image(systemName: home.tiles.isEmpty ? "bubble.left.and.bubble.right.fill" : "checkmark.circle.fill")
                        .font(.system(size: 96))
                        .foregroundStyle(home.tiles.isEmpty ? Theme.accent : Theme.good)
                        .accessibilityHidden(true)
                }
            } else {
                // The big button does the job the screen is for: it adds the next
                // thing. Going back to Claude is the quiet one underneath.
                ScreenFrame(sentence: home.nextTile == nil
                                ? (waiting.contains { $0.state == .handedOver && $0.how == .clicks }
                                   ? "Finish these where they opened. Then press Done here."
                                   : "Finish these where they opened, then tell Claude.")
                                                           : "Claude has these ready for you.",
                            buttonTitle: home.nextTile.map { $0.kind == .skill ? "Look at the first one" : "Add the first one" } ?? "Open Claude",
                            showsBack: false,
                            quietTitle: home.nextTile == nil ? nil : "Open Claude",
                            quietAction: home.nextTile == nil ? nil : openClaude,
                            spoken: spokenList,
                            action: { if let t = home.nextTile { home.press(t) } else { openClaude() } }) {
                    VStack(spacing: 8) {
                        HStack(alignment: .top, spacing: 18) {
                            ForEach(shown) { tile in
                                RequestTile(tile: tile, press: { home.press(tile) }, done: { home.markDone(tile) })
                            }
                        }
                        if home.tiles.count > shown.count {
                            Text("and \(home.tiles.count - shown.count) more after these")
                                .font(.system(size: 13, weight: .medium, design: .rounded))
                                .foregroundStyle(.secondary)
                        }
                        if home.assistant == .both {
                            Text("These are set up for Claude. Moblee does not set them up for ChatGPT yet.")
                                .font(.system(size: 13, weight: .medium, design: .rounded))
                                .foregroundStyle(.secondary)
                        }
                    }
                    .padding(.horizontal, 30)
                }
            }
        }
        // Bottom right. The window has no title bar of its own, so its top strip
        // is where the window is dragged by, and a small control put there may
        // not take a click at all; the top is also where a two-line sentence
        // reaches. The big button and the quiet one under it sit in the middle
        // of the bottom, and this corner is free on every home screen.
        .overlay(alignment: .bottomTrailing) {
            if showsMain && !repairing { assistantControl }
        }
        .onAppear {
            guard !still else { return }
            home.startWatching()
        }
        .onDisappear { home.stopWatching() }
    }

    private var spokenList: String {
        "Claude has these ready for you. " + shown.filter { $0.state != .done }
            .map { "\($0.title). \($0.why)" }.joined(separator: " Next: ")
    }

    private var updatePrompt: some View {
        ScreenFrame(sentence: "A newer Moblee is ready for your wiki. Your pages are not touched.",
                    buttonTitle: "Update", showsBack: false,
                    quietTitle: "Not now", quietAction: { home.updateSetAside = true },
                    // On a Mac with no choice of assistant on record, the update asks first.
                    action: { flow.beginUpdate() }) {
            VStack(spacing: 14) {
                Image(systemName: "arrow.up.circle.fill")
                    .font(.system(size: 96)).foregroundStyle(Theme.accent)
                    .accessibilityHidden(true)
                Text("\(home.wikiVersion)  →  \(home.packVersion)")
                    .font(.system(size: 20, weight: .semibold, design: .rounded))
                    .foregroundStyle(.secondary)
                    .accessibilityLabel("From version \(home.wikiVersion) to \(home.packVersion)")
            }
        }
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
                .font(.system(size: 96)).foregroundStyle(home.repairFailed ? .red : Theme.waiting)
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
            VStack(spacing: 14) {
                Image(systemName: "arrow.down.app.fill")
                    .font(.system(size: 96)).foregroundStyle(Theme.waiting)
                    .accessibilityHidden(true)
                Text("Your wiki: \(home.wikiVersion)   This Moblee: \(home.packVersion)")
                    .font(.system(size: 17, weight: .semibold, design: .rounded))
                    .foregroundStyle(.secondary)
                    .accessibilityLabel("Your wiki is version \(home.wikiVersion). This Moblee is version \(home.packVersion).")
            }
        }
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
        VStack(alignment: .trailing, spacing: 0) {
            if home.wikiIsNewerThanApp {
                Text(Self.changeNeedsNewest)
                    .font(.system(size: 12, weight: .medium, design: .rounded))
                    .foregroundStyle(.secondary)
                    .padding(.trailing, 9)
            }
            HStack(spacing: 2) {
                Text("Assistant: \(home.assistant.name)")
                    .foregroundStyle(.secondary)
                    .padding(.trailing, home.canChangeAssistant || home.assistant.wantsChatGPT ? 6 : 9)
                if home.canChangeAssistant {
                    cornerButton("Change", id: "change-assistant") { flow.beginUpdate(changingAssistant: true) }
                }
                if home.assistant.wantsChatGPT {
                    cornerButton("Prove the guard", id: "prove-guard") { trustOpen = true }
                }
            }
        }
        .font(.system(size: 12, weight: .semibold, design: .rounded))
        // Low enough that the upper line clears the big button, and far enough
        // right that the lower one clears the quiet button in the middle.
        .padding(.trailing, 12).padding(.bottom, 4)
    }

    /// Small words, but a target a finger on a trackpad does not miss: the
    /// whole padded box takes the click, not the letters alone.
    private func cornerButton(_ title: String, id: String, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            Text(title)
                .padding(.horizontal, 9).padding(.vertical, 6)
                .contentShape(Rectangle())
        }
        .buttonStyle(.plain).foregroundStyle(Theme.accent)
        .accessibilityIdentifier(id)
    }
}

struct RequestTile: View {
    let tile: HomeModel.Tile
    let press: () -> Void
    let done: () -> Void
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    var body: some View {
        VStack(spacing: 8) {
            Image(systemName: tile.state == .done ? "checkmark.circle.fill" : tile.symbol)
                .font(.system(size: 40, weight: .medium))
                .foregroundStyle(tile.state == .done ? Theme.good
                                 : ((tile.state == .failed || tile.state == .blocked) ? .red : Theme.accent))
                .frame(height: 50)
                .symbolEffect(.pulse, options: .repeating, isActive: tile.state == .running && !reduceMotion)
                .accessibilityHidden(true)
            Text(tile.title)
                .font(.system(size: 15, weight: .semibold, design: .rounded))
                .multilineTextAlignment(.center).lineLimit(2).minimumScaleFactor(0.85)
            Text(tile.note.isEmpty ? tile.why : tile.note)
                .font(.system(size: 13, weight: .regular, design: .rounded))
                .foregroundStyle(tile.note.isEmpty ? Color.primary.opacity(0.85) : Theme.badText)
                .multilineTextAlignment(.center).lineLimit(3).minimumScaleFactor(0.85)
            if tile.kind != .skill {
                HStack(spacing: 4) {
                    if tile.paid { Image(systemName: "creditcard.fill").accessibilityHidden(true) }
                    Text(tile.detail)
                }
                .font(.system(size: 13, weight: .medium, design: .rounded))
                .foregroundStyle(tile.paid ? Theme.waitingText : Color.secondary)
                .multilineTextAlignment(.center)
            }
            Spacer(minLength: 0)
            Group {
                switch tile.state {
                case .waiting:
                    Button(tile.kind == .skill ? "Look" : "Add", action: press)
                        .buttonStyle(.borderedProminent).tint(Theme.accent).controlSize(.large)
                case .running:
                    Label("Adding…", systemImage: "arrow.triangle.2.circlepath")
                        .foregroundStyle(Theme.waitingText)
                case .handedOver:
                    HStack(spacing: 8) {
                        // Anything done by clicks inside Claude, whether it is on the
                        // pack's list (Google) or not, is finished by the owner's word:
                        // nothing outside Claude can see those connections.
                        if tile.how == .clicks {
                            Button("Done", action: done).buttonStyle(.borderedProminent).tint(Theme.good)
                        }
                        Button("Again", action: press).buttonStyle(.bordered)
                    }
                    .controlSize(.regular)
                case .done:
                    Text("Added").foregroundStyle(Theme.goodText)
                case .failed:
                    Button("Try again", action: press)
                        .buttonStyle(.bordered).controlSize(.large)
                case .blocked:
                    Text("Tell Claude").foregroundStyle(Theme.badText)
                }
            }
            .font(.system(size: 14, weight: .semibold, design: .rounded))
            .frame(height: 34)
        }
        .padding(.horizontal, 12).padding(.vertical, 14)
        .frame(width: 200, height: 262)
        .background(CardBackground())
        .accessibilityElement(children: .contain)
        .accessibilityLabel("\(tile.title). \(tile.why)")
        .accessibilityValue(stateWord)
    }

    private var stateWord: String {
        switch tile.state {
        case .waiting: return "waiting to be added"
        case .running: return "being added"
        case .handedOver: return "opened elsewhere, to be finished there"
        case .done: return "added"
        case .failed: return "did not work. \(tile.note)"
        case .blocked: return "cannot be added. \(tile.note)"
        }
    }
}

/// Shown before anything is added that the owner should see first: a skill
/// Claude wrote, a Terminal window, or clicks inside Claude.
struct ExplainScreen: View {
    @EnvironmentObject var home: HomeModel
    @Environment(\.stillPicture) private var still
    let tile: HomeModel.Tile

    private var isSkill: Bool { tile.kind == .skill }
    private var isTerminal: Bool { tile.kind == .item && tile.how == .terminal }

    var body: some View {
        ScreenFrame(
            sentence: isSkill ? "Claude wrote this skill for you. It will work in every Claude session on this Mac."
                : (isTerminal ? "A black window opens and types for itself. Follow it, then come back."
                              : "Do these three in Claude. Then come back and press Done."),
            buttonTitle: isSkill ? "Add it" : (isTerminal ? "Open it" : "Show me"),
            showsBack: false,
            quietTitle: "Not now", quietAction: { home.explaining = nil },
            spoken: isSkill ? "Claude wrote this skill for you. It says: \(tile.detail)" : nil,
            action: {
                if isSkill { home.addSkill(tile) }
                else if isTerminal { home.openTerminal(for: tile) }
                else { home.openClicks(for: tile) }
                home.explaining = nil
            }
        ) {
            if isSkill {
                skillPreview
            } else if isTerminal {
                HStack(alignment: .top, spacing: 18) {
                    HandoffCard(number: 1, symbol: "terminal.fill", title: "It types for itself",
                                detail: "Press Return if it asks you to")
                    HandoffCard(number: 2, symbol: "key.fill", title: "Your Mac password",
                                detail: "Nothing shows as you type. That is normal.")
                    HandoffCard(number: 3, symbol: "clock.fill", title: "Wait",
                                detail: "Downloads take a while. Then close it.")
                }
                .padding(.horizontal, 30)
            } else if tile.steps.count == 3 {
                // The pack's own three cards for this item: where to go, what to
                // switch on by name, and how to tell it worked. Without them an
                // owner lands in Claude with nothing to look for.
                HStack(alignment: .top, spacing: 18) {
                    HandoffCard(number: 1, symbol: "gearshape.fill", title: tile.steps[0][0], detail: tile.steps[0][1])
                    HandoffCard(number: 2, symbol: "link", title: tile.steps[1][0], detail: tile.steps[1][1])
                    HandoffCard(number: 3, symbol: "text.bubble.fill", title: tile.steps[2][0], detail: tile.steps[2][1])
                }
                .padding(.horizontal, 30)
            } else {
                HStack(alignment: .top, spacing: 18) {
                    HandoffCard(number: 1, symbol: "gearshape.fill", title: "Connectors",
                                detail: "The page opens. If it says moved: Customise, then Connectors")
                    HandoffCard(number: 2, symbol: "link", title: "Connect \(tile.key)",
                                detail: tile.paid ? "Press Connect and sign in. Paying is your choice"
                                                  : "Find it, press Connect, sign in with your own account")
                    HandoffCard(number: 3, symbol: "text.bubble.fill", title: "Check it worked",
                                detail: "Ask Claude to use it. If it answers, it is connected")
                }
                .padding(.horizontal, 30)
            }
        }
    }

    /// The one line the skill says about itself, then the whole of what Claude
    /// would be told to do, so that the owner is never adding words unseen.
    private var skillPreview: some View {
        let whole = "WHAT IT SAYS IT DOES\n\(tile.detail.isEmpty ? "It does not say." : tile.detail)\n\n"
            + "EVERYTHING CLAUDE WOULD BE TOLD (\(tile.files.count) file\(tile.files.count == 1 ? "" : "s"): "
            + tile.files.prefix(6).joined(separator: ", ") + ")\n\(tile.body)"
        return VStack(alignment: .leading, spacing: 8) {
            Label(tile.key, systemImage: "wand.and.stars")
                .font(.system(size: 18, weight: .semibold, design: .rounded))
            Group {
                if still {
                    // a scrolling area cannot be drawn to a picture file
                    Text(whole).frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
                } else {
                    ScrollView { Text(whole).frame(maxWidth: .infinity, alignment: .leading).textSelection(.enabled) }
                }
            }
            .font(.system(size: 13, design: .rounded))
        }
        .padding(16)
        .frame(width: 600, height: 270, alignment: .topLeading)
        .background(CardBackground(corner: 20))
    }
}

/// The update, shown the same way as the first build.
struct UpdateScreen: View {
    @EnvironmentObject var flow: Flow
    @EnvironmentObject var home: HomeModel
    @EnvironmentObject var install: InstallRun
    @Environment(\.stillPicture) private var still

    private var failed: Bool { if case .failed = install.phase { return true }; return false }

    var body: some View {
        ScreenFrame(
            sentence: install.phase == .finished ? "Your wiki is up to date."
                : (failed ? "The update stopped. Your pages were not touched." : "Updating your wiki…"),
            buttonTitle: failed ? "Try again" : "Done",
            buttonEnabled: install.phase == .finished || failed,
            showsBack: false,
            quietTitle: failed ? "Not now" : nil,
            quietAction: failed ? { home.updateSetAside = true; backHome() } : nil,
            action: {
                if failed { start(); return }
                backHome()
            }
        ) {
            VStack(spacing: 8) {
                LazyVGrid(columns: Array(repeating: GridItem(.fixed(150), spacing: 16), count: 3), spacing: 8) {
                    ForEach(install.items) { item in BuildTile(item: item, small: true) }
                }
                if failed { QuietButton(title: "Show what happened", action: { install.showDiary() }) }
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
        // An update that put a new guard in place for ChatGPT asks for the
        // owner's trust again, even if they put the Trust screen off earlier
        // in this opening of the app: that was an answer about the old guard.
        if install.trustNeeded { home.trustSetAside = false }
        home.load(home: flow.home, bundledPack: flow.bundledPack)
        flow.mode = .home
    }
}
