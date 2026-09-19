import SwiftUI
import AppKit

/// The last screen: into Claude, at the new wiki, with the opening words ready.
/// Claude's app cannot be opened at a folder from outside, so the three clicks
/// are shown as pictures and the words are put on the clipboard.
struct HandoffScreen: View {
    @EnvironmentObject var flow: Flow
    @EnvironmentObject var install: InstallRun
    @State private var opened = false

    private var wikiFolderName: String {
        guard let p = install.vaultPath else { return flow.wikiName }
        return URL(fileURLWithPath: p).lastPathComponent
    }

    var body: some View {
        ScreenFrame(
            sentence: opened ? "The words are copied. Paste them to Claude."
                             : "Last step. Do these three in Claude.",
            buttonTitle: opened ? "Finish" : "Open Claude",
            showsBack: false,
            action: act
        ) {
            HStack(spacing: 18) {
                HandoffCard(number: 1, symbol: "chevron.left.forwardslash.chevron.right",
                            title: "Click Code", detail: "at the top of Claude")
                HandoffCard(number: 2, symbol: "folder.fill",
                            title: "Pick your wiki", detail: "Wiki ▸ \(wikiFolderName)")
                HandoffCard(number: 3, symbol: "text.bubble.fill",
                            title: "Say", detail: "“\(Flow.openingWords)”")
            }
            .padding(.horizontal, 36)
        }
    }

    private func act() {
        if opened {
            NSApplication.shared.terminate(nil)
            return
        }
        let board = NSPasteboard.general
        board.clearContents()
        board.setString(Flow.openingWords, forType: .string)
        if !flow.isTestMode,
           let url = NSWorkspace.shared.urlForApplication(withBundleIdentifier: "com.anthropic.claudefordesktop") {
            NSWorkspace.shared.openApplication(at: url, configuration: NSWorkspace.OpenConfiguration())
        }
        withAnimation(.easeInOut(duration: 0.3)) { opened = true }
    }
}

struct HandoffCard: View {
    let number: Int
    let symbol: String
    let title: String
    let detail: String

    var body: some View {
        VStack(spacing: 10) {
            Text("\(number)")
                .font(.system(size: 17, weight: .bold, design: .rounded))
                .foregroundStyle(.white)
                .frame(width: 32, height: 32)
                .background(Circle().fill(Theme.accent))
            Image(systemName: symbol)
                .font(.system(size: 40, weight: .medium))
                .foregroundStyle(Theme.accent)
                .frame(height: 60)
            Text(title)
                .font(.system(size: 18, weight: .semibold, design: .rounded))
            Text(detail)
                .font(.system(size: 14, weight: .medium, design: .rounded))
                .foregroundStyle(.secondary)
                .multilineTextAlignment(.center)
                .lineLimit(2)
                .minimumScaleFactor(0.8)
        }
        .padding(.horizontal, 10)
        .frame(width: 196, height: 224)
        .background(
            RoundedRectangle(cornerRadius: 22, style: .continuous)
                .fill(Color(nsColor: .controlBackgroundColor))
                .shadow(color: .black.opacity(0.10), radius: 10, y: 4))
    }
}
