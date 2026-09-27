import SwiftUI
import AppKit

/// (v0.9.6) The screen the check-up button leads to.
///
/// It has four things to say and says them in this order: something is
/// happening; whether the wiki looks healthy; that the report is saved and
/// where; and what to do with it. The health card sits in the middle of it,
/// because that is what the card was built for — one screen for whoever is
/// helping the owner — and because it is the screen an owner can photograph and
/// send if everything else fails them.
struct ClinicScreen: View {
    /// Drawn again when the owner presses "Bigger text". (v0.9.4)
    @ObservedObject private var textSize = TextSize.shared
    @EnvironmentObject var flow: Flow
    @EnvironmentObject var home: HomeModel
    @ObservedObject var clinic: Clinic
    @Environment(\.stillPicture) private var still
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    var body: some View {
        ScreenFrame(
            sentence: Clinic.sentence(for: clinic.state),
            buttonTitle: "Done",
            buttonEnabled: Clinic.canGoOn(clinic.state),
            showsBack: false,
            quietTitle: Clinic.quietWords(for: clinic.state),
            quietAction: Clinic.quietWords(for: clinic.state) == nil ? nil : { clinic.showTheFile() },
            action: {
                clinic.forget()
                flow.mode = .home
            }
        ) {
            switch clinic.state {
            case .idle, .running:
                working
            case .finished(let done):
                found(done.card, saved: done.savedAs != nil)
            case .noWiki:
                onlyASymbol("books.vertical.fill", Theme.accent)
            case .couldNotCheck:
                onlyASymbol("exclamationmark.triangle.fill", Theme.waiting)
            }
        }
        // The check-up starts as the screen arrives, the way an update does. A
        // picture file draws whatever state it was asked for and runs nothing.
        .onAppear {
            guard !still, clinic.state == .idle else { return }
            clinic.begin(home: flow.home, vault: home.vault, pack: pack,
                         wikiVersion: home.wikiVersion, packVersion: home.packVersion)
        }
    }

    /// The Moblee folder this Mac uses. The app settles its own pack there and
    /// keeps the note of where it is pointing at it, so this is the same folder
    /// the owner's assistant and the check-up itself would find.
    private var pack: URL? {
        let note = flow.home.appendingPathComponent(".config/moblee/package-path")
        if let text = try? String(contentsOf: note, encoding: .utf8) {
            let path = text.trimmingCharacters(in: .whitespacesAndNewlines)
            if !path.isEmpty, FileManager.default.fileExists(atPath: path) {
                return URL(fileURLWithPath: path, isDirectory: true)
            }
        }
        return HomeModel.mobleePacks(home: flow.home).last ?? flow.bundledPack
    }

    private var working: some View {
        VStack(spacing: Theme.pt(18)) {
            Image(systemName: "stethoscope")
                .font(Theme.font(90, .regular, .default))
                .foregroundStyle(Theme.accent)
                .symbolEffect(.pulse, options: .repeating, isActive: !reduceMotion && !still)
                .accessibilityHidden(true)
            Text(Self.takesAFewSeconds)
                .font(Theme.font(17, .medium))
                .foregroundStyle(.secondary)
        }
    }

    static let takesAFewSeconds = "This takes a few seconds. Nothing is being changed."

    private func onlyASymbol(_ symbol: String, _ colour: Color) -> some View {
        Image(systemName: symbol)
            .font(Theme.font(96, .regular, .default))
            .foregroundStyle(colour)
            .accessibilityHidden(true)
    }

    /// The health card, drawn from the same facts the card itself is printed
    /// from: the headline, what is wrong worst first with its field-guide code,
    /// what could not be checked, and what to do next. The card's own text goes
    /// into the report word for word; this is the same thing at a size an owner
    /// can read across a room, with the line under it saying what to do with the
    /// file.
    private func found(_ card: Clinic.Card, saved: Bool) -> some View {
        VStack(spacing: Theme.pt(8)) {
            VStack(alignment: .leading, spacing: Theme.pt(8)) {
                HStack(spacing: Theme.pt(8)) {
                    Image(systemName: card.healthy ? "checkmark.seal.fill" : "exclamationmark.triangle.fill")
                        .foregroundStyle(card.healthy ? Theme.good : Theme.waiting)
                        .accessibilityHidden(true)
                    Text(Self.cardTitle)
                        .font(Theme.font(16, .semibold))
                    Spacer(minLength: Theme.pt(0))
                }
                Text(card.headline)
                    .font(Theme.font(14))
                    .fixedSize(horizontal: false, vertical: true)
                    .lineLimit(2)
                ForEach(Array(Self.rowsShown(card).enumerated()), id: \.offset) { _, row in line(row) }
                if let more = Self.andMore(shown: Self.rowsShown(card).count, of: Self.rowsThereAre(card)) {
                    Text(more).font(Theme.font(13)).foregroundStyle(.secondary)
                }
                if let first = card.actions.first {
                    HStack(alignment: .top, spacing: Theme.pt(8)) {
                        Image(systemName: "arrow.right.circle.fill")
                            .foregroundStyle(Theme.accent)
                            .frame(width: Theme.pt(30), alignment: .leading)
                            .accessibilityHidden(true)
                        Text(first).font(Theme.font(13, .medium))
                            .fixedSize(horizontal: false, vertical: true).lineLimit(2)
                    }
                    .padding(.top, Theme.pt(2))
                }
            }
            .padding(Theme.pt(16))
            // As tall as what is on it and no taller: a healthy wiki has two
            // lines to say and should not be given a card with half a screen of
            // white under them. The room the card can take is bounded by the
            // three findings and the one action above it, which is why the
            // height does not have to be nailed down.
            .frame(width: Theme.pt(600), alignment: .topLeading)
            .background(CardBackground(corner: 18))
            // (v0.9.6) The whole card, read aloud. An owner who would rather be
            // told than read is exactly the owner this screen was built for.
            .overlay(alignment: .topTrailing) {
                ListenButton(id: Self.listenId, speech: Speech(Self.said(card, saved: saved)), what: "the health card")
                    .padding(Theme.pt(10))
            }
            // (v0.9.6) Only when there is a file to send. Where the report could
            // not be saved, the sentence above asks for a photograph instead, and
            // this line under it contradicted that.
            if saved {
                Text(Clinic.sendIt)
                    .font(Theme.font(14, .medium))
                    .foregroundStyle(.secondary)
            }
        }
    }

    static let listenId = "listen-health-card"
    static let cardTitle = "Moblee health card"
    /// How many findings fit on this screen. The card itself holds five and two,
    /// and a window is shorter than a terminal, so this shows fewer and says how
    /// many it is not showing, exactly as the card does. Every one of them is in
    /// the report, which is the thing that gets sent.
    static let mostRows = 3

    /// What is worth the owner's eye, worst first: the things that are wrong,
    /// and, only when nothing is wrong, the things that could not be checked.
    /// Never both — the headline already counts what could not be checked, and a
    /// screen that lists two kinds of finding at once asks a person who does not
    /// read much to read twice as far.
    static func rowsShown(_ card: Clinic.Card) -> [Clinic.Card.Row] {
        Array((card.wrong.isEmpty ? card.unchecked : card.wrong).prefix(mostRows))
    }

    static func rowsThereAre(_ card: Clinic.Card) -> Int {
        card.wrong.isEmpty ? card.uncheckedTotal : card.wrongTotal
    }

    /// (v0.9.6) It used to end "all of them in the report", and that was not
    /// true. The card the check-up hands over holds five findings at most, so
    /// with nine things wrong the screen promised the owner a report with nine
    /// in it and the report carried five — and then said so itself, two
    /// paragraphs further down, which is worse than not saying it at all. The
    /// sentence the whole feature rests on is "send that file"; it must not
    /// oversell what is in the file.
    static func andMore(shown: Int, of total: Int) -> String? {
        total > shown ? "and \(total - shown) more. The full check-up lists every one." : nil
    }

    /// What the card's listen control reads: everything on the card, in the
    /// order it is drawn. Worked out here beside the drawing, so the two cannot
    /// drift apart, and static so a check can read it back.
    static func said(_ card: Clinic.Card, saved: Bool = true) -> String {
        var out = [cardTitle + ". " + card.headline]
        out += rowsShown(card).map { $0.line }
        if let more = andMore(shown: rowsShown(card).count, of: rowsThereAre(card)) { out.append(more) }
        if let first = card.actions.first { out.append("What to do next. " + first) }
        if saved { out.append(Clinic.sendIt) }
        return out.joined(separator: " ")
    }

    /// One finding: its entry in the companion's field guide, then the finding.
    /// One line, shrinking a little rather than wrapping, because the card is a
    /// fixed height and a wrapped line would push the one below it off the
    /// bottom; the whole of every line is in the report.
    private func line(_ row: Clinic.Card.Row) -> some View {
        HStack(alignment: .top, spacing: Theme.pt(8)) {
            Text(row.code.isEmpty ? "-" : row.code)
                .font(Theme.font(12, .semibold, .monospaced))
                .foregroundStyle(Theme.accent)
                .frame(width: Theme.pt(30), alignment: .leading)
            Text(row.line)
                .font(Theme.font(13))
                .lineLimit(1)
                .minimumScaleFactor(0.8)
            Spacer(minLength: Theme.pt(0))
        }
    }
}
