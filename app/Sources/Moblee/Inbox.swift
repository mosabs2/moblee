import SwiftUI
import AppKit
import UniformTypeIdentifiers

/// (v0.9.5) Dropping something on Moblee puts it in the wiki's inbox.
///
/// Getting a thing into the wiki used to mean knowing where the wiki folder is
/// in Finder and knowing which folder inside it to put the thing in. Owners do
/// not do that. It is also how a note meant for the wiki goes missing: an owner
/// sends a file as a message attachment, their assistant cannot reach it,
/// and it never arrives. Dropping the saved file on Moblee is a route an owner
/// can manage on their own, and it lands in the one place the pack already tells
/// them about: `raw/`, the inbox their assistant reads when they ask it to (see
/// `vault-template/raw/HOW-TO-ADD-CONTENT.md`).
///
/// THE PROMISE, and it is the product's central one. This COPIES. It never
/// moves the original and it never deletes anything of the owner's — not on the
/// way through and not on any of the ways it can fail. The only thing it ever
/// removes is one of its own half-made hidden copies, which is the same
/// discipline `Placement` keeps when the app moves itself, and which is why the
/// copy is made under a hidden name and given its real name only once it is
/// whole: a half-copied file left sitting in the inbox under the name the owner
/// dropped would both be read as the whole thing by the assistant and take the
/// name the next try wanted.
///
/// It NEVER OVERWRITES. A name already taken in `raw/` gets a number after it,
/// the way `Flow.freeLocation` numbers a wiki folder whose name is taken, and
/// the file already there is not touched, read or moved.
///
/// (v0.9.5) That promise is kept by the FILESYSTEM and not by a look followed by
/// a move. It used to be `guard !somethingAt(to)` and then `FileManager.moveItem`,
/// which is two separate questions with a gap between them, and `moveItem`'s own
/// guard is the same shape — it looks, and then it calls `rename(2)`, which
/// replaces whatever is at the name without a word. Two things arriving at one
/// name in that gap both passed both guards and one of them was destroyed, six
/// times out of six against a driver that raced them. Anything writing into
/// `raw/` in that moment could be the victim: a second drop, an iCloud or
/// Dropbox sync of the wiki folder, the assistant part-way through an ingest.
/// So the last step is now `renamex_np(..., RENAME_EXCL)`, which is one
/// operation the kernel either does or refuses: there is no moment between the
/// asking and the doing for anything to appear in. A refusal means the name was
/// taken after all, and the next free name is asked for and tried again.
///
/// Nothing here goes to the network, and there is nothing in this file that
/// could: it is `FileManager` and `Data` and no more.
enum Inbox {
    /// The biggest single file Moblee will take. Said in the megabytes Finder
    /// shows (which are 1000-based, not 1024-based), because the number in the
    /// sentence the owner reads has to be the number they saw in Finder.
    ///
    /// Why there is a limit at all: the wiki is a git repository of pages, and
    /// the assistant reads what lands here. A two-gigabyte film dropped on
    /// Moblee would make every later commit slow for ever and could never be
    /// read by anything. 100 MB takes every PDF, screenshot, scan and voice
    /// memo an owner has ever sent, and stops the one thing that does real harm.
    static let biggestMegabytes = 100
    static let biggestBytes = biggestMegabytes * 1_000_000

    /// The name Moblee's own half-made copies wear while they are being made.
    /// Hidden, so an owner looking in the inbox never sees one.
    static let incomingPrefix = ".moblee-incoming-"

    /// How old one of Moblee's own half-made copies has to be before a later
    /// drop sweeps it away.
    ///
    /// (v0.9.5) There used to be no age at all: every drop deleted every
    /// `.moblee-incoming-*` in the inbox as its first act, including the one a
    /// drop running at that very moment was part-way through writing. The
    /// victim's last step then failed and its file was refused with "Moblee
    /// could not put that in your wiki… Tell Claude" — the worst sentence in
    /// the app, said about a file that was perfectly readable and a wiki that
    /// was perfectly well. Two drops a moment apart is not a strange thing to
    /// do: it is what dropping on the Dock icon twice looks like. A leftover
    /// worth sweeping is one from a run that was cut off — the app was force
    /// quit, or the Mac lost power — and that one is minutes or days old, never
    /// seconds. Ten minutes is far longer than the largest file Moblee takes
    /// can possibly need, and far shorter than an owner would ever notice.
    static let leftoverAge: TimeInterval = 600

    /// Why one dropped thing, or a whole drop, could not be taken. Every one of
    /// these is said out loud: a drop that quietly did nothing is the one
    /// outcome this feature may not have.
    enum Refusal: Equatable {
        /// There is no wiki on this Mac yet, so there is no inbox to put it in.
        case noWikiYet
        /// A wiki is being made, updated or repaired right now.
        case busy
        /// A folder rather than a file.
        case isAFolder
        case tooBig
        case cannotRead
        /// Something was dropped, but it carried neither a file nor any words.
        case nothingToTake
        /// (v0.9.5) The name it was dropped under cannot be a file name at all:
        /// it was nothing but full stops, or nothing but spaces. Its own
        /// refusal, because nothing failed and there is nothing for an
        /// assistant to look at — the owner renames it and drops it again. It
        /// used to be told as `.couldNotCopy`, which sent an owner to bother
        /// their assistant about a copy that had never been attempted.
        case nameUnusable
        case couldNotCopy

        /// How this reads in the install diary. No name and no path: see
        /// `Inbox.diaryLines`.
        var diaryWord: String {
            switch self {
            case .noWikiYet: return "there is no wiki on this Mac yet"
            case .busy: return "a wiki was being made, updated or repaired"
            case .isAFolder: return "it is a folder, and Moblee takes files"
            case .tooBig: return "it is bigger than \(Inbox.biggestMegabytes) MB"
            case .cannotRead: return "Moblee could not read it"
            case .nothingToTake: return "there was nothing in it to take"
            case .nameUnusable: return "its name could not be a file name"
            case .couldNotCopy: return "it could not be copied into the wiki"
            }
        }
    }

    /// One thing that was dropped and not taken, with the name the owner will
    /// recognise it by. The name is for the screen in front of them and goes
    /// nowhere else.
    struct TurnedAway: Equatable {
        let name: String
        let why: Refusal
    }

    /// What became of one drop, however many things were in it.
    struct Landing: Equatable {
        /// The names the things now have in `raw/`, in the order they were
        /// dropped. A name here may differ from the name dropped, because a
        /// name already taken gets a number.
        var landed: [String] = []
        var turnedAway: [TurnedAway] = []
        /// The whole drop was refused before anything at all was looked at:
        /// there is no wiki, or Moblee is busy, or nothing was dropped.
        var wholeDrop: Refusal?

        var anythingLanded: Bool { !landed.isEmpty }
        /// The first reason anything was refused, which is the one the sentence
        /// is built from when nothing landed at all.
        var firstRefusal: Refusal? { wholeDrop ?? turnedAway.first?.why }
    }

    // MARK: where it goes

    /// The wiki's inbox. One place names it.
    static func rawFolder(in vault: URL) -> URL {
        vault.appendingPathComponent("raw", isDirectory: true)
    }

    /// Whether there is ANYTHING at this name, a broken link included. Asked
    /// with `lstat` rather than `FileManager.fileExists`, which follows a link
    /// and would call a broken one nothing at all — and a name that looked free
    /// but was not is exactly how something already there gets overwritten.
    static func somethingAt(_ url: URL) -> Bool {
        var about = stat()
        return lstat(url.path, &about) == 0
    }

    /// A dropped file's own name, made safe to be one component of a path.
    ///
    /// A file name cannot hold a `/` on a Mac, so this cannot be how a drop
    /// escapes the inbox — but the name may come from a pasteboard rather than
    /// from Finder, so it is treated as untrusted anyway, exactly as the request
    /// list is (`HomeModel.plain`). The two characters that mean something to a
    /// path go; a leading full stop goes, because a file hidden in the inbox is
    /// a file the owner cannot see and the assistant will not list; and a name
    /// longer than a Mac allows is cut short with its ending kept, since the
    /// ending is what says what kind of file it is. Nil when nothing usable is
    /// left, which is not a name at all.
    static func safeName(_ name: String) -> String? {
        var kept = name.replacingOccurrences(of: "/", with: "-")
            .replacingOccurrences(of: ":", with: "-")
            .trimmingCharacters(in: .whitespacesAndNewlines)
        // Every leading full stop goes, and any space hiding behind one, until
        // the name really begins.
        while let first = kept.first, first == "." || first.isWhitespace { kept.removeFirst() }
        // A name that was nothing but full stops or nothing but spaces is not a
        // name at all, and there is nothing left of it to cut short. There is
        // no test for "." and ".." here: the loop above has already emptied
        // both of them, and a test that can never be true is a test nobody can
        // trust. (v0.9.5)
        guard !kept.isEmpty else { return nil }
        let cut = cutToFit(kept)
        return cut.isEmpty ? nil : cut
    }

    /// The longest a file's name may be, in BYTES of UTF-8 and not in letters.
    ///
    /// (v0.9.5) It was 180 letters, and the filesystem does not count letters.
    /// APFS and HFS+ both stop at 255 bytes, and one letter is up to four of
    /// them: 180 emoji are 180 letters and 708 bytes, so they passed this and
    /// then failed inside `copyItem`, and the owner was shown "Moblee could not
    /// put that in your wiki… Tell Claude" over a file that was perfectly
    /// readable and a wiki that was perfectly well. Rare and safe, and the
    /// wrong thing to say. 240 rather than 255 leaves room for the number
    /// `freeName` may put on the end of a name that is already taken.
    static let longestBytes = 240

    /// A name cut short to fit, with its ending kept, since the ending is what
    /// says what kind of file it is. Never cut through the middle of a letter:
    /// half of an emoji is not a character and would not be a name.
    static func cutToFit(_ name: String) -> String {
        guard name.utf8.count > longestBytes else { return name }
        let ending = (name as NSString).pathExtension
        let start = (name as NSString).deletingPathExtension
        let tail = ending.isEmpty ? "" : "." + ending
        // An ending so long that nothing of the name would be left is not an
        // ending worth keeping, so the whole name is simply cut instead.
        if !tail.isEmpty, tail.utf8.count < longestBytes {
            let cut = firstBytes(of: start, longestBytes - tail.utf8.count)
            if !cut.isEmpty { return cut + tail }
        }
        return firstBytes(of: name, longestBytes)
    }

    /// As much of the front of a piece of words as fits in so many bytes,
    /// counted letter by letter so that no letter is ever cut in half.
    private static func firstBytes(of words: String, _ bytes: Int) -> String {
        var kept = ""
        var used = 0
        for letter in words {
            let size = String(letter).utf8.count
            if used + size > bytes { break }
            kept.append(letter)
            used += size
        }
        return kept
    }

    /// A name in `raw/` that nothing is using. The name dropped, if it is free;
    /// otherwise the same name with a number after it, the way
    /// `Flow.freeLocation` numbers a wiki folder whose name is taken. The file
    /// already there is never touched, and never even read.
    static func freeName(_ wanted: String, in folder: URL) -> URL {
        let start = (wanted as NSString).deletingPathExtension
        let ending = (wanted as NSString).pathExtension
        func named(_ n: Int) -> String {
            guard n > 1 else { return wanted }
            return ending.isEmpty ? "\(start) \(n)" : "\(start) \(n).\(ending)"
        }
        var n = 1
        while n <= 500 {
            let url = folder.appendingPathComponent(named(n))
            if !somethingAt(url) { return url }
            n += 1
        }
        // Five hundred of the same name is not an owner's inbox, but a run of
        // numbers must not turn into a name that is taken after all.
        let tail = String(UUID().uuidString.prefix(8))
        let name = ending.isEmpty ? "\(start) \(tail)" : "\(start) \(tail).\(ending)"
        return folder.appendingPathComponent(name)
    }

    // MARK: files

    /// Copies each dropped file into the wiki's inbox, and says what became of
    /// each. Safe to call off the main thread, and meant to be: a large file on
    /// a slow disk must not stop the window drawing.
    ///
    /// Safe to call from two threads at once as well, and that is not an
    /// accident: a drop on the Dock icon and a drop on the window can be a
    /// moment apart, and the wiki folder may be synced by iCloud or Dropbox
    /// while this runs. Nothing here decides a name and then acts on the
    /// decision; see `copy`. (v0.9.5)
    static func take(files: [URL], pictures: [Picture] = [], into vault: URL,
                     now: Date = Date()) -> Landing {
        var landing = Landing()
        guard !files.isEmpty || !pictures.isEmpty else {
            landing.wholeDrop = .nothingToTake; return landing
        }
        let fm = FileManager.default
        let raw = rawFolder(in: vault)
        // A wiki always has one; a wiki whose owner tidied it away gets it back
        // rather than a refusal it could do nothing about.
        try? fm.createDirectory(at: raw, withIntermediateDirectories: true)
        guard fm.fileExists(atPath: raw.path) else {
            landing.wholeDrop = .couldNotCopy
            return landing
        }
        clearOurOwnLeftovers(in: raw)
        for dropped in files {
            // A link is followed before anything is judged, so that a link to a
            // folder is refused as the folder it points at rather than copied
            // in as a link pointing out of the wiki.
            let from = dropped.resolvingSymlinksInPath()
            let shown = dropped.lastPathComponent
            var isFolder: ObjCBool = false
            guard fm.fileExists(atPath: from.path, isDirectory: &isFolder) else {
                landing.turnedAway.append(TurnedAway(name: shown, why: .cannotRead)); continue
            }
            // A folder is refused, and a package (a .app, a Photos library) is
            // a folder. See `Inbox.Refusal.isAFolder` in `sentence` for why
            // this is a refusal and not a copy of the contents.
            if isFolder.boolValue {
                landing.turnedAway.append(TurnedAway(name: shown, why: .isAFolder)); continue
            }
            guard fm.isReadableFile(atPath: from.path) else {
                landing.turnedAway.append(TurnedAway(name: shown, why: .cannotRead)); continue
            }
            let size = (try? fm.attributesOfItem(atPath: from.path)[.size] as? Int) ?? nil
            guard let bytes = size else {
                landing.turnedAway.append(TurnedAway(name: shown, why: .cannotRead)); continue
            }
            if bytes > biggestBytes {
                landing.turnedAway.append(TurnedAway(name: shown, why: .tooBig)); continue
            }
            // Nothing failed here and there is nothing for an assistant to
            // look at: the name simply cannot be a file name. Its own refusal.
            guard let wanted = safeName(shown) else {
                landing.turnedAway.append(TurnedAway(name: shown, why: .nameUnusable)); continue
            }
            if let landed = copy(from, wanting: wanted, in: raw) {
                landing.landed.append(landed)
            } else {
                landing.turnedAway.append(TurnedAway(name: shown, why: .couldNotCopy))
            }
        }
        for picture in pictures {
            if let landed = write(picture.bytes, wanting: pictureName(picture, now: now), in: raw) {
                landing.landed.append(landed)
            } else {
                landing.turnedAway.append(TurnedAway(name: pictureName(picture, now: now),
                                                     why: .couldNotCopy))
            }
        }
        return landing
    }

    /// The hidden name one half-made copy wears while it is being made.
    ///
    /// (v0.9.5) A WHOLE UUID, not the first eight letters of one. Eight is two
    /// chances in a hundred thousand of two drops picking the same name, and
    /// the two things that then happen are both bad: `copyItem` fails over a
    /// name that is taken, and the failure path deletes what is at that name,
    /// which is the other drop's file. A whole UUID cannot collide in any
    /// number of drops an owner will ever make, which is what lets the failure
    /// paths below delete this name without asking whose it is: it is this
    /// attempt's own, and nothing else's, always.
    static func incomingName() -> String { incomingPrefix + UUID().uuidString }

    /// One file copied in, whole or not at all, under a free name in the inbox.
    /// Gives back the name it really landed under, or nothing if it did not.
    ///
    /// The copy is made under a hidden name of Moblee's own and given its real
    /// name only when it is there in full. That is the order `Placement.move`
    /// keeps for the same reason: until the last step, a failure leaves
    /// everything as it was. The original is only ever READ — `copyItem`, never
    /// `moveItem` — and the only thing ever removed is Moblee's own half-made
    /// hidden copy, which is nothing of the owner's and no use to anyone.
    static func copy(_ from: URL, wanting wanted: String, in raw: URL) -> String? {
        let fm = FileManager.default
        let incoming = raw.appendingPathComponent(incomingName())
        do {
            try fm.copyItem(at: from, to: incoming)
        } catch {
            try? fm.removeItem(at: incoming)        // our own, half-made, a moment old
            return nil
        }
        return name(incoming, wanting: wanted, in: raw)
    }

    /// The same for bytes Moblee itself has in hand rather than a file on the
    /// owner's disk — a picture dragged out of a web page, which has no file
    /// anywhere to copy from. Written whole under the hidden name first, for
    /// the same reason. (v0.9.5)
    static func write(_ bytes: Data, wanting wanted: String, in raw: URL) -> String? {
        let fm = FileManager.default
        let incoming = raw.appendingPathComponent(incomingName())
        do {
            try bytes.write(to: incoming, options: [.withoutOverwriting])
        } catch {
            try? fm.removeItem(at: incoming)
            return nil
        }
        return name(incoming, wanting: wanted, in: raw)
    }

    /// The last step, and the whole of the promise that nothing is overwritten.
    ///
    /// `renamex_np` with `RENAME_EXCL` is one operation: the kernel gives the
    /// hidden copy its real name, or it refuses because something is already
    /// wearing that name, and there is no moment in between for anything to
    /// appear in. That is what the old pair of steps — ask whether the name is
    /// free, then `moveItem` — could not promise, because `moveItem`'s own
    /// guard is the same pair again and ends in `rename(2)`, which replaces
    /// without a word. A refusal is not a failure: it means the name was taken
    /// while the copy was being made, so the next free name is asked for and
    /// the same one operation tried again. (v0.9.5)
    private static func name(_ incoming: URL, wanting wanted: String, in raw: URL) -> String? {
        let fm = FileManager.default
        // Far more tries than `freeName` has numbers, so the only way out of
        // this loop is a name that worked or a refusal that was not about the
        // name being taken.
        for _ in 0..<600 {
            let to = freeName(wanted, in: raw)
            // Never anywhere but the inbox, whatever the name turned out to be.
            guard to.deletingLastPathComponent().standardizedFileURL.path
                    == raw.standardizedFileURL.path else { break }
            if renamex_np(incoming.path, to.path, UInt32(RENAME_EXCL)) == 0 {
                return to.lastPathComponent
            }
            var why = errno
            // Not every disk knows `renamex_np`; a wiki kept on a shared folder
            // over the network may say so rather than doing it. `link` is the
            // same promise in another shape — it is one operation and it
            // refuses a name that is taken — so the promise holds there too
            // rather than falling back to something that overwrites.
            if why == ENOTSUP || why == EINVAL {
                if link(incoming.path, to.path) == 0 {
                    unlink(incoming.path)
                    return to.lastPathComponent
                }
                why = errno
            }
            if why != EEXIST { break }
        }
        try? fm.removeItem(at: incoming)
        return nil
    }

    /// Half-made copies from a try that was cut off (the app was force quit, or
    /// the Mac lost power part-way through a drop). They are Moblee's own,
    /// hidden, and of no use to anybody; nothing of the owner's is ever touched
    /// here, because nothing of the owner's could ever carry this name.
    ///
    /// (v0.9.5) Only ones that have been there a while. A drop running at this
    /// moment has one of these open and is writing into it, and sweeping that
    /// away made the other drop fail and told its owner "Moblee could not put
    /// that in your wiki… Tell Claude" about a file that was perfectly fine.
    /// See `leftoverAge`.
    private static func clearOurOwnLeftovers(in raw: URL, now: Date = Date()) {
        let fm = FileManager.default
        for name in (try? fm.contentsOfDirectory(atPath: raw.path)) ?? [] where name.hasPrefix(incomingPrefix) {
            let one = raw.appendingPathComponent(name)
            let made = (try? fm.attributesOfItem(atPath: one.path)[.modificationDate] as? Date) ?? nil
            // A leftover whose age cannot be read is left alone: the one thing
            // this may never do is delete something that is still being written.
            guard let made, now.timeIntervalSince(made) > leftoverAge else { continue }
            try? fm.removeItem(at: one)
        }
    }

    // MARK: dropped words

    private static let dayStamp: DateFormatter = {
        let f = DateFormatter()
        f.dateFormat = "yyyy-MM-dd"
        f.locale = Locale(identifier: "en_GB_POSIX")
        return f
    }()

    private static let minuteStamp: DateFormatter = {
        let f = DateFormatter()
        f.dateFormat = "yyyy-MM-dd HH:mm"
        f.locale = Locale(identifier: "en_GB_POSIX")
        return f
    }()

    /// A dated name, so that a second note dropped the same day is plainly the
    /// same day's and the numbering does the rest.
    static func noteName(now: Date) -> String { "Dropped note \(dayStamp.string(from: now)).md" }

    /// The file dropped words become. It says where it came from, in the first
    /// thing anybody reads, because the assistant that later reads the inbox has
    /// to be able to tell a note the owner dropped from a page somebody wrote:
    /// a dropped note is the owner's own raw words and has had no checking at
    /// all. `raw/HOW-TO-ADD-CONTENT.md` already promises that everything in this
    /// folder is source material and not the wiki; this says which source.
    static func noteBody(_ text: String, now: Date) -> String {
        let title = (noteName(now: now) as NSString).deletingPathExtension
        return """
        # \(title)

        Source: words dropped on the Moblee app on \(minuteStamp.string(from: now)). The owner
        dropped these on Moblee's window; nobody wrote them into the wiki.

        ---

        \(text)
        """
    }

    /// Words dropped rather than a file: they become one plain markdown file in
    /// the inbox. Safe to call off the main thread.
    static func take(text: String, into vault: URL, now: Date) -> Landing {
        var landing = Landing()
        let words = text.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !words.isEmpty else { landing.wholeDrop = .nothingToTake; return landing }
        let fm = FileManager.default
        let raw = rawFolder(in: vault)
        try? fm.createDirectory(at: raw, withIntermediateDirectories: true)
        guard let data = noteBody(words, now: now).data(using: .utf8) else {
            landing.wholeDrop = .couldNotCopy
            return landing
        }
        // The same last step a dropped file gets, for the same reason: a note
        // written straight to a chosen name would fail outright if a second
        // note took that name in the meantime. (v0.9.5)
        if let landed = write(data, wanting: noteName(now: now), in: raw) {
            landing.landed.append(landed)
        } else {
            landing.wholeDrop = .couldNotCopy
        }
        return landing
    }

    // MARK: a dropped picture

    /// (v0.9.5) A picture dragged out of somewhere that has no file to give.
    ///
    /// An image dragged out of a web page, or out of a Preview or Photos
    /// window, puts the picture's own bytes on the pasteboard and no file URL
    /// at all: there is no file anywhere on the Mac to copy. Moblee had told
    /// owners in three places that they could "drag a file, a photo or a piece
    /// of text", and asked macOS for files and words only, so such a drag was
    /// not offered to Moblee at all — it bounced back, and nothing was said.
    /// A refusal in silence is the one outcome this feature may not have, and
    /// the sentence the owner had been given was simply untrue. So the bytes
    /// are taken and written into the inbox as a picture file of their own.
    struct Picture: Equatable {
        let bytes: Data
        /// What kind of picture it is — "png", "jpeg", "tiff" — which is what
        /// the file's ending has to say so that anything opening it later
        /// knows what it is holding.
        let ending: String
    }

    /// A dated name, exactly as a dropped note gets one, so that a second
    /// picture dropped the same day is plainly the same day's and `freeName`'s
    /// numbering does the rest.
    static func pictureName(_ picture: Picture, now: Date) -> String {
        let ending = picture.ending.isEmpty ? "png" : picture.ending
        return "Dropped picture \(dayStamp.string(from: now)).\(ending)"
    }

    // MARK: what the owner is told

    /// The words the pack itself already uses for this: `raw/` is the inbox, and
    /// "Process the new files in raw/." is the sentence
    /// `vault-template/raw/HOW-TO-ADD-CONTENT.md` tells the owner to say. Moblee
    /// says the same thing in the same words, so that the screen and the wiki's
    /// own instructions cannot drift apart.
    static let nextStep = "process the new files in raw/"

    /// The receipt, or the refusal. One sentence, which is the instruction, in
    /// the shape every other screen's sentence has.
    static func sentence(for landing: Landing, talksTo: String) -> String {
        guard landing.anythingLanded else {
            return refusalSentence(landing.firstRefusal ?? .nothingToTake, talksTo: talksTo)
        }
        let where_ = "in your wiki, in the folder called raw"
        let what: String
        if landing.landed.count == 1 {
            // The name is one the owner will go and look for in Finder, so it is
            // left exactly as Finder will show it; see `OwnWords`.
            what = "“\(OwnWords.asFinderShowsIt(landing.landed[0]))” is \(where_)."
        } else {
            what = "\(landing.landed.count) things are \(where_)."
        }
        let missed: String
        switch landing.turnedAway.count {
        case 0: missed = ""
        case 1: missed = " One did not go."
        default: missed = " \(landing.turnedAway.count) did not go."
        }
        return what + missed + " Tell \(talksTo): \(nextStep)."
    }

    /// One sentence for each way a drop can be refused. Plain words, never a
    /// technical message, and each one says what the owner can do about it.
    static func refusalSentence(_ why: Refusal, talksTo: String) -> String {
        switch why {
        case .noWikiYet:
            return "Moblee has no wiki yet. Make your wiki first, then drop this on Moblee again."
        case .busy:
            return "Moblee is busy making, updating or repairing a wiki. Wait until it says it has finished, then drop this again."
        case .isAFolder:
            // Decided: a folder is refused, not copied. A folder can hold
            // thousands of files and other folders, and the owner cannot see
            // from the outside what would land; the receipt "4 things landed"
            // would be a lie over a folder holding four hundred. Opening it and
            // dragging what is inside is one extra action an owner can do and
            // can see the result of.
            return "Moblee takes files, not folders. Open the folder and drop the files inside it."
        case .tooBig:
            return "That is too big for your wiki. Moblee takes files up to \(biggestMegabytes) MB."
        case .cannotRead:
            return "Moblee could not read that. Nothing was changed. Save it to your desktop first, then drop it again."
        case .nothingToTake:
            return "There was nothing in that to put in your wiki. Drag the file itself, or a photo, or some words."
        case .nameUnusable:
            // Nothing failed and nothing is wrong, so this is the one refusal
            // that does not send the owner to their assistant: the name is the
            // only thing in the way, and renaming it is theirs to do.
            return "That name cannot be a file name. Nothing of yours was changed. Give it a name, then drop it again."
        case .couldNotCopy:
            return "Moblee could not put that in your wiki. Nothing of yours was changed or lost. Tell \(talksTo)."
        }
    }

    /// How each refused thing reads on the receipt, beside its name.
    ///
    /// (v0.9.5) Who the owner talks to is passed in rather than written here.
    /// Three of these used to say "Claude" whoever the wiki was for. They are
    /// not reachable from the receipt today — a drop refused for one of those
    /// three reasons is refused whole, and a whole refusal has no list of names
    /// under it — but a hard-coded assistant's name in a product that asks the
    /// owner which assistant they use is a trap for whoever makes one of them
    /// reachable next.
    static func turnedAwayWords(_ why: Refusal, talksTo: String) -> String {
        switch why {
        case .isAFolder: return "a folder, not a file"
        case .tooBig: return "bigger than \(biggestMegabytes) MB"
        case .cannotRead: return "Moblee could not read it"
        case .nameUnusable: return "its name cannot be a file name"
        case .couldNotCopy: return "it could not be copied"
        case .noWikiYet, .busy, .nothingToTake: return refusalSentence(why, talksTo: talksTo)
        }
    }

    // MARK: the install diary

    /// What the diary is told, in the shape the diary already writes (see
    /// `Diary`, and `HomeModel.repair` for the same header-then-lines pattern a
    /// repair uses).
    ///
    /// THE FILE NAMES ARE NOT HERE, AND THAT IS DELIBERATE. The diary is the one
    /// file an owner is told is safe to send when something is wrong, and
    /// `Diary.redact` can only hide what it knows the shape of: the wiki's
    /// place, the wiki's folder name and the home folder. A dropped file's name
    /// is the owner's own content and can be anything at all — a person's name,
    /// a diagnosis, a solicitor's reference. Redaction cannot touch it, because
    /// nothing in the app knows what is in it. So the diary is told how many
    /// things landed and what became of the rest, which is everything anybody
    /// helping an owner needs in order to see that a drop happened and how it
    /// ended, and nothing of what was dropped. The names are on the screen in
    /// front of the owner, where they belong, and nowhere else.
    static func diaryLines(for landing: Landing) -> [String] {
        var lines = ["--- Moblee drop ---"]
        if let whole = landing.wholeDrop {
            lines.append("drop: nothing was taken: " + whole.diaryWord)
            return lines
        }
        if landing.anythingLanded {
            lines.append("drop: \(landing.landed.count) thing(s) copied into the wiki's inbox "
                         + "(no names here: what was dropped is the owner's own)")
        }
        for turned in landing.turnedAway {
            lines.append("drop: one thing was not taken: " + turned.why.diaryWord)
        }
        return lines
    }

    // MARK: what a drop carries

    /// Reads a drop's contents out of what macOS hands over. Both routes come
    /// through here: the window's own drop and the Dock icon's.
    ///
    /// A file wins over a picture, and a picture wins over words. Dragging a
    /// file out of Finder puts the file on the pasteboard AND, often, its name
    /// as text beside it, so words are only ever taken when there is neither a
    /// file nor a picture. A picture dragged out of a web page carries its own
    /// bytes AND the page's address as text, and the picture is what the owner
    /// dragged — the address would land as a note saying nothing. (v0.9.5)
    static func read(_ providers: [NSItemProvider],
                     then: @escaping @MainActor ([URL], String?, [Picture]) -> Void) {
        let fileType = UTType.fileURL.identifier
        let textType = UTType.plainText.identifier
        let group = DispatchGroup()
        let lock = NSLock()
        // Kept by the place each provider had in the drop, so several files
        // dropped at once land in the order the owner dropped them however
        // quickly each provider answers.
        var files: [Int: URL] = [:]
        var words: [Int: String] = [:]
        var pictures: [Int: Picture] = [:]
        for (at, provider) in providers.enumerated() {
            if provider.hasItemConformingToTypeIdentifier(fileType) {
                group.enter()
                provider.loadItem(forTypeIdentifier: fileType) { item, _ in
                    if let url = Self.fileURL(from: item) {
                        lock.lock(); files[at] = url; lock.unlock()
                    }
                    group.leave()
                }
            } else if let kind = pictureType(of: provider) {
                group.enter()
                provider.loadItem(forTypeIdentifier: kind.identifier) { item, _ in
                    if let bytes = Self.bytes(from: item), !bytes.isEmpty {
                        let picture = Picture(bytes: bytes,
                                              ending: kind.preferredFilenameExtension ?? "png")
                        lock.lock(); pictures[at] = picture; lock.unlock()
                    }
                    group.leave()
                }
            } else if provider.hasItemConformingToTypeIdentifier(textType) {
                group.enter()
                provider.loadItem(forTypeIdentifier: textType) { item, _ in
                    if let text = Self.text(from: item) {
                        lock.lock(); words[at] = text; lock.unlock()
                    }
                    group.leave()
                }
            }
        }
        group.notify(queue: .main) {
            MainActor.assumeIsolated {
                let found = files.keys.sorted().compactMap { files[$0] }
                let drawn = pictures.keys.sorted().compactMap { pictures[$0] }
                let said = words.keys.sorted().compactMap { words[$0] }.joined(separator: "\n\n")
                then(found, said.isEmpty ? nil : said, drawn)
            }
        }
    }

    /// The kinds of picture Moblee will take out of a drop that carries no
    /// file, in the order it would rather have them: the ones every Mac and
    /// every web page already speaks, most useful first. A named list rather
    /// than "anything conforming to `public.image`", because the ending on the
    /// file has to say truthfully what is inside it and only a named kind can
    /// promise that. (v0.9.5)
    static let pictureTypes: [UTType] = [.png, .jpeg, .heic, .gif, .tiff]

    /// Which of those a drop is offering, if any.
    static func pictureType(of provider: NSItemProvider) -> UTType? {
        pictureTypes.first { provider.hasItemConformingToTypeIdentifier($0.identifier) }
    }

    /// A file URL as a provider gives it: the bytes of a URL (which is what
    /// `public.file-url` is), the URL itself, or its path written out.
    static func fileURL(from item: Any?) -> URL? {
        if let url = item as? URL { return url.isFileURL ? url : nil }
        if let data = item as? Data {
            if let url = URL(dataRepresentation: data, relativeTo: nil), url.isFileURL { return url }
            if let text = String(data: data, encoding: .utf8), let url = URL(string: text), url.isFileURL { return url }
        }
        if let text = item as? String, let url = URL(string: text), url.isFileURL { return url }
        return nil
    }

    static func text(from item: Any?) -> String? {
        if let text = item as? String { return text }
        if let text = item as? NSString { return text as String }
        if let data = item as? Data { return String(data: data, encoding: .utf8) }
        return nil
    }

    /// A picture's own bytes as a provider gives them: the bytes themselves, or
    /// a file the provider wrote out for us to read. (v0.9.5)
    static func bytes(from item: Any?) -> Data? {
        if let data = item as? Data { return data }
        if let data = item as? NSData { return data as Data }
        if let url = item as? URL, url.isFileURL { return try? Data(contentsOf: url) }
        return nil
    }
}

/// (v0.9.5) What has just been dropped, and the receipt waiting to be read.
///
/// One of these for the whole app, because a drop on the Dock icon arrives
/// wherever the owner happens to be — on the welcome screen, mid-install, at
/// home — and the receipt has to be shown from all of them. `RootView` puts it
/// in front of whatever screen is there, the way the offer to move to
/// Applications does.
@MainActor
final class Dropped: ObservableObject {
    static let shared = Dropped()

    /// The receipt or the refusal on the screen now; nil when there is none.
    @Published var showing: Inbox.Landing?

    /// (v0.9.6) How many drops are still copying. It lives here, where a screen
    /// can watch it, rather than as a plain count on the app delegate:
    /// `AppDelegate.dropsInFlight` reads and writes this one. A screen has to be
    /// able to watch it because "Check my wiki" greys itself while a drop is in
    /// flight, and the home screen is the screen the owner is looking at for the
    /// whole of a big file's copy — the receipt only arrives once it is done.
    @Published var inFlight = 0

    /// The run this belongs to, set by `Flow` as it is made, the way
    /// `AppDelegate.install` is. Weak, because the run owns the app and not the
    /// other way round.
    weak var flow: Flow? {
        didSet { if flow != nil { takeWhatWasWaiting() } }
    }

    /// A drop that arrived before there was a run to hand it to.
    ///
    /// The Dock route is how this happens: an owner drops a file on Moblee's
    /// icon while Moblee is not open at all, so macOS starts the app and calls
    /// `application(_:open:)`, and that can be before SwiftUI has made the
    /// window and its `Flow`. Doing nothing then would be the one outcome this
    /// feature may not have — a drop that silently vanishes — so it is kept
    /// here and taken the moment there is somewhere to take it to.
    private var waiting: [(files: [URL], text: String?, pictures: [Inbox.Picture])] = []

    private init() {}

    private func takeWhatWasWaiting() {
        let held = waiting
        waiting = []
        for one in held { arrived(files: one.files, text: one.text, pictures: one.pictures) }
    }

    /// Everything a drop brings, from either route, arrives here.
    ///
    /// `then` is for the checks: the copying happens off the main thread, so
    /// there has to be one moment that is plainly after it.
    func arrived(files: [URL], text: String?, pictures: [Inbox.Picture] = [],
                 now: Date = Date(),
                 then: (@MainActor (Inbox.Landing) -> Void)? = nil) {
        guard let flow else {
            // No run yet to say which home folder this is: kept, not dropped.
            waiting.append((files, text, pictures))
            then?(Inbox.Landing())
            return
        }
        let home = flow.home
        func refuse(_ why: Inbox.Refusal) {
            var landing = Inbox.Landing()
            landing.wholeDrop = why
            settle(landing, home: home, vault: nil)
            then?(landing)
        }
        // A wiki being made, updated or repaired is being written to by the
        // pack's own scripts this very moment, and the closing commit takes
        // whatever is in the folder. A file dropped into the middle of that
        // would be committed half-copied, or swept into a commit that is
        // supposed to hold two files and nothing else. So it waits, and the
        // owner is told to wait. It covers a move of the app as well, where the
        // app is about to be replaced under itself.
        //
        // (v0.9.5) It is `busyMakingOrMending` and NOT `busyWithWork`, which a
        // drop of its own now counts towards: two drops a moment apart are an
        // ordinary thing for an owner to do — it is what two files let go over
        // the Dock icon looks like — and neither has any business telling the
        // other to wait. Two drops at once are safe; see `Inbox.take`.
        if AppDelegate.busyMakingOrMending { refuse(.busy); return }
        guard let vault = HomeModel.existingVault(home: home) else { refuse(.noWikiYet); return }
        if files.isEmpty, pictures.isEmpty,
           (text ?? "").trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
            refuse(.nothingToTake); return
        }
        // (v0.9.5) From here until the copy has finished, this is work that
        // must not be cut off. A 90 MB scan takes a moment to copy, and an
        // update or a repair started in that moment runs the pack's scripts
        // over the wiki and commits it while the copy is still going: the file
        // would land in the middle of that commit, which is the very thing the
        // refusal above exists to prevent, only the other way round. A quit in
        // that moment is refused for the same reason, exactly as it is during
        // an install, a move and a repair. See `AppDelegate.busyWithWork`.
        AppDelegate.dropsInFlight += 1
        // The copying is file work and can be slow on a slow disk, so it is not
        // done on the thread that draws the window.
        DispatchQueue.global(qos: .userInitiated).async {
            let landing = files.isEmpty && pictures.isEmpty
                ? Inbox.take(text: text ?? "", into: vault, now: now)
                : Inbox.take(files: files, pictures: pictures, into: vault, now: now)
            DispatchQueue.main.async {
                MainActor.assumeIsolated {
                    AppDelegate.dropsInFlight -= 1
                    self.settle(landing, home: home, vault: vault)
                    then?(landing)
                }
            }
        }
    }

    /// The receipt on the screen, and the line in the diary.
    private func settle(_ landing: Inbox.Landing, home: URL, vault: URL?) {
        for line in Inbox.diaryLines(for: landing) {
            Diary.write(line, home: home, vault: vault)
        }
        withAnimation(.easeInOut(duration: 0.25)) { showing = landing }
        // A drop on the Dock icon can arrive while Moblee is behind whatever
        // the owner was using, and a receipt on a window nobody can see is a
        // receipt nobody reads. Never in a practice run, which must not take
        // the front from the person at this Mac.
        if !Practice.on, !NSApp.isActive { NSApp.activate(ignoringOtherApps: true) }
    }

    /// The owner has read it.
    func readIt() {
        withAnimation(.easeInOut(duration: 0.25)) { showing = nil }
    }

    /// Who the receipt tells the owner to talk to.
    var talksTo: String {
        guard let flow else { return Assistant.claude.talksTo }
        return Assistant.onRecord(home: flow.home).talksTo
    }
}
