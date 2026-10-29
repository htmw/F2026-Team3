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
| `useDebounced(value, ms = 250)` | Search box → `?q=` param. |
| `useSaveState()` → `{ label, saving, run }` | Save button labels: `Save changes` → `Saving…` while `run(fn)` is pending → `Saved` for 2 s. `run` rethrows, so `.catch()` it into a `Notice`. `useFlash(ms)` is the underlying 2 s flag. |
| `optimisticAction({ setData, toast, apply, revert, request, undo, message })` (`optimistic.js`) | Optimistic change + toast with **Undo** (calls `undo`, the reverse endpoint). Rolls back and toasts `errorText` on failure. |
| `ACCENTS`, `applyAccent(hex)` (`theme.js`) | The four branding accents; `applyAccent` sets `--accent` (`AuthContext` applies `/auth/config` `accent` on load). |

After a mutation that changes a sidebar count, call `refreshBadges()` from `useAuth()`.

## UI (`components/ui/`)

| Component | Props / notes |
|---|---|
| `Card`, `CardHeader` | `dark`, `as`; header has `title`, `subtitle`, `action`. |
| `Button` | `variant`: primary, secondary, google, disabled, sun, mint, ghostDark, danger · `size`: lg/md/sm · `to` (router link) or `href` (plain link). |
| `Pill`, `Chip`, `PILL_TONES` | `tone`: teal (done/good), indigo (info), amber (pending/warning), gray (neutral), pink (needs attention), navy (current / selected). |
| `Avatar`, `initialsOf`, `toneFor` | `name` or `initials`, optional `tone` (defaults to a stable tone per name), `size` sm/md/lg. |
| `SegmentedTabs` (`Tabs.jsx`) | `options` (strings or `{ value, label, count }`), `value`, `onChange`, `label`. Use for every tab/filter row. |
| `Switch`, `SwitchRow` | `checked`, `onChange(next)`, `label`/`id`, `disabled`; row adds `description`. |
| `Field`, `TextInput`, `Select`, `Textarea`, `INPUT` | `Field` takes `id`, `label`, `aside`, `hint`, `error` and wires `aria-describedby`. |
| `SearchInput` | `label`, `placeholder`, `value`, `onChange(text)`, `onSubmit(text)` (Enter). Also via `PageHeader`'s `search` prop. |
| `Notice` | `tone` amber/teal/pink/indigo, optional `icon`. Inline warnings, pre-check and import results, form errors. |
| `StatTile` | `label`, `value`, `pill` (`{ tone, text }`), `pct` (bar only when set), `warn` (amber bar), `color` (`violet` / `amber` bar), `note`, `basis` (flex-basis, default 170px). Summary tiles on dashboards (student, advisor, admin), degree plan, assignments. |
| `ProgressBar` | `value` 0–100, `color`, `secondary` (second segment, e.g. in progress), `secondaryColor` (default: lighter `color`), `height`, `label`. |
| `BarChart` | `data: [{ label, value, highlight }]`, `max`, `unit`, `label`. Div bars; no chart library. |
| `ExportButton` | `href` (`apiUrl('/…csv')`), `label` (`Export CSV`), `doneLabel` (`Exported`, shown 2 s after a click). |
| `ColorSwatches` | `label`, `value`, `onChange(hex)`, `options` (`ACCENTS`). Radio group of colour dots (arrow keys select, 4 px navy ring on the selected one, `aria-label` "Teal (selected)"). Admin settings branding. |
| `ConfirmInline` | Two-step destructive confirm, never `window.confirm`: `label`, `warning`, `confirmLabel`, `busyLabel`, `onConfirm` (resolve `false` to stay open), `busy`, `disabled`, `triggerVariant` (danger), `children` (e.g. password field). |
| `Dialog` | `open`, `onClose`, `title`, `actions`. Native `<dialog>` (Esc, focus trap, backdrop). |
| `useToast().show({ message, actionLabel, onAction, duration })` | One toast at a time; e.g. "Approved — Undo". |
| `Loading`, `ErrorState`, `Empty` | The three data states + empty-list line. |
| `ChatBubble` | `mine` (right-aligned, dark), `name` (sender label above, for group chats), `time`. One chat message; AI answers use `AiMessage` instead. |
| `Icon` | `name`, `size`, `color` (hex or `var(--color-*)`). Add new paths to `PATHS`/`CIRCLES` rather than adding a library. |
| `Breadcrumb` | `items: [{ label, to? }]`. `nav aria-label="Breadcrumb"`; the last item is the current page (`aria-current`). Above a `PageHeader` on detail screens (advisor student record). |

## Settings (`components/settings/`)

| Component | Use |
|---|---|
| `SectionNav` | `sections: [{ id, label }]`. Section links that highlight the section nearest the top (sticky column on wide screens). Student and advisor Settings. |
| `SaveBar` | `dirty`, `saving`, `label` (from `useSaveState`), `error`, `onSave`, `onDiscard`. Sticky Save / Discard bar for a settings draft. |

## Meetings (`components/meetings/`)

| Component | Use |
|---|---|
| `OptionPills` | `options`, `value`, `onChange`, `label`; `multiple` makes `value` an array (office-hour days). Choice buttons with `aria-pressed`. Student Book a meeting, advisor Meetings. |
| `SlotGrid` | `slots: [{ startsAt, time, taken? }]`, `value`, `onChange(startsAt)`. Taken slots are struck through and disabled. |
| `BookForStudentDialog` | `open`, `onClose`, `onBooked(row)`, `today`, `studentId` (preselected). Advisee search, day, the advisor's free slots for that student, format, topic → `POST /advisor/meetings`. |

## Academics (`components/academics/`)

| Component | Use |
|---|---|
| `RequirementBars`, `RequirementBar` | Requirement groups with a stacked bar (done accent, in progress teal-bright). `RequirementBars` takes `groups: [{ title, count, done, inProgress, required }]` (advisor student record); `RequirementBar` is one row and renders `children` under the bar (student degree plan's course list). |

## AI (`components/ai/`)

| Component | Use |
|---|---|
| `AiMessage`, `SparkleTile` | An AI advisor answer: text, `PlanBlock`, follow-up, actions, "Based on" sources. Pass `onRate`/`onReport` for the student view; without them it is read-only (admin test box). |
| `PlanBlock` | `plan: [{ code, name, meta, fulfills, why, onPlan }]` rows. |
| `FlaggedAnswers` | Loads open flags and resolves them (Mark fixed / Dismiss, Undo reopens). Full list on AI settings (`id="flags"`, scrolls there for `/admin/ai#flags`); `compact` is the Admin overview card (first 4, "{open} open · {resolved} resolved", View all link). |

`lib/dates.js`: `relativeDate(iso)` → "Today", "Yesterday", "Sep 14"; `clockTime(iso)` → "15:04";
`addDays(ymd, n)`, `mondayOf(ymd)`, `shortDay(ymd, { weekday })` for `YYYY-MM-DD` dates.
`lib/status.js`: `EVENT_TYPES` / `EVENT_COLOR` (calendar colors, shared by Dashboard and Schedule); `ROLE_TONE` / `USER_STATUS_TONE` (admin users: role and account status pills, avatar tint); `CAPACITY_TONE` (admin advisors: caseload status pills).

## Admin (`components/admin/`)

| Component | Use |
|---|---|
| `SystemStatus` | `systems: [{ key, name, detail, status }]`, status `Healthy` / `Degraded` / `Down` / `Off` → dot + pill (teal / amber / pink / gray). List only; wrap it in a `Card`. Admin overview and Integrations (spec 35). |
| `InvitePanel` | `onDone`, `onCancel`. Emails (comma, space or newline separated, deduped by `parseEmails`) + Invite as Student / Advisor / Admin → `POST /admin/users/invite`; `role="status"` notice with sent count and skipped addresses. |
| `ImportPanel` | `onDone`, `onCancel`. `.csv` ≤ 1 MB picked through a hidden file input → raw `text/csv` `POST /admin/users/import`; notice with the imported count and skipped lines. |

## Messages (`components/messages/`)

Shared by student and advisor Messages screens (both use `/conversations`).

| Component | Use |
|---|---|
| `ConversationList` | `conversations` (from `GET /conversations`), `selectedId`, `onSelect(id)`. Avatar, name, role, preview, time, unread count. |
| `MessageThread` | `conversation` (a list row), `onRead(id)`, `onSent(id, message)`, `headerAction` (node), `aboveComposer(send)` (render prop, e.g. quick replies). Loads messages (which marks them read), optimistic send. Render with `key={conversation.id}`. Read-only for system conversations. |
| `Composer` | `value`, `onChange`, `onSend`, `sending`, `placeholder`. Enter sends, Shift+Enter is a new line. |
| `MessagesPage` | The whole Messages screen (search, list, thread, mark read, reply previews, New message dialog). `actions({ openNew })`, `headerActionFor(c)`, `readOnlyActionFor(c)`, `aboveComposerFor(c, send)`, `subtitle(unread)`, `searchLabel` / `searchPlaceholder`, `select` (`{ id }`, a new object selects that conversation and reloads). Student and advisor Messages are thin wrappers. |
| `QuickReplies` | `replies`, `onPick(text)` (pass `MessageThread`'s `send`: sends at once), `disabled`. Chips above the advisor composer. |
| `NewConversationDialog` | `open`, `onClose`, `onCreated(id)`. Contact search (`GET /conversations/contacts`) + optional first message. |

## Layout (`components/layout/`)

| Component | Use |
|---|---|
| `PageHeader` | `title`, `subtitle`, `initials`, `search`, `actions`. |
| `MasterDetail`, `ListRow`, `DetailEmpty` | Two-pane list/detail (`wideList` gives the list 3/5 of the width); `ListRow` takes `selected`, `onSelect`. Selection is local `useState`. |
| `AppShell`, `Sidebar` | Already wired per role via `config/nav.js`. |

Tap targets: controls are at least 44 px tall (`min-h-11`). When the design draws a smaller icon button or `size="sm"` button, add the `hit-44` utility (`index.css`): it grows the hit area without changing the look.

Colors: use theme tokens (`text-muted`, `bg-amber-soft`, `var(--color-accent)` …) from `src/index.css`, not hex values.
In SVG, set token colors through `style={{ fill/stroke }}`; presentation attributes don't resolve `var()`.
