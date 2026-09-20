import SwiftUI

/// The build itself: pictures that light up as the engine reports each step.
struct BuildScreen: View {
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
            VStack(spacing: 12) {
                LazyVGrid(columns: Array(repeating: GridItem(.fixed(150), spacing: 16), count: 3),
                          spacing: install.items.count > 6 ? 8 : 16) {
                    ForEach(install.items) { item in
                        BuildTile(item: item, small: install.items.count > 6)
                    }
                }
                if install.phase == .running {
                    Text("\(install.items.filter { $0.state == .done }.count) of \(install.items.count)")
                        .font(.system(size: 14, weight: .semibold, design: .rounded))
                        .foregroundStyle(.secondary)
                        .contentTransition(.numericText())
                }
            }
        }
        .onAppear {
            guard !still, install.phase == .idle else { return }
            begin()
        }
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

    var body: some View {
        VStack(spacing: small ? 4 : 8) {
            ZStack(alignment: .bottomTrailing) {
                Image(systemName: item.symbol)
                    .font(.system(size: small ? 24 : 34, weight: .medium))
                    .foregroundStyle(colour)
                    .frame(width: small ? 44 : 64, height: small ? 40 : 64)
                    .symbolEffect(.pulse, options: .repeating, isActive: item.state == .running && !reduceMotion)
                    .symbolEffect(.bounce, value: item.state == .done && !reduceMotion)
                if item.state == .done {
                    Image(systemName: "checkmark.circle.fill")
                        .font(.system(size: small ? 16 : 22))
                        .foregroundStyle(.white, Theme.good)
                        .transition(.scale.combined(with: .opacity))
                } else if item.state == .failed {
                    Image(systemName: "exclamationmark.circle.fill")
                        .font(.system(size: small ? 16 : 22))
                        .foregroundStyle(.white, .red)
                        .transition(.scale.combined(with: .opacity))
                }
            }
            .accessibilityHidden(true)
            Text(item.label)
                .font(.system(size: small ? 13 : 15, weight: .semibold, design: .rounded))
                .foregroundStyle(item.state == .waiting ? .secondary : .primary)
        }
        .frame(width: 150, height: small ? 76 : 118)
        .background(CardBackground(corner: small ? 16 : 20, dimmed: item.state == .waiting))
        .opacity(item.state == .waiting ? 0.6 : 1)
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(item.label)
        .accessibilityValue(stateWord)
    }

    private var stateWord: String {
        switch item.state {
        case .waiting: return "waiting"
        case .running: return "being made now"
        case .done: return "done"
        case .failed: return "did not work"
        }
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
