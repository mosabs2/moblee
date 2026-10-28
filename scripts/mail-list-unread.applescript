-- osascript scripts/mail-list-unread.applescript
-- Lists every unread message in each account's INBOX, one per line:
--   account <TAB> id <TAB> sender <TAB> subject <TAB> date received (YYYY-MM-DD)
-- Read-only: reads headers through Mail, opens no message body, changes nothing.
-- Ends with one "# account: N unread; mailboxes: ..." line per account, for the counts
-- and to show whether a "News" mailbox exists. Used by the mail pass at orient
-- (wiki/Wiki Operations/Mail Pass.md), only once the owner has said yes to it.
-- From the Moblee Hub recipe "Orient, the morning pass" 1.0.0.
on pad(n)
	if n < 10 then return "0" & n
	return n as text
end pad

on run
	set out to ""
	set summary to ""
	tell application "Mail"
		repeat with acct in accounts
			set acctName to name of acct
			try
				set mb to mailbox "INBOX" of acct
				set msgs to (messages of mb whose read status is false)
				repeat with m in msgs
					set d to date received of m
					set ds to ((year of d) as text) & "-" & my pad((month of d) as integer) & "-" & my pad(day of d)
					set subj to subject of m
					if subj is missing value then set subj to ""
					set out to out & acctName & tab & (id of m) & tab & (sender of m) & tab & subj & tab & ds & linefeed
				end repeat
				set boxNames to name of every mailbox of acct
				set AppleScript's text item delimiters to ", "
				set summary to summary & "# " & acctName & ": " & (count of msgs) & " unread; mailboxes: " & (boxNames as text) & linefeed
				set AppleScript's text item delimiters to ""
			on error errMsg
				set summary to summary & "# " & acctName & ": ERROR " & errMsg & linefeed
			end try
		end repeat
	end tell
	return out & summary
end run
