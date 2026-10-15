/**
 * What the companion commit script, which runs at the end of each reply, did after the
 * conversation's last reply: how many files it left uncommitted, this conversation's own and
 * others, and why. Null when it has no record for that reply.
 */
export type CommitNote = {
  state: 'committed' | 'clean' | 'blocked' | 'busy' | 'error'
  ownLeft: number
  otherLeft: number
  reason: string
}

/** The conversation as it stands once the cache has lapsed: how long since the last reply, its size, and its commit. */
export type Cold = { idleMinutes: number; tokens: number; commit: CommitNote | null }

declare module 'claude-code' {
  interface PluginState {
    'cold-cache-warning': {
      /** When the main conversation last had a model reply, in ms since the epoch; null before the first. */
      lastReplyAt: number | null
      /** Set once the conversation has been idle past the cache's lifetime and is big enough to matter. */
      cold: Cold | null
      /** The band was dismissed; cleared by the next reply. */
      isHidden: boolean
      /**
       * How long the cache is taken to last, in minutes. One hour unless a whole number of
       * minutes was found in ~/.config/moblee/cache-minutes when the session started.
       */
      cacheMinutes: number
    }
  }
}
