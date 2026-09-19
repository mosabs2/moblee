import SwiftUI

enum Theme {
    static let accent = Color(red: 0.16, green: 0.38, blue: 0.86)
    static let good = Color(red: 0.13, green: 0.62, blue: 0.38)
    static let waiting = Color(red: 0.93, green: 0.58, blue: 0.10)

    static var background: some View {
        ZStack {
            Color(nsColor: .windowBackgroundColor)
            LinearGradient(
                colors: [accent.opacity(0.0), accent.opacity(0.10)],
                startPoint: .top, endPoint: .bottom)
        }
    }
}

/// Every screen has the same skeleton: a picture, one sentence, one button.
struct ScreenFrame<Picture: View>: View {
    let sentence: String
    let buttonTitle: String
    var buttonEnabled: Bool = true
    var showsBack: Bool = true
    let action: () -> Void
    @ViewBuilder let picture: () -> Picture

    @EnvironmentObject var flow: Flow

    var body: some View {
        VStack(spacing: 0) {
            Spacer(minLength: 36)
            picture()
                .frame(maxWidth: .infinity)
                .frame(height: 270)
            Spacer(minLength: 12)
            Text(sentence)
                .font(.system(size: 24, weight: .semibold, design: .rounded))
                .multilineTextAlignment(.center)
                .padding(.horizontal, 60)
                .fixedSize(horizontal: false, vertical: true)
            Spacer(minLength: 20)
            HStack {
                if showsBack && flow.step != .welcome {
                    Button(action: flow.back) {
                        Image(systemName: "chevron.left")
                            .font(.system(size: 16, weight: .semibold))
                            .frame(width: 44, height: 44)
                    }
                    .buttonStyle(.plain)
                    .foregroundStyle(.secondary)
                    .accessibilityLabel("Back")
                }
                Button(action: action) {
                    Text(buttonTitle)
                        .font(.system(size: 19, weight: .semibold, design: .rounded))
                        .frame(minWidth: 220, minHeight: 50)
                }
                .buttonStyle(BigButtonStyle())
                .disabled(!buttonEnabled)
                .keyboardShortcut(.defaultAction)
                if showsBack && flow.step != .welcome {
                    // Balances the back arrow so the big button stays centred.
                    Color.clear.frame(width: 44, height: 44)
                }
            }
            .padding(.bottom, 40)
        }
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
