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
    ///
    /// It turns to "no" only when the guard has been proved, or when the owner
    /// has said the steps are done and put the proof off. Saying "I have done
    /// it" does not by itself change it, and neither does "Later" on the steps:
    /// a Moblee closed half-way, or a proof cut short, leaves the step waiting.
    static func note(home: URL) -> URL { home.appendingPathComponent(".config/moblee/trust-pending") }

    static func pending(home: URL) -> Bool {
        let text = (try? String(contentsOf: note(home: home), encoding: .utf8)) ?? ""
        return text.trimmingCharacters(in: .whitespacesAndNewlines) == "yes"
    }

    /// Whether the step is waiting for THIS owner. A note left from a time
    /// when the wiki was for ChatGPT says nothing to an owner who now uses
    /// Claude alone: ChatGPT's guard is no longer theirs to keep running.
    static func pending(home: URL, for assistant: Assistant) -> Bool {
        assistant.wantsChatGPT && pending(home: home)
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

    /// Before the five steps. ChatGPT's Hooks page lists nothing at all, and
    /// gives no reason, until a folder has been opened in ChatGPT at least
    /// once (seen in a real install on 21 September 2026): an owner who goes
    /// straight to the steps finds an empty page and no guard to trust. So the
    /// wiki folder is opened first, by ChatGPT's own File menu, which is the
    /// way that makes the wiki the folder ChatGPT works in.
    static let openFirst = "First open your wiki folder in ChatGPT: File menu, Open Folder."
    static let emptyUntilOpened = "Until a folder has been opened, ChatGPT's Hooks page is empty."
    /// Said after a proof that saw the guard not running. The likeliest cause
    /// comes first: with no folder ever opened in ChatGPT the Hooks page was
    /// empty, and there was nothing there to trust.
    static let folderThenSteps = "Open your wiki folder in ChatGPT first (File menu, Open Folder), then do the five steps."

    /// Where the Trust screen begins when the step is waiting: at the folder,
    /// before the steps.
    static let firstStage = TrustScreen.Stage.openFolder

    /// Where the big button leads from the stages the owner works through by
    /// hand: the folder, then the steps, then the offer of a proof. Nil for a
    /// stage whose button does something else (proves, tries again, leaves).
    static func stage(after stage: TrustScreen.Stage) -> TrustScreen.Stage? {
        switch stage {
        case .openFolder: return .steps
        case .steps, .notRunning: return .offer
        case .offer, .proving, .proved, .cannotTell: return nil
        }
    }

    /// "Later", pressed at one of the Trust screen's stages. At the folder, at
    /// the steps, or after a proof that saw the guard not running, the step is
    /// still to be done and the note is left saying so. After the owner has
    /// said the steps are done (the offer, or a proof that could not tell),
    /// putting the proof off is theirs to choose, and the note is answered.
    static func putOff(at stage: TrustScreen.Stage, home: URL) {
        switch stage {
        case .offer, .cannotTell: setPending(false, home: home)
        case .openFolder, .steps, .notRunning, .proving, .proved: break
        }
    }

    /// What a proof's result does to the note: proved answers it; a guard seen
    /// not to be running sets it, even for an owner who had no note before;
    /// "could not tell" leaves it as it was.
    static func record(_ result: GuardProof.Result, home: URL) {
        switch result {
        case .proved: setPending(false, home: home)
        case .notRunning: setPending(true, home: home)
        case .cannotTell: break
        }
    }

    /// The assistant the proof is run for, named to the check-up so that it
    /// and the app cannot read the record differently. The proof is only ever
    /// of ChatGPT's guard, so a record that does not include ChatGPT (it
    /// should not happen: the Trust screen is not shown then) is not passed on.
    static func proofAssistant(home: URL) -> Assistant {
        let onRecord = Assistant.onRecord(home: home)
        return onRecord.wantsChatGPT ? onRecord : .chatgpt
    }

    /// Said quietly beneath the steps, wherever they are shown.
    static let afterwards = "If ChatGPT is open, quit it and open it again afterwards."
}

/// Proving the guard: the pack's own check-up, asked to put the guard to the
/// test (`moblee-doctor.py --prove-guard --json`). It asks ChatGPT's agent to
/// remove two things in a scratch wiki and passes only if both survive. The
/// owner's wiki is never touched. It can take three minutes.
enum GuardProof {
    enum Result: Equatable { case proved, notRunning, cannotTell }

    /// Reads the check-up's findings (a list of rows, each with a `level`, a
    /// `text` and a `guide`). Two rows decide anything, and each is known by
    /// its fields as far as the fields allow:
    ///
    ///   not running   level PROBLEM with guide F26. F26 is the field guide's
    ///                 entry for an untrusted guard, and the only PROBLEM that
    ///                 carries it is the one raised when ChatGPT did delete.
    ///   proved        level OK whose text begins "Proved:". An OK row carries
    ///                 no guide, so here the opening word is all there is; the
    ///                 check-up keeps it, and the logic check reads a real
    ///                 sample of the check-up's output to notice if it moves.
    ///
    /// Anything else, or nothing readable at all, is "could not tell". A row
    /// that says not running always wins over one that says proved.
    static func read(_ data: Data) -> Result {
        guard let rows = (try? JSONSerialization.jsonObject(with: data)) as? [[String: Any]] else { return .cannotTell }
        var result = Result.cannotTell
        for row in rows {
            let level = row["level"] as? String ?? "", text = row["text"] as? String ?? ""
            let guide = row["guide"] as? String ?? ""
            if level == "PROBLEM" && guide == "F26" { return .notRunning }
            if level == "OK" && text.hasPrefix("Proved:") { result = .proved }
        }
        return result
    }

    /// The proof that is running now, if one is. Kept so that it can be ended:
    /// a proof left running after Moblee has closed would go on using the
    /// owner's ChatGPT allowance for minutes with nobody to read the answer.
    @MainActor private static var running: Process?
    /// Goes up whenever a proof is started or ended, so that an answer which
    /// arrives for an ended proof is dropped.
    @MainActor private static var turn = 0

    /// Python is started by a line that first puts it in a process group of
    /// its own and then becomes the check-up. The check-up starts ChatGPT's
    /// agent, which starts programs of its own; one signal to the group ends
    /// them all, where ending the check-up alone would orphan the rest.
    private static let ownGroup = "import os, sys\nos.setpgid(0, 0)\nos.execv(sys.argv[1], sys.argv[1:])"

    @MainActor
    static func run(home: URL, bundledPack: URL?, vault: String?, assistant: Assistant,
                    then: @escaping @MainActor (Result) -> Void) {
        stop()
        guard let bundledPack else { then(.cannotTell); return }
        turn += 1
        let mine = turn
        // Copying the pack into place is file work, so it happens off the main thread.
        DispatchQueue.global(qos: .userInitiated).async {
            let settled = try? InstallRun.settlePack(bundledPack, home: home)
            DispatchQueue.main.async {
                MainActor.assumeIsolated {
                    guard mine == turn else { return }
                    guard let settled else { then(.cannotTell); return }
                    let python = "/usr/bin/python3"
                    // The assistant is named, as the app read it, so that the
                    // check-up and the app cannot read the record differently.
                    var arguments = ["-c", ownGroup, python,
                                     settled.appendingPathComponent("scripts/moblee-doctor.py").path,
                                     "--prove-guard", "--json", "--assistant", assistant.rawValue]
                    if let vault { arguments += ["--vault", vault] }
                    let p = Process()
                    p.executableURL = URL(fileURLWithPath: python)
                    p.arguments = arguments
                    p.environment = EngineTask.environment(home: home)
                    p.standardInput = FileHandle.nullDevice
                    let out = Pipe()
                    p.standardOutput = out
                    p.standardError = FileHandle.nullDevice
                    do { try p.run() } catch { then(.cannotTell); return }
                    running = p
                    DispatchQueue.global(qos: .userInitiated).async {
                        let data = out.fileHandleForReading.readDataToEndOfFile()
                        p.waitUntilExit()
                        DispatchQueue.main.async {
                            MainActor.assumeIsolated {
                                if running === p { running = nil }
                                guard mine == turn else { return }
                                then(read(data))
                            }
                        }
                    }
                }
            }
        }
    }

    /// Ends the proof, and everything it started, if one is running: called
    /// when the Trust screen goes away and when Moblee closes.
    @MainActor
    static func stop() {
        turn += 1
        guard let p = running else { return }
        running = nil
        guard p.isRunning else { return }
        let pid = p.processIdentifier
        // The whole group; if it has not yet made its own (the first instant
        // of its life), the one process.
        if pid <= 1 || kill(-pid, SIGTERM) != 0 { p.terminate() }
    }
}

/// The Trust screen, and the proof that follows it.
///
/// First the reason, in two beats of one screen, since both do not fit the
/// window at a size that can be read: open the wiki folder in ChatGPT (a
/// button opens ChatGPT at it), then the five steps, with the same button and
/// a large "I have done it". Then the offer to prove it, which the owner may
/// put off ("Later"): nothing after this screen waits for the proof. Then one
/// of three plain results. The folder and the steps can be put off too; the
/// step then stays waiting (see `Trust.putOff`), and the home screen shows it
/// the next time.
///
/// Shown after an install or an update that said the step is needed, before
/// the hand-off; at home when an earlier run's step was never answered, or a
/// repair changed the guard; and, starting at the offer, when the owner presses
/// "Prove the guard" at home.
struct TrustScreen: View {
    enum Stage { case openFolder, steps, offer, proving, proved, notRunning, cannotTell }

    let vault: String?
    let done: () -> Void

    @EnvironmentObject var flow: Flow
    @EnvironmentObject var home: HomeModel
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @State private var stage: Stage

    init(start: Stage = Trust.firstStage, vault: String?, done: @escaping () -> Void) {
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
            quietAction: quietTitle == nil ? nil : later,
            spoken: spoken,
            // The verdict is one line, which leaves room for the line that
            // sends the owner to the folder first, above the steps.
            pictureHeight: stage == .notRunning ? 310 : 280,
            action: act
        ) {
            switch stage {
            case .openFolder:
                VStack(spacing: 16) {
                    OpenFolderFirst()
                    openChatGPT
                }
            case .steps, .notRunning:
                VStack(spacing: 8) {
                    if stage == .notRunning {
                        Text(Trust.folderThenSteps)
                            .font(.system(size: 16, weight: .semibold, design: .rounded))
                            .foregroundStyle(.primary)
                            .multilineTextAlignment(.center)
                            .fixedSize(horizontal: false, vertical: true)
                            .frame(width: 520)
                    }
                    TrustSteps()
                    Text(Trust.afterwards)
                        .font(.system(size: 13, weight: .medium, design: .rounded))
                        .foregroundStyle(.secondary)
                    openChatGPT
                }
            case .offer:
                VStack(spacing: 16) {
                    shield("lock.shield.fill", Theme.accent)
                    Text(Self.allowance)
                        .font(.system(size: 15, weight: .medium, design: .rounded))
                        .foregroundStyle(.secondary)
                }
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
        // Whatever takes this screen away (Later, a repair that cannot wait,
        // the window closing) ends a proof that is still running.
        .onDisappear { GuardProof.stop() }
    }

    private func shield(_ symbol: String, _ colour: Color) -> some View {
        Image(systemName: symbol)
            .font(.system(size: 96)).foregroundStyle(colour)
            .accessibilityHidden(true)
    }

    /// Opens ChatGPT at the wiki folder, as the hand-off does: the link first,
    /// and the app alone if the link is not taken. With no wiki known, the app.
    private var openChatGPT: some View {
        Button("Open ChatGPT") { ChatGPTApp.open(folder: vault, practice: flow.isTestMode) }
            .buttonStyle(.bordered).controlSize(.large)
            .font(.system(size: 15, weight: .semibold, design: .rounded))
            .accessibilityIdentifier("open-chatgpt")
    }

    private var sentence: String {
        switch stage {
        case .openFolder, .steps: return Self.reasonSentence
        case .offer: return "Moblee can prove the guard is running in ChatGPT. It can take three minutes."
        case .proving: return "Testing the guard in a practice folder. This can take three minutes."
        case .proved: return Self.provedSentence
        case .notRunning: return Self.notRunningSentence
        case .cannotTell: return Self.cannotTellSentence
        }
    }

    /// The same over both beats, the folder and the steps: one screen, one reason.
    static let reasonSentence = "ChatGPT will not run your wiki's delete guard until you tell it to trust it."
    /// The verdict alone. What to do about it (`Trust.folderThenSteps`) is said
    /// beneath it, above the steps.
    static let notRunningSentence = "The guard is not running in ChatGPT yet."
    static let provedSentence = "Proved. Asked to remove a folder and delete a page in a practice folder, ChatGPT was refused."
    static let cannotTellSentence = "Moblee could not tell. Check that ChatGPT is signed in, then try again."
    static let allowance = "It uses a little of your ChatGPT allowance."

    private var spoken: String? {
        switch stage {
        case .openFolder:
            return sentence + " " + Trust.openFirst + " " + Trust.emptyUntilOpened
        case .steps, .notRunning:
            let numbered = zip(["One", "Two", "Three", "Four", "Five"], Trust.steps).map { "\($0): \($1)." }
            let first = stage == .notRunning ? " " + Trust.folderThenSteps : ""
            return sentence + first + " " + numbered.joined(separator: " ") + " " + Trust.afterwards
        case .offer: return sentence + " " + Self.allowance
        default: return nil
        }
    }

    private var buttonTitle: String {
        switch stage {
        case .openFolder: return Self.openedTitle
        case .steps, .notRunning: return "I have done it"
        case .offer: return "Prove it"
        case .proving, .proved: return "Next"
        case .cannotTell: return "Try again"
        }
    }

    static let openedTitle = "I have opened it"

    /// Every stage but the test itself can be put off, the folder and the
    /// steps included: an owner who cannot do them now (ChatGPT not signed in,
    /// no time, the wrong assistant chosen) must not have "I have done it" as
    /// the only way on, since it would not be true. Put off there, the step
    /// stays waiting and the home screen brings it back the next time Moblee
    /// opens.
    private var quietTitle: String? {
        switch stage {
        case .openFolder, .steps, .offer, .notRunning, .cannotTell: return "Later"
        case .proving, .proved: return nil
        }
    }

    private func later() {
        Trust.putOff(at: stage, home: flow.home)
        home.refreshTrust(home: flow.home)
        done()
    }

    private func act() {
        switch stage {
        case .openFolder, .steps, .notRunning:
            // The note is left as it is: said done is not yet seen done.
            guard let next = Trust.stage(after: stage) else { return }
            withAnimation(.easeInOut(duration: 0.25)) { stage = next }
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
        GuardProof.run(home: flow.home, bundledPack: flow.bundledPack, vault: vault,
                       assistant: Trust.proofAssistant(home: flow.home)) { result in
            Trust.record(result, home: flow.home)
            home.refreshTrust(home: flow.home)
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

/// What comes before the five steps, on a card of its own: the instruction,
/// large, and quieter beneath it the reason it cannot be skipped.
struct OpenFolderFirst: View {
    var body: some View {
        VStack(spacing: 12) {
            Image(systemName: "folder.fill")
                .font(.system(size: 56, weight: .medium))
                .foregroundStyle(Theme.accent)
                .accessibilityHidden(true)
            Text(Trust.openFirst)
                .font(.system(size: 19, weight: .semibold, design: .rounded))
                .foregroundStyle(.primary)
                .multilineTextAlignment(.center)
                .fixedSize(horizontal: false, vertical: true)
            Text(Trust.emptyUntilOpened)
                .font(.system(size: 14, weight: .medium, design: .rounded))
                .foregroundStyle(.secondary)
                .multilineTextAlignment(.center)
                .fixedSize(horizontal: false, vertical: true)
        }
        .padding(.horizontal, 26).padding(.vertical, 22)
        .frame(width: 520)
        .background(CardBackground(corner: 20))
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(Trust.openFirst + " " + Trust.emptyUntilOpened)
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
