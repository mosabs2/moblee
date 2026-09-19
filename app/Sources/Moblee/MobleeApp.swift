import SwiftUI

@main
struct MobleeApp: App {
    @StateObject private var flow = Flow()

    init() {
        MainActor.assumeIsolated { Snapshots.runIfAsked() }
    }

    var body: some Scene {
        WindowGroup("Moblee") {
            RootView()
                .environmentObject(flow)
                .frame(width: 720, height: 520)
        }
        .windowResizability(.contentSize)
        .windowStyle(.hiddenTitleBar)
    }
}

/// The screens, in the order the owner meets them.
enum Step: Int, CaseIterable {
    case welcome
    case checkup
    case comingNext
}

/// Where the owner is, and the settings a run was started with.
final class Flow: ObservableObject {
    @Published var step: Step = .welcome

    /// Test mode: `--home <folder>` (or MOBLEE_TEST_HOME) makes the whole run
    /// treat that folder as the home folder, so an install can be rehearsed
    /// without touching the real one.
    let home: URL
    let isTestMode: Bool

    init() {
        let args = CommandLine.arguments
        var chosen: String? = ProcessInfo.processInfo.environment["MOBLEE_TEST_HOME"]
        if let i = args.firstIndex(of: "--home"), i + 1 < args.count {
            chosen = args[i + 1]
        }
        if let chosen, !chosen.isEmpty {
            home = URL(fileURLWithPath: chosen, isDirectory: true)
            isTestMode = true
        } else {
            home = FileManager.default.homeDirectoryForCurrentUser
            isTestMode = false
        }
        if let i = args.firstIndex(of: "--step"), i + 1 < args.count,
           let n = Int(args[i + 1]), let s = Step(rawValue: n) {
            step = s
        }
    }

    func next() {
        if let s = Step(rawValue: step.rawValue + 1) {
            withAnimation(.easeInOut(duration: 0.35)) { step = s }
        }
    }

    func back() {
        if let s = Step(rawValue: step.rawValue - 1) {
            withAnimation(.easeInOut(duration: 0.35)) { step = s }
        }
    }
}

struct RootView: View {
    @EnvironmentObject var flow: Flow

    var body: some View {
        ZStack(alignment: .top) {
            Theme.background.ignoresSafeArea()

            Group {
                switch flow.step {
                case .welcome: WelcomeScreen()
                case .checkup: CheckupScreen()
                case .comingNext: ComingNextScreen()
                }
            }
            .transition(.asymmetric(
                insertion: .move(edge: .trailing).combined(with: .opacity),
                removal: .move(edge: .leading).combined(with: .opacity)))

            if flow.isTestMode {
                Text("Practice run")
                    .font(.caption.weight(.semibold))
                    .padding(.horizontal, 10).padding(.vertical, 4)
                    .background(.orange.opacity(0.85), in: Capsule())
                    .foregroundStyle(.white)
                    .padding(.top, 10)
            }
        }
    }
}
