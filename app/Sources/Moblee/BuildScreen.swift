import SwiftUI

/// The build itself: six pictures that light up as the engine reports each step.
struct BuildScreen: View {
    @EnvironmentObject var flow: Flow
    @EnvironmentObject var install: InstallRun
    @Environment(\.stillPicture) private var still

    var body: some View {
        ScreenFrame(
            sentence: sentence,
            buttonTitle: buttonTitle,
            buttonEnabled: install.phase != .running && install.phase != .idle,
            showsBack: isFailed,
            action: act
        ) {
            LazyVGrid(columns: Array(repeating: GridItem(.fixed(150), spacing: 18), count: 3),
                      spacing: 18) {
                ForEach(install.items) { item in
                    BuildTile(item: item)
                }
            }
        }
        .onAppear {
            // Coming back here after a failure tries again.
            guard !still, install.phase == .idle || isFailed else { return }
            begin()
        }
    }

    private var isFailed: Bool {
        if case .failed = install.phase { return true }
        return false
    }

    private var sentence: String {
        switch install.phase {
        case .idle, .running: return "Building your wiki…"
        case .finished: return "Your wiki is ready."
        case .failed(let why):
            switch why {
            case "place-taken": return "That name is taken. Go back and change it."
            case "safety-layer": return "The guard could not switch on, so the build stopped."
            case "no-pack", "pack-copy": return "This copy of Moblee is incomplete. Download it again."
            default: return "Something stopped the build."
            }
        }
    }

    private var buttonTitle: String {
        switch install.phase {
        case .failed: return "Show what happened"
        default: return "Next"
        }
    }

    private func act() {
        switch install.phase {
        case .failed: install.showDiary()
        default: flow.next()
        }
    }

    private func begin() {
        guard let pack = flow.bundledPack else {
            install.phase = .failed(why: "no-pack")
            return
        }
        let place = flow.freeLocation()
        install.start(home: flow.home, ownerName: flow.trimmedName,
                      wikiName: place.name, location: place.url, bundledPack: pack)
    }
}

struct BuildTile: View {
    let item: InstallRun.Item
    @State private var pulse = false

    var body: some View {
        VStack(spacing: 8) {
            ZStack(alignment: .bottomTrailing) {
                Image(systemName: item.symbol)
                    .font(.system(size: 34, weight: .medium))
                    .foregroundStyle(colour)
                    .frame(width: 64, height: 64)
                    .scaleEffect(item.state == .running && pulse ? 1.12 : 1)
                if item.state == .done {
                    Image(systemName: "checkmark.circle.fill")
                        .font(.system(size: 22))
                        .foregroundStyle(.white, Theme.good)
                        .transition(.scale.combined(with: .opacity))
                } else if item.state == .failed {
                    Image(systemName: "exclamationmark.circle.fill")
                        .font(.system(size: 22))
                        .foregroundStyle(.white, .red)
                        .transition(.scale.combined(with: .opacity))
                }
            }
            Text(item.label)
                .font(.system(size: 15, weight: .semibold, design: .rounded))
                .foregroundStyle(item.state == .waiting ? .secondary : .primary)
        }
        .frame(width: 150, height: 118)
        .background(
            RoundedRectangle(cornerRadius: 20, style: .continuous)
                .fill(Color(nsColor: .controlBackgroundColor))
                .shadow(color: .black.opacity(item.state == .waiting ? 0.04 : 0.10), radius: 8, y: 3))
        .opacity(item.state == .waiting ? 0.55 : 1)
        .onAppear {
            withAnimation(.easeInOut(duration: 0.7).repeatForever(autoreverses: true)) { pulse = true }
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
