import SwiftUI

/// `--self-drive` (only with `--home <practice folder>`) opens the real window
/// and walks through every screen by itself, doing a real install into the
/// practice home folder on the way, then quits. Exit code 0 means every screen
/// opened and the install finished; a crash or a failed install is non-zero.
///
/// The picture-file drawing and the rehearsal never open a window, so they
/// cannot catch a fault that only happens while SwiftUI is drawing live
/// screens. This does. It is run before the app is ever put in front of a
/// person.
@MainActor
enum SelfDrive {
    static var asked: Bool { CommandLine.arguments.contains("--self-drive") }

    static func run(_ flow: Flow) async {
        guard flow.isTestMode else {
            print("--self-drive only runs with --home <practice folder>; nothing was done.")
            exit(2)
        }
        func say(_ s: String) { print("self-drive: \(s)"); fflush(stdout) }
        func pause(_ seconds: Double) async {
            try? await Task.sleep(nanoseconds: UInt64(seconds * 1_000_000_000))
        }

        say("welcome"); await pause(1.5)
        flow.next(); say("check-up"); await pause(7)      // long enough for two re-looks
        flow.next(); say("name"); await pause(1)
        flow.ownerName = "Tom & Sam"; await pause(1)
        flow.back(); say("back to check-up"); await pause(4)
        flow.next(); say("name again"); await pause(1)
        flow.next(); say("build")

        let deadline = Date().addingTimeInterval(180)
        while (flow.install.phase == .idle || flow.install.phase == .running) && Date() < deadline {
            await pause(0.2)
        }
        say("build ended: \(flow.install.phase)")
        await pause(1.5)
        flow.next(); say("hand-off"); await pause(2)

        let ok = flow.install.phase == .finished
        say(ok ? "every screen opened and the install finished" : "the install did not finish")
        exit(ok ? 0 : 1)
    }
}
