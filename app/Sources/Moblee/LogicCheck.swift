import Foundation
import UniformTypeIdentifiers

/// `--check-logic` (only with `--home <practice folder>`) checks the decisions
/// the app makes about the assistant without opening a window or running any
/// of the pack's scripts: whether an update asks the question first, what it
/// then tells the updater, how a progress line about ChatGPT's trust is taken,
/// how the proof's findings are read, and how the link into ChatGPT is made.
/// It writes only inside the practice home. Exit code 0 means every check held.
@MainActor
enum LogicCheck {
    /// (v0.9.5) A real PNG, the smallest one there is: a single transparent
    /// dot. Written out here rather than drawn, so that the check for a picture
    /// dropped with no file behind it hands `Inbox.read` the very bytes a web
    /// page's drag would, and never a picture this check made with the same
    /// code the app uses to read one.
    static let smallestPNG: Data = Data(base64Encoded:
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==")
        ?? Data()

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

        // (v0.9.2) A step that finished while a part of it did not. The tile is
        // not red, the run does finish, and the screen must still have something
        // to say: a step closing "done" over failed work is how an owner came to
        // be told nothing at all about a schedule that was never installed.
        let part = InstallRun()
        part.startUpdateItemsForTest()
        part.handle(["step": "weekly", "state": "partial", "n": 7, "of": 9])
        check("a partly-finished step is recorded and is not shown as broken",
              part.partial && part.items.contains { $0.key == "weekly" && $0.state == .done })
        part.finishForTest(code: 0)
        check("and the run still finishes, with the screen able to say so",
              part.phase == .finished && part.partial)
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
                                                           ("cannot-tell.json", .cannotTell), ("not-in-place.json", .cannotTell),
                                                           ("timed-out.json", .cannotTell)]
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
        // (v0.9.4) Claude's three steps are still word for word what they have
        // always been. What is new is one sentence under them, about the plan
        // the Code tab needs; it is asserted on its own, below, so that this
        // check goes on being about the three steps and nothing else.
        check("Claude's hand-off is word for word as it has always been, but for the plan line",
              HandoffScreen.sentence(for: .claude, opened: false) == "Last step. Do these three in Claude."
                  && HandoffScreen.cards(for: .claude, wiki: wikiName).map(\.title) == ["Click Code", "Pick your wiki", "Say"]
                  && HandoffScreen.cards(for: .claude, wiki: wikiName).map(\.detail)
                      == ["at the top of Claude", "Wiki ▸ Sam Wiki", "“get me started”"]
                  && HandoffScreen.cards(for: .both, wiki: wikiName)[0].detail == "Click Code at the top, then pick your wiki"
                  && HandoffScreen.spoken(for: .claude, wiki: wikiName)
                      == "Last step. In Claude: one, click Code at the top. Two, pick your wiki, called Sam Wiki. "
                          + "Three, say: get me started. The Code tab in Claude's app needs a paid Claude plan.")
        // An owner on the free plan who is sent to click Code finds nothing
        // there. The document has said so since the app route was written; now
        // the screen does, in the document's own words, wherever Claude is used.
        let planLine = "The Code tab in Claude's app needs a paid Claude plan."
        check("the hand-off says the Code tab needs a paid Claude plan, to an owner of Claude and to an owner of both",
              HandoffScreen.paidPlan == planLine
                  && HandoffScreen.planNote(for: .claude) == planLine
                  && HandoffScreen.planNote(for: .both) == planLine
                  && HandoffScreen.spoken(for: .claude, wiki: wikiName).hasSuffix(planLine)
                  && HandoffScreen.spoken(for: .both, wiki: wikiName).hasSuffix(planLine))
        check("and says nothing of plans to an owner of ChatGPT alone, who never opens Claude",
              HandoffScreen.planNote(for: .chatgpt) == nil
                  && !HandoffScreen.spoken(for: .chatgpt, wiki: wikiName).contains("plan")
                  && !HandoffScreen.sentence(for: .chatgpt, opened: false).contains("plan")
                  && !chatgptCards.contains { ($0.title + $0.detail).contains("plan") })
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

        // --- the look for a newer Moblee (v0.9.3) ---
        // Only a plain version is ever taken from GitHub's answer, and the
        // download address is built here, so nothing in a tampered answer can
        // choose where an owner is sent.
        check("a release tag reads as its version, with or without the v",
              NewerRelease.version(fromTag: "v0.9.3") == "0.9.3" && NewerRelease.version(fromTag: "0.10.0") == "0.10.0")
        let hostile = ["", "v", "1", "1.2.3.4.5", "1.2.x", "1..2", "-1.2", "12345.1", "0.9.3 ", " 0.9.3",
                       "v0.9.3;rm -rf ~", "0.9.3/../../x", "https://example.com/x.zip", "0.9.3\n", "１.２.３"]
        check("anything but a plain version is refused, including addresses, paths and commands",
              hostile.allSatisfy { NewerRelease.version(fromTag: $0) == nil })
        func answer(_ o: [String: Any]) -> Data { (try? JSONSerialization.data(withJSONObject: o)) ?? Data() }
        let app = [["name": "Moblee-0.9.3.zip"]]
        check("GitHub's answer for the latest release is read for its tag",
              NewerRelease.version(fromResponse: answer(["tag_name": "v0.9.3", "draft": false, "prerelease": false,
                                                         "assets": app])) == "0.9.3")
        check("a draft or a pre-release is never offered",
              NewerRelease.version(fromResponse: answer(["tag_name": "v0.9.3", "draft": true, "assets": app])) == nil
              && NewerRelease.version(fromResponse: answer(["tag_name": "v0.9.3", "prerelease": true, "assets": app])) == nil)
        check("a release that does not yet carry the app, or carries another version's, is not offered",
              NewerRelease.version(fromResponse: answer(["tag_name": "v0.9.3"])) == nil
              && NewerRelease.version(fromResponse: answer(["tag_name": "v0.9.3", "assets": [["name": "Moblee-0.9.2.zip"]]])) == nil
              && NewerRelease.version(fromResponse: answer(["tag_name": "v0.9.3", "assets": [["name": "Source code (zip)"]]])) == nil)
        check("an answer without a tag, a tag that is not a version, or no JSON at all gives nothing",
              NewerRelease.version(fromResponse: answer(["name": "Moblee 0.9.3"])) == nil
              && NewerRelease.version(fromResponse: answer(["tag_name": "latest"])) == nil
              && NewerRelease.version(fromResponse: Data("<html>rate limited</html>".utf8)) == nil)
        check("Download opens the app itself, on this project's own releases",
              NewerRelease.downloadURL(for: "0.9.3")?.absoluteString
                == "https://github.com/mosabs2/moblee/releases/download/v0.9.3/Moblee-0.9.3.zip")
        check("and no address is built from anything but a plain version",
              hostile.allSatisfy { NewerRelease.downloadURL(for: $0) == nil })
        check("a newer version is offered", NewerRelease.offer(latest: "0.9.3", current: "0.9.2", setAside: nil) == "0.9.3")
        check("the same or an older version is not",
              NewerRelease.offer(latest: "0.9.2", current: "0.9.2", setAside: nil) == nil
              && NewerRelease.offer(latest: "0.9.1", current: "0.9.2", setAside: nil) == nil)
        check("0.10.0 counts as newer than 0.9.9", NewerRelease.offer(latest: "0.10.0", current: "0.9.9", setAside: nil) == "0.10.0")
        check("Not now keeps that version away, and a newer one is offered again",
              NewerRelease.offer(latest: "0.9.3", current: "0.9.2", setAside: "0.9.3") == nil
              && NewerRelease.offer(latest: "0.9.4", current: "0.9.2", setAside: "0.9.3") == "0.9.4")
        check("no answer offers nothing", NewerRelease.offer(latest: nil, current: "0.9.2", setAside: nil) == nil)
        NewerRelease.setAside("0.9.3", home: home)
        check("Not now is remembered in the owner's own Moblee settings", NewerRelease.setAside(home: home) == "0.9.3")
        NewerRelease.setAside("0.9.3; rm -rf ~", home: home)
        check("and only a plain version is ever written there", NewerRelease.setAside(home: home) == "0.9.3")
        let day = Date(timeIntervalSince1970: 1_790_236_800)   // 24 September 2026, midday UTC
        NewerRelease.note(home: home, version: "0.9.3", now: day)
        check("an answer had today is used today without asking again",
              NewerRelease.askedToday(home: home, now: day) == (true, "0.9.3"))
        check("and tomorrow the app asks again",
              NewerRelease.askedToday(home: home, now: day.addingTimeInterval(86_400)).asked == false)
        try? "rubbish\n".write(to: NewerRelease.noteFile(home: home), atomically: true, encoding: .utf8)
        check("a note that cannot be read counts as not asked", NewerRelease.askedToday(home: home, now: day).asked == false)
        check("a practice run with no release switch asks nobody",
              NewerRelease.source(practice: true, args: ["Moblee", "--home", "/tmp/x", "--check-logic"]) == nil)
        check("told --live-release it asks GitHub, told --release-url it asks that address",
              NewerRelease.source(practice: true, args: ["--live-release"]) == NewerRelease.latestURL
              && NewerRelease.source(practice: true, args: ["--release-url", "http://10.255.255.1/x"])?.absoluteString == "http://10.255.255.1/x")
        check("a released app always asks GitHub itself, whatever it is started with",
              NewerRelease.source(practice: false, args: []) == NewerRelease.latestURL
              && NewerRelease.source(practice: false, args: ["--release-url", "https://example.com"]) == NewerRelease.latestURL)
        let shown = HomeModel()
        shown.wikiVersion = "0.9.2"; shown.packVersion = "0.9.2"; shown.newerRelease = "9.9.9"
        check("the line may show on the ordinary home screen", shown.newerReleaseLineAllowed)
        shown.wikiVersion = "0.7.0"
        check("but never over an update this app can make", shown.updateAvailable && !shown.newerReleaseLineAllowed)
        shown.wikiVersion = "0.9.2"; shown.needsRepair = true
        check("nor over a repair", !shown.newerReleaseLineAllowed)
        shown.needsRepair = false; shown.explaining = HomeModel.Tile(kind: .item, key: "x", title: "", why: "", detail: "", how: .silent, paid: false)
        check("nor over an explanation", !shown.newerReleaseLineAllowed)

        // --- the install diary a repair leaves (v0.9.4) ---
        // Repair changes an owner's Mac and used to write nothing at all, so a
        // Mac whose guard or skills had been put back carried no record of it,
        // and the check-up, which reads the diary, could not see that it had
        // happened. The lines are written from here rather than from the two
        // scripts, because the installer and the updater run those same scripts
        // and keep the diary themselves, and because only the app knows the
        // wiki's folder name — which is the thing that has to be kept out.
        let ownersWiki = URL(fileURLWithPath: "/Users/someone/Wiki/Alexandra Wiki", isDirectory: true)
        let theirHome = URL(fileURLWithPath: "/Users/someone", isDirectory: true)
        check("the diary writes the wiki's place, and its folder name, as <wiki>",
              Diary.redact("kept a copy of /Users/someone/Wiki/Alexandra Wiki/CLAUDE.md",
                           home: theirHome, vault: ownersWiki) == "kept a copy of <wiki>/CLAUDE.md"
                  && Diary.redact("the wiki called Alexandra Wiki", home: theirHome, vault: ownersWiki)
                      == "the wiki called <wiki>")
        check("and macOS's /private in front of either is taken with it",
              Diary.redact("/private/Users/someone/Wiki/Alexandra Wiki/x", home: theirHome, vault: ownersWiki) == "<wiki>/x")
        check("the home folder is written as ~, so the diary carries no account name",
              Diary.redact("installed /Users/someone/.claude/hooks/bash-guard.py", home: theirHome, vault: ownersWiki)
                  == "installed ~/.claude/hooks/bash-guard.py"
                  && Diary.redact("/private/Users/someone/.codex", home: theirHome, vault: ownersWiki) == "~/.codex")
        check("an owner's name never reaches the diary, not even through the wiki's folder name",
              !Diary.redact("/Users/someone/Wiki/Alexandra Wiki and Alexandra Wiki again",
                            home: theirHome, vault: ownersWiki).contains("Alexandra"))
        // Written for real into the practice home, twice, since the file is
        // added to and never replaced: a repair must not lose what an install said.
        let diaryFile = Diary.file(home: home)
        try? FileManager.default.removeItem(at: diaryFile)
        Diary.write("=== Moblee install begins ===", home: home, vault: nil)
        Diary.write("repair: started", home: home, vault: nil)
        Diary.writeOutput("installed something\n\n  and kept the old one  \n", home: home, vault: nil)
        let written = (try? String(contentsOf: diaryFile, encoding: .utf8)) ?? ""
        check("the diary is added to and never replaced, one stamped line at a time",
              written.contains("=== Moblee install begins ===") && written.contains("  repair: started")
                  && written.contains("    | installed something")
                  && written.contains("    | and kept the old one")
                  && written.split(separator: "\n").count == 4
                  && written.split(separator: "\n").allSatisfy {
                      $0.range(of: "^[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2}  ",
                               options: .regularExpression) != nil
                  })
        try? FileManager.default.removeItem(at: diaryFile)
        Diary.writeOutput((1...50).map { "line \($0)" }.joined(separator: "\n"), home: home, vault: nil)
        let manyLines = ((try? String(contentsOf: diaryFile, encoding: .utf8)) ?? "").split(separator: "\n")
        check("a step's own output is kept, but never without end",
              manyLines.count == 31 && manyLines.last?.hasSuffix("(20 more line(s) not kept)") == true)
        try? FileManager.default.removeItem(at: diaryFile)

        // --- the move, when another Moblee is open (v0.9.4) ---
        // The app used to refuse the move outright, and to refuse it whenever
        // ANY second Moblee was open, wherever it was running from. Now only the
        // copy at the destination is in the way, it is asked to close the way
        // one Mac app asks another, and the two ways that can end have two
        // different sentences: an owner mid-install must not be sent to close
        // the app that is doing the installing.
        check("a copy that took the quit request and stayed is busy; one that could not be asked is merely open",
              Placement.refusal(requestsSent: true) == .otherMobleeIsBusy
                  && Placement.refusal(requestsSent: false) == .anotherMobleeIsOpen)
        let moveSentences = Placement.Failure.allCases.map { PlacementScreen.sentence(failed: $0) }
        check("the two say different things, and the busy one says why",
              PlacementScreen.sentence(failed: .otherMobleeIsBusy)
                  == "The Moblee in Applications is busy with your wiki. Let it finish, then open this one again."
                  && PlacementScreen.sentence(failed: .anotherMobleeIsOpen)
                      == "The Moblee in Applications would not close. Close it yourself, then open this one again.")
        // (v0.9.4) Five ways a move can fail, and four sentences. This used to
        // be checked as "four different sentences" under a name that said no
        // two were the same, which was untrue of the code it stood over and
        // would have been satisfied by any four, in any places. What is
        // actually wanted is this: the three an owner can do something about
        // each have words of their own, and the two that are Moblee failing to
        // make a good copy of itself — the copy did not come out whole, or its
        // download mark would not clear — leave the Mac exactly as it was and
        // ask the owner for the same one thing, so they share the general
        // advice. Two different technical reasons for the same next step would
        // tell an owner who reads little nothing they can use.
        let generalAdvice = PlacementScreen.sentence(failed: nil)
        let ownWords: [Placement.Failure] = [.anotherMobleeIsOpen, .otherMobleeIsBusy, .somethingElseThere]
        let sameAdvice: [Placement.Failure] = [.copyIncomplete, .markNotCleared]
        check("every way a move can fail has a sentence; the three an owner can act on have their own, "
              + "and only the two that changed nothing share the general advice",
              Placement.Failure.allCases.count == ownWords.count + sameAdvice.count
                  && moveSentences.allSatisfy { !$0.isEmpty }
                  && Set(ownWords.map { PlacementScreen.sentence(failed: $0) }).count == ownWords.count
                  && ownWords.allSatisfy { PlacementScreen.sentence(failed: $0) != generalAdvice }
                  && sameAdvice.allSatisfy { PlacementScreen.sentence(failed: $0) == generalAdvice }
                  && Set(moveSentences).count == 4)
        // Nothing of this app's own is ever in the way of the move: this
        // process is left out of the list, whatever it is running from.
        check("the copy this very process is running from is never counted as one in the way",
              Placement.others(at: Placement.running).isEmpty)

        // --- a skill wearing a Moblee name that Moblee did not put there (v0.9.4) ---
        // An owner who installed with ChatGPT before the record existed had
        // Moblee's own skills in ~/.agents/skills, from an earlier Moblee. The
        // app compared them only with the pack it carries, found them different,
        // said a skill was missing, and offered a Repair whose script would not
        // replace a skill it could not prove Moblee had put there. The repair
        // could never succeed, and it was offered every time the app opened.
        let fmSkills = FileManager.default
        let yardS = home.appendingPathComponent("logic-check/skills", isDirectory: true)
        try? fmSkills.removeItem(at: yardS)
        func skillFile(_ at: URL, _ text: String) {
            try? fmSkills.createDirectory(at: at, withIntermediateDirectories: true)
            try? text.write(to: at.appendingPathComponent("SKILL.md"), atomically: true, encoding: .utf8)
        }
        let thisPack = yardS.appendingPathComponent("pack-new", isDirectory: true)
        skillFile(thisPack.appendingPathComponent("skills/companion"), "companion, this Moblee\n")
        skillFile(thisPack.appendingPathComponent("skills/brain"), "brain, this Moblee\n")
        let skillsHome = yardS.appendingPathComponent("home", isDirectory: true)
        let olderPack = skillsHome.appendingPathComponent("Library/Application Support/Moblee/pack-0.9.0",
                                                          isDirectory: true)
        skillFile(olderPack.appendingPathComponent("skills/companion"), "companion, an earlier Moblee\n")
        skillFile(olderPack.appendingPathComponent("skills/brain"), "brain, an earlier Moblee\n")
        // ChatGPT's folder, as the owner's Mac had it: an earlier Moblee's
        // copies, and no record anywhere saying Moblee put them there.
        skillFile(skillsHome.appendingPathComponent(".agents/skills/companion"), "companion, an earlier Moblee\n")
        skillFile(skillsHome.appendingPathComponent(".agents/skills/brain"), "brain, an earlier Moblee\n")
        let survey = HomeModel()
        var answer = survey.surveySkillsForTest(pack: thisPack, home: skillsHome, assistant: .chatgpt)
        check("an earlier Moblee's copy of a skill is recognised as Moblee's, by its content, from the packs left on this Mac",
              answer.put && answer.foreign.isEmpty)
        // Now one of them is the owner's own, matching no Moblee pack at all.
        skillFile(skillsHome.appendingPathComponent(".agents/skills/brain"), "my own brain skill\n")
        answer = survey.surveySkillsForTest(pack: thisPack, home: skillsHome, assistant: .chatgpt)
        check("a skill matching no Moblee pack is named, and is never taken for one a repair can replace",
              answer.foreign == ["brain"] && answer.put)
        // And what the app has proved is written down where the skills script
        // looks for it. The script replaces only a skill it can prove Moblee
        // put there; the record is where that proof lives; a skill left by an
        // install from before the record existed is in no record, which is why
        // the repair could never succeed. Only a skill that matches a pack is
        // ever written down: the owner's own is named on the screen instead.
        let noted = survey.recordEarlierMoblees()
        let recordNow = (try? String(contentsOf: skillsHome.appendingPathComponent(".config/moblee/skills-chatgpt"),
                                     encoding: .utf8)) ?? ""
        check("a skill the app has proved an earlier Moblee left is written into the skills script's own record, and the owner's is not",
              noted == ["companion"] && recordNow == "companion\n"
                  && HomeModel.recordedAsMoblees("companion", kind: "chatgpt", home: skillsHome)
                  && !HomeModel.recordedAsMoblees("brain", kind: "chatgpt", home: skillsHome))
        check("and writing it down a second time adds nothing",
              survey.recordEarlierMoblees().isEmpty
                  && !HomeModel.addToRecord("companion", kind: "chatgpt", home: skillsHome)
                  && ((try? String(contentsOf: skillsHome.appendingPathComponent(".config/moblee/skills-chatgpt"),
                                   encoding: .utf8)) ?? "") == "companion\n")
        check("and the screen says which skill it is and what to do about it",
              HomeModel.foreignSkillSentence(answer.foreign, talksTo: "ChatGPT")
                  == "A skill called “brain” is not Moblee's, and Moblee will not change it. "
                      + "Ask ChatGPT to rename it, then open Moblee again.")
        check("more than one is named together, and a long list is cut short",
              HomeModel.foreignSkillSentence(["a", "b"], talksTo: "Claude")
                  == "These skills are not Moblee's: “a”, “b”. Moblee will not change them. "
                      + "Ask Claude to rename them, then open Moblee again."
                  && HomeModel.foreignSkillSentence(["a", "b", "c", "d", "e"], talksTo: "Claude")
                      .contains("“a”, “b”, “c”, and 2 more"))
        // A skill that is simply not there is nothing to name: the repair puts it in.
        try? fmSkills.removeItem(at: skillsHome.appendingPathComponent(".agents/skills/brain"))
        answer = survey.surveySkillsForTest(pack: thisPack, home: skillsHome, assistant: .chatgpt)
        check("a skill that is missing altogether is a repair, not something of the owner's",
              answer.put && answer.foreign.isEmpty)
        // This pack's own copies in place: nothing to do, and nothing to say.
        skillFile(skillsHome.appendingPathComponent(".agents/skills/companion"), "companion, this Moblee\n")
        skillFile(skillsHome.appendingPathComponent(".agents/skills/brain"), "brain, this Moblee\n")
        answer = survey.surveySkillsForTest(pack: thisPack, home: skillsHome, assistant: .chatgpt)
        check("this Moblee's own copies in place ask for nothing", !answer.put && answer.foreign.isEmpty)
        // The record the skills script keeps, read exactly as the script reads it.
        let recordFile = skillsHome.appendingPathComponent(".config/moblee/skills-chatgpt")
        try? fmSkills.createDirectory(at: recordFile.deletingLastPathComponent(), withIntermediateDirectories: true)
        try? "companion\nbrain\n".write(to: recordFile, atomically: true, encoding: .utf8)
        check("a name in the skills script's own record is Moblee's, and one that is not there is not",
              HomeModel.recordedAsMoblees("companion", kind: "chatgpt", home: skillsHome)
                  && !HomeModel.recordedAsMoblees("companio", kind: "chatgpt", home: skillsHome)
                  && !HomeModel.recordedAsMoblees("gym-log", kind: "chatgpt", home: skillsHome))
        check("with no record at all, Claude's folder counts as Moblee's and ChatGPT's does not, as the script itself decides",
              HomeModel.recordedAsMoblees("companion", kind: "claude", home: yardS)
                  && !HomeModel.recordedAsMoblees("companion", kind: "chatgpt", home: yardS))
        // The whole-folder comparison, which is the one the script makes.
        let treeA = yardS.appendingPathComponent("tree-a", isDirectory: true)
        let treeB = yardS.appendingPathComponent("tree-b", isDirectory: true)
        skillFile(treeA, "same\n"); skillFile(treeB, "same\n")
        check("two folders holding the same files match", HomeModel.sameTree(treeA, treeB))
        try? "ignored".write(to: treeB.appendingPathComponent(".DS_Store"), atomically: true, encoding: .utf8)
        check("and Finder's own .DS_Store is not counted, as diff is told not to count it",
              HomeModel.sameTree(treeA, treeB))
        try? "extra".write(to: treeB.appendingPathComponent("more.md"), atomically: true, encoding: .utf8)
        check("a file in one and not the other does not match", !HomeModel.sameTree(treeA, treeB))
        try? fmSkills.removeItem(at: treeB.appendingPathComponent("more.md"))
        try? "changed\n".write(to: treeB.appendingPathComponent("SKILL.md"), atomically: true, encoding: .utf8)
        check("nor does the same file with different words in it", !HomeModel.sameTree(treeA, treeB))
        check("nor a folder that is not there at all",
              !HomeModel.sameTree(treeA, yardS.appendingPathComponent("no-such-tree")))

        // --- how big the words are (v0.9.4) ---
        // The window was nailed to 720 by 520 and every size in the app is
        // written in points, so an owner with poor eyesight could do nothing
        // at all about it: macOS's own text-size setting reaches none of it.
        check("the three steps are normal, a quarter bigger, and half as big again",
              TextSize.Step.allCases.map(\.scale) == [1.00, 1.25, 1.50]
                  && TextSize.Step.allCases.map(\.name) == ["Normal", "Bigger", "Biggest"])
        check("one press moves on one step, and round again from the biggest, so one control is the whole of it",
              TextSize.Step.normal.next == .bigger && TextSize.Step.bigger.next == .biggest
                  && TextSize.Step.biggest.next == .normal)
        let wasStep = TextSize.shared.step
        TextSize.shared.step = .normal
        let plainFont = Theme.font(24, .semibold)
        let plainPoints = Theme.pt(200)
        let plainWindow = (Theme.leastWidth, Theme.leastHeight)
        check("at the normal size nothing is changed at all: the window is still 720 by 520",
              plainPoints == 200 && plainWindow == (720, 520))
        TextSize.shared.step = .biggest
        check("at the biggest, a size, a card's width and the window's least size have all grown together",
              Theme.scale == 1.5 && Theme.pt(200) == 300 && Theme.font(24, .semibold) != plainFont
                  && Theme.leastWidth == 1080 && Theme.leastHeight == 780)
        check("and a card 200 points wide is never left 200 points wide while its words grow",
              Theme.pt(200) > plainPoints)
        // Kept, and still there the next time the app is opened. Read through
        // a second UserDefaults of its own, which is what a second opening is.
        let store = TextSize.store
        store.set("do not touch", forKey: "moblee.logic-check.something-else")
        TextSize.shared.step = .bigger
        check("the step is kept under Moblee's own key", TextSize.key == "moblee.textSize"
                  && store.integer(forKey: TextSize.key) == TextSize.Step.bigger.rawValue)
        check("and is read back as itself by an app opening afresh", TextSize.read(from: store) == .bigger)
        check("nothing else kept in the same settings is disturbed",
              store.string(forKey: "moblee.logic-check.something-else") == "do not touch")
        let unsaid = UserDefaults(suiteName: "moblee.logic-check.never-set") ?? .standard
        check("an owner who has never set it reads as normal", TextSize.read(from: unsaid) == .normal)
        TextSize.write(.biggest, to: unsaid)
        check("and what is written there is read back", TextSize.read(from: unsaid) == .biggest)
        unsaid.set(7, forKey: TextSize.key)
        check("a step some later Moblee knows and this one does not is read as normal, never refused",
              TextSize.read(from: unsaid) == .normal)
        unsaid.removeObject(forKey: TextSize.key)
        // The practice switch that draws a screen bigger writes nothing.
        let keptNow = store.integer(forKey: TextSize.key)
        TextSize.shared.drawAt(.biggest)
        check("drawing a screen at a bigger size leaves the owner's own choice exactly as it was",
              Theme.scale == 1.5 && store.integer(forKey: TextSize.key) == keptNow)
        check("and --text-scale is a practice switch, so a released Moblee never sees it",
              Practice.switches.contains("--text-scale"))
        // Put back what was kept before this check ran, really written, so that
        // the next practice run starts at the size it would have started at.
        TextSize.shared.step = wasStep

        // --- Escape, and where it must do nothing (v0.9.4) ---
        // The quiet place under the big button is not always a "not now": on
        // the home screen it is "Open Claude", and Escape must never press it.
        check("Escape does what \"Not now\" does", QuietWords.escapeCancels("Not now"))
        check("and nothing at all where the quiet words are something else, or where there are none",
              !QuietWords.escapeCancels("Open Claude")
                  && !QuietWords.escapeCancels("Show what happened")
                  && !QuietWords.escapeCancels("Later")
                  && !QuietWords.escapeCancels("What did Moblee make?")
                  && !QuietWords.escapeCancels(nil))

        // --- the Terminal explanation, one picture at a time (v0.9.4) ---
        // Three cards side by side is three things to read in one go, for an
        // owner who does not read much. The words are the ones they always were.
        check("there are three pictures, in the words they have always had",
              ExplainScreen.terminalCards.map(\.title) == ["It types for itself", "Your Mac password", "Wait"]
                  && ExplainScreen.terminalCards.map(\.detail)
                      == ["Press Return if it asks you to", "Nothing shows as you type. That is normal.",
                          "Downloads take a while. Then close it."])
        check("the big button says Next until the last of them, and only then opens the window",
              ExplainScreen.terminalButtonTitle(step: 0) == "Next"
                  && ExplainScreen.terminalButtonTitle(step: 1) == "Next"
                  && ExplainScreen.terminalButtonTitle(step: 2) == "Open it")
        check("and the owner is told which of the three they are on, in words",
              ExplainScreen.terminalWhere(step: 0) == "1 of 3"
                  && ExplainScreen.terminalWhere(step: 1) == "2 of 3"
                  && ExplainScreen.terminalWhere(step: 2) == "3 of 3")

        // --- laid out right to left (v0.9.4) ---
        // macOS mirrors a whole app when the Mac's own language is read right to
        // left, Arabic among them, and Moblee had never been looked at in that
        // state. Most of the mirroring is SwiftUI's own — leading and trailing,
        // an offset, a position, a drawn path, the edge a screen slides from —
        // and what is left is these decisions, which nothing would have caught.
        check("--rtl is a practice switch, so a released Moblee is laid out the way the Mac is set to and never the way it was asked",
              Practice.switches.contains("--rtl"))
        check("the back arrow points the way back goes, and is named so that it turns round with the words",
              Layout.backSymbol == "chevron.backward.circle.fill"
                  && !Layout.backSymbol.contains("left") && !Layout.backSymbol.contains("right"))
        check("and so is the arrow that means \"to there\", on the move to Applications",
              Layout.onwardsSymbol == "arrow.forward"
                  && !Layout.onwardsSymbol.contains("left") && !Layout.onwardsSymbol.contains("right"))
        check("a new screen arrives from the side \"on\" is on: the right where the words run left to right, the left where they run the other way",
              Layout.side(of: Layout.arrives, mirrored: false) == .right
                  && Layout.side(of: Layout.arrives, mirrored: true) == .left)
        check("and the screen before it leaves by the other side, whichever way that is",
              Layout.side(of: Layout.leaves, mirrored: false) == .left
                  && Layout.side(of: Layout.leaves, mirrored: true) == .right
                  && Layout.arrives != Layout.leaves)
        check("which assistant sits in the far bottom corner, and a newer Moblee in the near one, and they swap over together",
              Layout.side(ofCorner: Layout.assistantCorner, mirrored: false) == .right
                  && Layout.side(ofCorner: Layout.newerReleaseCorner, mirrored: false) == .left
                  && Layout.side(ofCorner: Layout.assistantCorner, mirrored: true) == .left
                  && Layout.side(ofCorner: Layout.newerReleaseCorner, mirrored: true) == .right)
        check("the two quiet lines at the bottom are never in the same corner, whichever way the words run",
              Layout.assistantCorner != Layout.newerReleaseCorner
                  && [false, true].allSatisfy {
                      Layout.side(ofCorner: Layout.assistantCorner, mirrored: $0)
                          != Layout.side(ofCorner: Layout.newerReleaseCorner, mirrored: $0)
                  })
        check("\"Bigger text\" is in the corner the reading ends at, which is the other corner from the one it is in here",
              Layout.side(ofCorner: Layout.biggerTextCorner, mirrored: false) == .right
                  && Layout.side(ofCorner: Layout.biggerTextCorner, mirrored: true) == .left)
        // The opposite decision, which looks wrong and is right: an arrow that
        // is a letter inside an English line is NOT turned round, because the
        // line keeps the direction of its own words whatever the layout does.
        // Turned round, the update screen was drawn as "0.7.0 ← 0.8.1" on a
        // line still read left to right.
        check("an arrow that is a letter in a sentence is left alone, because the sentence keeps its own direction",
              Layout.versionsArrow == "→" && Layout.intoAFolder == "▸"
                  && HandoffScreen.cards(for: .claude, wiki: wikiName)[1].detail == "Wiki ▸ Sam Wiki")

        // --- an owner whose own name is not written in English (v0.9.4) ---
        // The Mac may be in English while the owner's name is Arabic. The name
        // is typed on one screen, shown on three more, and is what the wiki's
        // folder is called; a name read right to left inside a sentence read
        // left to right takes its own order from the sentence unless it is told
        // to stand on its own.
        let light = "نور"                 // Arabic for "light", used as a given name
        let mixed = "نور Ali"
        check("the two marks that let a name stand on its own are put round it, and round nothing else",
              OwnWords.standingAlone(light) == "\u{2068}" + light + "\u{2069}"
                  && OwnWords.standingAlone("Sam") == "\u{2068}Sam\u{2069}")
        check("an empty name is left empty, so an owner who has typed nothing is shown nothing",
              OwnWords.standingAlone("") == "")
        let marked = OwnWords.standingAlone(light)
        let withoutMarks = String(String.UnicodeScalarView(
            marked.unicodeScalars.filter { $0.properties.generalCategory != .format }))
        check("the marks are invisible ones, and add no letter, digit or space to the name",
              withoutMarks == light && marked.count == light.count + 2)
        // Asked of the flow this check has been using all along, so that no
        // second one goes looking round the practice home.
        flow.ownerName = light
        check("a name typed in Arabic is kept exactly as typed, and the wiki folder is called after it",
              flow.trimmedName == light && flow.wikiName == light + " Wiki")
        flow.ownerName = mixed
        check("a name mixing Arabic and English is taken by its first word, as any other name is",
              flow.wikiName == light + " Wiki")
        flow.ownerName = "Sam Jones"
        check("and a name in English is still taken by its first word, exactly as before",
              flow.wikiName == "Sam Wiki")
        flow.ownerName = light
        let place = flow.freeLocation()
        check("no invisible mark ever reaches the folder's name or the place it is made in",
              !place.name.unicodeScalars.contains { $0.properties.generalCategory == .format }
                  && !place.url.path.contains(OwnWords.isolate) && !place.url.path.contains(OwnWords.pop)
                  && place.name == light + " Wiki")
        check("nor what is read aloud, which is left plain",
              !HandoffScreen.spoken(for: .claude, wiki: light + " Wiki").contains(OwnWords.isolate))

        // (v0.9.4, 26 September) The wiki folder's name is the other case, and
        // it wanted the opposite treatment. Told to stand on its own by the
        // first-strong mark, "نور Wiki" takes its direction from its first
        // letter, which is Arabic, and is drawn "Wiki نور" — while Finder,
        // which is where the owner is being sent to find it, shows "نور Wiki".
        // The hand-off's whole job is "find this folder", and it was naming it
        // backwards for every owner whose name is not written in English. A
        // folder name is given no mark of its own and takes the direction of
        // the line it sits in, which is an English line and reads left to
        // right, so the name comes first, as Finder writes it.
        let folder = light + " Wiki"
        check("a wiki folder's name is left exactly as Finder will show it, with no invisible mark at all",
              OwnWords.asFinderShowsIt(folder) == folder
                  && !OwnWords.asFinderShowsIt(folder).unicodeScalars
                      .contains { $0.properties.generalCategory == .format })
        check("and the screens that send an owner to that folder put no mark in it either",
              !HandoffScreen.cards(for: .claude, wiki: folder).contains {
                  $0.detail.contains(OwnWords.isolate) || $0.detail.contains(OwnWords.pop)
              } && HandoffScreen.cards(for: .claude, wiki: folder)[1].detail.hasSuffix(folder))
        // The two cases really are different, so that neither can quietly
        // become the other again.
        check("a name on its own still stands on its own, which is what settles the full stop after it",
              OwnWords.standingAlone(light) != OwnWords.asFinderShowsIt(light)
                  && OwnWords.standingAlone(light).hasPrefix(OwnWords.isolate))
        flow.ownerName = ""

        // --- the tile buttons the keyboard can now reach (v0.9.4) ---
        let aTile = HomeModel.Tile(kind: .item, key: "videos", title: "", why: "", detail: "",
                                   how: .terminal, paid: false)
        check("each tile's own buttons are named, so the keyboard and the walk can find them",
              RequestTile.buttonId(aTile) == "tile-videos" && RequestTile.doneId(aTile) == "tile-videos-done")
        // (v0.9.4) And the Get buttons on the check-up, which macOS puts in the
        // keyboard's way only where Full Keyboard Access has been switched on.
        check("each thing the Mac still needs has a named Get button, for the keyboard and for the walk",
              Checkup.need(.developerTools).getId == "get-apple-tools"
                  && Checkup.need(.claude).getId == "get-claude"
                  && Checkup.need(.chatgpt).getId == "get-chatgpt"
                  && Checkup.need(.obsidian).getId == "get-obsidian")

        // --- a repair must not be cut off half-way (v0.9.4) ---
        // An owner presses Repair in the copy in Applications; while the safety
        // script is writing into ~/.claude they open a freshly downloaded
        // Moblee and press "Move it there". That one finds this copy
        // (`Placement.others(at:)`), asks it to quit — and this copy used to say
        // yes, leaving "repair: started" in the diary with no ending line, the
        // Trust step never set waiting, and the check afterwards never run.
        check("a Moblee doing nothing lets itself be closed",
              !AppDelegate.busyWithWork)
        AppDelegate.repairing = true
        check("a Moblee half-way through a repair refuses to close, exactly as one half-way through an install does",
              AppDelegate.busyWithWork)
        AppDelegate.repairing = false
        check("and lets itself be closed again the moment the repair has ended",
              !AppDelegate.busyWithWork)
        // (v0.9.5) And a drop. Something dropped on Moblee is copied into the
        // wiki's inbox off the main thread, and a 90 MB scan takes a moment:
        // for that moment the wiki is being written to, and a quit would leave
        // one of Moblee's own hidden half-made copies in the owner's inbox with
        // no receipt at all. A count and not a flag, because two drops can be
        // in flight at once and the second ending must not let go of the first.
        AppDelegate.dropsInFlight += 1
        check("a Moblee part-way through putting a dropped file in the wiki refuses to close too",
              AppDelegate.busyWithWork)
        AppDelegate.dropsInFlight += 1
        AppDelegate.dropsInFlight -= 1
        check("and two drops at once are still busy when the first of them ends",
              AppDelegate.busyWithWork)
        AppDelegate.dropsInFlight -= 1
        check("and the moment the last drop has landed it lets itself be closed again",
              !AppDelegate.busyWithWork && AppDelegate.dropsInFlight == 0)
        // A drop waits for the three that run the pack's scripts over the wiki,
        // and never for another drop: two files let go over the Dock icon a
        // moment apart must both land.
        AppDelegate.dropsInFlight += 1
        check("but a drop does not make another drop wait, which is what two quick drops are",
              !AppDelegate.busyMakingOrMending)
        // The other half of the same fault, and the half nothing guarded: a
        // drop already refused to start under an update, and an update happily
        // started under a drop. Drop a 90 MB scan and press Update a second
        // later, and the updater's scripts rewrote and committed the wiki while
        // the copy was still running, so the copy's last step landed in the
        // middle of that commit.
        flow.mode = .home
        flow.beginUpdate()
        check("an update cannot start while a dropped file is still being copied into the wiki",
              flow.mode == .home && !flow.askingAssistant)
        var repairCameBack = false
        flow.homeModel.repair { repairCameBack = true }
        check("nor a repair, which runs the same scripts over the same wiki",
              repairCameBack && !AppDelegate.repairing && !flow.homeModel.repairFailed)
        AppDelegate.dropsInFlight -= 1
        flow.beginUpdate()
        check("and the moment the drop has landed, Update works again",
              flow.mode == .update)
        flow.cancelUpdateQuestion()
        check("the refusal the other copy shows is true of every one of those, and names none of them wrongly",
              PlacementScreen.sentence(failed: .otherMobleeIsBusy).contains("busy with your wiki")
                  && !PlacementScreen.sentence(failed: .otherMobleeIsBusy).contains("making, updating"))

        // --- the diary must not name a fault that was not found (v0.9.4) ---
        // The diary is the one file an owner is told is safe to send when they
        // need help. A script that exits non-zero and a check that then finds
        // nothing wrong used to share one ending line, and that line named the
        // last of the three reasons — "one of Moblee's skills is not this
        // Moblee's copy" — about a Mac with nothing wrong with its skills.
        let mended = HomeModel()
        check("with nothing wrong, there is no reason to name",
              mended.repairReason == "nothing")
        check("a repair that mended everything says so",
              HomeModel.repairEnding(stepDidNotFinish: false, stillWrong: false, reason: "nothing")
                  == "repair: ended; nothing is still wrong")
        check("a repair that left something wrong says what is still wrong",
              HomeModel.repairEnding(stepDidNotFinish: true, stillWrong: true,
                                     reason: "the delete guard is off")
                  == "repair: ENDED WITHOUT PUTTING IT RIGHT; still wrong: the delete guard is off")
        check("and a step that did not finish on a Mac with nothing wrong says exactly that, and names no fault",
              HomeModel.repairEnding(stepDidNotFinish: true, stillWrong: false, reason: "nothing")
                  == "repair: ENDED WITHOUT PUTTING IT RIGHT; a step did not finish, "
                      + "but the check afterwards found nothing wrong"
                  && !HomeModel.repairEnding(stepDidNotFinish: true, stillWrong: false, reason: "nothing")
                      .contains("still wrong"))

        // --- dropping something on Moblee (v0.9.5) ---
        //
        // The whole of it, without a window: what lands in the wiki's inbox,
        // what is refused and in what words, and — the one that matters most —
        // that the thing the owner dropped is still exactly where it was, byte
        // for byte, after every one of those.
        let yard = home.appendingPathComponent("logic-check/drops", isDirectory: true)
        let theirs = yard.appendingPathComponent("what the owner has", isDirectory: true)
        let notAWiki = yard.appendingPathComponent("not a wiki", isDirectory: true)
        let fm2 = FileManager.default
        try? fm2.createDirectory(at: theirs, withIntermediateDirectories: true)
        try? fm2.createDirectory(at: notAWiki, withIntermediateDirectories: true)
        let pointer = home.appendingPathComponent(".config/moblee/vault-path")
        let pointedAtBefore = (try? String(contentsOf: pointer, encoding: .utf8)) ?? ""
        func pointAtTheWiki(_ url: URL) {
            try? fm2.createDirectory(at: pointer.deletingLastPathComponent(), withIntermediateDirectories: true)
            try? (url.path + "\n").write(to: pointer, atomically: true, encoding: .utf8)
        }
        /// A wiki as `HomeModel.existingVault` knows one, with its inbox. A new
        /// one each time, rather than an old one emptied, so that nothing
        /// anywhere in this check ever deletes anything — which is the promise
        /// the checks below are about.
        var madeWiki = yard.appendingPathComponent("wiki 0", isDirectory: true)
        var raw = Inbox.rawFolder(in: madeWiki)
        var wikisMade = 0
        func freshWiki() {
            wikisMade += 1
            madeWiki = yard.appendingPathComponent("wiki \(wikisMade)", isDirectory: true)
            raw = Inbox.rawFolder(in: madeWiki)
            try? fm2.createDirectory(at: raw, withIntermediateDirectories: true)
            try? fm2.createDirectory(at: madeWiki.appendingPathComponent("wiki"), withIntermediateDirectories: true)
            try? "# rules\n".write(to: madeWiki.appendingPathComponent("CLAUDE.md"), atomically: true, encoding: .utf8)
            pointAtTheWiki(madeWiki)
        }
        func theirFile(_ name: String, _ words: String) -> URL {
            let url = theirs.appendingPathComponent(name)
            try? words.write(to: url, atomically: true, encoding: .utf8)
            return url
        }
        /// Everything about a file that must not change when it is dropped.
        struct AsItWas: Equatable {
            let there: Bool, bytes: Data?, size: Int, changed: Date?
            init(_ url: URL) {
                let fm = FileManager.default
                there = fm.fileExists(atPath: url.path)
                bytes = try? Data(contentsOf: url)
                let about = try? fm.attributesOfItem(atPath: url.path)
                size = (about?[.size] as? Int) ?? -1
                changed = about?[.modificationDate] as? Date
            }
        }
        func inTheirFolder() -> [String] {
            ((try? fm2.contentsOfDirectory(atPath: theirs.path)) ?? []).sorted()
        }
        /// One drop, through the very door both routes come through, waited for.
        func drop(files: [URL] = [], text: String? = nil,
                  pictures: [Inbox.Picture] = [], now: Date = Date()) -> Inbox.Landing {
            var landed: Inbox.Landing?
            Dropped.shared.arrived(files: files, text: text, pictures: pictures, now: now) { landed = $0 }
            let by = Date().addingTimeInterval(30)
            while landed == nil && Date() < by { RunLoop.main.run(until: Date().addingTimeInterval(0.02)) }
            Dropped.shared.showing = nil        // the receipt is read in the walk, not here
            return landed ?? Inbox.Landing()
        }
        func inTheInbox() -> [String] {
            ((try? fm2.contentsOfDirectory(atPath: raw.path)) ?? []).sorted()
        }

        // one file
        freshWiki()
        let one = theirFile("Gym plan.md", "sets and reps\n")
        let oneAsItWas = AsItWas(one)
        let theirFolderBefore = inTheirFolder()
        var landing = drop(files: [one])
        check("a file dropped on Moblee lands in the wiki's inbox under its own name",
              landing.landed == ["Gym plan.md"] && landing.turnedAway.isEmpty
                  && inTheInbox() == ["Gym plan.md"])
        check("and what landed is the same bytes as what was dropped",
              (try? Data(contentsOf: raw.appendingPathComponent("Gym plan.md"))) == oneAsItWas.bytes)
        // THE PROMISE. It copies; it never moves and never deletes.
        check("the file the owner dropped is still exactly where it was, byte for byte, with its size and its date",
              AsItWas(one) == oneAsItWas && inTheirFolder() == theirFolderBefore)
        check("nothing of Moblee's own half-made copies is left behind in the inbox",
              !inTheInbox().contains { $0.hasPrefix(Inbox.incomingPrefix) })

        // several at once, one receipt saying how many
        freshWiki()
        let several = [theirFile("Scan 1.pdf", "one\n"), theirFile("Scan 2.pdf", "two\n"),
                       theirFile("Notes.txt", "three\n")]
        let severalAsTheyWere = several.map(AsItWas.init)
        landing = drop(files: several)
        check("several files dropped at once all land, in the order they were dropped",
              landing.landed == ["Scan 1.pdf", "Scan 2.pdf", "Notes.txt"])
        check("and there is one receipt, which says how many",
              Inbox.sentence(for: landing, talksTo: "Claude")
                  == "3 things are in your wiki, in the folder called raw. Tell Claude: process the new files in raw/.")
        check("and every one of the originals is untouched",
              several.map(AsItWas.init) == severalAsTheyWere)

        // TWO DROPS AT ONCE, REALLY AT ONCE. Not an argument about a gap
        // between two lines: two threads let go at the same moment, both
        // carrying a file of the same name, over and over.
        //
        // This is the check the old code could not have passed. It asked
        // whether a name was free and then called `moveItem`, which asks again
        // and then calls `rename(2)`, which replaces without a word; two
        // threads both passed both guards and one file was destroyed while
        // both were told it had landed. Six times out of six against a driver.
        // The whole promise of this feature rests on it, and the thing writing
        // into `raw/` in that moment need not even be Moblee: an iCloud or
        // Dropbox sync of the wiki folder, or the assistant part-way through
        // reading the inbox, would do.
        freshWiki()
        let raceRounds = 24
        let racerA = yard.appendingPathComponent("racer A", isDirectory: true)
        let racerB = yard.appendingPathComponent("racer B", isDirectory: true)
        try? fm2.createDirectory(at: racerA, withIntermediateDirectories: true)
        try? fm2.createDirectory(at: racerB, withIntermediateDirectories: true)
        let sameNameA = racerA.appendingPathComponent("Both at once.md")
        let sameNameB = racerB.appendingPathComponent("Both at once.md")
        try? "AAAA\n".write(to: sameNameA, atomically: true, encoding: .utf8)
        try? "BBBB\n".write(to: sameNameB, atomically: true, encoding: .utf8)
        let racedInbox = raw
        var racedLandings: [Inbox.Landing] = []
        let racedLock = NSLock()
        for _ in 0..<raceRounds {
            DispatchQueue.concurrentPerform(iterations: 2) { which in
                let landing = Inbox.take(files: [which == 0 ? sameNameA : sameNameB], into: madeWiki)
                racedLock.lock(); racedLandings.append(landing); racedLock.unlock()
            }
        }
        let racedNames = ((try? fm2.contentsOfDirectory(atPath: racedInbox.path)) ?? [])
            .filter { !$0.hasPrefix(Inbox.incomingPrefix) }
        let racedBodies = racedNames.compactMap {
            try? String(contentsOf: racedInbox.appendingPathComponent($0), encoding: .utf8)
        }
        check("two drops at the very same moment, both of a file with the same name, both land and neither is destroyed",
              racedLandings.count == raceRounds * 2
                  && racedLandings.allSatisfy { $0.landed.count == 1 && $0.turnedAway.isEmpty }
                  && racedNames.count == raceRounds * 2)
        check("and every one of the two-at-a-time files is whole, so not one of them was written over",
              racedBodies.count == raceRounds * 2
                  && racedBodies.filter { $0 == "AAAA\n" }.count == raceRounds
                  && racedBodies.filter { $0 == "BBBB\n" }.count == raceRounds)
        check("every name the two of them landed under is a name of its own",
              Set(racedLandings.flatMap(\.landed)).count == raceRounds * 2
                  && Set(racedNames).count == racedNames.count)
        check("and neither of the two files the owner raced is touched",
              (try? String(contentsOf: sameNameA, encoding: .utf8)) == "AAAA\n"
                  && (try? String(contentsOf: sameNameB, encoding: .utf8)) == "BBBB\n")
        check("nothing of Moblee's own is left in the inbox after all of that",
              !((try? fm2.contentsOfDirectory(atPath: racedInbox.path)) ?? [])
                  .contains { $0.hasPrefix(Inbox.incomingPrefix) })
        // The hidden name a half-made copy wears used to be the first eight
        // letters of a UUID, which is two chances in a hundred thousand of two
        // drops picking the same one — and the failure path then deleted what
        // was at that name, which would be the other drop's file.
        check("the hidden name Moblee gives a half-made copy is a whole one, so two drops can never pick the same",
              Set((1...2000).map { _ in Inbox.incomingName() }).count == 2000
                  && Inbox.incomingName().count == Inbox.incomingPrefix.count + 36
                  && Inbox.incomingName().hasPrefix(Inbox.incomingPrefix))

        // A DROP MUST NOT SWEEP AWAY WHAT ANOTHER DROP IS STILL WRITING.
        // Moblee's own half-made copies are hidden and are swept up by a later
        // drop, which is right for one left by a run that was cut off — and
        // was wrong for one a drop running at this moment has open. The victim
        // was then refused with "Moblee could not put that in your wiki… Tell
        // Claude" over a file that was perfectly readable.
        freshWiki()
        let beingWritten = raw.appendingPathComponent(Inbox.incomingName())
        try? "half of something\n".write(to: beingWritten, atomically: true, encoding: .utf8)
        let fromACutOffRun = raw.appendingPathComponent(Inbox.incomingName())
        try? "abandoned\n".write(to: fromACutOffRun, atomically: true, encoding: .utf8)
        try? fm2.setAttributes([.modificationDate: Date().addingTimeInterval(-Inbox.leftoverAge - 60)],
                               ofItemAtPath: fromACutOffRun.path)
        _ = drop(files: [theirFile("While that was going on.md", "mine\n")])
        check("a drop leaves alone the half-made copy another drop is writing this moment",
              fm2.fileExists(atPath: beingWritten.path))
        check("but does sweep up one left behind by a run that was cut off",
              !fm2.fileExists(atPath: fromACutOffRun.path))
        check("and its own file lands all the same",
              inTheInbox().contains("While that was going on.md"))

        // words rather than a file
        freshWiki()
        let when = DateComponents(calendar: Calendar(identifier: .gregorian), timeZone: TimeZone.current,
                                  year: 2026, month: 9, day: 26, hour: 14, minute: 22).date ?? Date()
        landing = drop(text: "  Remember to ask about the roof.  ", now: when)
        let noteName = "Dropped note 2026-09-26.md"
        let note = (try? String(contentsOf: raw.appendingPathComponent(noteName), encoding: .utf8)) ?? ""
        check("words dropped become one plain markdown file with a dated name",
              landing.landed == [noteName] && inTheInbox() == [noteName])
        check("the file says the words were dropped on the app rather than written into the wiki",
              note.contains("dropped on the Moblee app on 2026-09-26 14:22")
                  && note.contains("nobody wrote them into the wiki"))
        check("and the owner's words are in it, exactly as they typed them, with nothing round them lost",
              note.contains("Remember to ask about the roof."))
        check("words with nothing in them are refused rather than made into an empty file",
              drop(text: "   \n  ").wholeDrop == .nothingToTake && inTheInbox() == [noteName])

        // a name already taken: the one already there is not touched
        let sameAgain = theirFile("Gym plan.md", "sets and reps\n")
        freshWiki()
        _ = drop(files: [sameAgain])
        let alreadyThere = raw.appendingPathComponent("Gym plan.md")
        try? "the first one, not to be replaced\n".write(to: alreadyThere, atomically: true, encoding: .utf8)
        let firstAsItWas = AsItWas(alreadyThere)
        landing = drop(files: [sameAgain])
        check("a name already taken in the inbox gets a number, the way a wiki folder's name does",
              landing.landed == ["Gym plan 2.md"] && inTheInbox() == ["Gym plan 2.md", "Gym plan.md"])
        check("and the file already there is left exactly as it was",
              AsItWas(alreadyThere) == firstAsItWas)
        _ = drop(files: [sameAgain])
        check("and a third of the same name goes on counting up",
              inTheInbox() == ["Gym plan 2.md", "Gym plan 3.md", "Gym plan.md"])
        check("the numbering keeps the ending, which is what says what kind of file it is",
              Inbox.freeName("Holiday.jpeg", in: raw).lastPathComponent == "Holiday.jpeg"
                  && Inbox.freeName("Gym plan.md", in: raw).lastPathComponent == "Gym plan 4.md")

        // a folder: refused, and left exactly as it is
        freshWiki()
        let theirFolder = theirs.appendingPathComponent("Holiday photos", isDirectory: true)
        try? fm2.createDirectory(at: theirFolder, withIntermediateDirectories: true)
        try? "a photo\n".write(to: theirFolder.appendingPathComponent("one.txt"), atomically: true, encoding: .utf8)
        landing = drop(files: [theirFolder])
        check("a folder is refused, and nothing of it is copied in",
              landing.landed.isEmpty && landing.turnedAway.map(\.why) == [.isAFolder] && inTheInbox().isEmpty)
        check("and the folder itself is still there, with what was in it",
              fm2.fileExists(atPath: theirFolder.appendingPathComponent("one.txt").path))
        check("the words say what to do instead, and say nothing technical",
              Inbox.sentence(for: landing, talksTo: "Claude")
                  == "Moblee takes files, not folders. Open the folder and drop the files inside it.")

        // something enormous, and something that cannot be read
        freshWiki()
        let huge = theirs.appendingPathComponent("Holiday film.mov")
        fm2.createFile(atPath: huge.path, contents: nil)
        if let handle = try? FileHandle(forWritingTo: huge) {
            try? handle.truncate(atOffset: UInt64(Inbox.biggestBytes + 1))
            try? handle.close()
        }
        let hugeAsItWas = AsItWas(huge)
        landing = drop(files: [huge])
        check("something bigger than Moblee takes is refused, and the refusal says the size in the megabytes Finder shows",
              landing.turnedAway.map(\.why) == [.tooBig] && inTheInbox().isEmpty
                  && Inbox.sentence(for: landing, talksTo: "Claude")
                      == "That is too big for your wiki. Moblee takes files up to 100 MB.")
        check("and the enormous file is still exactly where it was",
              AsItWas(huge) == hugeAsItWas)
        let unreadable = theirFile("Locked.txt", "shut\n")
        let unreadableAsItWas = AsItWas(unreadable)
        try? fm2.setAttributes([.posixPermissions: 0o000], ofItemAtPath: unreadable.path)
        landing = drop(files: [unreadable])
        check("a file Moblee cannot read is refused out loud, and never half-copied",
              landing.turnedAway.map(\.why) == [.cannotRead] && inTheInbox().isEmpty)
        try? fm2.setAttributes([.posixPermissions: 0o644], ofItemAtPath: unreadable.path)
        check("and that file is untouched too", AsItWas(unreadable) == unreadableAsItWas)
        check("a file that is not there at all is refused rather than passed over in silence",
              drop(files: [theirs.appendingPathComponent("never existed.txt")]).turnedAway.map(\.why) == [.cannotRead])

        // some land and some do not: one receipt, which says both
        freshWiki()
        landing = drop(files: [theirFile("Recipe.md", "flour\n"), theirFolder, huge])
        check("a drop where some land and some do not gives one receipt that says both",
              landing.landed == ["Recipe.md"] && landing.turnedAway.count == 2
                  && Inbox.sentence(for: landing, talksTo: "Claude")
                      == "“Recipe.md” is in your wiki, in the folder called raw. 2 did not go. "
                          + "Tell Claude: process the new files in raw/.")

        // no wiki yet: never silence
        let beforeAWiki = theirFile("Before the wiki.md", "nothing must happen to this\n")
        let beforeAsItWas = AsItWas(beforeAWiki)
        try? "\(notAWiki.path)\n".write(to: pointer, atomically: true, encoding: .utf8)
        landing = drop(files: [beforeAWiki])
        check("a drop on a Mac with no wiki yet says plainly that the wiki has to be made first",
              landing.wholeDrop == .noWikiYet
                  && Inbox.sentence(for: landing, talksTo: "Claude")
                      == "Moblee has no wiki yet. Make your wiki first, then drop this on Moblee again.")
        check("and it does nothing at all to what was dropped", AsItWas(beforeAWiki) == beforeAsItWas)

        // while a wiki is being made: the scripts are writing, so it waits
        freshWiki()
        flow.install.phase = .running
        landing = drop(files: [one])
        flow.install.phase = .idle
        check("a drop while a wiki is being made, updated or repaired is refused, and says to wait",
              landing.wholeDrop == .busy && inTheInbox().isEmpty
                  && Inbox.sentence(for: landing, talksTo: "Claude").hasPrefix("Moblee is busy making, updating or repairing a wiki."))
        AppDelegate.repairing = true
        let duringRepair = drop(files: [one])
        AppDelegate.repairing = false
        check("and a repair stops a drop for the same reason an install does",
              duringRepair.wholeDrop == .busy && inTheInbox().isEmpty)

        // the diary: how many, and not one word of what
        freshWiki()
        let diary = Diary.file(home: home)
        // Nothing is deleted here either: what the drop adds is read as the
        // part of the file that was not there a moment ago.
        let diaryBefore = (try? String(contentsOf: diary, encoding: .utf8)) ?? ""
        // The name has to be one nobody could mistake for a word the diary
        // writes of its own accord, and it has to look like a file an owner
        // would rather nobody read — which is the point being proved. It says
        // nothing about any owner: Moblee names no person and no relation
        // anywhere, in its screens or in its source.
        _ = drop(files: [theirFile("Confidential letter Zarquith.pdf", "private\n"), theirFolder])
        let whole = (try? String(contentsOf: diary, encoding: .utf8)) ?? ""
        let dropWrote = String(whole.dropFirst(diaryBefore.count))
        check("a drop writes itself into the install diary, the way a repair does",
              whole.hasPrefix(diaryBefore) && dropWrote.contains("--- Moblee drop ---")
                  && dropWrote.contains("drop: 1 thing(s) copied into the wiki's inbox")
                  && dropWrote.contains("drop: one thing was not taken: it is a folder, and Moblee takes files"))
        check("and the diary carries no file name of what was dropped, because that is the owner's own content",
              !dropWrote.contains("Confidential") && !dropWrote.contains("Zarquith")
                  && !dropWrote.contains("Holiday photos"))
        check("nor the wiki's place, its folder name, or the home folder",
              !dropWrote.contains(madeWiki.path) && !dropWrote.contains(madeWiki.lastPathComponent)
                  && !dropWrote.contains(home.path))
        check("every line a drop can write is free of names and paths",
              [Inbox.Landing(landed: ["ZZLANDEDZZ"], turnedAway: [.init(name: "QQREFUSEDQQ", why: .tooBig)]),
               Inbox.Landing(wholeDrop: .noWikiYet), Inbox.Landing(wholeDrop: .busy),
               Inbox.Landing(wholeDrop: .nothingToTake)]
                  .flatMap { Inbox.diaryLines(for: $0) }
                  .allSatisfy { !$0.contains("ZZLANDEDZZ") && !$0.contains("QQREFUSEDQQ") && !$0.contains("/") })

        // names that are not names
        check("a dropped name can never reach out of the inbox, whatever it says",
              (Inbox.safeName("../../away.txt").map { !$0.contains("/") && !$0.hasPrefix(".") } ?? false)
                  && Inbox.safeName("..") == nil && Inbox.safeName("") == nil
                  && Inbox.safeName(".hidden.md") == "hidden.md")
        let longLatin = Inbox.safeName(String(repeating: "a", count: 400) + ".pdf") ?? ""
        check("and a name longer than a Mac takes is cut short with its ending kept",
              longLatin.utf8.count <= Inbox.longestBytes && longLatin.hasSuffix(".pdf"))
        // The length a filesystem stops at is counted in BYTES, and one letter
        // can be four of them. 180 emoji were 180 letters and 708 bytes: they
        // passed a count of letters and then failed inside `copyItem`, and the
        // owner was told "Moblee could not put that in your wiki… Tell Claude"
        // over a file that was perfectly readable. Rare, safe, and the wrong
        // thing to say. Proved here by really copying one in.
        freshWiki()
        let manyLetters = String(repeating: "🙂", count: 180)
        let emojiName = Inbox.safeName(manyLetters) ?? ""
        check("a name is cut to the bytes a filesystem takes and not to a count of letters",
              manyLetters.count == 180 && manyLetters.utf8.count > 255
                  && emojiName.utf8.count <= Inbox.longestBytes && !emojiName.isEmpty)
        check("and a name cut short is never cut through the middle of a letter",
              emojiName.allSatisfy { $0 == "🙂" })
        // And really copied in, not merely cut on paper. A name of sixty-two
        // emoji is 248 bytes, which a Mac's own disk takes, so this is a file
        // that can exist — and it is longer than the inbox allows, so it has to
        // be cut before it is copied. The old rule counted letters, called
        // sixty-two short enough, and handed `copyItem` a name the filesystem
        // refused; the owner was then shown "Moblee could not put that in your
        // wiki… Tell Claude" over a file that was perfectly readable. (The same
        // fault at its worst needs a disk that counts a name differently from
        // the one the wiki is on — an older Mac disk, or a shared folder over
        // the network — which nothing here can make.)
        let longButReal = String(repeating: "🙂", count: 62)
        let longFile = theirFile(longButReal, "mine\n")
        landing = drop(files: [longFile])
        check("a long name really lands, rather than being refused with a sentence about telling an assistant",
              fm2.fileExists(atPath: longFile.path)
                  && landing.landed.count == 1 && landing.turnedAway.isEmpty
                  && inTheInbox() == landing.landed)
        check("and what landed wears a name cut to fit, with nothing else lost",
              (landing.landed.first ?? "").utf8.count <= Inbox.longestBytes
                  && (landing.landed.first ?? "").allSatisfy { $0 == "🙂" }
                  && (try? Data(contentsOf: raw.appendingPathComponent(landing.landed.first ?? "")))
                      == "mine\n".data(using: .utf8))
        // A name that is only full stops or only spaces is not a name, and
        // nothing failed. It used to be told as `couldNotCopy`, which sends an
        // owner to bother their assistant about a copy never attempted.
        check("a name that cannot be a file name says so, and does not send the owner to their assistant",
              Inbox.safeName("...") == nil && Inbox.safeName("   ") == nil
                  && Inbox.safeName(". . .") == nil
                  && !Inbox.refusalSentence(.nameUnusable, talksTo: "Claude").contains("Claude")
                  && Inbox.refusalSentence(.nameUnusable, talksTo: "Claude")
                      == "That name cannot be a file name. Nothing of yours was changed. Give it a name, then drop it again.")
        freshWiki()
        // A real file, perfectly readable, whose whole name is full stops.
        // Nothing about it fails; only the name cannot be used.
        let onlyDots = theirFile("...", "mine\n")
        let onlyDotsAsItWas = AsItWas(onlyDots)
        landing = drop(files: [onlyDots])
        check("and a real file whose whole name is full stops is refused for that reason and no other",
              landing.turnedAway.map(\.why) == [.nameUnusable] && inTheInbox().isEmpty
                  && Inbox.sentence(for: landing, talksTo: "ChatGPT")
                      == Inbox.refusalSentence(.nameUnusable, talksTo: "ChatGPT"))
        check("and that file is left exactly as it was", AsItWas(onlyDots) == onlyDotsAsItWas)

        // what a drop carries, read from what macOS really hands over
        func readDrop(_ providers: [NSItemProvider]) -> ([URL], String?, [Inbox.Picture]) {
            var got: ([URL], String?, [Inbox.Picture])?
            Inbox.read(providers) { f, t, p in got = (f, t, p) }
            let by = Date().addingTimeInterval(20)
            while got == nil && Date() < by { RunLoop.main.run(until: Date().addingTimeInterval(0.02)) }
            return got ?? ([], nil, [])
        }
        let asAFile = NSItemProvider(item: one.dataRepresentation as NSData,
                                     typeIdentifier: UTType.fileURL.identifier)
        let asWords = NSItemProvider(item: "some words" as NSString,
                                     typeIdentifier: UTType.plainText.identifier)
        let readFile = readDrop([asAFile])
        let readWords = readDrop([asWords])
        check("a dropped file is read back as the file it is",
              readFile.0.map(\.path) == [one.path] && readFile.1 == nil && readFile.2.isEmpty)
        check("and dropped words are read back as words",
              readWords.0.isEmpty && readWords.1 == "some words" && readWords.2.isEmpty)

        // (v0.9.5) A PICTURE WITH NO FILE BEHIND IT. An image dragged out of a
        // web page, or out of a Preview window, puts the picture's own bytes on
        // the board and no file URL at all. Moblee asked macOS for files and
        // words only, so SwiftUI never offered it the drag: it bounced back and
        // nothing was said — while `README.md`, `CHANGELOG.md` and the wiki's
        // own `raw/HOW-TO-ADD-CONTENT.md` all told the owner they could "drag a
        // file, a photo or a piece of text". The provider here is the shape
        // macOS really sends: raw bytes under a picture's own type.
        let pngBytes = Self.smallestPNG
        let asAPicture = NSItemProvider(item: pngBytes as NSData,
                                        typeIdentifier: UTType.png.identifier)
        let readPicture = readDrop([asAPicture])
        check("a picture dragged with no file behind it is read back as a picture",
              readPicture.0.isEmpty && readPicture.1 == nil
                  && readPicture.2.map(\.ending) == ["png"]
                  && readPicture.2.first?.bytes == pngBytes)
        // A web page hands over the picture AND the page's address as words.
        // The picture is what the owner dragged; the address would land as a
        // note saying nothing.
        let fromAWebPage = NSItemProvider()
        fromAWebPage.registerDataRepresentation(forTypeIdentifier: UTType.png.identifier,
                                                visibility: .all) { done in
            done(pngBytes, nil); return nil
        }
        fromAWebPage.registerDataRepresentation(forTypeIdentifier: UTType.plainText.identifier,
                                                visibility: .all) { done in
            done("https://example.invalid/a-page".data(using: .utf8), nil); return nil
        }
        let readWebPicture = readDrop([fromAWebPage])
        check("a picture dragged out of a web page is taken as the picture, not as the page's address",
              readWebPicture.2.count == 1 && readWebPicture.1 == nil && readWebPicture.0.isEmpty)
        freshWiki()
        landing = drop(pictures: [Inbox.Picture(bytes: pngBytes, ending: "png")], now: when)
        let pictureName = "Dropped picture 2026-09-26.png"
        check("a dropped picture becomes a dated picture file in the inbox, with the right ending",
              landing.landed == [pictureName] && inTheInbox() == [pictureName]
                  && (try? Data(contentsOf: raw.appendingPathComponent(pictureName))) == pngBytes)
        landing = drop(pictures: [Inbox.Picture(bytes: pngBytes, ending: "png")], now: when)
        check("and a second picture the same day gets a number rather than replacing the first",
              landing.landed == ["Dropped picture 2026-09-26 2.png"]
                  && (try? Data(contentsOf: raw.appendingPathComponent(pictureName))) == pngBytes)
        freshWiki()
        landing = drop(files: [one], pictures: [Inbox.Picture(bytes: pngBytes, ending: "png")], now: when)
        check("a drop carrying both a file and a picture takes both, and says so once",
              landing.landed == ["Gym plan.md", pictureName]
                  && Inbox.sentence(for: landing, talksTo: "Claude")
                      == "2 things are in your wiki, in the folder called raw. Tell Claude: process the new files in raw/.")
        // The window really does ask macOS for those kinds, which is the whole
        // of why the drag is offered at all.
        check("the window asks macOS for pictures as well as files and words",
              Inbox.pictureTypes.contains(.png) && Inbox.pictureTypes.contains(.jpeg)
                  && Inbox.pictureType(of: asAPicture) == .png
                  && Inbox.pictureType(of: asWords) == nil)

        freshWiki()
        landing = drop(files: [one], text: "the name of the file, which Finder puts on the board beside it")
        check("a file dropped with its own name as words beside it is taken as the file, and the words are ignored",
              landing.landed == ["Gym plan.md"] && !inTheInbox().contains { $0.hasPrefix("Dropped note") })
        check("a drop carrying neither a file nor any words is refused rather than passed over",
              drop().wholeDrop == .nothingToTake)

        // the receipt, and where a receipt may be shown
        check("the receipt names what landed and where, and what to do next, in the pack's own words",
              Inbox.sentence(for: Inbox.Landing(landed: ["Notes.txt"]), talksTo: "ChatGPT")
                  == "“Notes.txt” is in your wiki, in the folder called raw. Tell ChatGPT: process the new files in raw/.")
        // Every way a drop can end, taken from the type itself rather than
        // written out here, so that a reason added later cannot slip past this
        // by not being on somebody's list. (v0.9.5)
        let everyRefusal: [Inbox.Refusal] = [.noWikiYet, .busy, .isAFolder, .tooBig, .cannotRead,
                                             .nothingToTake, .nameUnusable, .couldNotCopy]
        check("every way a drop can be refused has its own sentence, and none of them is a technical message",
              everyRefusal.allSatisfy { why in
                  let said = Inbox.refusalSentence(why, talksTo: "Claude")
                  return said.count > 30 && said.hasSuffix(".") && !said.contains("Error")
                      && !said.contains("error") && !said.contains("/Users") && !said.contains("NS")
              })
        check("and no two of them say the same thing",
              Set(everyRefusal.map { Inbox.refusalSentence($0, talksTo: "Claude") }).count == everyRefusal.count
                  && Set(everyRefusal.map(\.diaryWord)).count == everyRefusal.count
                  && Set(everyRefusal.map { Inbox.turnedAwayWords($0, talksTo: "Claude") }).count
                      == everyRefusal.count)
        // (v0.9.5) Three of these used to say "Claude" whoever the wiki was
        // for. Unreachable from the receipt today, and a trap for whoever makes
        // one of them reachable next.
        check("and not one of them names an assistant the wiki is not for",
              everyRefusal.allSatisfy { !Inbox.turnedAwayWords($0, talksTo: "ChatGPT").contains("Claude") }
                  && everyRefusal.allSatisfy { !Inbox.refusalSentence($0, talksTo: "ChatGPT").contains("Claude") }
                  && Inbox.turnedAwayWords(.busy, talksTo: "ChatGPT")
                      == Inbox.refusalSentence(.busy, talksTo: "ChatGPT"))
        // The screen's own titles, asked of the screen and not of the value the
        // screen was handed. It used to read `landing.anythingLanded` straight
        // back out of the thing it had just put in, so the two words could have
        // been swapped over and it would have held. (v0.9.5)
        check("the receipt's button is Done when something landed and Carry on when nothing did",
              DropScreen.buttonTitle(for: Inbox.Landing(landed: ["a"])) == "Done"
                  && DropScreen.buttonTitle(for: Inbox.Landing(wholeDrop: .busy)) == "Carry on"
                  && DropScreen.buttonTitle(for: Inbox.Landing(landed: ["a"],
                                                               turnedAway: [.init(name: "b", why: .tooBig)]))
                      == "Done")
        try? (pointedAtBefore).write(to: pointer, atomically: true, encoding: .utf8)

        // --- read it to me, everywhere (v0.9.5) ---
        //
        // There was one listen control in the whole app and it read the screen's
        // big sentence. Everything else an owner is expected to read — the words
        // on every card, the tiles and their reasons, the check-up's findings,
        // the skill they are about to add, the receipt for what they dropped, the
        // five steps in ChatGPT, the update and repair sentences, the quiet
        // words — was silent, so an owner who would rather be told than read got
        // the headline and nothing else.
        //
        // What can be checked here is everything but the sound: which words each
        // control would say, which voice each piece of words asks for, that
        // starting one stops the one before it, and that nothing starts on its
        // own. Whether a voice really comes out of the Mac is the one thing
        // nothing here can hear.

        // Which voice. The rules are asked of a made-up Mac — a list of voices
        // and a language the Mac is set to — so that every one of them can be
        // checked on a Mac that does not happen to match.
        check("Moblee's own sentences are read in a British voice where the Mac has one",
              Voices.choose("Your wiki is ready.", .mobleesOwn,
                            have: ["en-US", "en-GB", "ar-SA"], macLanguage: "en-US") == "en-GB")
        check("with no British voice on the Mac, the Mac's own English is used, and failing that any English",
              Voices.choose("Your wiki is ready.", .mobleesOwn,
                            have: ["en-AU", "en-US"], macLanguage: "en-AU") == "en-AU"
                  && Voices.choose("Your wiki is ready.", .mobleesOwn,
                                   have: ["en-US"], macLanguage: "ar-SA") == "en-US")
        check("and with no English voice at all nothing is chosen, so macOS reads it in the voice the Mac itself would use",
              Voices.choose("Your wiki is ready.", .mobleesOwn, have: ["ar-SA"], macLanguage: "ar-SA") == nil
                  && Voices.choose("Your wiki is ready.", .mobleesOwn, have: [], macLanguage: "en-GB") == nil)
        // The whole point of the change: a name written in the owner's own script
        // is never read out by an English voice.
        check("the owner's own name written in Arabic asks for an Arabic voice, not an English one",
              Voices.choose(light, .theOwners, have: ["en-GB", "ar-SA"], macLanguage: "en-GB") == "ar-SA")
        check("and a voice for that language in whatever country's form the Mac happens to have",
              Voices.choose(light, .theOwners, have: ["en-GB", "ar-001"], macLanguage: "en-GB") == "ar-001")
        check("with no Arabic voice on the Mac it falls back to Moblee's own rather than refusing to read",
              Voices.choose(light, .theOwners, have: ["en-GB"], macLanguage: "en-GB") == "en-GB")
        check("the same for Hebrew, Greek, Russian, Thai and Korean",
              Voices.language(ofScriptIn: "שלום") == "he" && Voices.language(ofScriptIn: "Ελλάδα") == "el"
                  && Voices.language(ofScriptIn: "Привет") == "ru" && Voices.language(ofScriptIn: "สวัสดี") == "th"
                  && Voices.language(ofScriptIn: "안녕") == "ko")
        // (v0.9.5) The honest answer, said here as plainly as in the code. Kana
        // say Japanese. The Han characters say nothing at all: no rule over the
        // letters can tell 日本語 from 中文, because they are written with
        // characters from one shared set. The check that stood here was called
        // "Japanese is told from Chinese by its own letters" and then asserted
        // that 日本語 is Chinese, so it did not flag that a Japanese owner whose
        // name is in kanji had it read out in Mandarin — it guarded it.
        check("kana say Japanese outright",
              Voices.language(ofScriptIn: "日本のことば") == "ja"
                  && Voices.language(ofScriptIn: "アキラ") == "ja")
        check("but the Han characters are shared, so the letters alone cannot say which language they are",
              Voices.language(ofScriptIn: "日本語") == "zh" && Voices.language(ofScriptIn: "中文") == "zh"
                  && Voices.shareTheHanCharacters.contains("ja") && Voices.shareTheHanCharacters.contains("zh"))
        // So the Mac settles it, which is the best thing anything can do: an
        // owner whose Mac is set to Japanese reads and writes Japanese.
        check("so on a Mac set to Japanese, a name in kanji is read by the Japanese voice and not by the Mandarin one",
              Voices.choose("日本語", .theOwners, have: ["ja-JP", "zh-CN", "en-GB"], macLanguage: "ja-JP") == "ja-JP")
        check("and on a Mac set to Chinese the same name is read by the Mandarin voice",
              Voices.choose("日本語", .theOwners, have: ["ja-JP", "zh-CN", "en-GB"], macLanguage: "zh-CN") == "zh-CN")
        check("on a Mac set to neither, the shared characters are read as Chinese, which is a guess and is said to be one",
              Voices.choose("日本語", .theOwners, have: ["ja-JP", "zh-CN", "en-GB"], macLanguage: "en-GB") == "zh-CN")
        check("and kana are never given to the Mandarin voice, whatever the Mac is set to",
              Voices.choose("日本のことば", .theOwners,
                            have: ["ja-JP", "zh-CN", "en-GB"], macLanguage: "zh-CN") == "ja-JP")
        check("Latin letters say nothing about the language, because dozens are written in them",
              Voices.language(ofScriptIn: "Sam") == nil && Voices.language(ofScriptIn: "Gym plan.pdf") == nil)
        check("one stray letter does not decide: the letters are counted",
              Voices.language(ofScriptIn: "Holiday film in \(light)") == "ar"
                  && Voices.language(ofScriptIn: "\(light) and a long English sentence after it") == "ar")
        // Where the letters say nothing, the Mac's own language is used for the
        // owner's words if it is written in those same letters, and never where
        // it is not: an Arabic voice spelling out "Sam" is the fault this avoids.
        check("a Latin-lettered name on a French Mac is read in the Mac's own voice",
              Voices.choose("Étienne", .theOwners, have: ["en-GB", "fr-FR"], macLanguage: "fr-FR") == "fr-FR")
        check("but Moblee's own sentence on that same Mac is still read in English",
              Voices.choose("Your wiki is ready.", .mobleesOwn,
                            have: ["en-GB", "fr-FR"], macLanguage: "fr-FR") == "en-GB")
        check("and a Latin-lettered name on an Arabic Mac is not handed to the Arabic voice",
              Voices.choose("Sam", .theOwners, have: ["en-GB", "ar-SA"], macLanguage: "ar-SA") == "en-GB"
                  && !Voices.writtenInLatin("ar-SA") && Voices.writtenInLatin("fr-FR"))

        // What each control would say. Every one of these is asked of the very
        // words the screen beside it shows, and never of a second copy of them.
        let headlineOnly = Headline.speech(sentence: TrustScreen.notRunningSentence, spoken: nil, speech: nil)
        check("with nothing else said, a screen's listen control reads that screen's own sentence",
              headlineOnly.plain == TrustScreen.notRunningSentence
                  && headlineOnly.pieces.map(\.whose) == [.mobleesOwn])
        // (v0.9.5) Asked of the branch the hand-off really takes. It used to
        // pass `speech: nil`, and `Headline.speech` gives a `speech` back
        // before it ever looks at `spoken`, so it was checking a branch no
        // screen in the app reaches any more. And `Speech.plain` used to put a
        // space in front of a full stop that followed the owner's own words,
        // so the same sentence came back as "Sam Wiki . Three" and could never
        // have matched the screen's own words in the first place.
        let handoffSaid = HandoffScreen.spoken(for: .claude, wiki: wikiName)
        let handoffHeadline = Headline.speech(
            sentence: HandoffScreen.sentence(for: .claude, opened: false),
            spoken: handoffSaid,
            speech: Speech.sentence(handoffSaid, theirs: wikiName))
        check("and where a screen says more aloud than it shows, that is what is read",
              handoffHeadline.plain == handoffSaid)
        // And the branch in between, which the promise screen and the Trust
        // steps still take: more said aloud than shown, with nothing of the
        // owner's in it, so one voice reads the lot.
        let promiseWords = PromiseScreen.words(for: .claude)
        let promiseSaid = PromiseScreen.spoken(place: "Sam Wiki", words: promiseWords)
        let promiseHeadline = Headline.speech(sentence: promiseWords.sentence,
                                              spoken: promiseSaid, speech: nil)
        check("and a screen that says more aloud than it shows, with none of the owner's own words in it, reads all of it in one voice",
              promiseHeadline.plain == promiseSaid && promiseHeadline.pieces.map(\.whose) == [.mobleesOwn])
        check("and a sentence cut at the owner's own words goes back together exactly as the screen shows it",
              Speech.sentence("Pick your wiki, called \(wikiName). Then say the words.", theirs: wikiName).plain
                  == "Pick your wiki, called \(wikiName). Then say the words."
                  && Speech.sentence(handoffSaid, theirs: wikiName).pieces.map(\.whose)
                      == [.mobleesOwn, .theOwners, .mobleesOwn])

        // A tile: its title, the reason Claude asked for it, what it costs and
        // where it has got to — the reason being the part the owner is deciding
        // on, which had no voice at all.
        let spokenTile = HomeModel.Tile(kind: .item, key: "videos", title: "Watch and summarise videos",
                                        why: "You save YouTube videos to watch later.",
                                        detail: "About 4 min · 200 MB · free", how: .terminal, paid: false)
        let tileSaid = RequestTile.speech(for: spokenTile)
        check("a tile is read with its title, the reason it was asked for, what it costs and where it has got to",
              tileSaid.plain.contains(spokenTile.title) && tileSaid.plain.contains(spokenTile.why)
                  && tileSaid.plain.contains(spokenTile.detail)
                  && tileSaid.plain.contains(RequestTile.stateWord(spokenTile)))
        var brokenTile = spokenTile
        brokenTile.state = .failed
        brokenTile.note = "The download stopped half-way."
        check("a tile that went wrong is read with what went wrong, in the engine's own words, in place of the reason",
              RequestTile.speech(for: brokenTile).plain.contains(brokenTile.note)
                  && !RequestTile.speech(for: brokenTile).plain.contains(spokenTile.why))
        // A skill wears the name the owner asked for, in their own words.
        var arabicSkill = HomeModel.Tile(kind: .skill, key: light, title: "A skill Claude wrote: \(light)",
                                         why: "You asked for it.", detail: "It does a thing.",
                                         how: .silent, paid: false)
        arabicSkill.files = ["SKILL.md"]
        let skillSaid = RequestTile.speech(for: arabicSkill)
        check("a skill Claude wrote wears a name of the owner's own, so that name is read in a voice chosen for it",
              skillSaid.pieces.contains { $0.words == light && $0.whose == .theOwners }
                  && skillSaid.pieces.contains { $0.whose == .mobleesOwn }
                  && Voices.choose(light, .theOwners, have: ["en-GB", "ar-SA"], macLanguage: "en-GB") == "ar-SA")

        // The card that sends an owner to find their wiki folder in Finder.
        let arabicFolder = light + " Wiki"
        let folderCard = HandoffScreen.cards(for: .claude, wiki: arabicFolder)[1]
        let folderSaid = HandoffCard.speech(title: folderCard.title, detail: folderCard.detail,
                                            ownWords: arabicFolder)
        check("the card that names the wiki folder reads Moblee's words in Moblee's voice and the folder's name in one chosen for it",
              folderSaid.pieces.map(\.whose) == [.mobleesOwn, .theOwners]
                  && folderSaid.pieces.last?.words == arabicFolder
                  && folderSaid.plain.hasPrefix(folderCard.title)
                  && folderSaid.plain.hasSuffix(arabicFolder))
        check("a card with nothing of the owner's in it is read in one voice, as it always was",
              HandoffCard.speech(title: HandoffScreen.cards(for: .claude, wiki: arabicFolder)[0].title,
                                 detail: HandoffScreen.cards(for: .claude, wiki: arabicFolder)[0].detail,
                                 ownWords: arabicFolder).pieces.map(\.whose) == [.mobleesOwn])
        // The marks that let a name stand on its own on the screen must never
        // reach a voice; see `OwnWords`. The greeting is where they are put on.
        let greeted = NameScreen.greetingSpeech(light)
        check("the greeting reads Moblee's word in Moblee's voice and the owner's name in one chosen for the name",
              greeted.pieces == [.init("Hi,", .mobleesOwn), .init(light, .theOwners)]
                  && NameScreen.greeting(light).contains(OwnWords.isolate))
        check("and not one of the invisible marks reaches the voice",
              greeted.pieces.allSatisfy {
                  !$0.words.contains(OwnWords.isolate) && !$0.words.contains(OwnWords.pop)
              }
                  && Speech(NameScreen.greeting(light)).pieces.allSatisfy {
                      !$0.words.contains(OwnWords.isolate) && !$0.words.contains(OwnWords.pop)
                  })
        check("an owner who has typed nothing is greeted by a control that still has something to say",
              !NameScreen.greetingSpeech("").isEmpty)

        // The drop receipt: every name it shows, each in a voice for that name.
        let receipt = Inbox.Landing(landed: ["Gym plan.pdf", light + ".pdf"],
                                    turnedAway: [.init(name: "Holiday film.mov", why: .tooBig)])
        let receiptSaid = DropScreen.landedSpeech(for: receipt, talksTo: "Claude")
        let theirNames = receiptSaid.pieces.filter { $0.whose == .theOwners }.map(\.words)
        let arabicPdfVoice = Voices.choose(light + ".pdf", .theOwners,
                                           have: ["en-GB", "ar-SA"], macLanguage: "en-GB")
        check("the receipt reads every name it shows, each in a voice chosen for the letters the owner named it in",
              theirNames == ["Gym plan.pdf", light + ".pdf", "Holiday film.mov"]
                  && receiptSaid.plain.contains(Inbox.turnedAwayWords(.tooBig, talksTo: "Claude"))
                  && arabicPdfVoice == "ar-SA")
        check("and a receipt with more names than it shows says how many more, in the screen's own words",
              DropScreen.landedSpeech(for: Inbox.Landing(landed: (1...7).map { "Scan \($0).pdf" }),
                                      talksTo: "Claude").plain
                  .contains(DropScreen.moreLine(7 - DropScreen.namesShown)))

        // The build and update tiles, read as one list rather than one by one.
        let building = InstallRun()
        building.startUpdateItemsForTest()
        let listSaid = BuildScreen.listSpeech(building)
        check("the list of what is being made is read tile by tile, in the words on the tiles and where each has got to",
              building.items.allSatisfy { listSaid.plain.contains(BuildTile.said($0)) }
                  && listSaid.plain.hasPrefix("0 of \(building.items.count) done."))

        // The check-up's findings, and the three cards nobody could hear.
        check("a check-up card is read with what it is, whether it can wait, and where it has got to",
              NeedTile.speech(Checkup.need(.obsidian), present: nil, asked: false).plain
                  == Checkup.need(.obsidian).name + ". Can wait. Not on this Mac yet. Press Get."
                  && NeedTile.speech(Checkup.need(.claude), present: true, asked: false).plain
                      == Checkup.need(.claude).name + ". Here.")
        check("an assistant card says its own word, and whether it is the one chosen",
              AssistantChoice.speech(.claude, chosen: false).plain == Assistant.claude.name
                  && AssistantChoice.speech(.claude, chosen: true).plain.hasPrefix(Assistant.claude.name)
                  && AssistantChoice.speech(.claude, chosen: true).plain
                      != AssistantChoice.speech(.claude, chosen: false).plain)

        // Names. Every listen control on a screen has one of its own, so the
        // keyboard ring, the walk and a screen reader can each tell them apart,
        // and none of them collides with the control it stands beside.
        //
        // (v0.9.5) The screen is asked what is on it. What used to stand here
        // was a list of sixteen strings typed out by hand, asserted to have no
        // repeats (true of any sixteen different strings) and to be no longer
        // than sixteen (true of a list that is exactly sixteen long): neither
        // could fail, whatever the real screen did. And the screen it measured
        // was not the busiest one — a tile handed over for clicks grows a Done
        // button, and three of those are three stops nobody had counted.
        let threeThatAreWaiting: [HomeModel.Tile] = ["trips", "videos", "google"].map {
            var tile = HomeModel.Tile(kind: .item, key: $0, title: "", why: "", detail: "",
                                      how: .silent, paid: false)
            tile.state = .waiting
            return tile
        }
        let onTheHomeScreen = HomeScreen.busiest()
        check("every control on the busiest screen has a name of its own, listening and doing alike",
              Set(onTheHomeScreen).count == onTheHomeScreen.count && onTheHomeScreen.count >= 17)
        check("and the busiest screen really is the one with a Done button on every tile that has one",
              onTheHomeScreen.filter { $0.hasSuffix("-done") }.count == 2
                  && HomeScreen.busiest().count
                      > HomeScreen.stops(shown: threeThatAreWaiting, nextTileWaiting: true,
                                         canChangeAssistant: true, wantsChatGPT: true,
                                         newerRelease: true).count)
        check("and a listen control is never called the same thing as the control it stands beside",
              RequestTile.listenId(spokenTile) != RequestTile.buttonId(spokenTile)
                  && RequestTile.listenId(spokenTile) != RequestTile.doneId(spokenTile)
                  && NeedTile.listenId(Checkup.need(.claude)) != Checkup.need(.claude).getId
                  && AssistantChoice.listenId(.claude) != "assistant-" + Assistant.claude.rawValue)
        // (v0.9.5) Each listen control stands NEXT TO the words it reads on the
        // keyboard's round. The three tile speakers used to come as a run of
        // three before any of the three Add buttons, so an owner pressing Tab
        // could not tell from where they were which speaker belonged to which
        // tile. Asserted as adjacency and not as membership, and measured again
        // on the real window in the walk.
        func nextTo(_ ring: [String], _ listen: String, _ words: [String]) -> Bool {
            guard let at = ring.firstIndex(of: listen) else { return false }
            let beside = [at - 1, at + 1].filter { ring.indices.contains($0) }.map { ring[$0] }
            return words.isEmpty ? true : words.contains { beside.contains($0) }
        }
        check("every tile's listen control stands next to that tile's own buttons on the keyboard's round",
              HomeScreen.busiestTiles().allSatisfy { tile in
                  nextTo(onTheHomeScreen, RequestTile.listenId(tile),
                         [RequestTile.buttonId(tile), RequestTile.doneId(tile)])
              })
        check("and a tile's listen control never stands next to another tile's",
              HomeScreen.busiestTiles().allSatisfy { tile in
                  let at = onTheHomeScreen.firstIndex(of: RequestTile.listenId(tile)) ?? -1
                  let beside = [at - 1, at + 1].filter { onTheHomeScreen.indices.contains($0) }
                      .map { onTheHomeScreen[$0] }
                  return !beside.contains { $0.hasPrefix("listen-tile-") }
              })
        check("the quiet words and the two corner lines each have their listen control beside them too",
              nextTo(onTheHomeScreen, "listen-quiet", ["quiet"])
                  && nextTo(onTheHomeScreen, "listen-newer-line", ["download-newer", "newer-not-now"])
                  // (v0.9.6) "Check my wiki" joined this line, so it is one of the
                  // controls the line's listen control may stand beside.
                  && nextTo(onTheHomeScreen, "listen-assistant-line",
                            ["change-assistant", "prove-guard", "check-wiki"]))
        // The keyboard has to cross the screen in a sensible number of presses.
        // v0.9.4 made every control reachable by Tab; putting a listen control
        // beside every block of words is exactly the change that could turn that
        // into twenty presses to reach the thing the owner actually wants.
        //
        // (v0.9.5) Nineteen, and said out loud rather than left at a number the
        // list happened to be. That is the real worst case and it is one press
        // more than the eighteen the old ceiling was set at, which nothing was
        // measuring. The ceiling is held here and measured on the real window
        // in the walk.
        //
        // (v0.9.6) TWENTY, and the ceiling moved with it, which is worth reading
        // before it is moved again. Two separate pieces of this version each put
        // one more control on this screen — the way into the example wiki, and
        // "Check my wiki" — and neither could see the other while it was being
        // built. The number was only found when the two were brought together,
        // which is what this check is for.
        //
        // Nothing was taken off to make room, and that is deliberate: quietly
        // removing one item's button to keep another item's number is not a call
        // to make without asking. Whether twenty stops is too many for the people
        // this product is for is a design decision and not a test's to settle.
        // The honest options if it is too many are to drop the example button
        // from the ordinary home screen (it is also on the welcome screen, where
        // a new owner meets it), or to put the bottom corner's three controls
        // behind one stop. Raising the ceiling every time it is reached is how it
        // stops meaning anything.
        check("the busiest screen stays at twenty controls or fewer, listening and doing together",
              onTheHomeScreen.count <= 20
                  && onTheHomeScreen.filter { $0.hasPrefix("listen-") }.count * 2 <= onTheHomeScreen.count)
        check("the five Trust steps have a listen control each, named by which step it is",
              Set(Trust.steps.indices.map { TrustSteps.listenId(step: $0 + 1) }).count == Trust.steps.count
                  && TrustSteps.listenId(step: 1) == "listen-trust-step-1")
        check("and three cards abreast have one each, named by which card it is",
              Set((1...3).map { HandoffCard.listenId(number: $0) }).count == 3)

        // One voice at a time, and nothing speaks unasked. The synthesiser is the
        // real one; what is read here is which control it says is speaking.
        let voice = Speaker.shared
        check("nothing has spoken: not one screen, not one card, not the whole of this check so far",
              voice.speakingId == nil && voice.timesAsked == 0)
        voice.toggle("listen-one", Speech("one"))
        check("pressing a listen control starts it, and that control is the one that says it is speaking",
              voice.speakingId == "listen-one")
        voice.toggle("listen-two", Speech("two"))
        check("pressing another stops the first: one voice at a time, and only the second says it is speaking",
              voice.speakingId == "listen-two")
        voice.toggle("listen-two", Speech("two"))
        check("pressing the one that is speaking stops it", voice.speakingId == nil)
        voice.toggle("listen-three", Speech("three"))
        voice.stop()
        check("and leaving a screen stops whatever was reading", voice.speakingId == nil)
        let askedSoFar = voice.timesAsked
        voice.toggle("listen-nothing", Speech(""))
        check("a control with no words to say starts nothing, and is not counted as an asking",
              voice.speakingId == nil && voice.timesAsked == askedSoFar)
        // Three readings were started above, not four: pressing the control that
        // is already speaking stops it and starts nothing, which is the whole
        // point of the second press.
        check("every one of those was the owner pressing something; the app started none of them",
              askedSoFar == 3)
        // A block read in two voices is two utterances of one press.
        voice.toggle("listen-two-voices", greeted)
        check("a block read in two voices is still one control speaking", voice.speakingId == "listen-two-voices")
        voice.stop()

        // ------------------------------------------------------------------
        // (v0.9.6) The check-up an owner runs themselves, from one press.
        //
        // The live walk cannot be relied on for this, so every decision in it is
        // read back here without a window: where the report goes, that an earlier
        // one is never overwritten, the redaction, every refusal, the time limit,
        // and what the screen says for each outcome. A real practice wiki is
        // built under the practice home and the REAL check-up is run against it
        // through the app's own code, so what is proved here is the code an owner
        // meets and not a description of it.
        // ------------------------------------------------------------------
        let clinicYard = home.appendingPathComponent("clinic-check", isDirectory: true)
        let fmc = FileManager.default

        /// A wiki of the shape Moblee makes, in a folder of this check's own. The
        /// folder is named with a word that appears nowhere else, so a report that
        /// carried the wiki's own folder name could not hide it.
        func practiceWiki(_ folder: String, owner: String?, rulesFile: String = "CLAUDE.md",
                          withIdentity: Bool = true) -> URL {
            let v = clinicYard.appendingPathComponent(folder, isDirectory: true)
            for sub in ["wiki", "raw/processed", "Clippings/processed", "outputs/lint"] {
                try? fmc.createDirectory(at: v.appendingPathComponent(sub), withIntermediateDirectories: true)
            }
            let named = owner ?? "[Your Name]"
            try? ("# rules\n\nThis is an Obsidian vault: a personal knowledge base for \(named) "
                  + "where the assistant is the maintainer.\n")
                .write(to: v.appendingPathComponent(rulesFile), atomically: true, encoding: .utf8)
            try? "0.9.6\n".write(to: v.appendingPathComponent("VERSION"), atomically: true, encoding: .utf8)
            // A wiki with one of its four always-there files never written is how
            // the check for a missing one is made, so that nothing in this check
            // has to remove a file.
            if withIdentity {
                try? "# Identity\n".write(to: v.appendingPathComponent("wiki/Identity.md"),
                                         atomically: true, encoding: .utf8)
            }
            try? "# Context\n\nLast refreshed: 2026-09-20\n"
                .write(to: v.appendingPathComponent("wiki/_context.md"), atomically: true, encoding: .utf8)
            try? "# Index\n".write(to: v.appendingPathComponent("wiki/Index.md"), atomically: true, encoding: .utf8)
            try? "# Log\n\n## [2026-09-21 09:00 +0100] ingest | one\n\n## [2026-09-22 10:00 +0100] query | two\n"
                .write(to: v.appendingPathComponent("wiki/log.md"), atomically: true, encoding: .utf8)
            return v
        }

        /// A stand-in check-up, for the ways a real one can go wrong. It is a
        /// python file in a pack's own place, so the app runs it by exactly the
        /// code path that runs the real one.
        func standInPack(_ folder: String, python: String?) -> URL {
            let p = clinicYard.appendingPathComponent(folder, isDirectory: true)
            if let python {
                try? fmc.createDirectory(at: p.appendingPathComponent("scripts"), withIntermediateDirectories: true)
                try? python.write(to: p.appendingPathComponent("scripts/moblee-doctor.py"),
                                  atomically: true, encoding: .utf8)
            } else {
                try? fmc.createDirectory(at: p, withIntermediateDirectories: true)
            }
            return p
        }

        /// Runs the check-up to its end without a window, pumping the run loop the
        /// way `--rehearse` does, and hands back the state the screen would show.
        func runClinic(vault: URL?, pack: URL?, limit: TimeInterval = Clinic.timeLimit,
                       waiting: TimeInterval = 150) -> Clinic.State {
            let clinic = Clinic()
            clinic.begin(home: home, vault: vault, pack: pack,
                         wikiVersion: "0.9.6", packVersion: "0.9.6", limit: limit)
            let deadline = Date().addingTimeInterval(waiting)
            while clinic.state == .running && Date() < deadline {
                RunLoop.main.run(until: Date().addingTimeInterval(0.05))
            }
            return clinic.state
        }

        /// Every file under a folder, by its place inside it and its bytes: the
        /// way to say that a read-only check-up really read only.
        func fingerprint(_ folder: URL) -> [String: Data] {
            var out: [String: Data] = [:]
            // The practice home is under /tmp, which on a Mac is a link to
            // /private/tmp, so the paths the walk hands back begin with the
            // resolved one while the folder's own does not. Every spelling of the
            // root is taken off, or a file's place inside the wiki comes out as
            // "/privateraw/..." and nothing matches anything (seen here today).
            let roots = [folder.path, folder.resolvingSymlinksInPath().path, "/private" + folder.path]
            guard let walk = fmc.enumerator(at: folder, includingPropertiesForKeys: nil) else { return out }
            for case let url as URL in walk {
                var isFolder: ObjCBool = false
                guard fmc.fileExists(atPath: url.path, isDirectory: &isFolder), !isFolder.boolValue else { continue }
                var key = url.path
                for root in roots where key.hasPrefix(root + "/") {
                    key = String(key.dropFirst(root.count + 1))
                    break
                }
                out[key] = (try? Data(contentsOf: url)) ?? Data()
            }
            return out
        }

        // --- who the owner is, and the name the report is filed under ---
        let rules = "a personal knowledge base for Mary Ann where the assistant is the maintainer."
        check("the owner's name is read from the wiki's rules file, the way the clinic note reads it",
              Clinic.ownerName(inRules: rules) == "Mary Ann")
        check("a rules file nobody filled in names nobody, rather than naming the placeholder",
              Clinic.ownerName(inRules: "knowledge base for [Your Name] where") == nil
                  && Clinic.ownerName(inRules: "nothing of the kind") == nil)
        check("the report's file name takes the first word only, lower case, with anything that is not a plain letter a hyphen",
              Clinic.ownerKey(from: "Mary Ann") == "mary" && Clinic.ownerKey(from: "Zoë") == "zo-"
                  && Clinic.ownerKey(from: "Ali & Noor") == "ali" && Clinic.ownerKey(from: nil) == "owner")
        check("so the report is the file the clinic note names",
              Clinic.reportName(ownerKey: "sam") == "clinic-report-sam-\(Clinic.roundStamp).md"
                  && Clinic.reportName(ownerKey: Clinic.ownerKey(from: nil))
                      == "clinic-report-owner-\(Clinic.roundStamp).md")
        check("and the date in the name is the day the check-up ran, written the same way in any language",
              Clinic.stamp(for: Date(timeIntervalSince1970: 1_790_856_000)) == "checkup-2026-10-01"
                  && Clinic.reportName(ownerKey: "sam", on: Date(timeIntervalSince1970: 1_790_856_000))
                      == "clinic-report-sam-checkup-2026-10-01.md")
        // (v0.9.6) A name with no a-to-z letter in it at all. The note's rule
        // turns every character into a hyphen, and this follows the note rather
        // than improving on it, because the maintainer's process reads reports by
        // the name the note gives and a Moblee that filed them somewhere else
        // would simply be missed. v0.9.4 taught Moblee to take a name in Arabic,
        // so this is an ordinary case and not a curiosity. Nothing breaks: the file
        // still begins `clinic-report-`, which is what the owner is told to look
        // for, and the report's own `vault_owner:` line carries their name as
        // they typed it. (Decided 27 September 2026: nothing but hyphens gave
        // every such owner the same file name, so it falls back to "owner".)
        check("a name with no plain letters in it still makes a file the owner can be told to look for",
              Clinic.ownerKey(from: "نور") == "owner" && Clinic.ownerKey(from: "Zoë") == "zo-"
                  && Clinic.reportName(ownerKey: Clinic.ownerKey(from: "نور"))
                      .hasPrefix("clinic-report-"))
        let chatgptWiki = practiceWiki("wiki-chatgpt", owner: "Noor", rulesFile: "AGENTS.md")
        check("a wiki laid down for ChatGPT alone names its owner in AGENTS.md, and is read there",
              Clinic.ownerName(inWiki: chatgptWiki) == "Noor")

        // --- where the report goes, and that an earlier one is never written over ---
        let realWiki = practiceWiki("zqxwiki-kept", owner: "Sam")
        let clinicRaw = realWiki.appendingPathComponent("raw", isDirectory: true)
        // Two files an earlier round left behind, so the loose ends have something
        // to count and a clinic note has a status to report.
        try? "waiting\n".write(to: clinicRaw.appendingPathComponent("a note.md"), atomically: true, encoding: .utf8)
        try? "---\nstatus: NOT YET CARRIED OUT (something)\n---\n"
            .write(to: clinicRaw.appendingPathComponent("clinic-checkup-2026-09-24.md"), atomically: true, encoding: .utf8)
        let beforeRun = fingerprint(realWiki)
        let firstState = runClinic(vault: realWiki, pack: flow.bundledPack)
        var firstCard: Clinic.Card?
        var firstName: String?
        if case .finished(let done) = firstState { firstCard = done.card; firstName = done.savedAs }
        check("the real check-up runs from the app's own code and comes back with a health card",
              firstCard != nil && !(firstCard?.lines.isEmpty ?? true))
        check("and the report is saved in the wiki's own raw folder, under the clinic note's name",
              firstName == "clinic-report-sam-\(Clinic.roundStamp).md"
                  && fmc.fileExists(atPath: clinicRaw.appendingPathComponent(
                        "clinic-report-sam-\(Clinic.roundStamp).md").path))
        let firstReport = (try? String(contentsOf: clinicRaw.appendingPathComponent(
            "clinic-report-sam-\(Clinic.roundStamp).md"), encoding: .utf8)) ?? ""
        let secondState = runClinic(vault: realWiki, pack: flow.bundledPack)
        var secondName: String?
        if case .finished(let done) = secondState { secondName = done.savedAs }
        let firstAfter = (try? String(contentsOf: clinicRaw.appendingPathComponent(
            "clinic-report-sam-\(Clinic.roundStamp).md"), encoding: .utf8)) ?? ""
        check("a second check-up never writes over the first report: it gets a number of its own",
              secondName == "clinic-report-sam-\(Clinic.roundStamp)-2.md"
                  && fmc.fileExists(atPath: clinicRaw.appendingPathComponent(
                        "clinic-report-sam-\(Clinic.roundStamp)-2.md").path))
        check("and the first report is left exactly as it was, word for word",
              !firstReport.isEmpty && firstAfter == firstReport)
        check("a third goes on counting up rather than replacing either",
              Clinic.freeReport(in: clinicRaw, named: "clinic-report-sam-\(Clinic.roundStamp).md").lastPathComponent
                  == "clinic-report-sam-\(Clinic.roundStamp)-3.md")
        check("and every one of them still begins clinic-report-, which is the name the owner is told to look for",
              [firstName, secondName].allSatisfy { ($0 ?? "").hasPrefix("clinic-report-") })

        // --- it reads and changes nothing else ---
        let afterRun = fingerprint(realWiki)
        let added = Set(afterRun.keys).subtracting(beforeRun.keys)
        check("the check-up wrote nothing in the wiki but its own two reports",
              added == Set(["raw/clinic-report-sam-\(Clinic.roundStamp).md",
                            "raw/clinic-report-sam-\(Clinic.roundStamp)-2.md"]))
        check("and changed not one byte of anything that was already there, wiki/ included",
              beforeRun.allSatisfy { afterRun[$0.key] == $0.value })

        // --- the redaction, which is the check-up's own and not a second one ---
        let redacted = firstReport
        check("nothing in the report says where the home folder is",
              !redacted.contains(home.path) && !redacted.contains("/Users/"))
        check("nor where the wiki is, nor what its folder is called",
              !redacted.contains(realWiki.path) && !redacted.contains("zqxwiki-kept"))
        // Every line of the card, word for word, blank ones apart (Swift finds no
        // empty string inside a string, so asking for one asks for the impossible).
        check("the card in the report is the check-up's own lines, which the check-up redacted",
              (firstCard?.lines ?? []).filter { !$0.isEmpty }.allSatisfy { redacted.contains($0) }
                  && (firstCard?.lines.count ?? 0) > 5)
        check("and the owner's name is there, which is the one name the clinic note allows",
              redacted.contains("vault_owner: Sam"))

        // --- the report follows the clinic note's Section 5 ---
        let frontmatter = ["date:", "type: Moblee clinic report", "round: \(Clinic.round)", "vault_owner:",
                           "executed_by:", "pack_version_found:", "app_version_found:",
                           "assistant_on_record:", "note_status:", "do_not_ingest: true"]
        var inOrder = true
        var at = redacted.startIndex
        for key in frontmatter {
            guard let found = redacted.range(of: key, range: at..<redacted.endIndex) else { inOrder = false; break }
            at = found.upperBound
        }
        check("the report carries the clinic note's frontmatter, every key of it, in the note's own order", inOrder)
        let headings = ["## 1. Summary", "## 2. The owner's answers", "## 3. Versions and the assistant",
                        "## 4. The check-up", "## 5. Loose ends", "## 6. Counts, and where the wiki lives",
                        "## 7. Where the note was wrong about this wiki"]
        var sectionsInOrder = true
        at = redacted.startIndex
        for head in headings {
            guard let found = redacted.range(of: head, range: at..<redacted.endIndex) else { sectionsInOrder = false; break }
            at = found.upperBound
        }
        check("and its seven sections, in the note's own order", sectionsInOrder)
        check("the marker that keeps a later ingest from swallowing the report is on it",
              redacted.contains("do_not_ingest: true"))
        // The owner's two answers are the thing the app cannot supply, and a
        // report that left the heading bare or made an answer up would be worse
        // than one that says plainly that nobody was asked.
        check("the round is PARTIAL, and says what is missing, rather than claiming to be done",
              redacted.contains("note_status: PARTIAL (") && !redacted.contains("note_status: EXECUTED"))
        check("and the owner's answers say in plain words that nobody was asked, with nothing invented in their place",
              redacted.contains("which asks nobody"))
        check("the loose ends and the counts are numbers and dates, taken from this wiki",
              redacted.contains("Waiting in `raw/`: 1") && redacted.contains("The last entry in the log is dated 2026-09-22")
                  && redacted.contains("`_context.md` was last refreshed 2026-09-20")
                  && redacted.contains("Pages in the wiki: 4"))
        check("a clinic note still waiting in raw/ is reported by Moblee's own name for it, with its status",
              redacted.contains("`clinic-checkup-2026-09-24.md`: status NOT"))
        check("and the report says where the wiki lives as a kind of place, never as a path",
              redacted.contains("The wiki lives in the home folder, outside Desktop and Documents"))

        // --- where the wiki lives, as a kind of place ---
        check("the kind of place is read from the folder as the owner's Mac names it",
              Clinic.kindOfPlace(vault: home.appendingPathComponent("Desktop/W"), home: home) == "the Desktop folder"
                  && Clinic.kindOfPlace(vault: home.appendingPathComponent("Documents/W"), home: home)
                      == "the Documents folder"
                  && Clinic.kindOfPlace(vault: URL(fileURLWithPath: "/Users/x/Library/Mobile Documents/W"),
                                        home: home) == "iCloud Drive"
                  && Clinic.kindOfPlace(vault: URL(fileURLWithPath: "/Volumes/disk/W"), home: home)
                      == "somewhere else on this Mac")

        // --- the wiki's history, and the loose ends, measured on their own ---
        // A wiki of this check's own, so that the reports the two runs above wrote
        // are not themselves among the things being counted.
        let endsWiki = practiceWiki("wiki-ends", owner: "Sam", withIdentity: false)
        try? "waiting\n".write(to: endsWiki.appendingPathComponent("raw/one.md"), atomically: true, encoding: .utf8)
        try? "waiting\n".write(to: endsWiki.appendingPathComponent("Clippings/two.md"), atomically: true, encoding: .utf8)
        try? "---\nstatus: EXECUTED 2026-09-24\n---\n"
            .write(to: endsWiki.appendingPathComponent("raw/clinic-checkup-2026-09-24.md"),
                   atomically: true, encoding: .utf8)
        let ends = Clinic.looseEnds(vault: endsWiki, home: home, toolsInstalled: false)
        check("with Apple's tools missing the wiki's history is not read at all, and the report says why rather than saying nought",
              ends.uncommitted == nil && ends.saves == nil
                  && (ends.historyWhy ?? "").contains("Apple's tools"))
        check("the other loose ends are still measured without them, as counts and dates and nothing else",
              ends.wikiPages == 3 && ends.waitingInRaw == 1 && ends.waitingInClippings == 1
                  && ends.lastLogEntry == "2026-09-22" && ends.contextRefreshed == "2026-09-20"
                  // (v0.9.6) The WHOLE status, not its first word. On a PARTIAL
                  // the reason is the only part worth reading, and taking the
                  // first word left the bare word "PARTIAL", which says nothing.
                  && ends.clinicFiles.count == 1
                  && ends.clinicFiles.first?.status == "EXECUTED 2026-09-24")
        // (v0.9.6) A report of Moblee's own is not a clinic note and is not
        // listed as one. The companion is told never to move a report out of
        // `raw/`, so without this every round would list the rounds before it as
        // notes with no status line, and the one signal the line exists to give
        // — was the note stamped? — would be buried in Moblee's own output by
        // round four. A PARTIAL keeps its reason here too.
        try? "---\nstatus: PARTIAL (commit refused: the gate said the file is too long)\n---\n"
            .write(to: endsWiki.appendingPathComponent("raw/clinic-checkup-2026-10-01.md"),
                   atomically: true, encoding: .utf8)
        try? "---\ndate: 2026-09-24\n---\n"
            .write(to: endsWiki.appendingPathComponent("raw/clinic-report-sam-checkup-2026-09-24.md"),
                   atomically: true, encoding: .utf8)
        let endsAgain = Clinic.looseEnds(vault: endsWiki, home: home, toolsInstalled: false)
        check("a report Moblee wrote itself is never listed as a clinic note waiting to be stamped",
              endsAgain.clinicFiles.count == 2
                  && !endsAgain.clinicFiles.contains { $0.name.hasPrefix("clinic-report-") })
        check("and a PARTIAL keeps the reason it is partial, which is the only part worth reading",
              endsAgain.clinicFiles.contains {
                  $0.status == "PARTIAL (commit refused: the gate said the file is too long)"
              })
        check("and a file every Moblee wiki should have, gone missing, is named",
              ends.coreFilesMissing == ["wiki/Identity.md"])
        check("a wiki with no history at all says so, rather than reporting nought changes waiting to be saved",
              Clinic.looseEnds(vault: endsWiki, home: home,
                               toolsInstalled: Checkup.developerToolsInstalled()).uncommitted == nil)

        // --- every refusal, against a real stand-in check-up ---
        check("with no wiki on the Mac there is nothing to check, and nothing is written",
              runClinic(vault: nil, pack: flow.bundledPack) == .noWiki)
        let bareWiki = practiceWiki("wiki-no-checkup", owner: "Sam")
        let noDoctor = runClinic(vault: bareWiki, pack: standInPack("pack-empty", python: nil))
        var noDoctorSaved: String?
        if case .couldNotCheck(let why, let savedAs) = noDoctor {
            check("a Moblee with no check-up inside it says so, and gives no verdict on the wiki", why == .noCheckup)
            noDoctorSaved = savedAs
        } else {
            check("a Moblee with no check-up inside it says so", false)
        }
        // The clinic note asks for a report even then, so that whoever looks after
        // Moblee learns the check-up is broken on this Mac.
        let noDoctorReport = noDoctorSaved.flatMap {
            try? String(contentsOf: bareWiki.appendingPathComponent("raw/\($0)"), encoding: .utf8)
        } ?? ""
        check("and a report is still written, in the clinic note's own words, with no verdict in it",
              noDoctorReport.contains("health not checked: no check-up on this Mac")
                  && noDoctorReport.contains("No verdict is given"))
        let failing = runClinic(vault: practiceWiki("wiki-failing", owner: "Sam"),
                                pack: standInPack("pack-failing", python: "import sys\nsys.exit(3)\n"))
        check("a check-up that stops with an error is reported as that, and nothing else",
              failing == .couldNotCheck(.didNotFinish(code: 3),
                                        savedAs: "clinic-report-sam-\(Clinic.roundStamp).md"))
        let guarded = runClinic(
            vault: practiceWiki("wiki-guarded", owner: "Sam"),
            pack: standInPack("pack-guarded", python:
                "import sys\nsys.stderr.write('Blocked by the vault safety gate (bash-guard.py): rm\\n')\n"
                + "sys.exit(2)\n"))
        check("a check-up the delete guard refuses is REFUSED BY GUARD and is never tried another way",
              guarded == .couldNotCheck(.refusedByGuard,
                                        savedAs: "clinic-report-sam-\(Clinic.roundStamp).md"))
        let guardedReport = (try? String(contentsOf: clinicYard.appendingPathComponent(
            "wiki-guarded/raw/clinic-report-sam-\(Clinic.roundStamp).md"), encoding: .utf8)) ?? ""
        check("and the report says REFUSED BY GUARD, as the clinic note asks",
              guardedReport.contains("REFUSED BY GUARD"))
        // The time limit, against a check-up that never ends. One second here;
        // an owner always gets Clinic.timeLimit.
        let started = Date()
        let slow = runClinic(vault: practiceWiki("wiki-slow", owner: "Sam"),
                             pack: standInPack("pack-slow", python: "import time\ntime.sleep(300)\n"),
                             limit: 1, waiting: 60)
        let tookSeconds = Date().timeIntervalSince(started)
        check("a check-up that never ends is stopped at its time limit, and the owner is told",
              slow == .couldNotCheck(.tookTooLong, savedAs: "clinic-report-sam-\(Clinic.roundStamp).md")
                  && tookSeconds < 30)
        check("and the limit an owner gets is ninety seconds, about ten times the longest run seen",
              Clinic.timeLimit == 90)

        // --- what the screen says, for every way it can end ---
        let healthyCard = Clinic.Card(lines: ["Moblee health card, 26 September 2026"],
                                      state: "healthy",
                                      headline: "This wiki looks healthy. Nothing was found to be wrong.")
        var poorlyCard = healthyCard
        poorlyCard.state = "unwell"
        poorlyCard.headline = "This wiki needs attention: 3 things to look at."
        poorlyCard.wrong = [.init(code: "F13", line: "The wiki is in the Desktop folder, which iCloud copies."),
                            .init(code: "F05", line: "A scheduled job is not running."),
                            .init(code: "F18", line: "Something is still waiting in the app."),
                            .init(code: "F41", line: "A page holds something that looks like a password.")]
        poorlyCard.wrongTotal = 4
        poorlyCard.unchecked = [.init(code: "F36", line: "Whether the guard is trusted cannot be seen from here.")]
        poorlyCard.uncheckedTotal = 1
        poorlyCard.actions = ["Open the Moblee app: it offers Repair, or the update, when it can help."]
        let says: [Clinic.State] = [
            .running,
            .finished(.init(card: healthyCard, savedAs: "clinic-report-sam-checkup-2026-09-24.md")),
            .finished(.init(card: poorlyCard, savedAs: "clinic-report-sam-checkup-2026-09-24.md")),
            .finished(.init(card: healthyCard, savedAs: nil)),
            .noWiki,
            .couldNotCheck(.noCheckup, savedAs: "x.md"),
            .couldNotCheck(.didNotFinish(code: 3), savedAs: "x.md"),
            .couldNotCheck(.refusedByGuard, savedAs: "x.md"),
            .couldNotCheck(.tookTooLong, savedAs: "x.md"),
        ]
        let sentences = says.map { Clinic.sentence(for: $0) }
        check("every way the check-up can end has a sentence of its own, and no two of them say the same thing",
              Set(sentences).count == sentences.count)
        check("not one of them is a technical message",
              sentences.allSatisfy { said in
                  !["exit", "error", "python", "moblee-doctor", "JSON", "code ", "/", "--"]
                      .contains { said.lowercased().contains($0.lowercased()) }
              })
        check("a healthy wiki is told so, and told where the report is",
              Clinic.sentence(for: says[1])
                  == "Your wiki looks healthy. The report is saved in your wiki's raw folder.")
        check("a wiki with things wrong is told how many, in plain words, and told where the report is",
              Clinic.sentence(for: says[2]).contains("needs attention: 4 things to look at")
                  && Clinic.sentence(for: says[2]).contains("raw folder"))
        check("a report that could not be saved says so, and says to photograph the screen, which is what the card is for",
              Clinic.sentence(for: says[3]).contains("photograph this screen")
                  && Clinic.quietWords(for: says[3]) == nil)
        check("every refusal says that nothing has changed",
              says.suffix(4).allSatisfy { Clinic.sentence(for: $0).contains("Nothing has changed") })
        check("the owner cannot press on until there is something to tell them",
              !Clinic.canGoOn(.running) && !Clinic.canGoOn(.idle)
                  && says.dropFirst().allSatisfy { Clinic.canGoOn($0) })
        check("and a saved report has a way back to the file, while an unsaved one offers nothing",
              Clinic.quietWords(for: says[1]) == "Show me the file"
                  && Clinic.quietWords(for: .noWiki) == nil)
        check("the health card on the screen reads out everything it shows, and says what to do with the file",
              ClinicScreen.said(poorlyCard).contains(poorlyCard.headline)
                  && ClinicScreen.said(poorlyCard).contains("F13") == false
                  && ClinicScreen.said(poorlyCard).contains(poorlyCard.wrong[0].line)
                  && ClinicScreen.said(poorlyCard).contains("and 1 more")
                  && ClinicScreen.said(poorlyCard).hasSuffix(Clinic.sendIt))
        // (v0.9.6) It used to end "all of them in the report", and the report
        // does not hold all of them: the card the check-up hands over carries
        // five findings at most. The screen must not oversell the file the owner
        // is about to send, which is the one thing this whole feature asks them
        // to do. It now points at the full check-up, as the printed card does.
        check("a card longer than the screen says how many it is not showing, rather than stopping short in silence",
              ClinicScreen.andMore(shown: 3, of: 4) == "and 1 more. The full check-up lists every one."
                  && ClinicScreen.andMore(shown: 3, of: 3) == nil)
        check("and it never promises the report holds every finding, because the card it is built from does not",
              !(ClinicScreen.andMore(shown: 3, of: 9) ?? "").contains("all of them"))
        check("and the button that starts it all is on the home screen's own keyboard round",
              HomeScreen.busiest().contains("check-wiki"))

        // --- the button while Moblee is already busy with the wiki ---
        //
        // A check-up of a wiki that is being written to at that moment describes
        // neither the wiki before nor the wiki after, so it is refused. The point
        // of these is that the owner can SEE it is refused. A repair takes the
        // whole corner off the home screen, so that one looks after itself; a
        // drop does not, and the home screen is what the owner is looking at for
        // the whole of a big file's copy, because the receipt only arrives once
        // the copy has finished.
        let busyFlow = Flow()
        busyFlow.mode = .home
        check("with nothing going on, the check-up can be started", busyFlow.canBeginClinic)
        AppDelegate.dropsInFlight += 1
        check("while a dropped file is still being copied in, the button says it cannot be pressed",
              !busyFlow.canBeginClinic)
        busyFlow.beginClinic()
        check("and it cannot be started round the button either, by the keyboard or any other road",
              busyFlow.mode == .home)
        AppDelegate.dropsInFlight -= 1
        check("and the moment the copy has landed it can be started again", busyFlow.canBeginClinic)
        busyFlow.beginClinic()
        check("which really does open the check-up", busyFlow.mode == .clinic)
        // The count is on `Dropped.shared`, which a screen can watch. Held as a
        // plain number on the app delegate, the button would have gone on
        // looking pressable for the whole of the copy.
        check("the count of drops still copying is something a screen can watch, or the greying never happens",
              Dropped.shared.inFlight == 0 && { AppDelegate.dropsInFlight += 1
                                                let seen = Dropped.shared.inFlight == 1
                                                AppDelegate.dropsInFlight -= 1
                                                return seen }())

        // --- the card is read from the check-up and never assembled here ---
        check("the card a program is given is read as the check-up prints it",
              Clinic.Card.read("""
              {"lines": ["one", "two"], "state": "unwell", "headline": "h",
               "wrong": [{"level": "PROBLEM", "guide": "F01", "line": "l"}], "wrong_total": 2,
               "unchecked": [], "unchecked_total": 0, "actions": ["do this"]}
              """)?.wrongTotal == 2)
        check("a line of something else on the way past does not make the findings unreadable",
              Clinic.Card.read("a warning from somewhere\n{\"lines\": [\"one\"], \"state\": \"healthy\"}")?.state
                  == "healthy")
        check("and rubbish is no card at all, rather than an empty one",
              Clinic.Card.read("nothing like it") == nil && Clinic.Card.read("{\"state\": \"healthy\"}") == nil)
        // (v0.9.6) The one change to the pack's check-up that this feature would
        // like: every finding, redacted, in `--card --json`. With the pack as it
        // stands there is none, and the report says in plain words what it cannot
        // give; the moment the pack offers one, the same report carries the whole
        // of the check-up's output instead. Both halves are read back here, so
        // neither can be broken by the other being added.
        var wholeFacts = Clinic.Facts(owner: "Sam", wikiVersion: "0.9.6", packVersion: "0.9.6",
                                      appVersion: "0.9.6", assistantOnRecord: "claude",
                                      place: "the home folder, outside Desktop and Documents",
                                      ends: ends, today: Date())
        let withoutFindings = Clinic.report(card: healthyCard, trouble: nil, facts: wholeFacts)
        check("with the pack as it is, the report says plainly that the lines found to be right are not in it",
              withoutFindings.contains("The lines that were found to be right are not on the card"))
        var wholeCard = healthyCard
        wholeCard.findings = [.init(level: "OK", code: "", line: "The delete guard is installed."),
                              .init(level: "LOOK", code: "F13", line: "The wiki is in the Desktop folder.")]
        wholeFacts.owner = "Sam"
        let withFindings = Clinic.report(card: wholeCard, trouble: nil, facts: wholeFacts)
        check("and where the check-up hands over every finding, the report carries every one of them, with its field-guide code",
              withFindings.contains("- **OK** The delete guard is installed.")
                  && withFindings.contains("- **LOOK** The wiki is in the Desktop folder. (field guide F13)")
                  && !withFindings.contains("The lines that were found to be right are not on the card"))
        check("a level and a field-guide code are read off each finding the check-up hands over",
              Clinic.Card.read("""
              {"lines": ["one"], "state": "unwell",
               "findings": [{"level": "PROBLEM", "guide": "F02", "line": "l"}]}
              """)?.findings == [.init(level: "PROBLEM", code: "F02", line: "l")])

        // --- the example wiki an owner reads inside the app (v0.9.6) ----------
        //
        // A new owner is asked to build a wiki without ever having seen one.
        // Nine written pages ship inside the app and this is the whole of what
        // can be proved about reading them without a window: the markdown subset
        // against the pages it was written for, the marker and the frontmatter
        // hidden, every one of the links resolving, a link that does not, the
        // list of pages, where the way out goes, and that not a single byte of
        // the example is touched by reading the whole of it.
        //
        // Nothing here writes anything anywhere. That is the point of the last
        // check: the example lives inside the app bundle, which a signed app may
        // never write into, and it is the one place in Moblee where mistaking a
        // worked example for a starter template would really happen.
        if let pages = flow.examplePages {
            let fm = FileManager.default
            /// Every file under the example, with its size, its date and its
            /// words, so that the whole of the reading below can be shown to
            /// have changed not one of them.
            func fingerprint() -> [String: String] {
                var out: [String: String] = [:]
                guard let walk = fm.enumerator(at: pages.root,
                                               includingPropertiesForKeys: [.contentModificationDateKey],
                                               options: []) else { return out }
                for case let file as URL in walk {
                    let bytes = (try? Data(contentsOf: file))?.count ?? -1
                    let when = (try? file.resourceValues(forKeys: [.contentModificationDateKey]))?
                        .contentModificationDate?.timeIntervalSince1970 ?? -1
                    let words = (try? String(contentsOf: file, encoding: .utf8))?.hashValue ?? 0
                    out[file.path] = "\(bytes)/\(when)/\(words)"
                }
                return out
            }
            let before = fingerprint()

            check("the example wiki is inside the app, and the page it opens on is in it",
                  pages.byName[ExampleReader.firstPage] != nil && pages.byName.count >= 9)
            // The example opens on Welcome and NOT on Index, which is in the map
            // and was deliberately not chosen: a catalogue is the least useful
            // thing to hand somebody who has never seen a wiki.
            let reader = ExampleReader(pages: pages)
            check("the example opens on Welcome, not on Index, though Index is one of its pages",
                  reader.showing == .page(ExampleReader.firstPage)
                      && reader.showing != .page("Index") && pages.byName["Index"] != nil)
            check("and there is nowhere to go back to until the reader has followed something",
                  !reader.canGoBack)

            // --- the marker and the frontmatter, both hidden ---
            // Every one of the nine pages opens with an HTML comment saying the
            // example is invented and is never installed. Hiding it is
            // deliberate: an owner is meant to see the example LOOK like a wiki
            // and be told once by the frame round it, not nine times by the
            // content. The frame's own line is checked below.
            let everyBlock = pages.inOrder.flatMap { Markdown.blocks(pages.text(of: $0)) }
            check("the marker on every page is an HTML comment, and not one word of it is drawn",
                  !everyBlock.contains { $0.words.contains("MOBLEE EXAMPLE") }
                      && pages.inOrder.allSatisfy { pages.text(of: $0).contains("MOBLEE EXAMPLE") })
            // (v0.9.6) WHERE the marker is, and not only that it is somewhere.
            // `example-wiki/README.md` promises it is the first line, so that
            // anybody opening a file meets it at once; checking only that the
            // word appears would pass on a marker buried at the bottom of a
            // page, and did. Identity.md is the one exception and is named
            // rather than waved through: a real Identity.md has YAML
            // frontmatter, and frontmatter has to come first or it is not
            // frontmatter, so the marker follows it.
            check("and it is the first line of every page, or the first line after the frontmatter",
                  pages.inOrder.allSatisfy { name in
                      let text = pages.text(of: name)
                      if text.hasPrefix("<!-- MOBLEE EXAMPLE") { return true }
                      guard text.hasPrefix("---\n"),
                            let end = text.range(of: "\n---\n", range: text.index(text.startIndex,
                                                                                  offsetBy: 3)..<text.endIndex)
                      else { return false }
                      return text[end.upperBound...]
                          .drop(while: { $0 == "\n" })
                          .hasPrefix("<!-- MOBLEE EXAMPLE")
                  })
            check("and YAML frontmatter is hidden too, so the page begins at its own heading",
                  pages.text(of: "Identity").hasPrefix("---")
                      && !everyBlock.contains { $0.words.contains("excluded-from-default-skill-reads") }
                      && Markdown.blocks(pages.text(of: "Identity")).first == .heading(level: 1, spans: [Markdown.Span(words: "Identity")]))
            // Frontmatter is only frontmatter at the very top. `log.md` has a
            // horizontal rule written the same three hyphens in the middle of it,
            // and read as an opening it would have hidden the rest of the page.
            let rules = everyBlock.filter { $0 == .rule }.count
            check("three hyphens in the middle of a page is a rule and not the start of frontmatter",
                  rules == 1 && Markdown.blocks(pages.text(of: "log")).contains(.rule)
                      && Markdown.blocks(pages.text(of: "log")).contains { $0.words.contains("initialised") })
            check("every page begins with its own first-level heading, and no page uses a third level",
                  pages.inOrder.allSatisfy { name in
                      if case .heading(let level, _)? = Markdown.blocks(pages.text(of: name)).first {
                          return level == 1
                      }
                      return false
                  // (v0.9.6) EVERY page, not just the log. This half used to
                  // look at `log.md` alone, so a `###` added to any of the other
                  // eight would have passed — and `Markdown.headingParts` caps
                  // the level at two (`min(hashes, 2)`), so it would have been
                  // drawn silently as a level-two heading and nothing would ever
                  // have shown it. `ExampleWiki.swift`'s own note says "no `###`
                  // anywhere", about all nine pages; this now checks what that
                  // says.
                  } && pages.inOrder.allSatisfy { !pages.text(of: $0).contains("\n### ") })

            // --- the subset, against the pages it was written for ---
            // Every mark the example contains is consumed: what is drawn carries
            // no leftover markup at all. A code span is the one exception and is
            // shown exactly as written, which is what keeps `[[Page Name]]` in
            // the rules file a piece of words.
            let drawnWords = everyBlock.flatMap { $0.spans }.filter { !$0.code }.map(\.words)
            check("every mark the example uses is read, so not one piece of markup is left in the words an owner sees",
                  !drawnWords.contains { words in
                      ["[[", "]]", "**", "~~", "`", "<!--", "-->"].contains { words.contains($0) }
                  })
            let allSpans = everyBlock.flatMap { $0.spans }
            check("and each of the five kinds of piece really appears in the example, so none of the subset is dead and none is missing",
                  allSpans.contains { $0.bold } && allSpans.contains { $0.italic }
                      && allSpans.contains { $0.struck } && allSpans.contains { $0.code }
                      && allSpans.contains { $0.link != nil })
            // Underscore emphasis is ordinary markdown and is deliberately NOT
            // read: the example's working-state page is called `_context`.
            check("underscores are not read as emphasis, because the example has a page called _context",
                  Markdown.spans("[[_context]] and `wiki/_context.md`").allSatisfy { !$0.italic && !$0.bold }
                      && pages.resolve("_context") == "_context")

            // --- inline code is read before a wikilink ---
            // Read the other way round the example has 64 links across 7 targets
            // and one of them — a made-up page name inside an instruction about
            // how to cite pages — can never resolve.
            let tricky = "A `[[Page Name]]` in code, **bold with [[Bread]] in it**, "
                + "*italic*, ~~struck~~ and [[Reading|books]] and [[Bread#The starter]]."
            let trickySpans = Markdown.spans(tricky)
            check("inline code is read before a wikilink, so a page name inside backticks is words and never a link",
                  trickySpans.contains { $0.code && $0.words == "[[Page Name]]" && $0.link == nil })
            check("a wikilink inside bold is a link and bold at once, and a struck-through piece is struck through",
                  trickySpans.contains { $0.link == "Bread" && $0.bold }
                      && trickySpans.contains { $0.struck && $0.words == "struck" }
                      && trickySpans.contains { $0.italic && $0.words == "italic" })
            // The example's own struck-through closed item has bold AND a link
            // inside it, which is why a span carries its styles as flags rather
            // than as a tree of one style each.
            check("the example's own struck-through closed item keeps the link inside it, which one style at a time would have lost",
                  Markdown.blocks(pages.text(of: "_context")).flatMap { $0.spans }
                      .filter { $0.struck && $0.link != nil }.map { Markdown.pageName(ofLink: $0.link!) } == ["Bicycle"])

            // --- how a link is resolved ---
            check("a link with an alias goes to the page and shows the alias",
                  pages.resolve("Bread|the Saturday loaf") == "Bread"
                      && Markdown.shown(ofLink: "Bread|the Saturday loaf") == "the Saturday loaf")
            check("a link to a heading inside a page goes to the page, and shows the page's name",
                  pages.resolve("Bread#The starter") == "Bread"
                      && Markdown.shown(ofLink: "Bread#The starter") == "Bread")
            check("a page named in the wrong case is found all the same, as Obsidian finds it",
                  pages.resolve("bread") == "Bread" && pages.resolve("BREAD") == "Bread")
            check("and a link to nothing at all resolves to nothing rather than to some page or other",
                  pages.resolve("Porridge") == nil && pages.resolve("") == nil
                      && pages.resolve("#Heading") == nil)

            // --- EVERY link in the shipped example, walked ---
            // The check the example's own honesty rests on as it is edited: each
            // `[[link]]` on each page, resolved against the map the reader builds
            // when it opens, and really followed.
            let walker = ExampleReader(pages: pages)
            var everyLinkResolves = true
            var howMany = 0
            var linkedTo = Set<String>()
            for name in pages.inOrder {
                for link in Markdown.links(in: pages.text(of: name)) {
                    howMany += 1
                    guard let to = pages.resolve(link) else { everyLinkResolves = false; continue }
                    linkedTo.insert(to)
                    walker.follow(link)
                    if walker.showing != .page(to) { everyLinkResolves = false }
                }
                walker.openPages()
                walker.back()
            }
            print("logic: the example: \(pages.byName.count) pages, \(howMany) links, "
                  + "\(linkedTo.count) pages linked to, \(rules) rule(s)")
            check("every wikilink in the shipped example resolves, and following it really arrives at that page",
                  everyLinkResolves && howMany > 0)
            // The one pair of double brackets in the whole example that is not a
            // link is the one inside backticks, and it is not counted as one.
            let bracketPairs = pages.inOrder.reduce(0) {
                $0 + pages.text(of: $1).components(separatedBy: "[[").count - 1
            }
            check("exactly one pair of double brackets in the example is not a link, and it is the one inside backticks",
                  bracketPairs == howMany + 1)

            // --- a link that leads nowhere ---
            let lost = ExampleReader(pages: pages)
            lost.follow("Porridge")
            check("a link that leads nowhere leaves the reader on the page it was on, with one quiet line and nothing technical",
                  lost.showing == .page(ExampleReader.firstPage) && lost.missing == "Porridge"
                      && !lost.canGoBack
                      && ExampleReader.notInTheExample == "That page is not in the example.")
            lost.openPages()
            check("and the line goes the moment the owner does anything else",
                  lost.missing == nil && lost.showing == .pages)

            // --- back, and the list of pages ---
            let trail = ExampleReader(pages: pages)
            trail.follow("Bread")
            trail.follow("Reading")
            check("back goes back through the pages that were read, one at a time",
                  trail.showing == .page("Reading") && trail.canGoBack)
            trail.back()
            check("  to the page before", trail.showing == .page("Bread"))
            trail.back()
            check("  and back to the page the example opened on",
                  trail.showing == .page(ExampleReader.firstPage) && !trail.canGoBack)
            check("the list of pages is built from the very map the links resolve against, with the way in first",
                  pages.inOrder.first == ExampleReader.firstPage
                      && Set(pages.inOrder) == Set(pages.byName.keys)
                      && pages.inOrder.count == pages.byName.count)
            check("and a page opened from that list can be left the same way",
                  { let r = ExampleReader(pages: pages); r.openPages(); r.follow("Index")
                    let arrived = r.showing == .page("Index"); r.back()
                    return arrived && r.showing == .pages }())

            // --- the row of link buttons, which is how the keyboard follows one ---
            // An inline link inside wrapping text takes no keyboard focus on
            // macOS, so the links on a page are also drawn as buttons under it.
            // Both come from the same place, so neither can offer a link the
            // other does not.
            check("the buttons under a page are that page's own links, once each, in the order they are written",
                  reader.linksOn("Bread") == ["Reading", "_context", "Index"]
                      && reader.linksOn("Bicycle") == ["Index", "_context"])
            let onAPage = ExampleScreen.stops(linksOnThePage: reader.linksOn("Bread"),
                                              canGoBack: true, showingAPage: true, missing: true)
            check("every control on a page of the example has a name of its own: each link, the way back, the list, and both quiet lines",
                  Set(onAPage).count == onAPage.count
                      && reader.linksOn("Bread").allSatisfy { onAPage.contains(ExampleScreen.linkId($0)) }
                      && onAPage.contains("back") && onAPage.contains("quiet")
                      && onAPage.contains("listen-quiet")
                      && onAPage.contains("listen-example-missing")
                      && onAPage.contains("listen-example-chrome")
                      && onAPage.contains("read-aloud"))
            // Every block of words on the screen has a listen control beside it,
            // as every block of words in the app has had since v0.9.5: the page
            // itself, the row of link buttons, the quiet words, the line about a
            // missing page, and the line of chrome.
            check("  and the row of link buttons is read as a line, with its own control beside it",
                  ExampleScreen.linksSaid(reader.linksOn("Bread"))
                      == "Pages this one links to: Reading, _context, Index."
                      && onAPage.last(where: { $0.hasPrefix("example-link-") })
                          .flatMap { onAPage.firstIndex(of: $0) }
                          .map { onAPage[$0 + 1] } == ExampleScreen.linksListenId)
            check("and the keyboard crosses a page of the example in far fewer presses than the home screen",
                  onAPage.count < HomeScreen.busiest().count)

            // --- the words are read aloud, like every other block of words ---
            check("a page is read aloud in its own words, with its marker and its markup gone",
                  reader.spoken(of: "Bread").hasPrefix("Bread")
                      && reader.spoken(of: "Bread").contains("cast-iron pot")
                      && !reader.spoken(of: "Bread").contains("MOBLEE EXAMPLE")
                      && !reader.spoken(of: "Bread").contains("[[")
                      && !reader.spoken(of: "Bread").contains("**")
                      && !Speech(reader.spoken(of: "Bread")).isEmpty)
            check("  and the page's own title is what the screen puts at the top of it",
                  reader.title(of: "Bread") == "Bread" && reader.title(of: "_context") == "Working state and tempo"
                      && reader.body(of: "Bread").first != reader.blocks(of: "Bread").first)

            // --- the one line of chrome, and nothing that offers a template ---
            check("one quiet line says whose wiki this is, and says it is invented",
                  ExampleReader.chrome == "Example wiki. Sam is invented."
                      && ExampleReader.chrome.contains("invented"))
            check("and not one word anywhere on the example offers to use it, copy it, or start a wiki from it",
                  ExampleReader.everyWord.allSatisfy { words in
                      !ExampleReader.mustNeverSay.contains { words.lowercased().contains($0) }
                  } && !ExampleScreen.linksHere.lowercased().contains("copy"))
            // And the list that check rests on really catches something, rather
            // than being a list of phrases nobody would write anyway.
            check("  and that list really would catch it",
                  ExampleReader.mustNeverSay.contains { "Use this as my wiki".lowercased().contains($0) }
                      && ExampleReader.mustNeverSay.contains { "Copy it into your wiki".lowercased().contains($0) })
            // Nothing on the example may open anything outside the app: a link is
            // drawn as Moblee's own scheme and the number of the link on the page,
            // and every other address is refused here rather than handed on.
            check("a link inside the words carries Moblee's own scheme, and no other address is ever acted on",
                  ExampleScreen.url(forLinkNumber: 3)?.scheme == ExampleScreen.scheme
                      && ExampleScreen.url(forLinkNumber: 3).flatMap(ExampleScreen.linkNumber) == 3
                      && ExampleScreen.linkNumber(in: URL(string: "https://example.com/")!) == nil
                      && ExampleScreen.linkNumber(in: URL(string: "file:///etc/passwd")!) == nil)

            // --- the two ways in, and the way out of each ---
            check("the way into the example says the same four words in both places it appears",
                  ExampleReader.wayIn == "See an example wiki")
            let ring = HomeScreen.busiest()
            let wayIn = ring.firstIndex(of: "second-button") ?? -1
            let lastTile = ring.lastIndex { $0.hasPrefix("listen-tile-") } ?? -1
            let quietWords = ring.firstIndex(of: "quiet") ?? -1
            check("on the home screen it is a second big button, which the keyboard reaches after the cards and before the quiet lines",
                  wayIn > lastTile && lastTile >= 0 && wayIn < quietWords)
            let fromInstall = Flow()
            fromInstall.mode = .install
            fromInstall.step = .welcome
            fromInstall.openExample()
            check("an owner with no wiki can open the example from the install",
                  fromInstall.example?.showing == .page(ExampleReader.firstPage))
            fromInstall.closeExample()
            check("and closing it puts them back at the install, on the screen they left",
                  fromInstall.example == nil && fromInstall.mode == .install && fromInstall.step == .welcome)
            let fromHome = Flow()
            fromHome.mode = .home
            fromHome.openExample()
            fromHome.closeExample()
            check("an owner who already has a wiki is put back on the home screen",
                  fromHome.example == nil && fromHome.mode == .home)

            // --- and not one byte of it was touched ---
            // Every page above was read, every link followed, the list of pages
            // opened nine times. The example lives inside the app bundle, and a
            // signed app may never write into its own bundle.
            let after = fingerprint()
            check("reading the whole example, and following every link in it, changed not one file in it",
                  !before.isEmpty && after == before)
            check("  and there is no copy of the example anywhere in the practice home",
                  !fm.fileExists(atPath: home.appendingPathComponent("example-wiki").path)
                      && !fm.fileExists(atPath: home.appendingPathComponent("Sam Wiki").path))
        } else {
            check("the example wiki is inside the app", false)
        }

        print(failed == 0 ? "logic: every check held" : "logic: \(failed) check(s) FAILED")
        exit(failed == 0 ? 0 : 1)
    }
}
