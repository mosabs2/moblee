---
type: Wiki Operations Reference
from: Moblee Hub recipe orient-morning-pass 1.0.0, built into Moblee 0.16.0
---

# Mail Pass

The mail pass is an optional part of **orient**. Once the owner has said yes to it, it keeps their unread Apple Mail down to the messages that need them, and turns the ones that need action into to-dos at the top of today's Plan. It reads headers only (sender, subject, date), through Apple Mail on this Mac, with the two scripts in `scripts/`. It is listed with everything else on [[What Your Wiki Can Do]].

## Off until the owner says yes

The pass does not run until a line under "Installed, and why" on [[Habits and Tools]] says the owner agreed to it, for example ``- `mail-pass`, 4 November 2026: keeps my unread mail to what needs me``.

**Offered once, and only where it fits.** If "How the owner works" on that page says their mail is in Apple Mail, offer it once, in one line, at the end of an orient: "I can sort your unread Apple Mail each morning, by sender and subject only, and never delete or send anything. Want that?" If the page does not say where their mail lives, ask that first, once. Mail in a browser or another app means no offer. A no goes under "Said no to" with the date, and the pass is not offered again for 90 days. "Not now" is not a no.

**On their yes**, ask these one at a time and write the answers under "Fitted to the owner" below, dated:

1. Which accounts in Mail the pass should cover: all, or only some.
2. Anyone or anything whose mail always stays unread, even if it looks like a promotion.
3. Where news newsletters go: a mailbox called News, another name, or left unread.
4. Automatic money notices (receipts, payment alerts): left unread with the rest of the money mail, or marked read. Asked once, never raised again unless the owner raises it.
5. How many unread messages feel like too many.

The first time a script talks to Mail, macOS asks whether the assistant's app may control Mail. The owner clicks **OK**. If no box appears and the script fails with "Not authorised to send Apple events to Mail", the owner opens System Settings, Privacy & Security, Automation, and switches on Mail under the app the assistant runs in.

## What stays unread, and what does not

**Stays unread:**

- **People.** Mail from a real person to the owner, including forwards from someone they know.
- **Money.** Banks, cards, billing, invoices, receipts, statements, payment reminders. These are never opened.
- **Action.** Anything the owner must do something about: a parcel to collect, a deadline, a form to confirm, an invitation, a renewal falling due, a sign-in the owner did not make. Each one is named in the sitrep and added to the top of today's Plan. It is marked read only when the owner says it is done.

**Marked read:** promotions, shops and offers, social notices, club and venue mailings, tracking and delivery notices, order confirmations, and sign-in alerts for something the owner did themselves.

**Marked read and moved to the News mailbox** (or the name in answer 3): news and analysis newsletters, kept for reading when the owner wants them.

**Never:** delete, send, reply, unsubscribe, put in junk, or open a message body. The only exceptions are on the owner's word for a named message ("what does the email from X say?"). When unsure which group a message is in, leave it unread and name it.

## The steps

1. **List.** `osascript scripts/mail-list-unread.applescript > "<scratch folder>/unread.txt"`. Each line is account, id, sender, subject and date, separated by tabs, and the end has one `# account: N unread; mailboxes: ...` line per account. It changes nothing. Use the session's scratch folder, never the wiki.
2. **Sort only what is new.** Anything still unread from an earlier pass was left unread on purpose. Sort only what arrived since the last pass, unless the owner asks for a full re-sort.
3. **Write the ids.** For each account, one file of ids to mark read and one of ids to file as news, one id per line, in the scratch folder. Never pass an empty file (the script stops with `End of file error`); skip that account instead.
4. **Act.** Mark read: `osascript scripts/mail-tidy.applescript read "<account>" none "<file>"`. News: `osascript scripts/mail-tidy.applescript news "<account>" "News" "<file>"`, which makes the mailbox first if the account has none. Each prints `read <account>: N of M`; N should equal M. Write account names exactly as the list prints them, in quotes. At most four `osascript` calls in one command.
5. **Report** one line, `Unread N (was M): people P, money Q, action R`, then the action items, one short line each, and add them to the top of today's Plan.

**The first pass is different:** show the owner the counts per group and per account, and every message that would stay unread as action, and act only on their yes. After that the pass runs at every orient without asking.

## When it breaks

- **A Gmail move times out** ("AppleEvent timed out"). Gmail accounts in Mail are slow. Run the same command again: it only acts on messages still unread in the inbox.
- **`End of file error (-39)`.** The id file was empty. Skip that account.
- **`Can't get account "…" (-1728)`.** The account name is wrong or was renamed. List again and copy the name exactly as printed.
- **An account is missing from the list.** Mail lists only accounts switched on in its settings. If an account shows `ERROR`, open Mail, let it finish syncing, and list again.
- **Mail is not set up on this Mac.** Say so in the sitrep's mail line and carry on with the rest of orient.

## Fitted to the owner

*(Empty until the owner says yes. Then one dated line per answer above, in the owner's words where possible, and a line for each correction they make later.)*
