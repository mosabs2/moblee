import SwiftUI

/// The only typed question in the whole install.
struct NameScreen: View {
    @EnvironmentObject var flow: Flow
    @FocusState private var focused: Bool

    var body: some View {
        ScreenFrame(
            sentence: "What should Claude call you?",
            buttonTitle: "Next",
            buttonEnabled: !flow.trimmedName.isEmpty,
            action: flow.next
        ) {
            VStack(spacing: 22) {
                HStack(alignment: .bottom, spacing: 14) {
                    Image(systemName: "sparkles")
                        .font(.system(size: 40, weight: .medium))
                        .foregroundStyle(Theme.accent)
                        .frame(width: 72, height: 72)
                        .background(Circle().fill(Color(nsColor: .controlBackgroundColor))
                            .shadow(color: .black.opacity(0.12), radius: 8, y: 3))
                    Text(flow.trimmedName.isEmpty ? "Hi…" : "Hi, \(flow.trimmedName).")
                        .font(.system(size: 22, weight: .semibold, design: .rounded))
                        .padding(.horizontal, 20).padding(.vertical, 14)
                        .background(
                            RoundedRectangle(cornerRadius: 20, style: .continuous)
                                .fill(Theme.accent.opacity(0.12)))
                        .animation(.easeOut(duration: 0.15), value: flow.trimmedName)
                }
                nameField
                    .font(.system(size: 28, weight: .medium, design: .rounded))
                    .multilineTextAlignment(.center)
                    .padding(.vertical, 14)
                    .frame(width: 380)
                    .background(
                        RoundedRectangle(cornerRadius: 16, style: .continuous)
                            .fill(Color(nsColor: .controlBackgroundColor))
                            .shadow(color: .black.opacity(0.10), radius: 8, y: 3))
                    .focused($focused)
                    .onSubmit { if !flow.trimmedName.isEmpty { flow.next() } }
            }
        }
        .onAppear { focused = true }
    }

    @Environment(\.stillPicture) private var still

    /// A real text field cannot be drawn to a picture file, so the drawn
    /// version shows the same words as plain text.
    @ViewBuilder private var nameField: some View {
        if still {
            Text(flow.ownerName.isEmpty ? "Your name" : flow.ownerName)
                .foregroundStyle(flow.ownerName.isEmpty ? .tertiary : .primary)
                .frame(maxWidth: .infinity)
        } else {
            TextField("Your name", text: $flow.ownerName)
                .textFieldStyle(.plain)
        }
    }
}
