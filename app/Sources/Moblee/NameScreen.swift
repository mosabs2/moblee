import SwiftUI

/// The only typed question in the whole install. The question is the screen's
/// sentence, which sits directly above the box it is asking about.
struct NameScreen: View {
    @EnvironmentObject var flow: Flow
    @FocusState private var focused: Bool
    @Environment(\.stillPicture) private var still

    var body: some View {
        ScreenFrame(
            sentence: "What should Claude call you?",
            buttonTitle: "Next",
            buttonEnabled: !flow.trimmedName.isEmpty,
            action: flow.next
        ) {
            VStack(spacing: 22) {
                nameField
                    .font(.system(size: 28, weight: .medium, design: .rounded))
                    .multilineTextAlignment(.center)
                    .padding(.vertical, 14)
                    .frame(width: 380)
                    .background(CardBackground(corner: 16))
                    .focused($focused)
                    .accessibilityLabel("What should Claude call you?")
                HStack(alignment: .bottom, spacing: 14) {
                    Image(systemName: "sparkles")
                        .font(.system(size: 36, weight: .medium))
                        .foregroundStyle(Theme.accent)
                        .frame(width: 64, height: 64)
                        .background(Circle().fill(Theme.card)
                            .overlay(Circle().stroke(Theme.cardEdge, lineWidth: 1))
                            .shadow(color: .black.opacity(0.12), radius: 8, y: 3))
                    Text(flow.trimmedName.isEmpty ? "Hi…" : "Hi, \(flow.trimmedName).")
                        .font(.system(size: 22, weight: .semibold, design: .rounded))
                        .padding(.horizontal, 20).padding(.vertical, 14)
                        .background(
                            RoundedRectangle(cornerRadius: 20, style: .continuous)
                                .fill(Theme.accent.opacity(0.14)))
                        .animation(.easeOut(duration: 0.15), value: flow.trimmedName)
                }
                .accessibilityHidden(true)
            }
        }
        .onAppear { focused = true }
    }

    /// A real text field cannot be drawn to a picture file, so the drawn
    /// version shows the same words as plain text. Return is left to the big
    /// button (it is the window's default action), so it is handled once.
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

/// Said before anything is made: exactly what Moblee is about to put on this
/// Mac, and where. A beginner is being asked to let an app from the internet
/// change Claude's settings; this is the plain statement that earns it.
struct PromiseScreen: View {
    @EnvironmentObject var flow: Flow

    var body: some View {
        let place = flow.resumePlace ?? flow.chosenPlace ?? flow.freeLocation()
        ScreenFrame(
            sentence: "Here is what Moblee will make. Nothing else is touched.",
            buttonTitle: flow.resumePlace == nil ? "Make it" : "Finish it",
            spoken: "Here is what Moblee will make. One: a folder for your wiki, called \(place.name). "
                + "Two: a guard, so Claude can never delete anything in it. "
                + "Three: the skills Claude needs to keep it. Nothing else on your Mac is touched.",
            action: flow.next
        ) {
            HStack(alignment: .top, spacing: 18) {
                HandoffCard(number: 1, symbol: "folder.fill", title: "Your wiki",
                            detail: "A folder called “\(place.name)” inside “Wiki”, in your home folder")
                HandoffCard(number: 2, symbol: "lock.shield.fill", title: "A guard",
                            detail: "So Claude can never delete anything in it")
                HandoffCard(number: 3, symbol: "graduationcap.fill", title: "Claude's skills",
                            detail: "What Claude needs to keep your wiki")
            }
            .padding(.horizontal, 30)
        }
    }
}
