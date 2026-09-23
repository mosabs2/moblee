---
last_reviewed:
---

# Habits and Tools

How the owner works day to day, how they like the assistant to work with them, and what has been added to Moblee to match. The assistant writes this page from conversation: the first "get me started" conversation, the corrections the owner makes along the way, and the setup reviews. It is how the assistant knows what to suggest, what not to suggest again, and how to talk. See [[Index]] for the rest of the wiki.

## How the owner works

*(Filled in during the "get me started" conversation, in the owner's words: where their mail, calendar and notes live, what they read, watch and make, what they repeat. Leave blank rather than guess.)*

## How the assistant talks with the owner

*(Short replies or full ones, spoken or not, and anything else the owner has asked for. Until something is written here, replies are short: two or three lines, one question at a time.)*

## Working with the owner

*(One dated line for every correction the owner makes to how the assistant works, in their words, written the moment it is made. For example: - 19 September 2026: "show me the page before you commit it".)*

## Waiting in Moblee

*(One line per thing agreed with the owner and not yet added: a dash, the key in backticks, the date, and the reason the owner gave. The same things are listed in `.moblee/requests.json`, which the Moblee app reads. A line moves to "Installed, and why" once the check shows it working.)*

## Installed, and why

*(One line per checklist item that has been added and checked, moved here from "Waiting in Moblee" and marked working: a dash, the item's key in backticks, the date, and the reason the owner gave. For example: - `videos`, 19 September 2026: saves YouTube and Instagram videos to watch later (working).)*

## Made for the owner

*(One entry per made-to-measure build: what it is, where it lives in the vault, how it is started, what it depends on, the date, and why it was built, in the owner's words.)*

## Said no to

*(One line per item the owner turned down, in the same form: a dash, the key in backticks, the date, and the reason if one was given. The assistant does not suggest these again for ninety days unless the owner raises them, and the weekly health check stays quiet about them too. A no to the "get me started" conversation or a setup review is written with the key `companion`; a vault made before v0.9.1 may carry `get-started` instead, which still counts.)*

## Review history

*(One dated line per setup review: what changed, or that nothing did.)*
