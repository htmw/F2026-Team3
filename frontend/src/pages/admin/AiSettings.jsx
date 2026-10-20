import { useState } from 'react'
import PageHeader from '../../components/layout/PageHeader.jsx'
import AiMessage from '../../components/ai/AiMessage.jsx'
import FlaggedAnswers from '../../components/ai/FlaggedAnswers.jsx'
import Button from '../../components/ui/Button.jsx'
import Card, { CardHeader } from '../../components/ui/Card.jsx'
import { Field, Select, TextInput } from '../../components/ui/Field.jsx'
import Icon from '../../components/ui/Icon.jsx'
import Notice from '../../components/ui/Notice.jsx'
import { SwitchRow } from '../../components/ui/Switch.jsx'
import SegmentedTabs from '../../components/ui/Tabs.jsx'
import { Empty, ErrorState, Loading } from '../../components/ui/Status.jsx'
import { useToast } from '../../components/ui/Toast.jsx'
import { useAuth } from '../../auth/AuthContext.jsx'
import { api } from '../../lib/api.js'
import { useApi } from '../../lib/useApi.js'
import { useSaveState } from '../../lib/useSaveState.js'

const FEATURES = [
  ['advisor', 'AI advisor', 'Students can ask Acadmate questions. Turning this off shows them a "book a meeting" banner instead.'],
  ['planSuggestions', 'Course-plan suggestions', 'Answers may propose courses for a student’s plan.'],
  ['gradeInsights', 'Grade-based insights', 'Answers may use grades and GPA.'],
  ['proactiveTips', 'Proactive dashboard tips', 'Show the next-term recommendation on student dashboards.'],
]
const SOURCES = [
  ['catalog', 'Course catalog', 'Courses, prerequisites and when they are offered.'],
  ['audits', 'Degree audits', 'Requirements, credits, plans and expected graduation.'],
  ['grades', 'Grades', 'Course grades and GPA.'],
  ['schedules', 'Schedules', 'Classes, events and advising meetings.'],
]
const SETTING_KEYS = ['features', 'sources', 'style', 'blockedTopics', 'engine', 'dailyLimit']
const pick = (settings) => Object.fromEntries(SETTING_KEYS.map((key) => [key, settings[key]]))

function BlockedTopics({ topics, onChange }) {
  const [text, setText] = useState('')
  const add = (event) => {
    event.preventDefault()
    const topic = text.trim()
    if (topic && !topics.some((t) => t.toLowerCase() === topic.toLowerCase())) onChange([...topics, topic])
    setText('')
  }
  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap gap-2">
        {topics.map((topic) => (
          <span key={topic} className="flex items-center gap-1 rounded-full bg-pink-soft py-1 pl-3 pr-1 text-[13px] font-semibold text-pink-ink">
            {topic}
            <button type="button" aria-label={`Remove ${topic}`} onClick={() => onChange(topics.filter((t) => t !== topic))}
              className="flex size-6 cursor-pointer items-center justify-center rounded-full border-0 bg-transparent text-pink-ink hover:bg-surface">
              <Icon name="x" size={13} />
            </button>
          </span>
        ))}
      </div>
      <form className="flex gap-2" onSubmit={add}>
        <label htmlFor="ai-topic" className="sr-only">New blocked topic</label>
        <TextInput id="ai-topic" maxLength={80} value={text} onChange={(event) => setText(event.target.value)} placeholder="e.g. Housing" className="h-11" />
        <Button type="submit" variant="secondary" disabled={!text.trim()}>Add</Button>
      </form>
    </div>
  )
}

function TestBox({ settings }) {
  const students = useApi('/admin/users?role=student&pageSize=200')
  const [studentId, setStudentId] = useState('')
  const [question, setQuestion] = useState('Am I on track to graduate?')
  const [result, setResult] = useState(null)
  const [running, setRunning] = useState(false)
  const [error, setError] = useState(null)
  const chosen = studentId || students.data?.rows[0]?.id || ''

  const run = async (event) => {
    event.preventDefault()
    setRunning(true)
    setError(null)
    try {
      setResult(await api('/admin/ai/test', { method: 'POST', body: { question: question.trim(), studentId: chosen, settings: pick(settings) } }))
    } catch (err) {
      setError(err.message)
    } finally {
      setRunning(false)
    }
  }

  return (
    <Card as="section" className="gap-4">
      <CardHeader title="Test box" subtitle="Ask as a student, using the settings on this page (even unsaved ones). Nothing is stored." />
      {students.error && <Notice tone="pink">{students.error.message}</Notice>}
      <form className="flex flex-col gap-3" onSubmit={run}>
        <Field id="ai-test-student" label="Answer as">
          <Select id="ai-test-student" value={chosen} onChange={(event) => setStudentId(event.target.value)} disabled={!students.data}>
            {students.data?.rows.map((s) => <option key={s.id} value={s.id}>{s.name} · {s.dept}</option>)}
          </Select>
        </Field>
        <Field id="ai-test-question" label="Question">
          <TextInput id="ai-test-question" maxLength={1000} value={question} onChange={(event) => setQuestion(event.target.value)} />
        </Field>
        <div><Button type="submit" disabled={running || !chosen || !question.trim()}>{running ? 'Running…' : 'Run test'}</Button></div>
      </form>
      {error && <Notice tone="pink">{error}</Notice>}
      {result && (
        <div className="flex flex-col gap-2 border-t border-canvas pt-3">
          <span className="text-xs font-semibold text-muted">
            Test only, not saved · {result.engine === 'Claude' ? 'Answered by Claude' : 'Rule-based answer'}
            {!result.advisorOn && ' · Students can’t ask right now: the AI advisor is turned off'}
          </span>
          <AiMessage message={result.reply} />
        </div>
      )}
    </Card>
  )
}

export default function AdminAiSettings() {
  const { user } = useAuth()
  const toast = useToast()
  const { data, error, reload, setData } = useApi('/admin/ai/settings')
  const [form, setForm] = useState(null)
  const { label: saveLabel, saving, run } = useSaveState()
  const [saveError, setSaveError] = useState(null)

  if (error) {
    return (
      <>
        <PageHeader title="AI settings" />
        <ErrorState message={error.message} onRetry={reload} />
        {/* Flags have their own endpoint, so review stays possible when settings fail to load. */}
        <FlaggedAnswers />
      </>
    )
  }
  if (!data) return <Loading label="Loading AI settings…" />

  const current = form ?? pick(data)
  const set = (patch) => setForm({ ...current, ...patch })
  const dirty = form != null && JSON.stringify(form) !== JSON.stringify(pick(data))

  const save = () => {
    setSaveError(null)
    // The engine is only sent when it changed, so a server without a key can still save other settings.
    const { engine, ...rest } = current
    run(async () => {
      const saved = await api('/admin/ai/settings', { method: 'PATCH', body: engine === data.engine ? rest : current })
      setData(saved)
      setForm(null)
      toast.show({ message: 'AI settings saved' })
    }).catch((err) => setSaveError(err.message))
  }

  return (
    <>
      <PageHeader title="AI settings" subtitle="Control what the AI advisor can do and which student data it may use." initials={user?.initials}
        actions={<Button onClick={save} disabled={saving || !dirty} aria-live="polite">{saveLabel}</Button>} />
      {saveError && <Notice tone="pink">{saveError}</Notice>}
      {dirty && <Notice tone="indigo">You have unsaved changes. The test box already uses them.</Notice>}

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card as="section" className="gap-2">
          <CardHeader title="Features" />
          <div className="flex flex-col">
            {FEATURES.map(([key, label, description]) => (
              <SwitchRow key={key} id={`feature-${key}`} label={label} description={description} checked={current.features[key]}
                onChange={(next) => set({ features: { ...current.features, [key]: next } })} />
            ))}
          </div>
        </Card>

        <Card as="section" className="gap-2">
          <CardHeader title="Data sources" subtitle="What answers may read about a student" />
          <div className="flex flex-col">
            {SOURCES.map(([key, label, description]) => (
              <SwitchRow key={key} id={`source-${key}`} label={label} description={description} checked={current.sources[key]}
                onChange={(next) => set({ sources: { ...current.sources, [key]: next } })} />
            ))}
          </div>
        </Card>

        <Card as="section" className="gap-4">
          <CardHeader title="Answers" />
          <div className="flex flex-col gap-2">
            <span className="text-sm font-semibold">Answered by</span>
            <SegmentedTabs label="Answer engine" value={current.engine} onChange={(engine) => set({ engine })}
              options={[{ value: 'Claude', label: 'Claude (AI)' }, { value: 'Rules', label: 'Rule-based' }]} />
            {!data.claudeAvailable && (
              <span className="text-[13px] text-muted">Claude isn’t configured on the server (ANTHROPIC_API_KEY), so answers are rule-based.</span>
            )}
            {data.claudeAvailable && current.engine === 'Claude' && (
              <span className="text-[13px] text-muted">Questions and the student data needed to answer them are sent to Anthropic. Blocked topics never are.</span>
            )}
          </div>
          <div className="flex flex-col gap-2">
            <span className="text-sm font-semibold">Default reply style</span>
            <SegmentedTabs label="Reply style" options={['Concise', 'Balanced', 'Detailed']} value={current.style} onChange={(style) => set({ style })} />
            <span className="text-[13px] text-muted">Students can choose their own style in Settings.</span>
          </div>
          <Field id="ai-limit" label="Questions per student per day">
            <TextInput id="ai-limit" type="number" min={1} max={500} value={current.dailyLimit} className="max-w-[140px]"
              onChange={(event) => set({ dailyLimit: Math.max(1, Math.min(500, Number(event.target.value) || 1)) })} />
          </Field>
        </Card>

        <Card as="section" className="gap-3">
          <CardHeader title="Blocked topics" subtitle="Questions on these topics are handed to a person and never sent to the AI." />
          {current.blockedTopics.length === 0 && <Empty>No blocked topics.</Empty>}
          <BlockedTopics topics={current.blockedTopics} onChange={(blockedTopics) => set({ blockedTopics })} />
        </Card>

        <TestBox settings={current} />
        <FlaggedAnswers />
      </div>
    </>
  )
}
