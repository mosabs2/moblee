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

            // --- a lost choice file: what the wiki's own rules files show ---
            // Made-up wikis in a folder of the check's own (never "Wiki", which
            // would look like an install), one for each way the files are laid down.
            let fm = FileManager.default
            let yard = home.appendingPathComponent("logic-check/wikis", isDirectory: true)
            func wiki(_ name: String, real: [String], links: [String: String]) -> URL {
                let v = yard.appendingPathComponent(name, isDirectory: true)
                try? fm.createDirectory(at: v.appendingPathComponent("wiki"), withIntermediateDirectories: true)
                for r in real { try? "# rules\n".write(to: v.appendingPathComponent(r), atomically: true, encoding: .utf8) }
                for (from, to) in links {
                    try? fm.createSymbolicLink(atPath: v.appendingPathComponent(from).path, withDestinationPath: to)
                }
                return v
            }
            let forChatGPT = wiki("chatgpt-with-link", real: ["AGENTS.md"], links: ["CLAUDE.md": "AGENTS.md"])
            let linkDropped = wiki("chatgpt-link-dropped", real: ["AGENTS.md"], links: [:])
            let forBoth = wiki("both", real: ["CLAUDE.md"], links: ["AGENTS.md": "CLAUDE.md"])
            let forClaude = wiki("claude", real: ["CLAUDE.md"], links: [:])
            let twoFiles = wiki("two-real-files", real: ["CLAUDE.md", "AGENTS.md"], links: [:])
            check("a real AGENTS.md with CLAUDE.md a link to it is read as a wiki for ChatGPT",
                  Assistant.inferred(vault: forChatGPT) == .chatgpt)
            check("and so is a real AGENTS.md whose link a sync tool dropped",
                  Assistant.inferred(vault: linkDropped) == .chatgpt)
            check("a real CLAUDE.md says nothing about the assistant, with an AGENTS.md link, without one, or beside a real AGENTS.md",
                  Assistant.inferred(vault: forBoth) == nil && Assistant.inferred(vault: forClaude) == nil
                      && Assistant.inferred(vault: twoFiles) == nil)
            let vaultNote = home.appendingPathComponent(".config/moblee/vault-path")
            func pointAt(_ v: URL) {
                try? fm.createDirectory(at: vaultNote.deletingLastPathComponent(), withIntermediateDirectories: true)
                try? (v.path + "\n").write(to: vaultNote, atomically: true, encoding: .utf8)
            }
            var recognised = true
            for v in [forChatGPT, linkDropped, forBoth, forClaude, twoFiles] {
                pointAt(v)
                if HomeModel.existingVault(home: home)?.path != v.path { recognised = false }
            }
            check("a wiki is recognised by either rules file, real or a link", recognised)
            pointAt(forClaude)
            check("with no choice on record and a wiki laid down for Claude, the choice is read as Claude",
                  Assistant.onRecord(home: home) == .claude)
            pointAt(forChatGPT)
            check("with no choice on record and a wiki laid down for ChatGPT alone, the choice is read as ChatGPT",
                  Assistant.onRecord(home: home) == .chatgpt)
            check("and an update still asks, since nothing is on record", Assistant.mustAsk(home: home))
            record("somebody-else\n")
            check("a word on record that cannot be read is no record: the wiki's files are asked, as for no file",
                  Assistant.onRecord(home: home) == .chatgpt && Assistant.mustAsk(home: home))
            record("claude\n")
            check("a choice on record is believed over the shape of the files", Assistant.onRecord(home: home) == .claude)
            pointAt(forClaude)      // the checks below are of a wiki laid down for Claude
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
        // A line about something the app does not count — a step it has no tile
        // for, a line with no step at all — is still ignored. That is right: it
        // says nothing about the work the app is showing.
        let quiet = InstallRun()
        quiet.handle(["step": "trust", "state": "something-new"])
        quiet.handle(["step": "a-step-from-the-future", "state": "start", "n": 3, "of": 9])
        quiet.handle(["state": "needed"])
        check("lines about steps the app does not count are ignored",
              !quiet.trustNeeded && quiet.phase == .idle && quiet.items.allSatisfy { $0.state == .waiting })

        // (v0.9.1) But an unknown state on a step the app IS counting must never
        // be ignored. This assertion used to say the opposite, and in doing so
        // it certified the fault: `needs-commit` was dropped, the tile stayed
        // grey, the script exited 0, every tile went green, and the owner was
        // told "Your wiki is up to date" over an update that was never
        // committed. An unrecognised state on a counted step now means
        // "not finished", which is the safe reading of a newer pack's message.
        let newer = InstallRun()
        newer.handle(["step": "safety", "state": "a-state-from-the-future"])
        check("an unknown state on a counted step is not treated as success",
              newer.phase != .finished && newer.items.contains { $0.key == "safety" && $0.state == .failed })

        // The state that fault was found through, end to end: the closing step
        // reports it, the run-level line repeats it, and a zero exit afterwards
        // must not turn it into a finish.
        let staged = InstallRun()
        staged.startUpdateItemsForTest()
        staged.handle(["step": "finish", "state": "needs-commit", "n": 9, "of": 9])
        check("needs-commit is recorded and the step is not shown as broken",
              staged.needsCommit && staged.items.contains { $0.key == "finish" && $0.state == .done })
        staged.handle(["step": "done", "state": "needs-commit", "n": 9, "of": 9])
        staged.finishForTest(code: 0)
        check("a refused commit does not end as finished",
              staged.phase == .needsCommit && staged.phase != .finished)
        // ChatGPT keeps its trust by the entry in its hooks list and takes no
        // account of the guard file. So what a repair printed when it only
        // replaced that file sets nothing waiting; only the scripts' own line
        // does, on a line of its own, and never a sentence that merely names it.
        let replacedOnly = """
        Delete guard for ChatGPT
          previous guard kept at ~/.config/moblee/backups/20260921-101500/codex-bash-guard.py
          installed ~/.codex/hooks/bash-guard.py
        Hook registration in ~/.codex/hooks.json
          already registered; nothing to change
        The delete guard for ChatGPT was updated. ChatGPT keeps the trust you gave it.
        Prove the guard again: python3 scripts/moblee-doctor.py --prove-guard
        A line that only names @@moblee-trust-needed chatgpt is not the line.
        """
        let updatedOnly = InstallRun()
        updatedOnly.handle(["step": "safety", "state": "start", "n": 4, "of": 8])
        updatedOnly.handle(["step": "safety", "state": "ok", "n": 4, "of": 8])
        check("a repair or an update that only replaced ChatGPT's guard file sets no Trust step waiting: only the scripts' trust-needed line does",
              !Trust.saidNeeded(in: replacedOnly) && !updatedOnly.trustNeeded
                  && Trust.saidNeeded(in: replacedOnly + "\n" + Trust.neededLine + "\n")
                  && Trust.neededLine == "@@moblee-trust-needed chatgpt")

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
        check("not running is known by its level and its guide, whatever the sentence says",
              GuardProof.read(rows([["level": "PROBLEM", "text": "Reworded one day.", "guide": "F26"]])) == .notRunning)
        check("the same guide on a row that is not a PROBLEM decides nothing",
              GuardProof.read(rows([["level": "CANNOT SEE", "text": "Whether the delete guard has been trusted", "guide": "F26"]])) == .cannotTell)
        check("a row that says not running wins over one that says proved",
              GuardProof.read(rows([["level": "OK", "text": "Proved: the delete guard is running in ChatGPT.", "guide": NSNull()],
                                    ["level": "PROBLEM", "text": "The delete guard is not running in ChatGPT.", "guide": "F26"]])) == .notRunning)

        // The same, read from samples of what the check-up really prints (kept
        // in app/Fixtures/prove-guard with a note of where they came from), so
        // that the rows above, typed here by hand, are not the only witness.
        if let folder = Flow.value(after: "--fixtures", in: Practice.args) {
            let samples = URL(fileURLWithPath: folder, isDirectory: true).appendingPathComponent("prove-guard")
            let expected: [(String, GuardProof.Result)] = [("proved.json", .proved), ("not-running.json", .notRunning),
                                                           ("cannot-tell.json", .cannotTell), ("not-in-place.json", .cannotTell)]
            for (name, want) in expected {
                let data = try? Data(contentsOf: samples.appendingPathComponent(name))
                check("the check-up's own sample \(name) is read as \(want)", data.map { GuardProof.read($0) == want } ?? false)
            }
        } else {
            check("the check-up's own samples were given (--fixtures <app/Fixtures>)", false)
        }
        // And the check-up this app carries still says what the samples say: the
        // opening word of the proved line, and the guide on the not-running line.
        if let pack = flow.bundledPack,
           let source = try? String(contentsOf: pack.appendingPathComponent("scripts/moblee-doctor.py"), encoding: .utf8) {
            check("the check-up in this app's pack still opens its proved line with \"Proved:\" at level OK",
                  source.contains("f.add(OK, \"Proved:"))
            var carriesGuide = false
            if let start = source.range(of: "f.add(PROBLEM, \"The delete guard is not running in ChatGPT.") {
                let call = source[start.lowerBound...].prefix(400)
                if let end = call.range(of: "return") { carriesGuide = call[..<end.lowerBound].contains("\"F26\")") }
            }
            check("and still gives its not-running line the guide F26 at level PROBLEM", carriesGuide)
        } else {
            check("this app carries a pack whose check-up can be read", false)
        }

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

        // --- the wiki folder is opened in ChatGPT before the five steps ---
        // ChatGPT's Hooks page is empty until a folder has been opened there,
        // so the Trust screen begins at the folder and only then shows the steps.
        check("the Trust screen begins at opening the wiki folder, before the steps",
              Trust.firstStage == .openFolder && flow.trustStart == .openFolder)
        check("from the folder the big button leads to the five steps, and from the steps to the offer of a proof",
              Trust.stage(after: .openFolder) == .steps && Trust.stage(after: .steps) == .offer)
        check("after a proof that saw the guard not running, the steps lead to the offer again",
              Trust.stage(after: .notRunning) == .offer)
        check("the folder comes first in words: File menu, Open Folder, and why the Hooks page is empty",
              Trust.openFirst == "First open your wiki folder in ChatGPT: File menu, Open Folder."
                  && Trust.emptyUntilOpened == "Until a folder has been opened, ChatGPT's Hooks page is empty.")
        check("the five steps are word for word as verified",
              Trust.steps == ["Open the ChatGPT menu and choose Settings", "Choose Hooks, under the heading Coding",
                              "Open “User config”", "Press Trust beside the hook that ends bash-guard.py",
                              "Turn its switch on"])
        check("a guard seen not running sends the owner to the folder first, then the five steps",
              TrustScreen.notRunningSentence == "The guard is not running in ChatGPT yet."
                  && Trust.folderThenSteps
                      == "Open your wiki folder in ChatGPT first (File menu, Open Folder), then do the five steps.")

        // --- the hand-off's words ---
        let wikiName = "Sam Wiki"
        // ChatGPT's window has a switch at the top, Chat or Work. Only in Work
        // does the chat run in the opened wiki folder, and the app's button
        // cannot set it, so the owner is told to, in every form of the words.
        check("the hand-off for ChatGPT has the owner open the wiki folder, then choose Work, then say the words",
              HandoffScreen.sentence(for: .chatgpt, opened: false)
                  == "Last step. Open your wiki folder in ChatGPT, choose Work at the top, then say the words."
                  && HandoffScreen.sentence(for: .chatgpt, opened: true)
                      == "The words are copied. In ChatGPT choose Work at the top, then paste them.")
        let chatgptCards = HandoffScreen.cards(for: .chatgpt, wiki: wikiName)
        check("and its three pictures say the same: the wiki folder by the File menu's Open Folder, Work not Chat, the words",
              chatgptCards.map(\.title) == ["Open your wiki folder", "Choose Work", "Say"]
                  && chatgptCards.map(\.detail) == ["File menu, Open Folder, then Wiki ▸ Sam Wiki",
                                                    "at the top of the window, not Chat", "“get me started”"])
        let chatgptSpoken = HandoffScreen.spoken(for: .chatgpt, wiki: wikiName)
        check("read aloud, ChatGPT's hand-off names Open Folder first and Work before the words",
              chatgptSpoken == "Last step. In ChatGPT: one, open the File menu, choose Open Folder and pick your wiki folder, "
                  + "called Sam Wiki. Two, choose Work at the top of the window, not Chat. Three, say: get me started.")
        check("for both, ChatGPT's line is the File menu's Open Folder, the wiki folder, then Work",
              HandoffScreen.cards(for: .both, wiki: wikiName)[1]
                  == HandoffScreen.Card(symbol: Assistant.chatgpt.symbol, title: "With ChatGPT",
                                        detail: "File menu, Open Folder, pick your wiki folder, and choose Work at the top")
                  && HandoffScreen.spoken(for: .both, wiki: wikiName).contains(
                      "With ChatGPT: in the File menu choose Open Folder, pick your wiki folder, and choose Work at the top."))
        check("Claude's hand-off is word for word as it has always been",
              HandoffScreen.sentence(for: .claude, opened: false) == "Last step. Do these three in Claude."
                  && HandoffScreen.cards(for: .claude, wiki: wikiName).map(\.title) == ["Click Code", "Pick your wiki", "Say"]
                  && HandoffScreen.cards(for: .claude, wiki: wikiName).map(\.detail)
                      == ["at the top of Claude", "Wiki ▸ Sam Wiki", "“get me started”"]
                  && HandoffScreen.cards(for: .both, wiki: wikiName)[0].detail == "Click Code at the top, then pick your wiki"
                  && HandoffScreen.spoken(for: .claude, wiki: wikiName)
                      == "Last step. In Claude: one, click Code at the top. Two, pick your wiki, called Sam Wiki. Three, say: get me started.")
        let trustSaid: [String] = [Trust.openFirst, Trust.emptyUntilOpened, Trust.folderThenSteps, Trust.afterwards,
                                   TrustScreen.reasonSentence,
                                   TrustScreen.notRunningSentence, TrustScreen.openedTitle] + Trust.steps
        func handoffSaid(_ a: Assistant) -> [String] {
            [HandoffScreen.sentence(for: a, opened: false), HandoffScreen.sentence(for: a, opened: true),
             HandoffScreen.spoken(for: a, wiki: wikiName)]
                + HandoffScreen.cards(for: a, wiki: wikiName).flatMap { [$0.title, $0.detail] }
        }
        let chatgptSaid = handoffSaid(.chatgpt).joined(separator: " ")
        check("the hand-off for ChatGPT names both Open Folder and Work, on its pictures and read aloud",
              chatgptSaid.contains("Open Folder") && chatgptSaid.contains("Work")
                  && chatgptCards.contains { $0.detail.contains("Open Folder") }
                  && chatgptCards.contains { $0.title.contains("Work") }
                  && chatgptSpoken.contains("Open Folder") && chatgptSpoken.contains("Work"))
        check("Work is named to ChatGPT's owner alone: never in Claude's hand-off, never on the Trust screen",
              !(handoffSaid(.claude) + trustSaid).contains { $0.contains("Work") })
        check("nothing on the Trust screen or the hand-off tells an owner to make a project",
              !(trustSaid + Assistant.allCases.flatMap(handoffSaid)).contains { $0.lowercased().contains("project") })

        // What each way of leaving the Trust screen does to the note.
        Trust.setPending(true, home: home)
        Trust.putOff(at: .openFolder, home: home)
        check("Later on opening the folder leaves the step waiting", Trust.pending(home: home))
        Trust.putOff(at: .steps, home: home)
        check("Later on the steps leaves the step waiting", Trust.pending(home: home))
        Trust.putOff(at: .offer, home: home)
        check("Later on the offer, after the owner said the steps are done, answers it", !Trust.pending(home: home))
        Trust.record(.notRunning, home: home)
        check("a proof that sees the guard not running sets the step waiting again", Trust.pending(home: home))
        Trust.putOff(at: .notRunning, home: home)
        check("and Later after that leaves it waiting", Trust.pending(home: home))
        Trust.record(.cannotTell, home: home)
        check("a proof that could not tell changes nothing", Trust.pending(home: home))
        Trust.record(.proved, home: home)
        check("a proof that proves the guard answers it", !Trust.pending(home: home))

        // A note left from when the wiki was for ChatGPT, read by an owner who
        // has since changed to Claude alone.
        Trust.setPending(true, home: home)
        check("a waiting note is not shown to an owner whose choice is Claude alone",
              !Trust.pending(home: home, for: .claude))
        check("and is shown to one who uses ChatGPT, alone or with Claude",
              Trust.pending(home: home, for: .chatgpt) && Trust.pending(home: home, for: .both))
        let model = flow.homeModel
        model.assistant = .claude
        model.refreshTrust(home: home)
        check("at home, for Claude alone, the Trust screen is not waiting", !model.trustPending)
        model.assistant = .both
        model.refreshTrust(home: home)
        check("at home, for both, it is", model.trustPending)
        Trust.setPending(false, home: home)
        model.refreshTrust(home: home)

        // --- a wiki newer than this app ---
        model.assistant = .claude
        model.wikiVersion = "0.9.0"; model.packVersion = "0.9.0"
        check("on a wiki of this app's own version, Change is offered", model.canChangeAssistant)
        model.tiles = [HomeModel.Tile(kind: .item, key: "trips", title: "Trip planning", why: "", detail: "",
                                      how: .silent, paid: false, state: .running)]
        check("but not while something is being added", !model.canChangeAssistant)
        flow.mode = .home
        flow.beginUpdate(changingAssistant: true)
        check("and pressing it then would start nothing", flow.mode == .home && !flow.askingAssistant)
        model.tiles = []
        model.wikiVersion = "0.9.1"
        check("on a wiki newer than this app, Change is hidden", !model.canChangeAssistant)
        flow.beginUpdate(changingAssistant: true)
        check("and neither Change nor Update can start this app's older updater",
              flow.mode == .home && !flow.askingAssistant)
        flow.beginUpdate()
        check("by either door", flow.mode == .home)
        model.safetyOff = true
        check("a guard that looks off on a newer wiki is not this app's to repair", model.repairIsForANewerMoblee)
        var ended = false
        model.repair { ended = true }
        check("and Repair, if it were ever asked for, runs nothing and reports no failure",
              ended && !model.repairFailed)
        model.wikiVersion = "0.9.0"
        check("on a wiki of this app's own version, the same guard is this app's to repair", !model.repairIsForANewerMoblee)
        model.safetyOff = false
        model.wikiVersion = ""; model.packVersion = ""

        // --- the hook entry that counts as on, for ChatGPT ---
        check("the entry this Moblee writes counts as on", HomeModel.coversBothWays("Bash|apply_patch"))
        check("so does one a later Moblee widens", HomeModel.coversBothWays("Bash|apply_patch|write_file"))
        check("one that covers the shell alone does not", !HomeModel.coversBothWays("Bash"))
        check("nor does an entry with no matcher", !HomeModel.coversBothWays(nil))

        // --- a ChatGPT app with no agent inside it ---
        let apps = home.appendingPathComponent("logic-check/apps", isDirectory: true)
        let older = apps.appendingPathComponent("older/ChatGPT.app", isDirectory: true)
        let newest = apps.appendingPathComponent("newest/ChatGPT.app", isDirectory: true)
        let fmApps = FileManager.default
        try? fmApps.createDirectory(at: older.appendingPathComponent("Contents/Resources"), withIntermediateDirectories: true)
        try? fmApps.createDirectory(at: newest.appendingPathComponent("Contents/Resources"), withIntermediateDirectories: true)
        let agent = newest.appendingPathComponent("Contents/Resources/codex")
        try? "#!/bin/sh\n".write(to: agent, atomically: true, encoding: .utf8)
        try? fmApps.setAttributes([.posixPermissions: 0o755], ofItemAtPath: agent.path)
        check("a ChatGPT app with its agent inside is ready", ChatGPTApp.state(of: newest) == .ready)
        check("a ChatGPT app with no agent inside is an older one, not a ready one", ChatGPTApp.state(of: older) == .older)
        check("no app at all is missing", ChatGPTApp.state(of: apps.appendingPathComponent("none/ChatGPT.app")) == .missing
              && ChatGPTApp.state(of: nil) == .missing)
        check("the older one is named as such, with where to get the newest",
              ChatGPTApp.olderSentence == "Your ChatGPT app is an older one. Get the newest from chatgpt.com/download.")
        check("the name question names no assistant",
              !NameScreen.words.contains("Claude") && !NameScreen.words.contains("ChatGPT"))

        print(failed == 0 ? "logic: every check held" : "logic: \(failed) check(s) FAILED")
        exit(failed == 0 ? 0 : 1)
    }
}
