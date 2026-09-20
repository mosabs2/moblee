import Foundation

/// `--check-logic` (only with `--home <practice folder>`) checks the decisions
/// the app makes about the assistant without opening a window or running any
/// of the pack's scripts: whether an update asks the question first, what it
/// then tells the updater, how a progress line about ChatGPT's trust is taken,
/// how the proof's findings are read, and how the link into ChatGPT is made.
/// It writes only inside the practice home. Exit code 0 means every check held.
@MainActor
enum LogicCheck {
    static func run() -> Never {
        let flow = Flow()
        guard flow.isTestMode else {
            print("--check-logic only runs with --home <practice folder>; nothing was done.")
            exit(2)
        }
        var failed = 0
        func check(_ what: String, _ ok: Bool) {
            print("logic: \(ok ? "ok" : "FAILED"): \(what)")
            if !ok { failed += 1 }
        }
        let home = flow.home
        let file = Assistant.file(home: home)
        func record(_ text: String) {
            try? FileManager.default.createDirectory(at: file.deletingLastPathComponent(), withIntermediateDirectories: true)
            try? text.write(to: file, atomically: true, encoding: .utf8)
        }

        // --- whether an update asks first, and what it then tells the updater ---
        if !FileManager.default.fileExists(atPath: file.path) {
            check("with no choice on record, an update asks the question first", Assistant.mustAsk(home: home))
            check("and the scripts' reading of no file is Claude", Assistant.onRecord(home: home) == .claude)
            flow.beginUpdate()
            check("pressing Update then shows the question before the update", flow.mode == .update && flow.askingAssistant)
            flow.updateAssistant = .both
            flow.updateQuestionAnswered()
            check("the answer is what the updater is told",
                  Assistant.updateOption(answered: flow.updateAssistant) == ["--assistant", "both"])
            flow.cancelUpdateQuestion()
            check("Not now on the question goes back home with nothing to tell the updater",
                  flow.mode == .home && !flow.askingAssistant && flow.updateAssistant == nil)
        } else {
            check("the practice home had no choice on record to begin with", false)
        }
        for (text, expected) in [("claude\n", Assistant.claude), ("chatgpt\n", .chatgpt), ("both\n", .both), (" both \n", .both)] {
            record(text)
            check("a record of \(expected.rawValue) is read as such, and an update asks nothing",
                  Assistant.stored(home: home) == expected && !Assistant.mustAsk(home: home))
        }
        record("chatgpt\n")
        flow.beginUpdate()
        check("with a choice on record, pressing Update goes straight to the update", flow.mode == .update && !flow.askingAssistant)
        check("and the updater is told nothing, so the record stands",
              Assistant.updateOption(answered: flow.updateAssistant).isEmpty)
        flow.cancelUpdateQuestion()
        flow.beginUpdate(changingAssistant: true)
        check("Change asks the question even with a choice on record", flow.askingAssistant)
        flow.cancelUpdateQuestion()
        record("Both\n")
        check("a word written as the scripts would not read it counts as no choice", Assistant.mustAsk(home: home))
        record("somebody-else\n")
        check("a word the scripts do not know counts as no choice: the update asks, and the scripts read Claude",
              Assistant.mustAsk(home: home) && Assistant.onRecord(home: home) == .claude)
        record("claude\n")

        // --- progress lines ---
        let run = InstallRun()
        run.handle(["step": "trust", "state": "needed", "assistant": "chatgpt"])
        check("the trust-needed line is noticed", run.trustNeeded)
        let quiet = InstallRun()
        quiet.handle(["step": "trust", "state": "something-new"])
        quiet.handle(["step": "a-step-from-the-future", "state": "start", "n": 3, "of": 9])
        quiet.handle(["state": "needed"])
        quiet.handle(["step": "safety", "state": "a-state-from-the-future"])
        check("lines that are not understood are ignored: no trust step, nothing failed, no tile changed",
              !quiet.trustNeeded && quiet.phase == .idle && quiet.items.allSatisfy { $0.state == .waiting })

        // --- the proof's findings ---
        func rows(_ list: [[String: Any]]) -> Data { (try? JSONSerialization.data(withJSONObject: list)) ?? Data() }
        check("a Proved line is read as proved",
              GuardProof.read(rows([["level": "OK", "text": "This wiki is set up to be used with ChatGPT.", "guide": NSNull()],
                                    ["level": "OK", "text": "Proved: the delete guard is running in ChatGPT.", "guide": NSNull()]])) == .proved)
        check("a guard seen not to run is read as not running",
              GuardProof.read(rows([["level": "PROBLEM", "text": "The delete guard is not running in ChatGPT. Asked to remove", "guide": "F26"]])) == .notRunning)
        check("CANNOT TELL is read as could not tell",
              GuardProof.read(rows([["level": "CANNOT TELL", "text": "ChatGPT is not signed in on this Mac", "guide": NSNull()]])) == .cannotTell)
        check("some other problem is never taken for a verdict on the guard",
              GuardProof.read(rows([["level": "PROBLEM", "text": "The delete guard is not installed for ChatGPT.", "guide": "F02"]])) == .cannotTell)
        check("nothing readable is read as could not tell", GuardProof.read(Data("Traceback".utf8)) == .cannotTell)

        // --- the link into ChatGPT ---
        check("the link carries the absolute path, percent-encoded",
              ChatGPTApp.link(toFolder: "/Users/sam/Wiki/Tom & Sam Wiki")?.absoluteString
                  == "codex://new?path=/Users/sam/Wiki/Tom%20%26%20Sam%20Wiki")
        check("an accented letter is encoded too",
              ChatGPTApp.link(toFolder: "/Users/zoë/Wiki")?.absoluteString == "codex://new?path=/Users/zo%C3%AB/Wiki")
        check("a path that is not absolute makes no link", ChatGPTApp.link(toFolder: "Wiki/Sam Wiki") == nil)

        // --- the note that the Trust step is waiting ---
        check("no note means nothing is waiting", !Trust.pending(home: home))
        Trust.setPending(true, home: home)
        check("the note is kept", Trust.pending(home: home))
        Trust.setPending(false, home: home)
        check("and answered, without being deleted",
              !Trust.pending(home: home) && FileManager.default.fileExists(atPath: Trust.note(home: home).path))

        print(failed == 0 ? "logic: every check held" : "logic: \(failed) check(s) FAILED")
        exit(failed == 0 ? 0 : 1)
    }
}
