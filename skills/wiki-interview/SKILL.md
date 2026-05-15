---
name: wiki-interview
description: Conduct a structured interview with the user about a topic, then write the conversation as a wiki page. Use when the user wants to capture knowledge from their own mind (their experience, opinions, thinking on a subject) rather than ingest from an external source. Trigger phrases include "interview me about", "help me write a page on", "walk me through my thoughts on", "capture my thinking about", "I want to write a page on X but I don't have any source material", "let's talk through X for the wiki", or any clear variant. Do not trigger on requests that have an external source attached (those route to the standard ingest pass), on simple lookups, or on chitchat.
---

# wiki-interview

This skill conducts a structured interview with the user about a topic and produces a wiki page from the conversation. It exists to capture knowledge that lives only in the user's head, where there is no PDF, no article, no Clipping to ingest, only the user's experience and thinking on a subject.

## When to use

The standard wiki workflow assumes a source: a file in `raw/`, a Clipping, a meeting note. The ingest pass reads the source and writes it into wiki pages. That workflow works well for external material, but the wiki also benefits from material that has no external source, the user's tacit knowledge about their own work, their philosophy on a subject, the shape of a decision they have already made and want to make legible to themselves.

Use this skill when:

- The user has a topic they want a wiki page on, but no source material to ingest. The material is in their head.
- The user wants to make tacit knowledge explicit: how they approach a recurring problem, what they have learned from a specific experience, how their thinking on a subject has settled.
- The user says some variant of "interview me about X", "help me write a page on X", "let's talk through my thoughts on X", "I want to capture my thinking on X".
- A conversational page would suit the topic better than a synthesis page (memoir-style material, philosophy, approach pieces, career retrospectives).

Do not use this skill when:

- The user has attached a source (PDF, article, Clipping, meeting note). That is the standard ingest pass, not an interview.
- The user wants a quick factual answer or a one-off note. That is a query or a wiki-capture, not an interview.
- The user wants a comparative analysis or a synthesis across pages. That is the brain skill.

## The interview process

The skill walks through six phases. Move through them deliberately. The pace of the interview matters as much as the content; rushing produces shallow material, and the point of this skill is to surface what would not surface in a fast back-and-forth.

### 1. Topic selection

Open by asking what the user wants to interview about. If the topic is broad ("my career", "my golf"), help narrow it before starting. A good interview topic is specific enough to have a shape but open enough to surface unstated thinking. "How I think about hiring engineers" is a good topic. "My career" is not (it is too broad, and would produce a thin survey rather than a deep page).

If the user lands on a topic that is too narrow ("the time in 2019 when we shipped Project X"), check whether they want a single-event memoir page or whether they want to draw a wider lesson out of it. Either is fine, but the framing changes the outline.

Confirm the topic explicitly before moving on. Restate it in one sentence and check it lands.

### 2. Outline

Once the topic is fixed, propose a four-to-six question outline based on what the topic seems to ask for. The outline is the spine of the interview and of the eventual page. A good outline:

- Has questions, not headings. "What first drew you to this?" is a question; "Origins" is a heading.
- Moves from concrete to abstract, or from origin to current view, depending on the shape of the topic.
- Leaves room for follow-ups. The outline is a starting point, not a script.
- Covers at least one question that pushes against the user's stated view, to surface friction.

Present the outline back to the user and confirm. They may want to add a question, drop one, or reorder. Adjust before the interview starts.

### 3. The interview

Walk through each outline question in order. After asking a question:

- Listen to the answer carefully. The full answer, not the first sentence of it.
- Ask one or two follow-ups before moving on. "What do you mean by X?", "Was there a moment that made you think that?", "What changed your view?"
- Don't move on too fast. If the answer feels thin, ask a different angle on the same question rather than ploughing on.
- Let pauses sit. If the user types "hmm, give me a second", give them the second.
- Push back gently when the user contradicts themselves or when the answer doesn't land. The user is the expert on the topic; the interviewer's job is to help them say what they actually think, which sometimes means surfacing tension in what they have said so far.

Avoid:

- Leading questions ("Don't you think X?"). Ask open questions and let the user fill them in.
- Multi-part questions. Ask one thing at a time.
- Summarising too early. The user's words are the material; don't paraphrase before you have heard the whole answer.
- Filler agreement ("That makes sense", "Totally"). Listen and ask the next thing.

Take notes as you go. The notes are what the page is written from; treat them seriously.

### 4. Synthesis check

Before writing the page, summarise what you have heard back to the user. Two or three paragraphs that name the main threads of the interview, in the user's own framing where possible. Ask whether the summary lands.

The synthesis check is the moment to catch:

- A thread you missed and the user wants to add.
- A thread you over-weighted and the user wants to play down.
- A framing the user wants to adjust.
- An idea that came up that the user wants drawn out further before the page is written.

Iterate the synthesis until the user confirms it. Then write.

### 5. Write the page

Compose the wiki page from the interview notes and the confirmed synthesis. The voice is the user's, lightly edited for flow and structure. The goal is a page that reads as the user would write it on their best day, not a transcript of the conversation and not a third-party summary.

Structure conventions:

- One H1 title (the topic, as confirmed in step 1).
- One short opening paragraph that names what the page is and where it came from (an interview, with the date).
- H2 sections per outline question theme, in the order the outline followed. Use a heading that captures the theme, not the literal question.
- Prose paragraphs under each H2. Avoid bullet lists unless the content is genuinely list-like (a sequence of steps, an inventory of items).
- Wikilinks where they fit naturally. Don't force them; if no existing page is a good link target, leave the reference as plain text and let the wiki accumulate around it.
- A closing paragraph that names what the user thinks is still open, if anything. This makes the page a live document rather than a closed statement.
- A source line at the foot of the page: `Source: Interview with the user, [DATE].`

House style applies: British English, no em dashes, no emojis, absolute dates only, third person if the wiki uses third person elsewhere or first person if the user prefers their own pages in first person (check on the first interview, then follow the same convention afterwards).

### 6. Place and log

Once the page is drafted:

- Place it at the right location in the vault. New top-level pages go to `wiki/<Title>.md`. Sections that extend an existing page get appended to that page, with a clear H2 header marking the new material as interview-sourced.
- Append a log entry to `wiki/log.md` in the form `## [YYYY-MM-DD HH:MM ±TZ] interview | <Title>`, with a short body paragraph describing what was interviewed and what the page covers.
- Surface the page link for user review. Ask whether they want changes before considering it complete.
- Confirm the user has no further changes before closing the interview.

## Tone

Conversational. Curious. Slow. Treat it like a podcast interview, not an interrogation, and not a meeting. The user is the expert; the interviewer's job is to be interested, ask the next useful question, and help the user say what they actually think.

The interviewer is not a therapist. Don't probe into emotional material that the topic doesn't call for. Don't push when the user signals they want to move on. Don't try to make the topic deeper than it is.

The interviewer is also not a stenographer. Active listening means following the line of thought, not transcribing word-for-word. The notes are what the page is built from, and the notes should capture the shape of the user's thinking, not every clause they uttered.

## Output

A wiki page in the user's voice, lightly edited for flow, structured as described above, logged in `wiki/log.md`, and surfaced to the user for review.

If the user wants the conversation itself preserved alongside the page (for reference, for future re-interview, or for transcript review), save the interview transcript as a companion file under `raw/processed/interviews/<DATE>-<topic-slug>.md`. This is optional; ask before saving.

## Examples of good interview topics

- "How I think about [your career or profession or craft]"
- "My approach to [a recurring decision in your life or work]"
- "What I learned from [a specific experience or project]"
- "My philosophy on [a subject area you have a settled view on]"
- "How I read [a category of material: novels, research papers, news]"
- "The shape of my [routine, week, year]"
- "What I have changed my mind about regarding [a subject]"
- "My theory of [a problem you have thought about for a long time]"
- "What [a person or experience] taught me"

A good test of topic readiness: if the user can talk about it for ten minutes without external prompts, the topic is ready. If they would need to look things up, the topic is closer to a research page than an interview page; consider routing to a standard ingest with the user's notes as the source instead.

## Notes on running the interview

- The interview can take anywhere from twenty minutes to two hours depending on the topic. Don't try to compress it; the point is depth.
- If the user wants to pause and resume, save the notes so far and the outline state, and let them pick up later from the synthesis-check step or wherever they left off.
- If the interview surfaces a strong thread that is its own topic, name it and ask whether to schedule a follow-up interview rather than trying to cover it inside the current one.
- After the page is written, the user may ask for an edit pass. Treat it as a normal wiki edit, not as a re-interview, unless they want to reopen the conversation.
