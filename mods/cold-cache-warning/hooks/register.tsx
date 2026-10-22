// Cold-cache warning — a band above the prompt when a long conversation has gone cold.
//
// Claude keeps a long conversation cheap to carry on for a while after the last reply. That
// does not last — about an hour on most plans — and after it, the next message makes Claude
// read the whole conversation again. When that has happened to a conversation big enough to
// matter, a band above the prompt says so before anything is typed: how long it has been
// idle, and roughly how much would be re-read. The /cache command reports the same at any time.
//
// Nothing is ever sent anywhere, and no model call is ever made. No message is held, delayed or
// blocked, so a dictated message can never be lost.
//
// The band also says whether the wiki's work has been committed, so it is clear that the
// conversation is safe to leave for a fresh one. A companion script commits the wiki at the end
// of each reply and records what it did, per conversation, in
// ~/.config/moblee/state/turn-end-commit.json. The band reads that record; it never runs git.
//
// The cache's lifetime is not the same on every plan, so it can be set: put a whole number of
// minutes in ~/.config/moblee/cache-minutes and the band waits that long instead of the hour.

import { atom, read, update } from 'claude-code'
import type { EngineInterface, Register } from 'claude-code'

import type { Cold, CommitNote } from '../types'

const DEFAULT_MINUTES = 60 // the cache's lifetime unless the owner has set their own
const MIN_MINUTES = 1
const MAX_MINUTES = 24 * 60 // longer than a day is not a cache lifetime; treat it as a slip
const MIN_TOKENS = 60_000 // below this a cold re-read costs too little to mention
const TICK_MS = 60 * 1000
const KEEP_MS = 30 * 24 * 60 * 60 * 1000 // last-reply times kept in the store this long
const PREFIX = 'last-reply:'

const lastReplyAt = atom({ plugin: 'cold-cache-warning', key: 'lastReplyAt' } as const, null)
const cold = atom({ plugin: 'cold-cache-warning', key: 'cold' } as const, null)
const isHidden = atom({ plugin: 'cold-cache-warning', key: 'isHidden' } as const, false)
const cacheMinutes = atom({ plugin: 'cold-cache-warning', key: 'cacheMinutes' } as const, DEFAULT_MINUTES)

export function idleText(minutes: number): string {
  const h = Math.floor(minutes / 60)
  const m = minutes % 60
  if (h === 0) return `${m} min`
  return m === 0 ? `${h} h` : `${h} h ${m} min`
}

export function tokensText(n: number): string {
  const rounded = n >= 10_000 ? Math.round(n / 1000) * 1000 : n
  return String(rounded).replace(/\B(?=(\d{3})+(?!\d))/g, ',')
}

// The lifetime the owner has set, in minutes. Anything that is not a plain whole number of
// minutes within reason — a missing file, an empty one, a word, a negative, nought, something
// absurd — falls back to the default rather than breaking the band.
export function parseMinutes(text: string | null | undefined): number {
  const trimmed = String(text ?? '').trim()
  if (!/^\d{1,5}$/.test(trimmed)) return DEFAULT_MINUTES
  const n = Number(trimmed)
  if (!Number.isInteger(n) || n < MIN_MINUTES || n > MAX_MINUTES) return DEFAULT_MINUTES
  return n
}

// How the band and /cache name the cache's lifetime. It differs between plans, so the default is
// given as a rough hour rather than as a fact; a lifetime the owner has set is given as theirs.
export function lifetimeText(minutes: number): string {
  return minutes === DEFAULT_MINUTES ? 'about an hour on most plans' : `about ${idleText(minutes)}, as you have set it`
}

const ASK = 'In a new conversation, say "commit what the last conversation left".'

export function commitLine(c: CommitNote): string {
  const n = (k: number, word: string) => `${k} ${word}${k === 1 ? '' : 's'}`
  if (c.state === 'committed' || c.state === 'clean') {
    return 'Everything from this conversation is committed, so it is safe to start a new one.'
  }
  if (c.state === 'blocked' && c.ownLeft > 0) {
    return `${n(c.ownLeft, 'file')} this conversation edited ${c.ownLeft === 1 ? 'is' : 'are'} not committed: the wiki's commit check stopped ${c.ownLeft === 1 ? 'it' : 'them'}. ${ASK}`
  }
  if (c.state === 'blocked') {
    return `Everything this conversation edited is committed. ${n(c.otherLeft, 'other file')} in the wiki ${c.otherLeft === 1 ? 'is' : 'are'} not: the commit check stopped ${c.otherLeft === 1 ? 'it' : 'them'}. ${ASK}`
  }
  return `The automatic commit after the last reply did not finish${c.reason ? ` (${c.reason})` : ''}. ${ASK}`
}

const STATES = ['committed', 'clean', 'blocked', 'busy', 'error']
const STALE_MS = 2 * 60 * 1000 // a record written more than this before the last reply belongs to an earlier one

let homeDir: string | null = null // the owner's home folder, asked of the engine once per process
let statusPath: string | null = null // ~/.config/moblee/state/turn-end-commit.json, found at session start

// The owner's home folder, or null if the engine would not say. Asked once and kept.
async function findHome($: EngineInterface): Promise<string | null> {
  if (homeDir === null) {
    const env = await $.process.run(['/usr/bin/printenv', 'HOME']).catch(() => undefined)
    const dir = env?.exitCode === 0 ? env.stdout.trim() : ''
    if (dir.startsWith('/')) homeDir = dir
  }
  return homeDir
}

// What the turn-end commit recorded for this conversation's last reply; null when there is no such record.
async function commitNote($: EngineInterface, last: number): Promise<CommitNote | null> {
  if (statusPath === null) return null
  try {
    const all = JSON.parse(await $.fs.read(statusPath)) as Record<string, Record<string, unknown>>
    const entry = all[await $.session.id()]
    if (entry === undefined || !STATES.includes(String(entry.state))) return null
    const at = Date.parse(String(entry.at))
    if (Number.isNaN(at) || at < last - STALE_MS) return null
    const count = (v: unknown) => (Array.isArray(v) ? v.length : 0)
    return {
      state: entry.state as CommitNote['state'],
      ownLeft: count(entry.own_left),
      otherLeft: count(entry.other_left),
      reason: String(entry.reason ?? '').slice(0, 160),
    }
  } catch {
    return null
  }
}

// Is the conversation cold now? Writes `cold` only when the answer changes or the minutes move.
async function check($: EngineInterface): Promise<void> {
  const last = await read($, lastReplyAt)
  const current = await read($, cold)
  if (last === null) {
    if (current !== null) await update($, cold, () => null)
    return
  }
  const idle = (await $.clock.now()) - last
  if (idle < (await read($, cacheMinutes)) * 60_000) {
    if (current !== null) await update($, cold, () => null)
    return
  }
  const tokens = (await $.session.usage()).context.tokens
  if (tokens === undefined || tokens < MIN_TOKENS) {
    if (current !== null) await update($, cold, () => null)
    return
  }
  const next: Cold = { idleMinutes: Math.floor(idle / 60_000), tokens, commit: await commitNote($, last) }
  if (
    current === null ||
    current.idleMinutes !== next.idleMinutes ||
    current.tokens !== next.tokens ||
    JSON.stringify(current.commit) !== JSON.stringify(next.commit)
  ) {
    await update($, cold, () => next)
  }
}

export const register: Register = on => {
  on('session.start', async ($, e, next) => {
    // A session resumed after the app restarted has no state of its own yet: the store has its
    // last reply, so a conversation left overnight still warns on its first view.
    const id = await $.session.id()
    const home = await findHome($)
    if (home !== null) {
      statusPath = `${home}/.config/moblee/state/turn-end-commit.json`
      // The owner's own cache lifetime, if they have written one down. Read fresh each session
      // so a change takes effect at the next one, and never allowed to throw.
      const set = await $.fs.read(`${home}/.config/moblee/cache-minutes`).catch(() => undefined)
      await update($, cacheMinutes, () => parseMinutes(set))
    }
    if ((await read($, lastReplyAt)) === null) {
      const saved = await $.store.get(PREFIX + id)
      if (typeof saved === 'number') await update($, lastReplyAt, () => saved)
    }
    const now = await $.clock.now()
    for (const key of await $.store.keys()) {
      if (!key.startsWith(PREFIX)) continue
      const at = await $.store.get(key)
      if (typeof at !== 'number' || now - at > KEEP_MS) await $.store.delete(key)
    }
    await $.command.register({
      name: 'cache',
      description: 'Says whether this conversation is still cheap to carry on, or has gone cold and would be re-read in full.',
    })
    await check($)
    $.clock.every(TICK_MS, () => {
      void check($)
    })
    return next(e)
  })

  // Every reply on the main conversation refreshes the cache: note the time, clear the band.
  on('turn.complete', async ($, e, next) => {
    const result = await next(e)
    if (e.agentId === undefined && e.usage !== undefined) {
      const now = await $.clock.now()
      await update($, lastReplyAt, () => now)
      await update($, cold, () => null)
      await update($, isHidden, () => false)
      await $.store.set(PREFIX + (await $.session.id()), now)
    }
    return result
  })

  on('command.run', { command: 'cache' }, async $ => {
    const last = await read($, lastReplyAt)
    if (last === null) return { text: 'No reply yet in this conversation, so there is no cache to keep warm.' }
    const minutes = await read($, cacheMinutes)
    const ttl = minutes * 60_000
    const idle = (await $.clock.now()) - last
    const tokens = (await $.session.usage()).context.tokens
    const size = tokens === undefined ? 'its size is not known yet' : `about ${tokensText(tokens)} tokens`
    if (idle < ttl) {
      const left = Math.max(1, Math.ceil((ttl - idle) / 60_000))
      return {
        text: `Warm. The last reply was ${idleText(Math.floor(idle / 60_000))} ago. The cache lasts ${lifetimeText(minutes)}, so it should hold for about ${left} more min. The conversation is ${size}.`,
      }
    }
    const note = await commitNote($, last)
    return {
      text: `Cold. No reply for ${idleText(Math.floor(idle / 60_000))}, longer than the cache holds — ${lifetimeText(minutes)}. The next message re-reads the whole conversation, ${size}.${note ? ` ${commitLine(note)}` : ''}`,
    }
  })

  on('ui.render', { component: 'AbovePrompt' }, async ($, e, next) => {
    if (e.props.hasSurvey || e.props.isWorking) return next(e)
    const state = await read($, cold)
    if (state === null || (await read($, isHidden))) return next(e)
    const minutes = await read($, cacheMinutes)

    const { Box, Button, Text } = $.ui.resolve(e)

    return (
      <Box flexDirection="column" gap={1}>
        <Text wrap="wrap">
          <Text bold>Cold start.</Text> No reply in this conversation for {idleText(state.idleMinutes)}, longer
          than its cache holds — {lifetimeText(minutes)}. Your next message makes Claude re-read all of it,
          about {tokensText(state.tokens)} tokens. For a new piece of work, a fresh conversation starts far smaller.
        </Text>
        {state.commit ? <Text wrap="wrap">{commitLine(state.commit)}</Text> : null}
        <Button key="hide" label="Got it" onPress={() => update($, isHidden, () => true)} />
      </Box>
    )
  })
}
