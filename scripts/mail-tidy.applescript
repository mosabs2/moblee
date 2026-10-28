-- osascript scripts/mail-tidy.applescript <read|news> <account name> <News mailbox name, or none> <file of message ids, one per line>
-- read: marks each listed unread INBOX message read. The third word is not used.
-- news: marks each listed unread INBOX message read and moves it to the named mailbox
--       in the same account, making that mailbox first if the account has none.
-- It never deletes, sends, replies, unsubscribes or marks anything as junk: the
-- recipe's junk mode was left out of Moblee's copy on purpose.
-- Never pass an empty file: Mail stops with "End of file error (-39)". Skip that account.
-- Prints "<mode> <account>: N of M"; N equal to M means every listed message was found.
-- From the Moblee Hub recipe "Orient, the morning pass" 1.0.0.
on run argv
	set mode to item 1 of argv
	set acctName to item 2 of argv
	set boxName to item 3 of argv
	set idText to read (POSIX file (item 4 of argv)) as «class utf8»
	set targetIds to {}
	repeat with p in paragraphs of idText
		if (p as text) is not "" then set end of targetIds to (p as integer)
	end repeat
	set done to 0
	tell application "Mail"
		set mb to mailbox "INBOX" of account acctName
		if mode is "news" then
			if not (exists mailbox boxName of account acctName) then
				make new mailbox with properties {name:boxName} at account acctName
				delay 2
			end if
			set newsBox to mailbox boxName of account acctName
			repeat with n in targetIds
				set found to (messages of mb whose id is (n as integer))
				if (count of found) > 0 then
					set m to item 1 of found
					set read status of m to true
					move m to newsBox
					set done to done + 1
				end if
			end repeat
		else if mode is "read" then
			-- Each listed message is found by its own id, as news does. Two separate
			-- lists of unread messages, read side by side, could fall out of step if
			-- mail arrived between them, and mark an unlisted message read.
			repeat with n in targetIds
				set found to (messages of mb whose id is (n as integer))
				if (count of found) > 0 then
					set read status of (item 1 of found) to true
					set done to done + 1
				end if
			end repeat
		else
			error "The first word must be read or news."
		end if
	end tell
	return mode & " " & acctName & ": " & done & " of " & (count of targetIds)
end run
