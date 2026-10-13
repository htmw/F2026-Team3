# Shared components

Build every screen from these pieces. Visual reference: run `npm run dev` and open
<http://localhost:5173/dev/ui> (dev only, not in production builds). Design rules live in
`.claude/specs/00-shared-design-system.md`.

## Data (`src/lib/`)

| Export | Use |
|---|---|
| `useApi(path)` → `{ data, error, loading, reload, setData }` | Every screen's GET. Aborts on unmount/path change; `path = null` skips. Render `ErrorState` → `Loading` → content. |
| `api(path, { method, body, signal, contentType })` | Mutations. JSON by default; `contentType: 'text/csv'` sends a string/File as-is (CSV imports). Throws `ApiError` (`status`, `code`, `message`, `details`). |
| `apiUrl(path)` | Absolute URL for browser-followed links: `<Button href={apiUrl('/admin/audit.csv')} download>`. |
| `errorText(err)` | `ApiError` message plus any per-field `details`, for a toast or `Notice`. |
| `useDebounced(value, ms)` | Search box → `?q=` param. |

After a mutation that changes a sidebar count, call `refreshBadges()` from `useAuth()`.

## UI (`components/ui/`)

| Component | Props / notes |
|---|---|
| `Card`, `CardHeader` | `dark`, `as`; header has `title`, `subtitle`, `action`. |
| `Button` | `variant`: primary, secondary, google, disabled, sun, mint, ghostDark, danger · `size`: lg/md/sm · `to` (router link) or `href` (plain link). |
| `Pill`, `Chip`, `PILL_TONES` | `tone`: teal (done/good), indigo (info), amber (pending/warning), gray (neutral), pink (needs attention). |
| `Avatar`, `initialsOf`, `toneFor` | `name` or `initials`, optional `tone` (defaults to a stable tone per name), `size` sm/md/lg. |
| `SegmentedTabs` (`Tabs.jsx`) | `options` (strings or `{ value, label, count }`), `value`, `onChange`, `label`. Use for every tab/filter row. |
| `Switch`, `SwitchRow` | `checked`, `onChange(next)`, `label`/`id`, `disabled`; row adds `description`. |
| `Field`, `TextInput`, `Select`, `Textarea`, `INPUT` | `Field` takes `id`, `label`, `aside`, `hint`, `error` and wires `aria-describedby`. |
| `SearchInput` | `label`, `placeholder`, `value`, `onChange(text)`. Also via `PageHeader`'s `search` prop. |
| `Notice` | `tone` amber/teal/pink/indigo, optional `icon`. Inline warnings, pre-check and import results, form errors. |
| `ProgressBar` | `value` 0–100, `color`, `height`, `label`. |
| `BarChart` | `data: [{ label, value, highlight }]`, `max`, `unit`, `label`. Div bars; no chart library. |
| `Dialog` | `open`, `onClose`, `title`, `actions`. Native `<dialog>` (Esc, focus trap, backdrop). |
| `useToast().show({ message, actionLabel, onAction, duration })` | One toast at a time; e.g. "Approved — Undo". |
| `Loading`, `ErrorState`, `Empty` | The three data states + empty-list line. |
| `ChatBubble` | `mine` (right-aligned, dark), `name` (sender label above, for group chats), `time`. One chat message; AI answers use `AiMessage` instead. |
| `Icon` | `name`, `size`, `color` (hex or `var(--color-*)`). Add new paths to `PATHS`/`CIRCLES` rather than adding a library. |

## AI (`components/ai/`)

| Component | Use |
|---|---|
| `AiMessage`, `SparkleTile` | An AI advisor answer: text, `PlanBlock`, follow-up, actions, "Based on" sources. Pass `onRate`/`onReport` for the student view; without them it is read-only (admin test box). |
| `PlanBlock` | `plan: [{ code, name, meta, fulfills, why, onPlan }]` rows. |
| `FlaggedAnswers` | Loads open flags and resolves them (Mark fixed / Dismiss). Used on Admin overview and AI settings. |

`lib/dates.js`: `relativeDate(iso)` → "Today", "Yesterday", "Sep 14"; `clockTime(iso)` → "15:04";
`addDays(ymd, n)`, `mondayOf(ymd)`, `shortDay(ymd, { weekday })` for `YYYY-MM-DD` dates.
`lib/status.js`: `EVENT_TYPES` / `EVENT_COLOR` (calendar colors, shared by Dashboard and Schedule).

## Messages (`components/messages/`)

Shared by student and advisor Messages screens (both use `/conversations`).

| Component | Use |
|---|---|
| `ConversationList` | `conversations` (from `GET /conversations`), `selectedId`, `onSelect(id)`. Avatar, name, role, preview, time, unread count. |
| `MessageThread` | `conversation` (a list row), `onRead(id)`, `onSent(id, message)`, `headerAction` (node), `aboveComposer(send)` (render prop, e.g. quick replies). Loads messages (which marks them read), optimistic send. Render with `key={conversation.id}`. Read-only for system conversations. |
| `Composer` | `value`, `onChange`, `onSend`, `sending`, `placeholder`. Enter sends, Shift+Enter is a new line. |
| `NewConversationDialog` | `open`, `onClose`, `onCreated(id)`. Contact search (`GET /conversations/contacts`) + optional first message. |

## Layout (`components/layout/`)

| Component | Use |
|---|---|
| `PageHeader` | `title`, `subtitle`, `initials`, `search`, `actions`. |
| `MasterDetail`, `ListRow`, `DetailEmpty` | Two-pane list/detail; `ListRow` takes `selected`, `onSelect`. Selection is local `useState`. |
| `AppShell`, `Sidebar` | Already wired per role via `config/nav.js`. |

Colors: use theme tokens (`text-muted`, `bg-amber-soft`, `var(--color-accent)` …) from `src/index.css`, not hex values.
In SVG, set token colors through `style={{ fill/stroke }}`; presentation attributes don't resolve `var()`.
