# Project help for the Sprint 2 demo

Status: enabled in the guarded local team demo, November 14, 2026. User authorized project-document retrieval for a clearly labeled demonstration. No university academic-policy corpus is approved.

## Try it

Open http://127.0.0.1:5179/student/ai-advisor while signed in as a synthetic student. Ask:

- How do I submit my degree plan in AcadMate?
- What does a course risk estimate mean?
- How do I book an advising meeting?

Supported help replies begin with Project help and quote a checked guide passage. Answers display as plain text without a guide link or technical citation details. Versions and exact line ranges remain in the backend citation metadata for verification. Ordinary student-record questions continue through the existing academic tools. For example, What is my GPA? is not intercepted by project help.

A question such as What is the minimum GPA required by university policy? declines to assert policy and directs the student to their advisor and applicable official catalog. Existing configured blocked topics still run first. No course plan is submitted and no message or meeting is created by retrieving help.

## Approved scope and provenance

The corpus at data/knowledge/project_help contains three curated guides derived from already verified project workflows: plan submission/feedback, course assessments and messages/meetings. Each Markdown file has a manifest entry with explicit project_demo scope, version, SHA-256, audiences, approval date and the user's category authorization. This is user-authorized project help, not a claim of university or team-wide academic-policy approval.

Do not auto-index the repository, technical setup files, credentials, student records or arbitrary uploads. In particular the project help corpus contains no passwords or model probabilities. The manifest is maintained through source review, not through a model response or user-supplied URL. Changed content requires review and an updated checksum. The document-approval date uses the actual UTC calendar, independently of the simulated academic prediction cutoff.

The retriever is lexical paragraph search with a two-content-token overlap minimum. It returns one verbatim excerpt, not an LLM-generated policy answer. It has no embeddings, training, external service call or new runtime dependency. Unsupported app-help queries can abstain or continue to the existing engine when they are outside its narrow help-intent routing. This is not a general semantic RAG system or proof of comprehensive language coverage.

## Integration

Authored knowledge modules live in backend/knowledge. tools/apply_project_help.py applies a guarded, repeatable overlay only to the isolated team export:

- Existing services.ai._answer runs the existing blocked-topic guard first, then opt-in project help, then the existing engine/fallback for other queries.
- Verified citations are created by the server retriever. Engine-provided citation fields are removed; generated source names cannot become verified links.
- Existing AI JSON payload stores citation metadata without a database schema change. Thread serialization and MessageOut add a citations list; existing plan/source/action fields remain intact.
- GET /api/v1/help/documents/{document_id} is authenticated and returns checked plain text with private no-store caching and nosniff. Unknown/unapproved IDs return 404; source integrity failure returns a generic 503. Corpus paths are resolved inside the fixed source directory.
- AiMessage keeps the plain-text answer and does not render citation links. The authenticated source endpoint remains available for verification.

Enable with ACADMATE_PROJECT_HELP_ENABLED=true. The local risk_mvp.team_host enables it by default; other hosts remain opt-in. Setting it false restores the original answer selection and makes source documents unavailable. Existing school-level AI disabling, quotas, source preferences and topic guards remain in the established workflow. Project help reads no personal sources, and it does not add a new preference or treat project documents as catalog policy.

Reapply only to the intended review export, from repo root:

```powershell
python tools/apply_project_help.py --snapshot ml/outputs/main-integration/team-review-9dba938-a0c1930
```

The main team-export preparer now calls this overlay for new exports. Source changes are uncommitted and must be reviewed before shared adoption. The existing shared backend source, frozen model, calibration and original academic CSVs were not modified.

## Actual verification

- Retrieval foundation: seven unit tests passed (exact passages/line citations, approval/audience/scope/date restrictions, integrity/path checks and abstention).
- Focused project-help + existing AI/admin-AI regression: 33 passed in 10.54 seconds. A further run with the feature globally enabled also passed: 33 tests in 9.37 seconds.
- Full combined backend suite after integration: **426 passed**, zero failures/errors/skips, in 101.46 seconds. Real frozen-model smoke remained enabled. Only the dedicated local *_test database was rebuilt. JUnit: ml/outputs/project-help-backend-results-v1.xml.
- Frontend: **14 passed**, zero failures, one older standalone live-demo test skipped. Current combined live inference and new citation rendering passed. Production build passed with the existing bundle warning.
- Live local proxy verification: all three guide IDs returned exact cited passages; policy abstention, existing grade-appeal guard, authenticated source access and unchanged admin settings/student thread list passed. This used the existing non-persisting admin test box. Persisted student conversation/citation behavior was exercised separately on the disposable pytest database, not the working demo. Latest evidence: ml/outputs/project-help-live-v2.json (the v1 result is preserved). The follow-up guide was clarified to distinguish student booking from advisor scheduling; the latest live check also verifies the student-specific booking passage. The final guide text passed the live citation checks. A subsequent presentation-only change removed citation links and passed its focused test and build; the full backend run predates that UI change.

Subsequent Chrome review verified the student degree-plan help answer and authenticated source opening. At the user's request, the link was then removed: the focused plain-text rendering test and production build passed. No browser recheck after link removal is claimed.

Reproduce the non-persisting live proxy check with a NEW output filename:

```powershell
.\ml\outputs\handoff-venv-v1\Scripts\python.exe tools/verify_project_help_demo.py --output ml/outputs/project-help-live-new.json
```

The tool uses only existing public synthetic-demo accounts and forces Rules in the unsaved preview. It sends no external messages, calls no LLM provider and does not store chat messages or change AI settings.

## Remaining scope

S2-10 now has a working project-help retrieval/citation demonstration. Approved institutional-source ingestion, semantic retrieval, live Brightspace mapping and external provider delivery remain separate scope. The advisor follow-up policy remains a proposal, not newly approved policy. Normal team review is still required. No commit, push, merge or shared database change occurred.


Presentation update: removed the guide link and version/line details from AI replies at the user's request. Backend retrieval and stored citation metadata are preserved.
