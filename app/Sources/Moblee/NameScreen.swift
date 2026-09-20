import SwiftUI

/// The only typed question in the whole install. The question is the screen's
/// sentence, which sits directly above the box it is asking about.
struct NameScreen: View {
    @EnvironmentObject var flow: Flow
    @FocusState private var focused: Bool
    @Environment(\.stillPicture) private var still

    /// The question of which assistant comes after this one, so the sentence
    /// names Claude, as it always has, unless the owner has already said
    /// otherwise (at the check-up, or by coming back from the next screen).
    private var question: String {
        switch flow.assistant {
        case .chatgpt: return "What should ChatGPT call you?"
        case .both: return "What should your assistant call you?"
        default: return "What should Claude call you?"
        }
    }

    var body: some View {
        ScreenFrame(
            sentence: question,
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
                    .accessibilityLabel(question)
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
        let words = Self.words(for: flow.assistant ?? .claude)
        ScreenFrame(
            sentence: "Here is what Moblee will make. Nothing else is touched.",
            buttonTitle: flow.resumePlace == nil ? "Make it" : "Finish it",
            spoken: "Here is what Moblee will make. One: a folder for your wiki, called \(place.name). "
                + "Two: a guard, \(words.guardSpoken). "
                + "Three: \(words.skillsSpoken). Nothing else on your Mac is touched.",
            action: flow.next
        ) {
            HStack(alignment: .top, spacing: 18) {
                HandoffCard(number: 1, symbol: "folder.fill", title: "Your wiki",
                            detail: "A folder called “\(place.name)” inside “Wiki”, in your home folder")
                HandoffCard(number: 2, symbol: "lock.shield.fill", title: "A guard",
                            detail: words.guardCard)
                HandoffCard(number: 3, symbol: "graduationcap.fill", title: words.skillsTitle,
                            detail: words.skillsCard)
            }
            .padding(.horizontal, 30)
        }
    }

    struct Words {
        let guardCard, guardSpoken, skillsTitle, skillsCard, skillsSpoken: String
    }

    /// Claude's words are as they have always been. With ChatGPT the guard's
    /// promise holds once the owner has trusted it there, and the card says so:
    /// the Trust screen after the build is where they do it.
    static func words(for assistant: Assistant) -> Words {
        switch assistant {
        case .claude:
            return Words(guardCard: "So Claude can never delete anything in it",
                         guardSpoken: "so Claude can never delete anything in it",
                         skillsTitle: "Claude's skills",
                         skillsCard: "What Claude needs to keep your wiki",
                         skillsSpoken: "the skills Claude needs to keep it")
        case .chatgpt:
            return Words(guardCard: "So ChatGPT cannot delete anything in it, once you trust it there",
                         guardSpoken: "so ChatGPT cannot delete anything in it, once you have trusted it there",
                         skillsTitle: "ChatGPT's skills",
                         skillsCard: "What ChatGPT needs to keep your wiki",
                         skillsSpoken: "the skills ChatGPT needs to keep it")
        case .both:
            return Words(guardCard: "So neither can delete anything in it. ChatGPT needs you to trust it first",
                         guardSpoken: "so neither assistant can delete anything in it. ChatGPT needs you to trust it first",
                         skillsTitle: "The skills",
                         skillsCard: "What each assistant needs to keep your wiki",
                         skillsSpoken: "the skills each assistant needs to keep it")
        }
    }
}
