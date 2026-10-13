import Anthropic from '@anthropic-ai/sdk'
import { config } from '../../config.js'
import { unavailable } from '../../lib/errors.js'
import { logger } from '../../lib/logger.js'
import { mergedPreferences, replyStyle } from '../../lib/preferences.js'
import { claudeAnswer } from './claudeEngine.js'
import { handoffReply, matchBlockedTopic } from './guard.js'
import { rulesAnswer } from './rulesEngine.js'
import { createTools } from './tools.js'

// The AI advisor's answer pipeline: school switch → blocked topics → Claude (if configured) → rules.

export const usesClaude = (settings) => settings.engine === 'Claude' && Boolean(config.anthropic)

export function threadTitle(text) {
  const clean = String(text).replace(/\s+/g, ' ').trim()
  if (clean.length <= 60) return clean
  const cut = clean.slice(0, 60)
  return `${cut.slice(0, cut.lastIndexOf(' ') > 30 ? cut.lastIndexOf(' ') : 60)}…`
}

// `history` is the thread's earlier messages ({ role, body }), oldest first. `engines` lets tests swap in
// a stub Claude client.
export async function answer({ ctx, text, history = [], settings, tz, today }, engines = {}) {
  if (!settings.features.advisor) throw unavailable('The AI advisor is turned off for your school.')
  const started = Date.now()
  const prefs = mergedPreferences(ctx.user.preferences)
  const style = replyStyle(ctx.user.preferences, settings.style)
  const base = { sources: [], engine: 'rules', model: null, usage: null }

  if (matchBlockedTopic(text, settings.blockedTopics)) {
    return { ...handoffReply(), ...base, latencyMs: Date.now() - started }
  }

  const args = { ctx, text, history, settings, prefs, style, tz, today }
  if (usesClaude(settings) || engines.claude) {
    const tools = createTools(args)
    try {
      return await claudeAnswer({ ...args, tools }, engines.claude)
    } catch (err) {
      const level = err instanceof Anthropic.APIError ? 'warn' : 'error'
      logger[level]('Claude answer failed; using rule-based answer', { error: err.message, status: err.status })
    }
  }
  const tools = createTools(args)
  const reply = await rulesAnswer({ ...args, tools })
  return { ...reply, ...base, sources: [...tools.used], latencyMs: Date.now() - started }
}
