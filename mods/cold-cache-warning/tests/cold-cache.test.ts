import { expect, mock, test } from 'claude-code/testing'
import type { Engine } from 'claude-code/testing'
import type { On, RenderElement } from 'claude-code'

const PLUGIN = 'cold-cache-warning'
const START = Date.UTC(2026, 9, 10, 9, 0)
const MIN = 60_000
const BAND = {
  plugin: PLUGIN,
  component: 'AbovePrompt',
  props: { hasSurvey: false, isWorking: false, maxRows: 10, bodyColumns: 100, scroll: { offset: 0, bodyRows: 10 }, view: {} },
} as const

const STATE_FILE = '/Users/test/.config/moblee/state/turn-end-commit.json'
const MINUTES_FILE = '/Users/test/.config/moblee/cache-minutes'

// The engine beneath the mod: a session of a given size, a store, a command registry, the
// commit record the companion script leaves at ~/.config/moblee/state/turn-end-commit.json, and
// the cache lifetime the owner may have written in ~/.config/moblee/cache-minutes.
function world(
  on: On,
  tokens: number | undefined,
  store: Record<string, unknown> = {},
  commits?: Record<string, unknown>,
  minutesFile?: string,
  files: Record<string, string> = {},
) {
  const clock = mock.clock(on, { now: START })
  mock.store(on, store)
  on('process.run', (_$, e) => ({
    value: { exitCode: 0, stdout: e.argv[1] === 'HOME' ? '/Users/test\n' : '', stderr: '', isStdoutTruncated: false, isStderrTruncated: false },
  }))
  on('fs.read', (_$, e) => {
    if (e.path === STATE_FILE && commits !== undefined) return { value: JSON.stringify(commits) }
    if (e.path === MINUTES_FILE && minutesFile !== undefined) return { value: minutesFile }
    const extra = files[e.path]
    if (extra !== undefined) return { value: extra }
    return { deny: 'ENOENT' }
  })
  on('session.id', () => ({ value: 'session-1' }))
  on('session.usage', () => ({ value: { startedAt: START, context: { tokens, window: 1_000_000 }, rateLimits: [] } }))
  on('command.register', (_$, e) => ({ value: { command: e.name } }))
  on('ui.render', ($, e) => h($.ui.resolve(e).Box, { key: 'engine-band' }) as RenderElement)
  on('session.start', () => ({ cwd: '/vault' }))
  on('turn.complete', (_$, e) => ({ text: e.answer }))
  return clock
}

const reply = { answer: 'done', durationMs: 1000, isAborted: false, turnId: 't1', reason: 'answer' as const,
  usage: { input_tokens: 10, output_tokens: 50, cache_read_input_tokens: 180_000, cache_creation_input_tokens: 2000, model: 'claude-opus-5-5' } }

test('a big conversation idle past the hour shows the band on both surfaces; the next reply clears it', async ($, on) => {
  const clock = world(on, 190_000)
  await $.session.start({ cwd: '/vault', surface: 'desktop', isInteractive: true })
  await $.turn.complete(reply)

  await clock.advance(59 * MIN)
  for (const surface of ['terminal', 'desktop'] as const) {
    const ui = await $.ui.mount({ ...BAND, surface })
    expect(await ui.find({ type: 'Text', text: /Cold start/ })).toBeUndefined()
    await ui.unmount()
  }

  await clock.advance(72 * MIN) // 2 h 11 min idle
  for (const surface of ['terminal', 'desktop'] as const) {
    const ui = await $.ui.mount({ ...BAND, surface })
    const text = (await ui.find({ type: 'Text', text: /Cold start/ }))?.text ?? ''
    expect(text).toMatch(/2 h 11 min/)
    expect(text).toMatch(/about 190,000\s+tokens/)
    expect(text).toMatch(/about an hour on most plans/)
    await ui.unmount()
  }

  await $.turn.complete(reply)
  const ui = await $.ui.mount({ ...BAND, surface: 'desktop' })
  expect(await ui.find({ type: 'Text', text: /Cold start/ })).toBeUndefined()
  await ui.unmount()
})

test('a small conversation never warns, however long it waits', async ($, on) => {
  const clock = world(on, 30_000)
  await $.session.start({ cwd: '/vault', surface: 'desktop', isInteractive: true })
  await $.turn.complete(reply)
  await clock.advance(5 * 60 * MIN)
  const ui = await $.ui.mount({ ...BAND, surface: 'desktop' })
  expect(await ui.find({ type: 'Text', text: /Cold start/ })).toBeUndefined()
  await ui.unmount()
})

test('Got it hides the band until the next reply', async ($, on) => {
  const clock = world(on, 190_000)
  await $.session.start({ cwd: '/vault', surface: 'desktop', isInteractive: true })
  await $.turn.complete(reply)
  await clock.advance(90 * MIN)
  const ui = await $.ui.mount({ ...BAND, surface: 'desktop' })
  expect(await ui.find({ type: 'Text', text: /Cold start/ })).toBeDefined()
  await ui.press({ key: 'hide' })
  expect(await ui.find({ type: 'Text', text: /Cold start/ })).toBeUndefined()
  await ui.unmount()
})

test('a session resumed after a restart remembers its last reply from the store', async ($, on) => {
  const clock = world(on, 190_000, { 'last-reply:session-1': START - 3 * 60 * MIN })
  await $.session.start({ cwd: '/vault', surface: 'desktop', isInteractive: true })
  await clock.settle()
  const ui = await $.ui.mount({ ...BAND, surface: 'desktop' })
  expect((await ui.find({ type: 'Text', text: /Cold start/ }))?.text ?? '').toMatch(/3 h/)
  await ui.unmount()
})

const askCache = ($: Engine) =>
  $.command.run({ command: 'cache', args: '', origin: { kind: 'composer' }, presentation: { isFullscreen: false, columns: 100 } })

test('/cache reports warm, then cold', async ($, on) => {
  const clock = world(on, 190_000)
  await $.session.start({ cwd: '/vault', surface: 'desktop', isInteractive: true })
  await $.turn.complete(reply)
  await clock.advance(20 * MIN)
  const warm = await askCache($)
  expect(warm.text).toMatch(
    /^Warm\. The last reply was 20 min ago\. The cache lasts about an hour on most plans, so it should hold for about 40 more min\./,
  )
  await clock.advance(60 * MIN)
  const cold = await askCache($)
  expect(cold.text).toMatch(/^Cold\. No reply for 1 h 20 min, longer than the cache holds — about an hour on most plans\./)
  expect(cold.text).toMatch(/about 190,000 tokens/)
})

const AT = (ms: number) => new Date(ms).toISOString()
const commitText = async ($: Engine) => {
  const ui = await $.ui.mount({ ...BAND, surface: 'desktop' })
  const cold = await ui.find({ type: 'Text', text: /Cold start/ })
  const line = (await ui.find({ type: 'Text', text: /committed|commit/ }))?.text
  await ui.unmount()
  return { cold: cold !== undefined, line }
}

test('the band says the conversation is committed when the turn-end commit recorded it', async ($, on) => {
  const clock = world(on, 190_000, {}, { 'session-1': { state: 'committed', at: AT(START + 4000), own_left: [], other_left: [], reason: '' } })
  await $.session.start({ cwd: '/vault', surface: 'desktop', isInteractive: true })
  await $.turn.complete(reply)
  await clock.advance(75 * MIN)
  const { cold, line } = await commitText($)
  expect(cold).toBe(true)
  expect(line).toMatch(/^Everything from this conversation is committed, so it is safe to start a new one\.$/)
  const report = await askCache($)
  expect(report.text).toMatch(/Everything from this conversation is committed/)
})

test('files the commit check stopped are counted and the way forward given', async ($, on) => {
  const clock = world(on, 190_000, {}, {
    'session-1': { state: 'blocked', at: AT(START + 4000), own_left: ['wiki/log.md', 'wiki/Golf.md'], other_left: [], reason: 'G6 dangling link' },
  })
  await $.session.start({ cwd: '/vault', surface: 'desktop', isInteractive: true })
  await $.turn.complete(reply)
  await clock.advance(75 * MIN)
  const { line } = await commitText($)
  expect(line).toMatch(/^2 files this conversation edited are not committed: the vault's commit check stopped them\. In a new conversation, say "commit what the last conversation left"\.$/)
})

test('a record from an earlier reply, or none at all, adds nothing to the band', async ($, on) => {
  const clock = world(on, 190_000, {}, { 'session-1': { state: 'committed', at: AT(START - 10 * MIN), own_left: [], other_left: [], reason: '' } })
  await $.session.start({ cwd: '/vault', surface: 'desktop', isInteractive: true })
  await $.turn.complete(reply)
  await clock.advance(75 * MIN)
  const stale = await commitText($)
  expect(stale.cold).toBe(true)
  expect(stale.line).toBeUndefined()
})

test('no record file: the band is as before', async ($, on) => {
  const clock = world(on, 190_000)
  await $.session.start({ cwd: '/vault', surface: 'desktop', isInteractive: true })
  await $.turn.complete(reply)
  await clock.advance(75 * MIN)
  const none = await commitText($)
  expect(none.cold).toBe(true)
  expect(none.line).toBeUndefined()
})

// The record lives under ~/.config/moblee/, which both assistants share; nothing is read from or
// written to ~/.claude/.
test('a record left under ~/.claude is not read', async ($, on) => {
  const clock = world(on, 190_000, {}, undefined, undefined, {
    '/Users/test/.claude/state/turn-end-commit.json': JSON.stringify({
      'session-1': { state: 'committed', at: AT(START + 4000), own_left: [], other_left: [], reason: '' },
    }),
  })
  await $.session.start({ cwd: '/vault', surface: 'desktop', isInteractive: true })
  await $.turn.complete(reply)
  await clock.advance(75 * MIN)
  const { cold, line } = await commitText($)
  expect(cold).toBe(true)
  expect(line).toBeUndefined()
})

// The cache's lifetime: one hour unless ~/.config/moblee/cache-minutes says otherwise.

test('with no setting the band waits the default hour', async ($, on) => {
  const clock = world(on, 190_000)
  await $.session.start({ cwd: '/vault', surface: 'desktop', isInteractive: true })
  await $.turn.complete(reply)

  await clock.advance(55 * MIN)
  let ui = await $.ui.mount({ ...BAND, surface: 'desktop' })
  expect(await ui.find({ type: 'Text', text: /Cold start/ })).toBeUndefined()
  await ui.unmount()

  await clock.advance(10 * MIN) // 1 h 5 min idle
  ui = await $.ui.mount({ ...BAND, surface: 'desktop' })
  const text = (await ui.find({ type: 'Text', text: /Cold start/ }))?.text ?? ''
  expect(text).toMatch(/1 h 5 min/)
  expect(text).toMatch(/longer than its cache holds — about an hour on most plans\./)
  await ui.unmount()
})

test('a cache lifetime the owner set is honoured by the band and by /cache', async ($, on) => {
  const clock = world(on, 190_000, {}, undefined, '30')
  await $.session.start({ cwd: '/vault', surface: 'desktop', isInteractive: true })
  await $.turn.complete(reply)

  await clock.advance(10 * MIN)
  const warm = await askCache($)
  expect(warm.text).toMatch(
    /^Warm\. The last reply was 10 min ago\. The cache lasts about 30 min, as you have set it, so it should hold for about 20 more min\./,
  )
  let ui = await $.ui.mount({ ...BAND, surface: 'desktop' })
  expect(await ui.find({ type: 'Text', text: /Cold start/ })).toBeUndefined()
  await ui.unmount()

  await clock.advance(25 * MIN) // 35 min idle: past the owner's half hour, short of the default
  ui = await $.ui.mount({ ...BAND, surface: 'desktop' })
  const text = (await ui.find({ type: 'Text', text: /Cold start/ }))?.text ?? ''
  expect(text).toMatch(/35 min/)
  expect(text).toMatch(/longer than its cache holds — about 30 min, as you have set it\./)
  expect(text).not.toMatch(/most plans/)
  await ui.unmount()

  const cold = await askCache($)
  expect(cold.text).toMatch(/^Cold\. No reply for 35 min, longer than the cache holds — about 30 min, as you have set it\./)
})

test('a longer cache lifetime the owner set keeps the band away until it has passed', async ($, on) => {
  const clock = world(on, 190_000, {}, undefined, '180\n')
  await $.session.start({ cwd: '/vault', surface: 'desktop', isInteractive: true })
  await $.turn.complete(reply)

  await clock.advance(120 * MIN) // 2 h idle: cold on the default, warm on the owner's three hours
  let ui = await $.ui.mount({ ...BAND, surface: 'desktop' })
  expect(await ui.find({ type: 'Text', text: /Cold start/ })).toBeUndefined()
  await ui.unmount()

  await clock.advance(70 * MIN) // 3 h 10 min idle
  ui = await $.ui.mount({ ...BAND, surface: 'desktop' })
  expect((await ui.find({ type: 'Text', text: /Cold start/ }))?.text ?? '').toMatch(
    /3 h 10 min, longer than its cache holds — about 3 h, as you have set it\./,
  )
  await ui.unmount()
})

// Every way the setting can be wrong falls back to the hour rather than breaking the band.
for (const [label, contents] of [
  ['empty', ''],
  ['only spaces', '   \n'],
  ['not a number', 'an hour'],
  ['negative', '-30'],
  ['nought', '0'],
  ['not a whole number', '12.5'],
  ['absurdly long', '99999'],
  ['longer than a day', '1441'],
  ['a number with something after it', '30 minutes'],
] as const) {
  test(`a cache-minutes setting that is ${label} falls back to the hour`, async ($, on) => {
    const clock = world(on, 190_000, {}, undefined, contents)
    await $.session.start({ cwd: '/vault', surface: 'desktop', isInteractive: true })
    await $.turn.complete(reply)

    await clock.advance(45 * MIN) // still warm on the default hour
    let ui = await $.ui.mount({ ...BAND, surface: 'desktop' })
    expect(await ui.find({ type: 'Text', text: /Cold start/ })).toBeUndefined()
    await ui.unmount()

    await clock.advance(25 * MIN) // 1 h 10 min idle: cold on the default hour
    ui = await $.ui.mount({ ...BAND, surface: 'desktop' })
    const text = (await ui.find({ type: 'Text', text: /Cold start/ }))?.text ?? ''
    expect(text).toMatch(/1 h 10 min/)
    expect(text).toMatch(/about an hour on most plans/)
    await ui.unmount()
  })
}
