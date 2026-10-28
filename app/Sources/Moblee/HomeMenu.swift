import SwiftUI
import AppKit

/// (0.16.0) The home screen's one corner: a single read-aloud for the whole
/// screen, and a single menu holding everything that used to sit round the foot
/// of the screen.
///
/// Until 0.16.0 the home screen carried the sentence, up to three cards with a
/// speaker each, two big buttons, a quiet line with its speaker, "Check my
/// wiki", the line about the assistant with Change and Prove the guard and a
/// speaker, a line about a newer Moblee with two buttons and a speaker, and
/// "Bigger text" at the top. Every one of those still does what it did; they
/// have only moved. The screen itself now has one big button and one quiet line.
///
/// The corner sits in the window's top strip, in the place "Bigger text" has
/// on every other screen, so nothing on the screen below can run under it and
/// it mirrors with the rest of the window (`Layout.homeMenuCorner`).
@MainActor
enum HomeMenu {
    static let buttonId = "home-menu"
    static let exampleId = "example-way-in"

    /// Whether the window's corner belongs to the home screen: the ordinary
    /// home screen is showing, and nothing has taken its place.
    static func shows(flow: Flow, home: HomeModel) -> Bool {
        flow.mode == .home && Dropped.shared.showing == nil && !flow.offerMove
            && flow.example == nil && home.showsMainHome
    }

    /// Every control inside the open menu, in the order it draws them.
    static func stops(hub: Bool, canChangeAssistant: Bool, wantsChatGPT: Bool,
                      newerRelease: Bool, showsExample: Bool) -> [String] {
        var ring: [String] = []
        if hub { ring.append("open-hub") }
        ring.append("check-wiki")
        if canChangeAssistant { ring.append("change-assistant") }
        if wantsChatGPT { ring.append("prove-guard") }
        if newerRelease { ring += ["download-newer", "newer-not-now"] }
        ring.append("bigger-text")
        if showsExample { ring.append(exampleId) }
        return ring
    }

    /// When "Open the hub" was last pressed. The page opens in the browser by
    /// itself, and a second press inside a few seconds would start a second
    /// page; held here because the menu closes as it is pressed.
    static var hubOpenedAt: Date?
    static var hubOpening: Bool { hubOpenedAt.map { Date().timeIntervalSince($0) < 6 } ?? false }

    static func newerReleaseSaid(_ version: String) -> String {
        "Moblee \(version) is out."
    }
}

/// What the window's top corner holds: the home screen's read-aloud and menu
/// when the home screen is showing, and "Bigger text" on every other screen.
struct StripCorner: View {
    @ObservedObject var flow: Flow
    @ObservedObject var home: HomeModel
    @ObservedObject private var dropped = Dropped.shared

    var body: some View {
        let shows = HomeMenu.shows(flow: flow, home: home)
        Group {
            if shows {
                HomeCorner(flow: flow, home: home)
            } else {
                BiggerTextButton()
            }
        }
        // (0.16.0) Anything that takes the home screen's place (another screen,
        // an explanation, a drop receipt, a repair, Add more, the example)
        // closes the menu, so it is never found open again behind it.
        .onChange(of: shows) { _, now in if !now && home.menuOpen { home.menuOpen = false } }
        .onChange(of: flow.mode) { _, _ in if home.menuOpen { home.menuOpen = false } }
    }
}

/// (0.16.0) While the menu is open, everything under it gives up the keyboard
/// (see `KeyboardHeldByMenu` in Theme.swift).
struct HoldKeyboardWhileMenuOpen: ViewModifier {
    @ObservedObject var flow: Flow
    @ObservedObject var home: HomeModel

    func body(content: Content) -> some View {
        content.environment(\.keyboardHeldByMenu, home.menuOpen && HomeMenu.shows(flow: flow, home: home))
    }
}

/// The read-aloud and the "…" button, side by side.
struct HomeCorner: View {
    @ObservedObject var flow: Flow
    @ObservedObject var home: HomeModel
    @ObservedObject private var textSize = TextSize.shared

    private func toggle() { withAnimation(.easeOut(duration: 0.12)) { home.menuOpen.toggle() } }

    var body: some View {
        HStack(spacing: Theme.pt(10)) {
            ListenButton(id: "read-aloud", speech: HomeScreen.speech(home),
                         what: "the whole screen", size: 20)
            Button(action: toggle) {
                Image(systemName: "ellipsis.circle.fill")
                    .font(Theme.font(20))
                    .foregroundStyle(Theme.accent)
                    .contentShape(Circle())
                    // A newer Moblee is waiting inside the menu: a small dot
                    // says there is something in there worth opening it for.
                    .overlay(alignment: .topTrailing) {
                        if home.newerReleaseLineAllowed {
                            Circle().fill(Theme.waiting)
                                .frame(width: Theme.pt(8), height: Theme.pt(8))
                                .offset(x: Theme.pt(1), y: -Theme.pt(1))
                                .accessibilityHidden(true)
                        }
                    }
            }
            .buttonStyle(.plain)
            .help("More: Check my wiki, your assistant, bigger text")
            .accessibilityLabel("More")
            .accessibilityValue(home.newerReleaseLineAllowed ? "A newer Moblee is out" : "")
            .keyboardReachable(HomeMenu.buttonId, corner: 13, press: toggle)
        }
        .padding(.trailing, Theme.pt(4))
    }
}

/// The open menu, drawn inside the window under the corner, over the screen.
/// Inside the window rather than as a separate popover, so that its buttons
/// say where they are drawn for the self-drive walk, take the keyboard like
/// every other control, and can be drawn to a picture file.
struct HomeMenuLayer: View {
    @ObservedObject var flow: Flow
    @ObservedObject var home: HomeModel
    @Environment(\.stillPicture) private var still

    var body: some View {
        if home.menuOpen && HomeMenu.shows(flow: flow, home: home) {
            ZStack(alignment: .topTrailing) {
                // A click anywhere else closes it, as a menu does.
                if !still {
                    Color.black.opacity(0.001)
                        .contentShape(Rectangle())
                        .onTapGesture { home.menuOpen = false }
                }
                HomeMenuPanel(flow: flow, home: home)
                    .padding(.top, Theme.topStrip + Theme.pt(2))
                    .padding(.trailing, Theme.pt(12))
            }
        }
    }
}

struct HomeMenuPanel: View {
    @ObservedObject var flow: Flow
    @ObservedObject var home: HomeModel
    @ObservedObject private var textSize = TextSize.shared
    @ObservedObject private var dropped = Dropped.shared

    private func close() { home.menuOpen = false }

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.pt(2)) {
            // (v0.13.0) On a wiki whose hub/ is a real clone, and nowhere else:
            // the Hub's own page, started the way its README says. It opens in
            // the browser and stops by itself when the tab closes.
            if let hub = home.hub {
                if HomeMenu.hubOpening {
                    quiet(Hub.openingSentence)
                } else {
                    item(Hub.openTitle, id: "open-hub") {
                        Hub.open(hub, vault: hub.folder.deletingLastPathComponent(), home: flow.home, practice: flow.isTestMode)
                        HomeMenu.hubOpenedAt = Date()
                    }
                }
            }
            // (v0.9.6) One press, and the pack's own read-only check-up runs and
            // saves its report where whoever looks after Moblee expects it.
            // Greyed while something dropped on Moblee is still being copied.
            item(HomeScreen.checkWiki, id: "check-wiki", enabled: flow.canBeginClinic) { flow.beginClinic() }
            divider
            // Which assistant the wiki is for, and a way to change it (the
            // question, then the updater with the answer). Change is made by
            // this app's updater, so it is not offered on a wiki a newer Moblee
            // made (the words say where to go instead), nor while something is
            // being added.
            quiet("Assistant: \(home.assistant.name)")
            if home.wikiIsNewerThanApp { quiet(HomeScreen.changeNeedsNewest) }
            if home.canChangeAssistant {
                item("Change", id: "change-assistant") { flow.beginUpdate(changingAssistant: true) }
            }
            // For an owner who uses ChatGPT, a way to put the guard to the test.
            if home.assistant.wantsChatGPT {
                item("Prove the guard", id: "prove-guard") { home.trustOpen = true }
            }
            // (v0.15.0) A newer Moblee published: Install hands over to the
            // updater, which shows what is new; Not now means this version is
            // not offered again. Never over an update this app can already make.
            if home.newerReleaseLineAllowed, let v = home.newerRelease {
                divider
                quiet(HomeMenu.newerReleaseSaid(v))
                item("Install", id: "download-newer") { Updater.shared.checkForUpdates() }
                    .accessibilityLabel("Install Moblee \(v)")
                item("Not now", id: "newer-not-now") { home.setAsideNewerRelease() }
                    .accessibilityLabel("Not now, do not offer Moblee \(v) again")
            }
            divider
            // (v0.9.4) Bigger text, which is in the window's corner on every
            // other screen. The menu stays open as it is pressed, so the three
            // sizes can be stepped through, and says which one is set.
            item("Bigger text", id: "bigger-text", detail: textSize.step.name, closes: false) {
                withAnimation(.easeOut(duration: 0.15)) { textSize.step = textSize.step.next }
            }
            .accessibilityValue(textSize.step.name)
            // (v0.9.6) The example wiki, which an owner with a wiki can still
            // want to look at; the welcome screen keeps its own way in.
            if flow.hasExample {
                item(ExampleReader.wayIn, id: HomeMenu.exampleId) { flow.openExample() }
            }
            // Escape closes the menu, and nothing else.
            Button("", action: close)
                .keyboardShortcut(.cancelAction)
                .frame(width: 0, height: 0).opacity(0)
                .accessibilityHidden(true)
        }
        .padding(.vertical, Theme.pt(8)).padding(.horizontal, Theme.pt(6))
        .frame(width: Theme.pt(250), alignment: .leading)
        .background(CardBackground(corner: 12))
        .accessibilityElement(children: .contain)
        .accessibilityLabel("More")
    }

    private var divider: some View {
        Rectangle().fill(Theme.cardEdge).frame(height: 1)
            .padding(.vertical, Theme.pt(4)).padding(.horizontal, Theme.pt(6))
    }

    private func quiet(_ words: String) -> some View {
        Text(words)
            .font(Theme.font(12, .medium))
            .foregroundStyle(.secondary)
            .fixedSize(horizontal: false, vertical: true)
            .padding(.horizontal, Theme.pt(10)).padding(.vertical, Theme.pt(3))
    }

    /// One line of the menu: the words, the whole width a target. `enabled:
    /// false` greys it and stops both the click and the keyboard's press.
    private func item(_ title: String, id: String, enabled: Bool = true, detail: String? = nil,
                      closes: Bool = true, action: @escaping () -> Void) -> some View {
        let run = {
            guard enabled else { return }
            if closes { close() }
            action()
        }
        return Button(action: run) {
            HStack {
                Text(title).font(Theme.font(14, .semibold))
                Spacer(minLength: Theme.pt(8))
                if let detail { Text(detail).font(Theme.font(12, .medium)).foregroundStyle(Color.secondary) }
            }
            .padding(.horizontal, Theme.pt(10)).padding(.vertical, Theme.pt(6))
            .frame(maxWidth: .infinity, alignment: .leading)
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .foregroundStyle(enabled ? Theme.accent : Color.secondary)
        .disabled(!enabled)
        // Return presses the item the keyboard is on, and the first item
        // takes the keyboard as the menu opens, so it is worked from there.
        .keyboardReachable(id, corner: 8, press: run, returnPresses: true,
                           takesFocus: id == firstItem)
    }

    private var firstItem: String { home.hub != nil && !HomeMenu.hubOpening ? "open-hub" : "check-wiki" }
}
