import SwiftUI

/// (v0.9.6) THE EXAMPLE WIKI, TO BE READ IN THE APP.
///
/// A new owner is asked to build a wiki without ever having seen one, and "what
/// is a wiki?" is the question no amount of explaining answers. Being shown one
/// does. The nine pages are written, checked and shipped inside the app; this is
/// the part that lets an owner read them.
///
/// It is reached from two places, because the people who need it most are at
/// opposite ends of the app: the welcome screen, for somebody who has no wiki
/// yet, and the home screen, for somebody who already has one and still does not
/// know what it is for. Both say the same four words.
///
/// STRICTLY READ ONLY, AND NEVER A TEMPLATE. Nothing here writes anything
/// anywhere: no copy, no folder, no file opened for writing, and nothing at all
/// into the app bundle the pages live in. There is no button that offers to use
/// the example, and `LogicCheck` reads every word on these screens against the
/// phrases that would suggest it. `vault-template/` is what a wiki is made from;
/// this is a thing to read.
///
/// TWO WAYS TO FOLLOW A LINK, AND ONE PLACE THAT DECIDES WHERE IT GOES. The
/// links in the middle of a sentence are what make the example LOOK like a
/// wiki, and they are drawn and clickable — but an inline link inside wrapping
/// text takes no keyboard focus on macOS, so an owner who cannot use a mouse
/// could not follow one. Under the page, therefore, is a row of ordinary
/// buttons, one for each page this one links to, which Tab reaches and Space
/// presses. Both routes call `ExampleReader.follow`, so neither can offer a link
/// the other does not.
struct ExampleScreen: View {
    @ObservedObject var reader: ExampleReader
    @EnvironmentObject var flow: Flow
    /// Drawn again when the owner presses "Bigger text". (v0.9.4)
    @ObservedObject private var textSize = TextSize.shared
    /// The reading area grows with the window, which is the whole point of a
    /// window that can be dragged bigger. (v0.9.4)
    @ObservedObject private var shape = WindowShape.shared
    @Environment(\.stillPicture) private var still

    /// Moblee's own scheme, and the only thing the words on this screen may ever
    /// carry as a link. A wikilink is drawn as this scheme and the number of the
    /// link on the page, so that nothing an owner presses inside the example can
    /// reach the browser, the Finder or anything else outside the app — and so
    /// that no page name, whatever is in it, has to survive being put into an
    /// address and taken back out again.
    static let scheme = "moblee-example"

    static func url(forLinkNumber number: Int) -> URL? { URL(string: "\(scheme):\(number)") }

    /// Which link on the page was pressed, or nothing at all for any address
    /// that is not one of Moblee's own. Every address is refused here rather
    /// than handed on, so a link on this screen can open nothing.
    static func linkNumber(in url: URL) -> Int? {
        guard url.scheme == scheme else { return nil }
        return Int(url.absoluteString.dropFirst(scheme.count + 1))
    }

    /// The name the keyboard, a screen reader and the self-drive walk find one
    /// of the page's links by. Moblee's own fixed word and the page's own name,
    /// which is one of the example's and never anything of the owner's.
    static func linkId(_ page: String) -> String { "example-link-" + page }
    static func pageId(_ page: String) -> String { "example-page-" + page }

    /// How much of the window the frame round the reading area takes: the
    /// heading, the two gaps, the big button and the quiet words under it. The
    /// rest is the page, so a window dragged taller is a page with more of it on
    /// screen. Generous rather than exact, because the heading may take two
    /// lines and a page that overran the bottom of the window would be worse
    /// than one with a little room to spare. 170 is what was left over when the
    /// four screens were drawn at all three text sizes and looked at: 200 left a
    /// finger's width of empty window under the row of link buttons.
    static let furniture: CGFloat = 170

    /// The reading area, in the units `ScreenFrame` multiplies by the text size.
    /// The window's own least size is the floor, so a screen drawn to a picture
    /// file — where no window has said how big it is — is drawn with the room
    /// the window would really have at that text size.
    private var bodyHeight: CGFloat {
        let room = max(shape.size.height, Theme.leastHeight) - Theme.topStrip - Theme.pt(Self.furniture)
        return max(200, room / Theme.scale)
    }

    private var page: String? {
        if case .page(let name) = reader.showing { return name }
        return nil
    }

    var body: some View {
        ScreenFrame(
            sentence: page.map { reader.title(of: $0) } ?? ExampleReader.pagesSentence,
            buttonTitle: ExampleReader.closeWords,
            showsBack: reader.canGoBack,
            quietTitle: page == nil ? nil : ExampleReader.pagesWords,
            quietAction: page == nil ? nil : { reader.openPages() },
            // The listen control beside the heading reads the whole page, since
            // the heading is the page's own first line and the page is one block
            // of words. Asked of the very blocks that are drawn.
            speech: Speech(page.map { reader.spoken(of: $0) } ?? pagesSpoken),
            reads: page == nil ? "the list of pages" : "this page",
            // Back inside the example moves back through the example, and must
            // never move the install on or back. (v0.9.6)
            backAction: { reader.back() },
            pictureHeight: bodyHeight,
            action: { flow.closeExample() }
        ) {
            // The reading area is given a definite size and the page is held
            // inside it. Without that, a page is as tall as its own words — the
            // welcome page is about three windows tall — and SwiftUI lets a
            // child overrun a frame it was given rather than squeezing it: the
            // first drawing of this screen had the heading pushed off the top of
            // the window and the page's words running underneath the big button.
            GeometryReader { room in
                let missing = reader.missing != nil
                let links = page.map { reader.linksOn($0) } ?? []
                let wide = min(room.size.width, Theme.pt(620))
                let tall = cardHeight(in: room.size.height, missing: missing, links: !links.isEmpty)
                VStack(spacing: Theme.pt(10)) {
                    if missing { missingLine.frame(width: wide, alignment: .leading) }
                    if let page {
                        pageCard(page, width: wide, height: tall)
                        if !links.isEmpty { linkRow(links).frame(width: wide, alignment: .leading) }
                    } else {
                        pageList(width: wide, height: tall)
                    }
                }
                .frame(width: room.size.width, height: room.size.height, alignment: .top)
            }
        }
        // The one quiet line that says whose wiki this is, in the corner the
        // reading ends at, on every screen of the example. Once from the frame
        // rather than nine times from the pages. (v0.9.6)
        .overlay(alignment: Layout.assistantCorner) { chromeLine }
    }

    // --- the page ------------------------------------------------------------

    /// One row of the page as it is drawn. Built in one pass with the list of
    /// the page's links, so that the number inside a link's address and the
    /// number in that list are the same number by construction.
    private struct Row: Identifiable {
        enum Kind { case big, small, words, bullet, rule }
        let id: Int
        let kind: Kind
        var text = AttributedString()
    }

    private func rows(of page: String) -> (rows: [Row], targets: [String]) {
        var rows: [Row] = []
        var targets: [String] = []
        for (at, block) in reader.body(of: page).enumerated() {
            switch block {
            case .rule:
                rows.append(Row(id: at, kind: .rule))
            case .heading(let level, let spans):
                rows.append(Row(id: at, kind: level == 1 ? .big : .small,
                                text: attributed(spans, &targets,
                                                 size: level == 1 ? 20 : 17, weight: .semibold)))
            case .paragraph(let spans):
                rows.append(Row(id: at, kind: .words,
                                text: attributed(spans, &targets, size: 15, weight: .regular)))
            case .bullet(let spans):
                rows.append(Row(id: at, kind: .bullet,
                                text: attributed(spans, &targets, size: 15, weight: .regular)))
            }
        }
        return (rows, targets)
    }

    /// One line's pieces as one run of words, with each style put on the piece
    /// it belongs to and each link made pressable. The links are numbered as
    /// they are met, and their pages are added to `targets` in the same order,
    /// which is what lets a press be turned back into a page.
    private func attributed(_ spans: [Markdown.Span], _ targets: inout [String],
                            size: CGFloat, weight: Font.Weight) -> AttributedString {
        var whole = AttributedString()
        for span in spans {
            var piece = AttributedString(span.words)
            var font = Theme.font(size, span.bold ? .semibold : weight,
                                  span.code ? .monospaced : .rounded)
            if span.italic { font = font.italic() }
            piece.font = font
            if span.struck { piece.strikethroughStyle = .single }
            if span.code { piece.foregroundColor = Theme.accent.opacity(0.85) }
            if let link = span.link {
                targets.append(Markdown.pageName(ofLink: link))
                piece.link = Self.url(forLinkNumber: targets.count - 1)
                piece.foregroundColor = Theme.accent
                piece.underlineStyle = .single
            }
            whole += piece
        }
        return whole
    }

    /// The page itself, on a card, in the shape a wiki page has: a heading, then
    /// paragraphs and bullets, with the links in them coloured and pressable.
    ///
    /// (v0.9.4's decision, kept) A page is a window onto a file and not a
    /// sentence of Moblee's, so its own words are laid out left to right even
    /// when the app is mirrored: the pages are written in English, their lines
    /// begin on the left, and right-aligning them would take every line's
    /// beginning away from where it is. The card, the buttons, the way back and
    /// the corner line all mirror with the rest of the app.
    /// What is left of the reading area once the quiet line about a missing page
    /// and the row of link buttons have had their share. Both are one line tall
    /// and both come and go, so the page grows and shrinks with them rather than
    /// being drawn at a size that only suits one of the four states.
    private func cardHeight(in room: CGFloat, missing: Bool, links: Bool) -> CGFloat {
        var left = room
        if missing { left -= Theme.pt(26) + Theme.pt(10) }
        if links { left -= Theme.pt(32) + Theme.pt(10) }
        return max(Theme.pt(120), left)
    }

    private func pageCard(_ page: String, width: CGFloat, height: CGFloat) -> some View {
        let drawn = rows(of: page)
        return VStack(alignment: .leading, spacing: Theme.pt(9)) {
            ForEach(drawn.rows) { row in
                switch row.kind {
                case .rule:
                    Divider().padding(.vertical, Theme.pt(2))
                case .big, .small:
                    Text(row.text).fixedSize(horizontal: false, vertical: true)
                        .padding(.top, Theme.pt(4))
                        .accessibilityAddTraits(.isHeader)
                case .words:
                    Text(row.text).fixedSize(horizontal: false, vertical: true)
                case .bullet:
                    HStack(alignment: .firstTextBaseline, spacing: Theme.pt(8)) {
                        Text("•").font(Theme.font(15, .semibold))
                        Text(row.text).fixedSize(horizontal: false, vertical: true)
                    }
                    .padding(.leading, Theme.pt(6))
                }
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(Theme.pt(16))
        .modifier(Scrolls(still: still, width: width, height: height))
        .environment(\.layoutDirection, .leftToRight)
        .background(CardBackground(corner: 20))
        // Every link the owner presses inside the words comes through here, and
        // NOTHING is ever handed on to macOS: an address that is not one of
        // Moblee's own is refused rather than opened, so there is no way for a
        // page in the example to send an owner anywhere.
        .environment(\.openURL, OpenURLAction { url in
            if let number = Self.linkNumber(in: url), drawn.targets.indices.contains(number) {
                reader.follow(drawn.targets[number])
            }
            return .handled
        })
    }

    /// A page can be longer than the window, and a scrolling area cannot be
    /// drawn to a picture file, so a drawn screen shows the top of the page
    /// standing still and the window scrolls it. The same two-way choice the
    /// skill preview makes.
    private struct Scrolls: ViewModifier {
        let still: Bool
        let width: CGFloat
        let height: CGFloat
        func body(content: Content) -> some View {
            Group {
                if still {
                    content.frame(width: width, height: height, alignment: .topLeading)
                } else {
                    ScrollView { content }.frame(width: width, height: height)
                }
            }
            // A page longer than the window is cut off at the bottom of the card
            // rather than drawn over whatever is under it.
            .clipped()
        }
    }

    /// The pages this one links to, as buttons: the way a link is followed from
    /// the keyboard, and the plainest way to follow one at all for an owner who
    /// would rather press a labelled button than find a coloured word in a
    /// paragraph.
    private func linkRow(_ targets: [String]) -> some View {
        HStack(spacing: Theme.pt(8)) {
            Text(Self.linksHere)
                .font(Theme.font(12, .semibold))
                .foregroundStyle(.secondary)
            ForEach(targets, id: \.self) { target in
                Button(action: { reader.follow(target) }) {
                    Text(target)
                        .font(Theme.font(13, .semibold))
                        .padding(.horizontal, Theme.pt(9)).padding(.vertical, Theme.pt(4))
                        .contentShape(Rectangle())
                }
                .buttonStyle(.plain)
                .foregroundStyle(Theme.accent)
                .accessibilityLabel("Open the page " + target)
                .keyboardReachable(Self.linkId(target), corner: 8,
                                   press: { reader.follow(target) })
            }
            // (v0.9.6) One control for the whole row, its buttons included, the
            // way the two quiet lines in the corners of the home screen each
            // have one. The names on these buttons are the only thing saying
            // where the page goes next, and an owner who would rather be told
            // than read would otherwise never learn there was a row there at
            // all. At the end of the row, so it stands beside its own words on
            // the keyboard's round and never beside the way back.
            ListenButton(id: Self.linksListenId, speech: Speech(Self.linksSaid(targets)),
                         what: "the pages this one links to", size: 13)
                .padding(.leading, Theme.pt(4))
        }
        .frame(maxWidth: Theme.pt(620), alignment: .leading)
    }

    static let linksHere = "Pages this one links to:"
    static let linksListenId = "listen-example-links"

    static func linksSaid(_ targets: [String]) -> String {
        linksHere + " " + targets.joined(separator: ", ") + "."
    }

    // --- every page ----------------------------------------------------------

    /// The list of every page, built from the same map the links resolve
    /// against, so a reader who has lost the thread can start again anywhere.
    private func pageList(width: CGFloat, height: CGFloat) -> some View {
        VStack(alignment: .leading, spacing: Theme.pt(3)) {
            ForEach(reader.pages.inOrder, id: \.self) { name in
                Button(action: { reader.follow(name) }) {
                    HStack(spacing: Theme.pt(10)) {
                        Image(systemName: "doc.text")
                            .font(Theme.font(14, .regular, .default))
                            .foregroundStyle(Theme.accent)
                            .accessibilityHidden(true)
                        Text(name)
                            .font(Theme.font(15, .semibold))
                            .foregroundStyle(Theme.accent)
                        // The page's own heading, but only where it is not the
                        // page's name over again: six of the nine say the same
                        // thing twice, and a list that reads "Bicycle Bicycle"
                        // nine times over is a list nobody reads.
                        if reader.title(of: name) != name {
                            Text(reader.title(of: name))
                                .font(Theme.font(13))
                                .foregroundStyle(.secondary)
                                .lineLimit(1)
                        }
                        Spacer(minLength: Theme.pt(0))
                    }
                    .padding(.horizontal, Theme.pt(8)).padding(.vertical, Theme.pt(4))
                    .contentShape(Rectangle())
                }
                .buttonStyle(.plain)
                .accessibilityLabel("Open the page " + name)
                .keyboardReachable(Self.pageId(name), corner: 8, press: { reader.follow(name) })
            }
        }
        .padding(Theme.pt(10))
        .modifier(Scrolls(still: still, width: width, height: height))
        .background(CardBackground(corner: 20))
    }

    /// What the list of pages reads: every page's name and its own title.
    private var pagesSpoken: String {
        ExampleReader.pagesSentence + "\n"
            + reader.pages.inOrder.map { "\($0). \(reader.title(of: $0))" }.joined(separator: "\n")
    }

    // --- the two quiet lines -------------------------------------------------

    /// A link that led nowhere. The owner stays exactly where they were and one
    /// line appears above the page. It says nothing about files, nothing about
    /// what went wrong, and nothing to tell an assistant: the example is a thing
    /// to read, and a missing page in it is not the owner's problem to fix.
    private var missingLine: some View {
        HStack(spacing: Theme.pt(6)) {
            Image(systemName: "questionmark.circle.fill")
                .font(Theme.font(15, .regular, .default))
                .foregroundStyle(Theme.waitingText)
                .accessibilityHidden(true)
            Text(ExampleReader.notInTheExample)
                .font(Theme.font(14, .semibold))
                .foregroundStyle(Theme.waitingText)
            ListenButton(id: "listen-example-missing",
                         speech: Speech(ExampleReader.notInTheExample),
                         what: "the line about the missing page", size: 13)
        }
        .frame(maxWidth: Theme.pt(620), alignment: .leading)
    }

    private var chromeLine: some View {
        HStack(spacing: Theme.pt(2)) {
            Text(ExampleReader.chrome)
                .foregroundStyle(.secondary)
            ListenButton(id: "listen-example-chrome", speech: Speech(ExampleReader.chrome),
                         what: "the line saying this is an example", size: 13)
                .padding(.leading, Theme.pt(4))
        }
        .font(Theme.font(12, .semibold))
        .padding(.trailing, Theme.pt(12)).padding(.bottom, Theme.pt(4))
    }

    /// (v0.9.6) Every control the keyboard stops at on a page of the example, in
    /// the order Tab reaches them, written here beside the code that draws them —
    /// the same arrangement `HomeScreen.stops` has, and for the same reason: a
    /// list of names typed into a check is a list of what somebody believed.
    static func stops(linksOnThePage: [String], canGoBack: Bool,
                      showingAPage: Bool, missing: Bool) -> [String] {
        var ring = ["bigger-text", "read-aloud"]
        if missing { ring.append("listen-example-missing") }
        if showingAPage, !linksOnThePage.isEmpty {
            ring += linksOnThePage.map(linkId) + [linksListenId]
        }
        if canGoBack { ring.append("back") }
        if showingAPage { ring += ["quiet", "listen-quiet"] }
        ring.append("listen-example-chrome")
        return ring
    }
}
