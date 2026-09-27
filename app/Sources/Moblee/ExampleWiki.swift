import Foundation

/// (v0.9.6) THE MARKDOWN THE EXAMPLE WIKI IS WRITTEN IN, AND NOTHING ELSE.
///
/// Moblee had no markdown reader at all before this: nothing under
/// `app/Sources/Moblee/` had ever looked inside a wiki page. Writing a general
/// one would be the wrong thing to do, because a general one fails in a general
/// way — on syntax nobody looked at, in front of an owner who cannot tell a
/// reader's fault from a wiki's. So this reads EXACTLY what the nine pages of
/// the shipped example contain, and the check in `LogicCheck` asserts that every
/// piece of syntax in every one of those pages was consumed. A tenth page that
/// uses something new fails the check before anybody is asked to read it.
///
/// WHAT THE EXAMPLE ACTUALLY CONTAINS, counted over
/// `example-wiki/Sam Wiki/**.md` on 26 September 2026:
///
///  * 9 first-level headings (`#`), one per file, and 48 second-level ones
///    (`##`). No `###` anywhere, and no underlined (setext) headings.
///  * 31 `-` bullets. None nested, and no numbered list anywhere.
///  * 27 `**bold**` runs, 6 `*italic*` runs (the source and session lines), and
///    ONE `~~struck-through~~` run — the closed item on `_context.md`, which
///    the brief's list of syntax did not mention and which has a bold run AND a
///    wikilink inside it. That is why a span carries its styles as flags rather
///    than as a tree of one style each: a flat `strike(String)` would have
///    swallowed `[[Bicycle]]` and lost one of the 63 links.
///  * 27 `` `inline code` `` runs. One of them is `` `[[Page Name]]` `` in
///    `CLAUDE.md`, and it is the reason inline code is read FIRST, before
///    wikilinks: read the other way round there are 64 links across 7 targets
///    and one of them — a made-up name inside an instruction about how to cite
///    pages — can never resolve. Read this way there are 63 across 6, and every
///    one of them resolves.
///  * 3 lines of three hyphens. ONE is a horizontal rule (`log.md`, under the
///    opening paragraph); the other two are the opening and closing of the only
///    piece of YAML frontmatter in the example (`Identity.md`). So frontmatter
///    is taken off first, and only by the rule that it must begin on the very
///    first line — otherwise the rule in `log.md` would open a block of
///    frontmatter that swallowed the rest of the page.
///  * 9 HTML comments, one per file: the marker that says the example is
///    invented and is never installed. Hiding them is the point. An owner is
///    meant to see the example LOOK like a wiki and be told once, by the frame
///    round it, rather than nine times by the content.
///  * 64 pairs of double brackets, of which 63 are links (see the code span
///    above) across 6 targets: Bread 15, _context 12, Index 11, Bicycle 10,
///    Reading 8, log 7. Not one of them uses an alias, a heading, or a path.
///    Aliases and headings are handled all the same, because Obsidian resolves
///    them and a page edited later may use one.
///
/// WHAT IS DELIBERATELY NOT READ, because the example does not contain it:
/// numbered lists, nested lists, task lists, tables, block quotes, fenced code,
/// `[text](address)` links, images, embeds (`![[…]]`), footnotes, highlights
/// (`==…==`), tags, backslash escapes, and — this one matters — UNDERSCORE
/// emphasis. `_italic_` and `__bold__` are ordinary markdown and are not read
/// here on purpose: the example's own working-state page is called `_context`,
/// and reading underscores as emphasis would turn `[[_context]]` and
/// `` `wiki/_context.md` `` into something they are not. Anything on that list
/// is drawn as the plain words it is written as, which is the failure an owner
/// can see and shrug at, rather than a reader that comes apart.
enum Markdown {
    /// A piece of one line: the words, whatever is true of them, and the page
    /// they lead to if they are a link.
    ///
    /// The styles are flags on one flat piece rather than a tree, for the
    /// `~~**Rear tyre.** … [[Bicycle]] …~~` case above: the example really does
    /// nest bold and a link inside a struck-through bullet, and a tree of one
    /// style each would have had to decide which of them to lose.
    struct Span: Equatable {
        var words: String
        var bold = false
        var italic = false
        var struck = false
        /// Inline code. Nothing inside it is read as markdown at all, which is
        /// what keeps `` `[[Page Name]]` `` out of the links.
        var code = false
        /// What was written inside the double brackets, before the alias and the
        /// heading are taken off it: `Page`, `Page|alias`, `Page#Heading`.
        /// Nothing here resolves it; `ExamplePages` does that.
        var link: String?
    }

    enum Block: Equatable {
        case heading(level: Int, spans: [Span])
        case paragraph([Span])
        case bullet([Span])
        case rule

        var spans: [Span] {
            switch self {
            case .heading(_, let s), .paragraph(let s), .bullet(let s): return s
            case .rule: return []
            }
        }

        /// The words alone, which is what is read aloud and what a check
        /// compares against.
        var words: String { spans.map(\.words).joined() }
    }

    // --- what is taken off before a page is read at all ----------------------

    /// YAML frontmatter, and only where it really is frontmatter: three hyphens
    /// on the VERY FIRST line, closed by three more. Obsidian shows none of it
    /// and neither does this.
    ///
    /// The "very first line" part is not a nicety. `log.md` has a horizontal
    /// rule in the middle of it, written the same three hyphens, and a rule
    /// that looked like an opening would have hidden the whole of the rest of
    /// the page.
    static func withoutFrontmatter(_ text: String) -> String {
        let lines = text.components(separatedBy: "\n")
        guard lines.first?.trimmingCharacters(in: .whitespaces) == "---" else { return text }
        guard let close = lines.dropFirst().firstIndex(where: {
            $0.trimmingCharacters(in: .whitespaces) == "---"
        }) else { return text }        // an opening with no closing is not frontmatter
        return lines[(close + 1)...].joined(separator: "\n")
    }

    /// HTML comments, which is what the example's own "this is invented and is
    /// never installed" marker is written as. Every one of the nine pages opens
    /// with one, Obsidian's reading view shows none of them, and neither does
    /// this. An opening with no ending is left exactly as it was written rather
    /// than swallowing the rest of the page.
    static func withoutComments(_ text: String) -> String {
        var out = ""
        var rest = Substring(text)
        while let open = rest.range(of: "<!--") {
            out += rest[rest.startIndex..<open.lowerBound]
            guard let close = rest.range(of: "-->", range: open.upperBound..<rest.endIndex) else {
                return out + rest[open.lowerBound...]
            }
            rest = rest[close.upperBound...]
        }
        return out + rest
    }

    // --- the blocks ----------------------------------------------------------

    /// A whole page, as the blocks it is made of. Lines that follow one another
    /// are one paragraph, as markdown has always worked; a blank line, a
    /// heading, a bullet or a rule ends it.
    static func blocks(_ raw: String) -> [Block] {
        let text = withoutComments(withoutFrontmatter(raw))
        var out: [Block] = []
        var paragraph: [String] = []
        func endParagraph() {
            guard !paragraph.isEmpty else { return }
            out.append(.paragraph(spans(paragraph.joined(separator: " "))))
            paragraph = []
        }
        for line in text.components(separatedBy: "\n") {
            let trimmed = line.trimmingCharacters(in: .whitespaces)
            if trimmed.isEmpty { endParagraph(); continue }
            if isRule(trimmed) { endParagraph(); out.append(.rule); continue }
            if let (level, words) = headingParts(trimmed) {
                endParagraph()
                out.append(.heading(level: level, spans: spans(words)))
                continue
            }
            if let words = bulletWords(trimmed) {
                endParagraph()
                out.append(.bullet(spans(words)))
                continue
            }
            paragraph.append(trimmed)
        }
        endParagraph()
        return out
    }

    /// Three or more hyphens and nothing else. Only hyphens: `***` and `___`
    /// are also rules in markdown and the example uses neither, so they are
    /// left as the words they are written as.
    static func isRule(_ line: String) -> Bool {
        line.count >= 3 && line.allSatisfy { $0 == "-" }
    }

    /// Hashes then a space. The example has only one and two; three or more is
    /// read as a second-level heading rather than shown as raw hashes, so a
    /// page edited later cannot put `###` in front of an owner.
    static func headingParts(_ line: String) -> (level: Int, words: String)? {
        let hashes = line.prefix { $0 == "#" }.count
        guard hashes >= 1 else { return nil }
        let after = line.dropFirst(hashes)
        guard after.first == " " else { return nil }
        return (min(hashes, 2), String(after.dropFirst()).trimmingCharacters(in: .whitespaces))
    }

    static func bulletWords(_ line: String) -> String? {
        guard line.hasPrefix("- ") else { return nil }
        return String(line.dropFirst(2))
    }

    // --- one line's pieces ---------------------------------------------------

    static func spans(_ line: String) -> [Span] { spans(Substring(line), style: Span(words: "")) }

    /// The order the marks are looked for is the whole of what makes this safe,
    /// and it is: inline code, then a wikilink, then `**bold**`, then
    /// `~~struck~~`, then `*italic*`.
    ///
    ///  * CODE FIRST, so nothing inside a code span is read as markdown. That
    ///    is what keeps `` `[[Page Name]]` `` a piece of words rather than a
    ///    link to a page that does not exist.
    ///  * BOLD BEFORE ITALIC, because `**` begins with `*` and the other way
    ///    round every bold run would be read as an empty italic one.
    ///
    /// A mark with no partner on the line is not a mark: it is added to the
    /// words as the character it is. That is the failure an owner can see and
    /// shrug at, and it is why this cannot come apart on a page it has not met.
    private static func spans(_ line: Substring, style: Span) -> [Span] {
        var out: [Span] = []
        var plain = ""
        func flush() {
            guard !plain.isEmpty else { return }
            var piece = style
            piece.words = plain
            out.append(piece)
            plain = ""
        }
        var at = line.startIndex
        while at < line.endIndex {
            let rest = line[at...]
            if rest.first == "`", let close = rest.dropFirst().firstIndex(of: "`") {
                flush()
                var piece = style
                piece.code = true
                piece.words = String(rest[rest.index(after: rest.startIndex)..<close])
                out.append(piece)
                at = rest.index(after: close)
                continue
            }
            if rest.hasPrefix("[["),
               let close = rest.range(of: "]]", range: rest.index(rest.startIndex, offsetBy: 2)..<rest.endIndex) {
                flush()
                let inside = String(rest[rest.index(rest.startIndex, offsetBy: 2)..<close.lowerBound])
                var piece = style
                piece.link = inside
                piece.words = shown(ofLink: inside)
                out.append(piece)
                at = close.upperBound
                continue
            }
            if rest.hasPrefix("**"),
               let close = rest.range(of: "**", range: rest.index(rest.startIndex, offsetBy: 2)..<rest.endIndex) {
                flush()
                var inner = style
                inner.bold = true
                out += spans(rest[rest.index(rest.startIndex, offsetBy: 2)..<close.lowerBound], style: inner)
                at = close.upperBound
                continue
            }
            if rest.hasPrefix("~~"),
               let close = rest.range(of: "~~", range: rest.index(rest.startIndex, offsetBy: 2)..<rest.endIndex) {
                flush()
                var inner = style
                inner.struck = true
                out += spans(rest[rest.index(rest.startIndex, offsetBy: 2)..<close.lowerBound], style: inner)
                at = close.upperBound
                continue
            }
            if rest.first == "*", let close = rest.dropFirst().firstIndex(of: "*") {
                flush()
                var inner = style
                inner.italic = true
                out += spans(rest[rest.index(after: rest.startIndex)..<close], style: inner)
                at = rest.index(after: close)
                continue
            }
            plain.append(line[at])
            at = line.index(after: at)
        }
        flush()
        return out
    }

    /// The words a link shows. `[[Page|alias]]` shows the alias, which is what
    /// an alias is for. `[[Page#Heading]]` shows the page's name alone: the
    /// heading is used to find the page and then dropped, because this reader
    /// has no way to jump to a place inside a page and showing "Page#Heading"
    /// to somebody who does not read much would say nothing.
    static func shown(ofLink inside: String) -> String {
        if let bar = inside.firstIndex(of: "|") {
            let alias = inside[inside.index(after: bar)...].trimmingCharacters(in: .whitespaces)
            if !alias.isEmpty { return alias }
        }
        return pageName(ofLink: inside)
    }

    /// The page a link means: the alias and the heading taken off, exactly as
    /// Obsidian takes them off.
    static func pageName(ofLink inside: String) -> String {
        var name = Substring(inside)
        if let bar = name.firstIndex(of: "|") { name = name[name.startIndex..<bar] }
        if let hash = name.firstIndex(of: "#") { name = name[name.startIndex..<hash] }
        return name.trimmingCharacters(in: .whitespaces)
    }

    /// Every link on a page, in the order it is written, as it was written
    /// inside the brackets. Asked of the blocks and not of the raw text, so a
    /// link the reader would not draw is not one a check can count.
    static func links(in raw: String) -> [String] {
        blocks(raw).flatMap { $0.spans.compactMap(\.link) }
    }

    /// A whole page as plain words, for reading aloud and for a check to
    /// compare with. A rule says nothing, so it says nothing here.
    static func plain(_ blocks: [Block]) -> String {
        blocks.compactMap { block -> String? in
            let words = block.words
            return words.isEmpty ? nil : words
        }.joined(separator: "\n")
    }
}

/// (v0.9.6) The pages of the example wiki inside the app, and the map that
/// resolves a `[[link]]` the way Obsidian resolves one.
///
/// Obsidian resolves a link BY PAGE NAME and not by path: `[[Bread]]` finds
/// `wiki/Bread.md` from a page at the vault root without either of them saying
/// where the other is. So the map is built from the file names, once, when the
/// example is opened, and every link is looked up in it.
///
/// It is READ ONLY, in the strongest sense there is: nothing in this file, and
/// nothing in `ExampleScreen`, opens a file for writing, creates a folder, or
/// copies anything anywhere. The example lives inside the app bundle, which a
/// signed app must never write into, and it is the one place in Moblee where
/// mistaking a worked example for a starter template would actually happen — so
/// there is no code here that could. `vault-template/` is what an owner's wiki
/// is made from; this folder is never installed, never copied and never offered.
struct ExamplePages {
    /// The page the example opens on. `Welcome.md` and not `Index.md`: Index is
    /// a catalogue, which is the least useful thing to hand somebody who has
    /// never seen a wiki. Welcome says what they are looking at and where to
    /// start.
    ///
    /// It is held here, on the pages themselves, rather than on the reader: the
    /// map is built off the main actor and needs to know which page must be in
    /// it before there is a reader at all.
    static let firstPage = "Welcome"

    /// The folder the pages are in — `example-wiki/Sam Wiki` inside the pack.
    let root: URL
    /// Page name (a file name without its `.md`) to the file itself.
    let byName: [String: URL]

    /// The folder inside the pack that holds the example, found by looking for
    /// the page the reader opens on rather than by knowing the folder's name.
    /// The example belongs to an invented person and could be renamed; the page
    /// it opens on is part of what the example IS.
    static func found(inPack pack: URL?) -> ExamplePages? {
        guard let pack else { return nil }
        let fm = FileManager.default
        let examples = pack.appendingPathComponent("example-wiki", isDirectory: true)
        guard let inside = try? fm.contentsOfDirectory(at: examples,
                                                      includingPropertiesForKeys: [.isDirectoryKey],
                                                      options: [.skipsHiddenFiles]) else { return nil }
        for folder in inside.sorted(by: { $0.path < $1.path }) {
            let opensOn = folder.appendingPathComponent(Self.firstPage + ".md")
            guard fm.fileExists(atPath: opensOn.path) else { continue }
            var byName: [String: URL] = [:]
            guard let walk = fm.enumerator(at: folder,
                                           includingPropertiesForKeys: nil,
                                           options: [.skipsHiddenFiles]) else { continue }
            for case let file as URL in walk where file.pathExtension.lowercased() == "md" {
                // A name already taken is left with the first file found, so the
                // map can never depend on which order the folder was walked in.
                let name = file.deletingPathExtension().lastPathComponent
                if byName[name] == nil { byName[name] = file }
            }
            guard byName[Self.firstPage] != nil else { continue }
            return ExamplePages(root: folder, byName: byName)
        }
        return nil
    }

    /// Which page a link means, or nothing at all where the example has no such
    /// page. Exactly by name first; then ignoring case, which is Obsidian's own
    /// fallback and covers a page written `[[bread]]` in a hurry.
    func resolve(_ link: String) -> String? {
        let want = Markdown.pageName(ofLink: link)
        guard !want.isEmpty else { return nil }
        if byName[want] != nil { return want }
        // Sorted, so that two pages whose names differ only in case could never
        // make this answer depend on the order a dictionary happened to be in.
        return byName.keys.sorted().first { $0.caseInsensitiveCompare(want) == .orderedSame }
    }

    /// Every page, for the list a reader who has lost the thread can restart
    /// from. The page the example opens on comes first, because it is the way
    /// in; the rest are in the order the Mac itself would sort them, so adding
    /// a page needs no editing here.
    var inOrder: [String] {
        let rest = byName.keys.filter { $0 != Self.firstPage }
            .sorted { $0.localizedStandardCompare($1) == .orderedAscending }
        return (byName[Self.firstPage] != nil ? [Self.firstPage] : []) + rest
    }

    func text(of name: String) -> String {
        guard let file = byName[name],
              let text = try? String(contentsOf: file, encoding: .utf8) else { return "" }
        return text
    }
}

/// (v0.9.6) An owner reading the example: which page they are on, how they got
/// there, and the quiet word when a link leads nowhere.
///
/// It is made when the example is OPENED and thrown away when it is closed, so
/// the map is built once per read and nothing about the example outlives it.
@MainActor
final class ExampleReader: ObservableObject {
    enum Showing: Equatable {
        case page(String)
        /// Every page in the example, so a reader who has lost the thread can
        /// start again. Built from the same map the links resolve against.
        case pages
    }

    /// The page the example opens on; see `ExamplePages.firstPage`.
    static let firstPage = ExamplePages.firstPage

    /// The words on the way in, in both of the places it appears.
    static let wayIn = "See an example wiki"
    /// The one line of chrome that says whose wiki this is. Once, from the frame
    /// round the example, rather than nine times from the pages: the marker in
    /// the content is an HTML comment and the reader hides it, which is
    /// deliberate — an owner is meant to see the example look like a wiki.
    static let chrome = "Example wiki. Sam is invented."
    static let closeWords = "Close the example"
    static let pagesWords = "All the pages"
    static let pagesSentence = "Every page in this example."
    /// A link that leads nowhere. Quiet, and it never says anything technical:
    /// the reader stays exactly where it was and one line appears.
    static let notInTheExample = "That page is not in the example."

    let pages: ExamplePages
    @Published private(set) var showing: Showing
    /// The link that led nowhere, if the last one did. Cleared by anything else
    /// the owner does.
    @Published private(set) var missing: String?

    /// Where the owner has been, so Back goes back rather than guessing.
    private var trail: [Showing] = []
    /// Pages already read off the disk. A page is read once per opening of the
    /// example however many times it is looked at.
    private var read: [String: [Markdown.Block]] = [:]

    init(pages: ExamplePages) {
        self.pages = pages
        showing = .page(Self.firstPage)
    }

    var canGoBack: Bool { !trail.isEmpty }

    /// The owner pressed a link. A link that resolves is followed; one that does
    /// not leaves them on the page they were reading with the quiet line above
    /// it, which is the one thing this may never do instead — crash, or show an
    /// empty page, or say something about a file.
    func follow(_ link: String) {
        guard let name = pages.resolve(link) else { missing = link; return }
        missing = nil
        trail.append(showing)
        showing = .page(name)
    }

    func openPages() {
        missing = nil
        guard showing != .pages else { return }
        trail.append(showing)
        showing = .pages
    }

    func back() {
        missing = nil
        guard let was = trail.popLast() else { return }
        showing = was
    }

    func blocks(of name: String) -> [Markdown.Block] {
        if let already = read[name] { return already }
        let blocks = Markdown.blocks(pages.text(of: name))
        read[name] = blocks
        return blocks
    }

    /// The page's own first heading, which is the page's title and becomes the
    /// heading of the screen. Its name where it has none.
    func title(of name: String) -> String {
        if case .heading(let level, let spans)? = blocks(of: name).first, level == 1 {
            let words = spans.map(\.words).joined()
            if !words.isEmpty { return words }
        }
        return name
    }

    /// What is drawn under the heading: the page, less the heading itself, which
    /// the screen has already shown.
    func body(of name: String) -> [Markdown.Block] {
        let blocks = self.blocks(of: name)
        if case .heading(let level, _)? = blocks.first, level == 1 { return Array(blocks.dropFirst()) }
        return blocks
    }

    /// Every page this one links to, once each, in the order they are written.
    /// Both the words in the middle of a sentence and the row of buttons under
    /// the page come from this, so the two can never offer different links.
    func linksOn(_ name: String) -> [String] {
        var seen = Set<String>()
        var out: [String] = []
        for link in blocks(of: name).flatMap({ $0.spans.compactMap(\.link) }) {
            let page = Markdown.pageName(ofLink: link)
            if page.isEmpty || seen.contains(page.lowercased()) { continue }
            seen.insert(page.lowercased())
            out.append(page)
        }
        return out
    }

    /// The whole of the page in front of the owner, in words, for the listen
    /// control beside its heading. The very blocks that are drawn, so what is
    /// read and what is shown cannot drift apart.
    func spoken(of name: String) -> String { Markdown.plain(blocks(of: name)) }

    // --- the words the screen uses, kept here so a check can ask for them ----

    /// Nothing on the example may offer to use it. This is the one place in
    /// Moblee where mistaking a worked example for a starter template would
    /// really happen, so the words are held here and a check reads every one of
    /// them against the phrases that would do it.
    static var everyWord: [String] {
        [wayIn, chrome, closeWords, pagesWords, pagesSentence, notInTheExample]
    }

    /// What must never be said about the example, in any of its words. An owner
    /// who took it for a template would spend an evening writing into a folder
    /// inside the app bundle that no update keeps and no assistant reads.
    static let mustNeverSay = ["use this", "use it as", "make this mine", "my wiki",
                               "your wiki", "start from this", "start with this",
                               "copy", "template", "install"]
}
