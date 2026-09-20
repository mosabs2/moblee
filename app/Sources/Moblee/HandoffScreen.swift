import SwiftUI
import AppKit

/// The last screen: into Claude, at the new wiki, with the opening words ready.
/// Claude's app cannot be opened at a folder from outside, so the three clicks
/// are shown as pictures and the words are put on the clipboard.
struct HandoffScreen: View {
    @EnvironmentObject var flow: Flow
    @EnvironmentObject var install: InstallRun
    @State private var opened = false
    @State private var showingReceipt = false

    private var wikiFolderName: String {
        guard let p = install.vaultPath else { return flow.wikiName }
        return URL(fileURLWithPath: p).lastPathComponent
    }

    var body: some View {
        ScreenFrame(
            sentence: showingReceipt ? "This is everything Moblee made on your Mac."
                : (opened ? "The words are copied. Paste them to Claude."
                          : "Last step. Do these three in Claude."),
            buttonTitle: showingReceipt ? "Back" : (opened ? "Finish" : "Open Claude"),
            showsBack: false,
            quietTitle: showingReceipt ? "Show the folder" : "What did Moblee make?",
            quietAction: {
                if showingReceipt, let p = install.vaultPath, !flow.isTestMode {
                    NSWorkspace.shared.activateFileViewerSelecting([URL(fileURLWithPath: p)])
                } else {
                    withAnimation(.easeInOut(duration: 0.25)) { showingReceipt = true }
                }
            },
            spoken: showingReceipt ? nil
                : "Last step. In Claude: one, click Code at the top. Two, pick your wiki, called \(wikiFolderName). "
                  + "Three, say: \(Flow.openingWords).",
            action: act
        ) {
            if showingReceipt {
                HStack(alignment: .top, spacing: 18) {
                    HandoffCard(number: 1, symbol: "folder.fill", title: "Your wiki",
                                detail: "“\(wikiFolderName)”, inside “Wiki” in your home folder")
                    HandoffCard(number: 2, symbol: "lock.shield.fill", title: "The guard and skills",
                                detail: "In Claude's own settings folder. Copies of anything replaced are kept.")
                    HandoffCard(number: 3, symbol: "doc.text.fill", title: "A diary of the install",
                                detail: "No names in it. Safe to send if you ever need help.")
                }
                .padding(.horizontal, 30)
            } else {
                HStack(alignment: .top, spacing: 18) {
                    HandoffCard(number: 1, symbol: "chevron.left.forwardslash.chevron.right",
                                title: "Click Code", detail: "at the top of Claude")
                    HandoffCard(number: 2, symbol: "folder.fill",
                                title: "Pick your wiki", detail: "Wiki ▸ \(wikiFolderName)")
                    HandoffCard(number: 3, symbol: "text.bubble.fill",
                                title: "Say", detail: "“\(Flow.openingWords)”")
                }
                .padding(.horizontal, 30)
            }
        }
    }

    private func act() {
        if showingReceipt {
            withAnimation(.easeInOut(duration: 0.25)) { showingReceipt = false }
            return
        }
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

/// One numbered card. The cards in a row line up from the top, whatever the
/// length of their words, and each is read out as one thing.
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
                .multilineTextAlignment(.center)
                .lineLimit(2).minimumScaleFactor(0.85)
            Text(detail)
                .font(.system(size: 14, weight: .medium, design: .rounded))
                .foregroundStyle(Color.primary.opacity(0.8))
                .multilineTextAlignment(.center)
                .lineLimit(3)
                .minimumScaleFactor(0.85)
            Spacer(minLength: 0)
        }
        .padding(.horizontal, 12).padding(.top, 18).padding(.bottom, 10)
        .frame(width: 196, height: 236, alignment: .top)
        .background(CardBackground())
        .accessibilityElement(children: .ignore)
        .accessibilityLabel("Step \(number). \(title). \(detail)")
    }
}
