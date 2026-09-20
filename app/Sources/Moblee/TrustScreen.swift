import SwiftUI
import AppKit

/// ChatGPT does not run a newly installed or changed hook until its owner has
/// trusted it, in ChatGPT's own settings, and only the owner can do that. Until
/// then ChatGPT skips the delete guard and nothing on its screen says so. The
/// installer and the updater say when this is so, on a line of their own; this
/// is where the app keeps that fact until the owner has acted on it.
enum Trust {
    /// A note of the app's own, beside its other notes. It says "yes" while
    /// the owner has still to press Trust, and "no" afterwards; it is never
    /// deleted. Kept on disk so that closing Moblee at the Trust screen does
    /// not lose the step: the home screen shows it the next time.
    static func note(home: URL) -> URL { home.appendingPathComponent(".config/moblee/trust-pending") }

    static func pending(home: URL) -> Bool {
        let text = (try? String(contentsOf: note(home: home), encoding: .utf8)) ?? ""
        return text.trimmingCharacters(in: .whitespacesAndNewlines) == "yes"
    }

    static func setPending(_ on: Bool, home: URL) {
        let file = note(home: home)
        if !on && !FileManager.default.fileExists(atPath: file.path) { return }
        try? FileManager.default.createDirectory(at: file.deletingLastPathComponent(), withIntermediateDirectories: true)
        try? ((on ? "yes" : "no") + "\n").write(to: file, atomically: true, encoding: .utf8)
    }

    /// The five steps, as verified in the ChatGPT app for Mac.
    static let steps = [
        "Open the ChatGPT menu and choose Settings",
        "Choose Hooks, under the heading Coding",
        "Open “User config”",
        "Press Trust beside the hook that ends bash-guard.py",
        "Turn its switch on",
    ]
}

/// Proving the guard: the pack's own check-up, asked to put the guard to the
/// test (`moblee-doctor.py --prove-guard --json`). It asks ChatGPT's agent to
/// remove two things in a scratch wiki and passes only if both survive. The
/// owner's wiki is never touched. It can take three minutes.
enum GuardProof {
    enum Result: Equatable { case proved, notRunning, cannotTell }

    /// Reads the check-up's findings. Only two lines decide anything: the one
    /// that says the guard was proved, and the one that says ChatGPT deleted
    /// what it was asked to. Anything else, or nothing readable at all, is
    /// "could not tell".
    static func read(_ data: Data) -> Result {
        guard let rows = (try? JSONSerialization.jsonObject(with: data)) as? [[String: Any]] else { return .cannotTell }
        var result = Result.cannotTell
        for row in rows {
            let level = row["level"] as? String ?? "", text = row["text"] as? String ?? ""
            if level == "PROBLEM" && text.hasPrefix("The delete guard is not running in ChatGPT") { return .notRunning }
            if level == "OK" && text.hasPrefix("Proved:") { result = .proved }
        }
        return result
    }

    @MainActor
    static func run(home: URL, bundledPack: URL?, vault: String?, then: @escaping @MainActor (Result) -> Void) {
        guard let bundledPack else { then(.cannotTell); return }
        // Copying the pack into place is file work, so it happens off the main thread.
        DispatchQueue.global(qos: .userInitiated).async {
            let settled = try? InstallRun.settlePack(bundledPack, home: home)
            DispatchQueue.main.async {
                MainActor.assumeIsolated {
                    guard let settled else { then(.cannotTell); return }
                    var arguments = [settled.appendingPathComponent("scripts/moblee-doctor.py").path,
                                     "--prove-guard", "--json"]
                    if let vault { arguments += ["--vault", vault] }
                    EngineTask.output(of: "/usr/bin/python3", arguments, home: home) { _, data in then(read(data)) }
                }
            }
        }
    }
}

/// The Trust screen, and the proof that follows it.
///
/// First the reason and the five steps, with a button that opens ChatGPT and a
/// large "I have done it". Then the offer to prove it, which the owner may put
/// off ("Later"): nothing after this screen waits for the proof. Then one of
/// three plain results.
///
/// Shown after an install or an update that said the step is needed, before
/// the hand-off; at home when an earlier run's step was never answered, or a
/// repair changed the guard; and, starting at the offer, when the owner presses
/// "Prove the guard" at home.
struct TrustScreen: View {
    enum Stage { case steps, offer, proving, proved, notRunning, cannotTell }

    let vault: String?
    let done: () -> Void

    @EnvironmentObject var flow: Flow
    @EnvironmentObject var home: HomeModel
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @State private var stage: Stage

    init(start: Stage = .steps, vault: String?, done: @escaping () -> Void) {
        self.vault = vault
        self.done = done
        _stage = State(initialValue: start)
    }

    var body: some View {
        ScreenFrame(
            sentence: sentence,
            buttonTitle: buttonTitle,
            buttonEnabled: stage != .proving,
            showsBack: false,
            quietTitle: quietTitle,
            quietAction: quietTitle == nil ? nil : done,
            spoken: spoken,
            action: act
        ) {
            switch stage {
            case .steps, .notRunning:
                VStack(spacing: 12) {
                    TrustSteps()
                    openChatGPT
                }
            case .offer:
                shield("lock.shield.fill", Theme.accent)
            case .proving:
                VStack(spacing: 16) {
                    Image(systemName: "lock.shield.fill")
                        .font(.system(size: 96)).foregroundStyle(Theme.accent)
                        .symbolEffect(.pulse, options: .repeating, isActive: !reduceMotion)
                        .accessibilityHidden(true)
                    Text("Your wiki is not touched.")
                        .font(.system(size: 15, weight: .medium, design: .rounded))
                        .foregroundStyle(.secondary)
                }
            case .proved:
                shield("checkmark.shield.fill", Theme.good)
            case .cannotTell:
                VStack(spacing: 18) {
                    shield("questionmark.circle.fill", Theme.waiting)
                    openChatGPT
                }
            }
        }
    }

    private func shield(_ symbol: String, _ colour: Color) -> some View {
        Image(systemName: symbol)
            .font(.system(size: 96)).foregroundStyle(colour)
            .accessibilityHidden(true)
    }

    private var openChatGPT: some View {
        Button("Open ChatGPT") { ChatGPTApp.open(folder: nil, practice: flow.isTestMode) }
            .buttonStyle(.bordered).controlSize(.large)
            .font(.system(size: 15, weight: .semibold, design: .rounded))
            .accessibilityIdentifier("open-chatgpt")
    }

    private var sentence: String {
        switch stage {
        case .steps: return "ChatGPT will not run your wiki's delete guard until you tell it to trust it."
        case .offer: return "Moblee can prove the guard is running in ChatGPT. It can take three minutes."
        case .proving: return "Testing the guard in a practice folder. This can take three minutes."
        case .proved: return "Proved. The delete guard is running in ChatGPT."
        case .notRunning: return "The guard is not running in ChatGPT yet. Do these five steps again."
        case .cannotTell: return "Moblee could not tell. Open ChatGPT once, sign in, then try again."
        }
    }

    private var spoken: String? {
        switch stage {
        case .steps, .notRunning:
            let numbered = zip(["One", "Two", "Three", "Four", "Five"], Trust.steps).map { "\($0): \($1)." }
            return sentence + " " + numbered.joined(separator: " ")
        default: return nil
        }
    }

    private var buttonTitle: String {
        switch stage {
        case .steps, .notRunning: return "I have done it"
        case .offer: return "Prove it"
        case .proving, .proved: return "Next"
        case .cannotTell: return "Try again"
        }
    }

    /// Everything after the steps can be put off. The steps themselves cannot:
    /// the guard does nothing in ChatGPT until they are done.
    private var quietTitle: String? {
        switch stage {
        case .offer, .notRunning, .cannotTell: return "Later"
        case .steps, .proving, .proved: return nil
        }
    }

    private func act() {
        switch stage {
        case .steps, .notRunning:
            Trust.setPending(false, home: flow.home)
            home.refreshTrust(home: flow.home)
            withAnimation(.easeInOut(duration: 0.25)) { stage = .offer }
        case .offer, .cannotTell:
            prove()
        case .proving:
            break
        case .proved:
            done()
        }
    }

    private func prove() {
        withAnimation(.easeInOut(duration: 0.25)) { stage = .proving }
        GuardProof.run(home: flow.home, bundledPack: flow.bundledPack, vault: vault) { result in
            // A guard seen not to be running is a step still to be done: if the
            // owner puts it off now, the home screen brings it back another day.
            if result == .notRunning {
                Trust.setPending(true, home: flow.home)
                home.refreshTrust(home: flow.home)
            }
            withAnimation(.easeInOut(duration: 0.3)) {
                switch result {
                case .proved: stage = .proved
                case .notRunning: stage = .notRunning
                case .cannotTell: stage = .cannotTell
                }
            }
        }
    }
}

/// The five steps as a short numbered list, on a card.
struct TrustSteps: View {
    var body: some View {
        VStack(alignment: .leading, spacing: 9) {
            ForEach(Array(Trust.steps.enumerated()), id: \.offset) { i, step in
                HStack(alignment: .center, spacing: 12) {
                    Text("\(i + 1)")
                        .font(.system(size: 14, weight: .bold, design: .rounded))
                        .foregroundStyle(.white)
                        .frame(width: 26, height: 26)
                        .background(Circle().fill(Theme.accent))
                        .accessibilityHidden(true)
                    Text(step)
                        .font(.system(size: 16, weight: .medium, design: .rounded))
                        .foregroundStyle(.primary)
                        .fixedSize(horizontal: false, vertical: true)
                }
                .accessibilityElement(children: .ignore)
                .accessibilityLabel("Step \(i + 1). \(step)")
            }
        }
        .padding(.horizontal, 22).padding(.vertical, 16)
        .frame(width: 520, alignment: .leading)
        .background(CardBackground(corner: 20))
    }
}
