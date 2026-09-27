import SwiftUI

/// The build itself: pictures that light up as the engine reports each step.
struct BuildScreen: View {
    /// Drawn again when the owner presses "Bigger text". (v0.9.4)
    @ObservedObject private var textSize = TextSize.shared
    @EnvironmentObject var flow: Flow
    @EnvironmentObject var install: InstallRun
    @Environment(\.stillPicture) private var still

    var body: some View {
        ScreenFrame(
            sentence: sentence,
            buttonTitle: buttonTitle,
            buttonEnabled: install.phase != .running && install.phase != .idle,
            showsBack: false,
            quietTitle: isFailed ? "Show what happened" : nil,
            quietAction: isFailed ? { install.showDiary() } : nil,
            action: act
        ) {
            VStack(spacing: Theme.pt(12)) {
                LazyVGrid(columns: Array(repeating: GridItem(.fixed(Theme.pt(150)), spacing: Theme.pt(16)), count: 3),
                          spacing: Theme.pt(install.items.count > 6 ? 8 : 16)) {
                    ForEach(install.items) { item in
                        BuildTile(item: item, small: install.items.count > 6)
                    }
                }
                if install.phase == .running {
                    Text("\(install.items.filter { $0.state == .done }.count) of \(install.items.count)")
                        .font(Theme.font(14, .semibold))
                        .foregroundStyle(.secondary)
                        .contentTransition(.numericText())
                }
            }
            // (v0.9.5) One listen control for the whole list, not one for each of
            // the six or nine tiles. A build tile carries two or three words and
            // is 150 by 76 at the smallest; nine speakers on nine of them would
            // crowd the tiles they belong to, which is the one thing a small
            // control on a full screen must not do. Read together the tiles ARE
            // one block — the list of what is being made, and how far it has got —
            // and that is what this reads. It sits in the corner of the room the
            // grid is given, not in the grid, so nothing in the layout moves: this
            // screen carries the longest sentence in the app and is the tightest
            // in the window at the biggest text size.
            //
            // The strip it is given is as wide as the grid and a little more
            // (three columns of 150 with 16 between them is 482), so it lands
            // just outside the grid's top corner and plainly belongs to it,
            // rather than away at the edge of the window where the picture area
            // really ends.
            .overlay(alignment: .top) {
                ListenButton(id: Self.listenId, speech: Self.listSpeech(install), what: "the list")
                    .frame(width: Theme.pt(Self.stripWidth), alignment: .trailing)
            }
        }
        .onAppear {
            guard !still, install.phase == .idle else { return }
            begin()
        }
    }

    static let listenId = "listen-build-list"

    /// Wide enough to hold the grid of tiles and leave the listen control just
    /// clear of its corner. (v0.9.5)
    static let stripWidth: CGFloat = 530

    /// Each thing being made, in the words on its own tile, and where it has got
    /// to — which no owner could hear before, since the tiles were silent and the
    /// sentence above them says only "Building your wiki…". (v0.9.5)
    static func listSpeech(_ install: InstallRun) -> Speech {
        let done = install.items.filter { $0.state == .done }.count
        var said = "\(done) of \(install.items.count) done."
        for item in install.items { said += " " + BuildTile.said(item) }
        return Speech(said)
    }

    private var isFailed: Bool {
        if case .failed = install.phase { return true }
        return false
    }

    private var why: String {
        if case .failed(let w) = install.phase { return w }
        return ""
    }

    private var sentence: String {
        switch install.phase {
        case .idle, .running: return "Building your wiki…"
        case .finished:
            // a step the engine carries on past (Claude's skills) can fail without stopping the build
            return install.items.contains { $0.state == .failed }
                ? "Your wiki is ready. One part needs a repair: open Moblee again later and press Repair."
                : "Your wiki is ready."
        case .needsCommit:
            // the words name the *install*, because this screen is only ever a
            // first build; the update screen says "update" for the same reason
            return "Your wiki is ready, but one thing is not saved into its history. "
                 + "Open your assistant and say: the Moblee install did not commit, please look and commit it."
        case .failed(let why):
            switch why {
            case "place-taken": return "There is already a folder with that name. Nothing was changed."
            case "no-room": return "This Mac is almost full, so nothing was started. Make some room, then try again."
            case "safety-layer": return "The guard could not switch on, so the build stopped. Nothing of yours was changed."
            case "no-pack", "pack-copy": return "This copy of Moblee is incomplete. Download it again."
            default: return "Something stopped the build. Nothing of yours was changed."
            }
        }
    }

    private var buttonTitle: String {
        switch install.phase {
        case .failed: return why == "place-taken" ? "Change the name" : "Try again"
        default: return "Next"
        }
    }

    private func act() {
        switch install.phase {
        case .failed:
            if why == "place-taken" {
                install.phase = .idle
                flow.chosenPlace = nil
                flow.step = .name
            } else {
                begin()       // into the same folder: the installer finishes what it started
            }
        default: flow.next()
        }
    }

    private func begin() {
        guard let pack = flow.bundledPack else {
            install.phase = .failed(why: "no-pack")
            return
        }
        // A second try goes into the same folder as the first: the installer
        // finishes a half-built wiki and never makes a second one beside it.
        let place = flow.resumePlace ?? flow.chosenPlace ?? flow.freeLocation()
        flow.chosenPlace = place
        install.start(home: flow.home, ownerName: flow.trimmedName,
                      wikiName: place.name, location: place.url, bundledPack: pack,
                      assistant: flow.assistant ?? .claude)
    }
}

struct BuildTile: View {
    let item: InstallRun.Item
    var small = false
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @ObservedObject private var textSize = TextSize.shared

    var body: some View {
        VStack(spacing: Theme.pt(small ? 4 : 8)) {
            ZStack(alignment: .bottomTrailing) {
                Image(systemName: item.symbol)
                    .font(Theme.font(small ? 24 : 34, .medium, .default))
                    .foregroundStyle(colour)
                    .frame(width: Theme.pt(small ? 44 : 64), height: Theme.pt(small ? 40 : 64))
                    .symbolEffect(.pulse, options: .repeating, isActive: item.state == .running && !reduceMotion)
                    .symbolEffect(.bounce, value: item.state == .done && !reduceMotion)
                if item.state == .done {
                    Image(systemName: "checkmark.circle.fill")
                        .font(Theme.font(small ? 16 : 22, .regular, .default))
                        .foregroundStyle(.white, Theme.good)
                        .transition(.scale.combined(with: .opacity))
                } else if item.state == .failed {
                    Image(systemName: "exclamationmark.circle.fill")
                        .font(Theme.font(small ? 16 : 22, .regular, .default))
                        .foregroundStyle(.white, .red)
                        .transition(.scale.combined(with: .opacity))
                }
            }
            .accessibilityHidden(true)
            Text(item.label)
                .font(Theme.font(small ? 13 : 15, .semibold))
                .foregroundStyle(item.state == .waiting ? .secondary : .primary)
        }
        .frame(width: Theme.pt(150), height: Theme.pt(small ? 76 : 118))
        .background(CardBackground(corner: small ? 16 : 20, dimmed: item.state == .waiting))
        .opacity(item.state == .waiting ? 0.6 : 1)
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(item.label)
        .accessibilityValue(stateWord)
    }

    private var stateWord: String { Self.stateWord(item) }

    static func stateWord(_ item: InstallRun.Item) -> String {
        switch item.state {
        case .waiting: return "waiting"
        case .running: return "being made now"
        case .done: return "done"
        case .failed: return "did not work"
        }
    }

    /// One tile, as it is read aloud: the words on it, then where it has got to.
    /// (v0.9.5)
    static func said(_ item: InstallRun.Item) -> String {
        item.label + ": " + stateWord(item) + "."
    }

    private var colour: Color {
        switch item.state {
        case .waiting: return .secondary
        case .running: return Theme.accent
        case .done: return Theme.good
        case .failed: return .red
        }
    }
}
