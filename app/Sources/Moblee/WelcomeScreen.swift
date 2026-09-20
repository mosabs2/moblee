import SwiftUI

struct WelcomeScreen: View {
    @EnvironmentObject var flow: Flow

    var body: some View {
        ScreenFrame(
            sentence: "You talk. Your assistant keeps your wiki.",
            buttonTitle: "Start",
            action: flow.next
        ) {
            TalkDiagram()
        }
    }
}

/// You -> Claude -> your wiki, with a dot travelling along the line.
struct TalkDiagram: View {
    @State private var travel: CGFloat = 0
    @State private var hasAppeared = false
    @Environment(\.stillPicture) private var still
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    private var appeared: Bool { hasAppeared || still }

    var body: some View {
        GeometryReader { geo in
            let w = geo.size.width
            let y = geo.size.height / 2
            let xs: [CGFloat] = [w * 0.22, w * 0.5, w * 0.78]

            ZStack {
                Path { p in
                    p.move(to: CGPoint(x: xs[0] + 56, y: y))
                    p.addLine(to: CGPoint(x: xs[2] - 56, y: y))
                }
                .stroke(Theme.accent.opacity(0.25),
                        style: StrokeStyle(lineWidth: 4, lineCap: .round, dash: [2, 12]))

                Circle()
                    .fill(Theme.accent)
                    .frame(width: 14, height: 14)
                    .position(x: xs[0] + 56 + (xs[2] - xs[0] - 112) * ((still || reduceMotion) ? 0.25 : travel), y: y)
                    .opacity(appeared ? 1 : 0)

                node("person.fill", "You", x: xs[0], y: y, delay: 0.0)
                // Which assistant is asked three screens on, so none is named here.
                node("sparkles", "Your assistant", x: xs[1], y: y, delay: 0.15)
                node("books.vertical.fill", "Your wiki", x: xs[2], y: y, delay: 0.3)
            }
        }
        .onAppear {
            hasAppeared = true
            guard !reduceMotion else { return }      // the picture says the same thing standing still
            withAnimation(.easeInOut(duration: 2.2).repeatForever(autoreverses: false)) {
                travel = 1
            }
        }
        .accessibilityElement(children: .ignore)
        .accessibilityLabel("A picture: you talk to your assistant, and it keeps your wiki.")
    }

    private func node(_ symbol: String, _ label: String,
                      x: CGFloat, y: CGFloat, delay: Double) -> some View {
        VStack(spacing: 10) {
            ZStack {
                Circle()
                    .fill(Theme.card)
                    .overlay(Circle().stroke(Theme.cardEdge, lineWidth: 1))
                    .shadow(color: .black.opacity(0.12), radius: 10, y: 4)
                    .frame(width: 104, height: 104)
                Image(systemName: symbol)
                    .font(.system(size: 44, weight: .medium))
                    .foregroundStyle(Theme.accent)
            }
            Text(label)
                .font(.system(size: 17, weight: .semibold, design: .rounded))
                .foregroundStyle(.primary)
        }
        .position(x: x, y: y + 14)
        .scaleEffect(appeared ? 1 : 0.6)
        .opacity(appeared ? 1 : 0)
        .animation(.spring(response: 0.55, dampingFraction: 0.7).delay(delay), value: appeared)
    }
}

