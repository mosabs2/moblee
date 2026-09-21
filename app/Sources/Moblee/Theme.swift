import SwiftUI
import AVFoundation

enum Theme {
    static let accent = Color(red: 0.16, green: 0.38, blue: 0.86)

    /// Colours that carry words are darker in light mode and lighter in dark
    /// mode, so that small text on a card clears 4.5 to 1 either way. The
    /// bright versions are for large symbols only.
    static let good = Color(red: 0.13, green: 0.62, blue: 0.38)
    static let waiting = Color(red: 0.93, green: 0.58, blue: 0.10)
    static let goodText = adaptive(light: (0.05, 0.42, 0.24), dark: (0.45, 0.86, 0.62))
    static let waitingText = adaptive(light: (0.62, 0.33, 0.00), dark: (1.00, 0.74, 0.35))
    static let badText = adaptive(light: (0.72, 0.10, 0.10), dark: (1.00, 0.55, 0.52))

    /// Cards sit on the window background. In dark mode the system's control
    /// background is almost the same black as the window, so cards get their
    /// own lighter grey there, and a hairline edge in both modes.
    static let card = adaptive(light: (1.0, 1.0, 1.0), dark: (0.17, 0.18, 0.21))
    static let cardEdge = Color.primary.opacity(0.08)

    static func adaptive(light: (Double, Double, Double), dark: (Double, Double, Double)) -> Color {
        Color(nsColor: NSColor(name: nil) { appearance in
            let isDark = appearance.bestMatch(from: [.darkAqua, .aqua]) == .darkAqua
            let c = isDark ? dark : light
            return NSColor(srgbRed: c.0, green: c.1, blue: c.2, alpha: 1)
        })
    }

    static var background: some View {
        ZStack {
            Color(nsColor: .windowBackgroundColor)
            LinearGradient(
                colors: [accent.opacity(0.0), accent.opacity(0.10)],
                startPoint: .top, endPoint: .bottom)
        }
    }
}

/// The card every tile is drawn on.
struct CardBackground: View {
    var corner: CGFloat = 22
    var dimmed = false
    var body: some View {
        RoundedRectangle(cornerRadius: corner, style: .continuous)
            .fill(Theme.card)
            .overlay(RoundedRectangle(cornerRadius: corner, style: .continuous).stroke(Theme.cardEdge, lineWidth: 1))
            .shadow(color: .black.opacity(dimmed ? 0.04 : 0.10), radius: 10, y: 4)
    }
}

/// Reads a screen's sentence aloud, on the Mac, when the owner asks. Nothing
/// leaves the Mac, and it never starts by itself.
@MainActor
final class Speaker: NSObject, ObservableObject, AVSpeechSynthesizerDelegate {
    static let shared = Speaker()
    @Published var speaking = false
    private let synth = AVSpeechSynthesizer()

    override init() { super.init(); synth.delegate = self }

    func toggle(_ text: String) {
        if synth.isSpeaking { synth.stopSpeaking(at: .immediate); speaking = false; return }
        let u = AVSpeechUtterance(string: text)
        u.voice = AVSpeechSynthesisVoice(language: "en-GB")
        u.rate = AVSpeechUtteranceDefaultSpeechRate * 0.92
        speaking = true
        synth.speak(u)
    }

    func stop() { if synth.isSpeaking { synth.stopSpeaking(at: .immediate) }; speaking = false }

    nonisolated func speechSynthesizer(_ s: AVSpeechSynthesizer, didFinish u: AVSpeechUtterance) {
        Task { @MainActor in self.speaking = false }
    }
    nonisolated func speechSynthesizer(_ s: AVSpeechSynthesizer, didCancel u: AVSpeechUtterance) {
        Task { @MainActor in self.speaking = false }
    }
}

/// Every screen has the same skeleton: the sentence first, since it is the
/// instruction; then the picture; then one big button. A second, quiet action
/// can sit under the big one.
struct ScreenFrame<Picture: View>: View {
    let sentence: String
    let buttonTitle: String
    var buttonEnabled: Bool = true
    var showsBack: Bool = true
    var quietTitle: String? = nil
    var quietAction: (() -> Void)? = nil
    /// A second large button beside the first, for the one screen that sends
    /// an owner to either of two apps. Both are then a little narrower.
    var secondTitle: String? = nil
    var secondAction: (() -> Void)? = nil
    /// What "Read it to me" says, if it should say more than the sentence.
    var spoken: String? = nil
    /// The room the picture is given. One screen (the proof that found the
    /// guard not running) has a one-line sentence and a taller picture.
    var pictureHeight: CGFloat = 280
    let action: () -> Void
    @ViewBuilder let picture: () -> Picture

    @EnvironmentObject var flow: Flow
    @ObservedObject private var speaker = Speaker.shared

    var body: some View {
        VStack(spacing: 0) {
            Spacer(minLength: 34)
            HStack(alignment: .firstTextBaseline, spacing: 10) {
                Text(sentence)
                    .font(.system(size: 24, weight: .semibold, design: .rounded))
                    .multilineTextAlignment(.center)
                    .fixedSize(horizontal: false, vertical: true)
                    .accessibilityAddTraits(.isHeader)
                Button { speaker.toggle(spoken ?? sentence) } label: {
                    Image(systemName: speaker.speaking ? "stop.circle.fill" : "speaker.wave.2.circle.fill")
                        .font(.system(size: 22))
                        .foregroundStyle(Theme.accent)
                }
                .buttonStyle(.plain)
                .accessibilityLabel(speaker.speaking ? "Stop reading" : "Read it to me")
                .help("Read it to me")
            }
            .padding(.horizontal, 48)
            Spacer(minLength: 14)
            picture()
                .frame(maxWidth: .infinity)
                .frame(height: pictureHeight)
            Spacer(minLength: 14)
            HStack {
                if showsBack && flow.step != .welcome {
                    Button(action: { speaker.stop(); flow.back() }) {
                        Image(systemName: "chevron.left.circle.fill")
                            .font(.system(size: 30))
                            .frame(width: 44, height: 44)
                    }
                    .buttonStyle(.plain)
                    .foregroundStyle(.secondary)
                    .accessibilityLabel("Back")
                    .accessibilityIdentifier("back")
                }
                Button(action: { speaker.stop(); action() }) {
                    Text(buttonTitle)
                        .font(.system(size: 19, weight: .semibold, design: .rounded))
                        .frame(minWidth: secondTitle == nil ? 220 : 170, minHeight: 50)
                }
                .buttonStyle(BigButtonStyle())
                .disabled(!buttonEnabled)
                .keyboardShortcut(.defaultAction)
                .accessibilityIdentifier("main-button")
                if let secondTitle, let secondAction {
                    Button(action: { speaker.stop(); secondAction() }) {
                        Text(secondTitle)
                            .font(.system(size: 19, weight: .semibold, design: .rounded))
                            .frame(minWidth: 170, minHeight: 50)
                    }
                    .buttonStyle(BigButtonStyle())
                    .accessibilityIdentifier("second-button")
                }
                if showsBack && flow.step != .welcome {
                    // Balances the back arrow so the big button stays centred.
                    Color.clear.frame(width: 44, height: 44)
                }
            }
            Group {
                if let quietTitle, let quietAction {
                    QuietButton(title: quietTitle, action: { speaker.stop(); quietAction() })
                } else {
                    Color.clear
                }
            }
            .frame(height: 26)
            .padding(.top, 6)
            .padding(.bottom, 16)
        }
    }
}

struct QuietButton: View {
    let title: String
    let action: () -> Void
    var body: some View {
        Button(title, action: action)
            .buttonStyle(.plain)
            .foregroundStyle(Theme.accent)
            .font(.system(size: 14, weight: .semibold, design: .rounded))
    }
}

struct BigButtonStyle: ButtonStyle {
    @Environment(\.isEnabled) private var isEnabled

    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .padding(.horizontal, 26)
            .foregroundStyle(.white)
            .background(
                RoundedRectangle(cornerRadius: 16, style: .continuous)
                    .fill(isEnabled ? Theme.accent : Color.gray.opacity(0.45)))
            .scaleEffect(configuration.isPressed ? 0.97 : 1)
            .animation(.easeOut(duration: 0.12), value: configuration.isPressed)
    }
}
