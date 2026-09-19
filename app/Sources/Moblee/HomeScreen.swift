import SwiftUI
import AppKit

/// The screen a returning owner sees.
struct HomeScreen: View {
    @EnvironmentObject var flow: Flow
    @EnvironmentObject var home: HomeModel
    @Environment(\.stillPicture) private var still
    @State private var repairing = false

    private var waiting: [HomeModel.Tile] { home.tiles.filter { $0.state != .done } }
    /// Three at a time, the ones still to do first; the rest take their place
    /// as these are added.
    private var shown: [HomeModel.Tile] {
        Array((waiting + home.tiles.filter { $0.state == .done }).prefix(3))
    }

    var body: some View {
        ZStack {
            if let tile = home.explaining {
                ExplainScreen(tile: tile)
            } else if home.updateAvailable {
                updatePrompt
            } else if home.needsRepair {
                repairPrompt
            } else if home.listUnreadable {
                ScreenFrame(sentence: "Moblee could not read its list. Tell Claude: run a check-up.",
                            buttonTitle: "Open Claude", showsBack: false, action: openClaude) {
                    Image(systemName: "exclamationmark.triangle.fill")
                        .font(.system(size: 90)).foregroundStyle(Theme.waiting)
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
                ScreenFrame(sentence: "Claude has these ready for you. Tap Add.",
                            buttonTitle: "Open Claude", showsBack: false, action: openClaude) {
                    VStack(spacing: 8) {
                        HStack(spacing: 18) {
                            ForEach(shown) { tile in
                                RequestTile(tile: tile) { home.press(tile) }
                            }
                        }
                        if home.tiles.count > shown.count {
                            Text("and \(home.tiles.count - shown.count) more after these")
                                .font(.system(size: 12.5, weight: .medium, design: .rounded))
                                .foregroundStyle(.secondary)
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

    private var updatePrompt: some View {
        ScreenFrame(sentence: "A newer Moblee is ready for your wiki.",
                    buttonTitle: "Update", showsBack: false,
                    action: { flow.install.phase = .idle; flow.mode = .update }) {
            VStack(spacing: 14) {
                Image(systemName: "arrow.up.circle.fill")
                    .font(.system(size: 96)).foregroundStyle(Theme.accent)
                Text("\(home.wikiVersion)  →  \(home.packVersion)")
                    .font(.system(size: 20, weight: .semibold, design: .rounded))
                    .foregroundStyle(.secondary)
                Text("Your pages are not touched.")
                    .font(.system(size: 15, weight: .medium, design: .rounded))
                    .foregroundStyle(.secondary)
                QuietButton(title: "Not now") { home.updateSetAside = true }
            }
        }
    }

    private var repairPrompt: some View {
        ScreenFrame(sentence: home.repairFailed ? "That did not work. Tell Claude: run a check-up."
                        : (repairing ? "Switching the guard back on…" : "The safety guard is off. Switch it back on."),
                    buttonTitle: home.repairFailed ? "Open Claude" : "Repair",
                    buttonEnabled: !repairing, showsBack: false,
                    action: {
                        if home.repairFailed { openClaude(); return }
                        repairing = true
                        home.repair { repairing = false }
                    }) {
            Image(systemName: "lock.shield.fill")
                .font(.system(size: 96)).foregroundStyle(home.repairFailed ? .red : Theme.waiting)
        }
    }

    private func openClaude() {
        if !flow.isTestMode,
           let url = NSWorkspace.shared.urlForApplication(withBundleIdentifier: "com.anthropic.claudefordesktop") {
            NSWorkspace.shared.openApplication(at: url, configuration: NSWorkspace.OpenConfiguration())
        }
    }
}

struct QuietButton: View {
    let title: String
    let action: () -> Void
    var body: some View {
        Button(title, action: action)
            .buttonStyle(.plain).foregroundStyle(.secondary)
            .font(.system(size: 13, weight: .medium, design: .rounded))
    }
}

struct RequestTile: View {
    let tile: HomeModel.Tile
    let press: () -> Void

    var body: some View {
        VStack(spacing: 8) {
            Image(systemName: tile.state == .done ? "checkmark.circle.fill" : tile.symbol)
                .font(.system(size: 40, weight: .medium))
                .foregroundStyle(tile.state == .done ? Theme.good
                                 : ((tile.state == .failed || tile.state == .blocked) ? .red : Theme.accent))
                .frame(height: 50)
            Text(tile.title)
                .font(.system(size: 15, weight: .semibold, design: .rounded))
                .multilineTextAlignment(.center).lineLimit(2).minimumScaleFactor(0.85)
            Text(tile.note.isEmpty ? tile.why : tile.note)
                .font(.system(size: 12.5, weight: .regular, design: .rounded))
                .foregroundStyle(tile.note.isEmpty ? Color.secondary : Color.red)
                .multilineTextAlignment(.center).lineLimit(3).minimumScaleFactor(0.85)
            if tile.kind != .skill {
                Text(tile.detail)
                    .font(.system(size: 11.5, weight: .medium, design: .rounded))
                    .foregroundStyle(tile.paid ? Theme.waiting : .secondary)
            }
            Spacer(minLength: 0)
            Group {
                switch tile.state {
                case .waiting:
                    Button(tile.kind == .skill ? "Look" : "Add", action: press)
                        .buttonStyle(.borderedProminent).tint(Theme.accent).controlSize(.large)
                case .running:
                    Label("Adding…", systemImage: "arrow.triangle.2.circlepath")
                        .foregroundStyle(Theme.waiting)
                case .handedOver:
                    Button("Open it again", action: press)
                        .buttonStyle(.bordered).controlSize(.large)
                case .done:
                    Text("Added").foregroundStyle(Theme.good)
                case .failed:
                    Button("Try again", action: press)
                        .buttonStyle(.bordered).controlSize(.large)
                case .blocked:
                    Text("Tell Claude").foregroundStyle(.red)
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

/// Shown before anything is added that the owner should see first: a skill
/// Claude wrote, a Terminal window, or clicks inside Claude.
struct ExplainScreen: View {
    @EnvironmentObject var home: HomeModel
    let tile: HomeModel.Tile

    private var isSkill: Bool { tile.kind == .skill }
    private var isTerminal: Bool { tile.kind == .item && tile.how == .terminal }

    var body: some View {
        ScreenFrame(
            sentence: isSkill ? "Claude wrote this skill. It works in every Claude session on this Mac."
                : (isTerminal ? "A black window opens. Follow it, then come back."
                              : "Do these three in Claude, then come back."),
            buttonTitle: isSkill ? "Add it" : (isTerminal ? "Open it" : "Show me"),
            showsBack: false,
            action: {
                if isSkill { home.addSkill(tile) }
                else if isTerminal { home.openTerminal(for: tile) }
                else { home.openClicks(for: tile) }
                home.explaining = nil
            }
        ) {
            VStack(spacing: 14) {
                if isSkill {
                    VStack(alignment: .leading, spacing: 10) {
                        Label(tile.key, systemImage: "wand.and.stars")
                            .font(.system(size: 18, weight: .semibold, design: .rounded))
                        Text("What it says it does")
                            .font(.system(size: 12, weight: .semibold, design: .rounded)).foregroundStyle(.secondary)
                        ScrollView {
                            Text(tile.detail.isEmpty ? "It does not say." : tile.detail)
                                .font(.system(size: 14, design: .rounded))
                                .frame(maxWidth: .infinity, alignment: .leading)
                        }
                        .frame(height: 96)
                        Text("Files: " + tile.files.prefix(6).joined(separator: ", ")
                             + (tile.files.count > 6 ? " and \(tile.files.count - 6) more" : ""))
                            .font(.system(size: 12, design: .rounded)).foregroundStyle(.secondary)
                            .lineLimit(2)
                    }
                    .padding(18)
                    .frame(width: 560, alignment: .leading)
                    .background(RoundedRectangle(cornerRadius: 20, style: .continuous)
                        .fill(Color(nsColor: .controlBackgroundColor))
                        .shadow(color: .black.opacity(0.10), radius: 10, y: 4))
                } else if isTerminal {
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
                QuietButton(title: "Not now") { home.explaining = nil }
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
                : (failed ? "The update stopped. Your pages were not touched." : "Updating your wiki…"),
            buttonTitle: failed ? "Show what happened" : "Done",
            buttonEnabled: install.phase == .finished || failed,
            showsBack: false,
            action: {
                if failed { install.showDiary(); return }
                backHome()
            }
        ) {
            VStack(spacing: 6) {
                LazyVGrid(columns: Array(repeating: GridItem(.fixed(140), spacing: 12), count: 3), spacing: 8) {
                    ForEach(install.items) { item in
                        BuildTile(item: item).scaleEffect(0.7).frame(width: 140, height: 80)
                    }
                }
                if failed { QuietButton(title: "Back", action: { home.updateSetAside = true; backHome() }) }
            }
            .padding(.top, 18)
        }
        .onAppear {
            guard !still, install.phase == .idle, let vault = home.vault, let pack = flow.bundledPack else { return }
            install.startUpdate(home: flow.home, vault: vault, bundledPack: pack)
        }
    }

    private func backHome() {
        home.load(home: flow.home, bundledPack: flow.bundledPack)
        flow.mode = .home
    }
}
