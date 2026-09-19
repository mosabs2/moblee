import SwiftUI
import AppKit

/// The screen a returning owner sees.
struct HomeScreen: View {
    @EnvironmentObject var flow: Flow
    @EnvironmentObject var home: HomeModel
    @Environment(\.stillPicture) private var still
    @State private var repairing = false

    private var waiting: [HomeModel.Tile] { home.tiles.filter { $0.state != .done } }

    var body: some View {
        ZStack {
            if let tile = home.explaining {
                ExplainScreen(tile: tile)
            } else if home.updateAvailable {
                ScreenFrame(sentence: "A newer Moblee is ready for your wiki.",
                            buttonTitle: "Update", showsBack: false,
                            action: { flow.mode = .update }) {
                    VStack(spacing: 14) {
                        Image(systemName: "arrow.up.circle.fill")
                            .font(.system(size: 96)).foregroundStyle(Theme.accent)
                        Text("\(home.wikiVersion)  →  \(home.packVersion)")
                            .font(.system(size: 20, weight: .semibold, design: .rounded))
                            .foregroundStyle(.secondary)
                        Text("Your pages are not touched.")
                            .font(.system(size: 15, weight: .medium, design: .rounded))
                            .foregroundStyle(.secondary)
                    }
                }
            } else if home.needsRepair {
                ScreenFrame(sentence: repairing ? "Switching the guard back on…" : "The safety guard is off. Switch it back on.",
                            buttonTitle: "Repair", buttonEnabled: !repairing, showsBack: false,
                            action: { repairing = true; home.repair { _ in repairing = false } }) {
                    Image(systemName: "lock.shield.fill")
                        .font(.system(size: 96)).foregroundStyle(Theme.waiting)
                }
            } else if waiting.isEmpty {
                ScreenFrame(sentence: home.tiles.isEmpty ? "Nothing is waiting. Talk to Claude."
                                                         : "All added. Tell Claude it is done.",
                            buttonTitle: "Open Claude", showsBack: false, action: openClaude) {
                    Image(systemName: home.tiles.isEmpty ? "bubble.left.and.bubble.right.fill" : "checkmark.circle.fill")
                        .font(.system(size: 96))
                        .foregroundStyle(home.tiles.isEmpty ? Theme.accent : Theme.good)
                }
            } else {
                ScreenFrame(sentence: waiting.count == 1 ? "Claude and you agreed on this. Tap Add."
                                                         : "Claude and you agreed on these. Tap Add.",
                            buttonTitle: "Open Claude", showsBack: false, action: openClaude) {
                    HStack(spacing: 18) {
                        ForEach(home.tiles.prefix(3)) { tile in
                            RequestTile(tile: tile) { home.press(tile) }
                        }
                    }
                    .padding(.horizontal, 30)
                }
            }
        }
        .onAppear {
            guard !still else { return }
            home.startWatching()
        }
        .onDisappear { home.stopWatching() }
    }

    private func openClaude() {
        if !flow.isTestMode,
           let url = NSWorkspace.shared.urlForApplication(withBundleIdentifier: "com.anthropic.claudefordesktop") {
            NSWorkspace.shared.openApplication(at: url, configuration: NSWorkspace.OpenConfiguration())
        }
    }
}

struct RequestTile: View {
    let tile: HomeModel.Tile
    let press: () -> Void
    @State private var spin = false

    var body: some View {
        VStack(spacing: 8) {
            Image(systemName: tile.state == .done ? "checkmark.circle.fill" : tile.symbol)
                .font(.system(size: 40, weight: .medium))
                .foregroundStyle(tile.state == .done ? Theme.good : (tile.state == .failed ? .red : Theme.accent))
                .frame(height: 50)
            Text(tile.title)
                .font(.system(size: 15, weight: .semibold, design: .rounded))
                .multilineTextAlignment(.center).lineLimit(2).minimumScaleFactor(0.85)
            Text(tile.why)
                .font(.system(size: 12.5, weight: .regular, design: .rounded))
                .foregroundStyle(.secondary)
                .multilineTextAlignment(.center).lineLimit(3).minimumScaleFactor(0.85)
            Text(tile.detail)
                .font(.system(size: 11.5, weight: .medium, design: .rounded))
                .foregroundStyle(tile.paid ? Theme.waiting : .secondary)
            Spacer(minLength: 0)
            Group {
                switch tile.state {
                case .waiting:
                    Button("Add", action: press)
                        .buttonStyle(.borderedProminent).tint(Theme.accent).controlSize(.large)
                case .running:
                    Label("Adding…", systemImage: "arrow.triangle.2.circlepath")
                        .foregroundStyle(Theme.waiting)
                case .handedOver:
                    Text("Finish it there").foregroundStyle(Theme.waiting)
                case .done:
                    Text("Added").foregroundStyle(Theme.good)
                case .failed:
                    Button("Try again", action: press)
                        .buttonStyle(.bordered).controlSize(.large)
                }
            }
            .font(.system(size: 14, weight: .semibold, design: .rounded))
            .frame(height: 34)
        }
        .padding(.horizontal, 12).padding(.vertical, 14)
        .frame(width: 200, height: 262)
        .background(
            RoundedRectangle(cornerRadius: 22, style: .continuous)
                .fill(Color(nsColor: .controlBackgroundColor))
                .shadow(color: .black.opacity(0.10), radius: 10, y: 4))
    }
}

/// Shown before anything that leaves the app: a Terminal window, or clicks
/// inside Claude. One picture of what is about to happen, then the button.
struct ExplainScreen: View {
    @EnvironmentObject var home: HomeModel
    let tile: HomeModel.Tile

    private var isTerminal: Bool { tile.kind == .item && tile.how == .terminal }

    var body: some View {
        ScreenFrame(
            sentence: isTerminal ? "A black window opens. Follow it, then come back."
                                 : "Do these three in Claude, then come back.",
            buttonTitle: isTerminal ? "Open it" : "Show me",
            showsBack: false,
            action: {
                if isTerminal { home.openTerminal(for: tile) } else { home.openClicks(for: tile) }
                home.explaining = nil
            }
        ) {
            VStack(spacing: 16) {
                if isTerminal {
                    HStack(spacing: 18) {
                        HandoffCard(number: 1, symbol: "terminal.fill", title: "It types for itself",
                                    detail: "Press Return if it asks to start")
                        HandoffCard(number: 2, symbol: "key.fill", title: "Your Mac password",
                                    detail: "Nothing shows as you type. That is normal.")
                        HandoffCard(number: 3, symbol: "clock.fill", title: "Wait",
                                    detail: "Downloads take a while. Then close it.")
                    }
                } else {
                    HStack(spacing: 18) {
                        HandoffCard(number: 1, symbol: "gearshape.fill", title: "Connectors",
                                    detail: "The page opens for you")
                        HandoffCard(number: 2, symbol: "link", title: "Connect",
                                    detail: "Find it in the list and press Connect")
                        HandoffCard(number: 3, symbol: "person.badge.key.fill", title: "Sign in",
                                    detail: tile.paid ? "Paying is your choice, on their site"
                                                      : "With your own account")
                    }
                }
                Button("Not now") { home.explaining = nil }
                    .buttonStyle(.plain).foregroundStyle(.secondary)
                    .font(.system(size: 13, weight: .medium, design: .rounded))
            }
            .padding(.horizontal, 30)
        }
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
                : (failed ? "The update stopped. Nothing of yours was changed." : "Updating your wiki…"),
            buttonTitle: failed ? "Show what happened" : "Done",
            buttonEnabled: install.phase == .finished || failed,
            showsBack: false,
            action: {
                if failed { install.showDiary(); return }
                home.load(home: flow.home, bundledPack: flow.bundledPack)
                flow.mode = .home
            }
        ) {
            LazyVGrid(columns: Array(repeating: GridItem(.fixed(150), spacing: 14), count: 3), spacing: 12) {
                ForEach(install.items) { item in
                    BuildTile(item: item).scaleEffect(0.82).frame(width: 150, height: 84)
                }
            }
        }
        .onAppear {
            guard !still, install.phase == .idle, let vault = home.vault, let pack = flow.bundledPack else { return }
            install.startUpdate(home: flow.home, vault: vault, bundledPack: pack)
        }
    }
}
