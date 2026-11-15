# Remaining Sprint 2 work: retrieval, follow-up and external verification

> Current checkpoint (November 14, 2026): see [SPRINT2_HANDOFF.md](SPRINT2_HANDOFF.md) for the reconciled status. Later evidence supersedes older pending/count statements below: 433 full backend passes with advisor defaults enabled; 14 full frontend passes with one older live test skipped; final plain-text UI change passed its focused test/build. Project-help retrieval is delivered for checked project guides only, with no displayed guide links. Institutional-policy retrieval, S2-08 policy approval and team release acceptance remain pending. Earlier dated evidence is retained.

Status: November 14, 2026. Implementation baseline and prior acceptance remain in SPRINT2_HANDOFF_ACCEPTANCE.md. This document separates completed local preparation from approvals and access that cannot be supplied by code.

## Approved-document retrieval foundation

Implemented `backend/knowledge/retrieval.py` as an isolated, standard-library excerpt retriever. It returns exact source text with document ID, title, version, SHA-256 and line range. It reads only reviewed UTF-8 .md/.txt documents inside an explicit corpus root. Each document requires reviewed manifest metadata: approved flag, approval owner/date, version, effective dates, audience, scope and checksum. Changed content, path escape and malformed approval provenance fail closed. Unapproved, expired, future, wrong-audience and wrong-scope documents are excluded. No supported match returns an explicit empty result, not an invented answer.

No corpus has been approved or activated. The seven passing tests use clearly identified temporary test-only documents. Project-demo documents cannot satisfy an academic-policy request. The approved flag is workflow metadata, not an independent digital signature: the manifest must be maintained through normal restricted source review. The server must choose role/scope/date; neither a browser parameter nor an LLM should grant access.

This is lexical paragraph retrieval, not semantic understanding or a complete RAG implementation. It makes no claim that matching words establish an answer to a policy question. It does not generate academic advice, call a provider, connect to a database or modify the current AI service. Retrieved text remains untrusted evidence and cannot authorize actions or override system instructions.

Pending source decision sent to the user: use existing project documentation as a clearly labeled demonstration corpus, or provide approved academic policy/catalog text. Do not treat existing database source labels, synthetic seed references or test fixtures as an approved institutional document corpus.

After the source decision:

1. Identify exact approved document sections, version, audience and scope. For PDF/Word sources, preserve the original and review the extracted text before approving its checksum.
2. Create the reviewed manifest. Empty is the default; never auto-approve everything in a folder.
3. Coordinate with the frontend/LLM owner before integrating with their existing `services.ai` workflow. Respect existing source preferences, topic guard, role context and fallback behavior. Keep the risk explanation separate from document citations.
4. Add a small answer/citation contract with source IDs resolved by the server. Do not let generated source labels count as verified citations. Return uncertainty and advisor referral when evidence is absent or insufficient.
5. Test source disabling, expired/changed sources, irrelevant queries, citations, role restrictions and retained existing AI behavior. Only then claim S2-10 delivery.

Actual tests: `python -m unittest discover -s tests -p test_approved_retrieval.py -v` -> **7 passed**. No live retrieval API, corpus ingestion, embedding model or new dependency was added. The earlier 418-case backend checkpoint predates this isolated unregistered module and has not been rerun for it.

## Proposed Sprint 2 advisor follow-up policy

This is a concrete project proposal for user/team approval, not an approved institutional policy and not an implemented new alert system.

Purpose: help an assigned advisor decide what to review and discuss. Preserve the existing attention rules and current UI. Do not introduce high/medium/low model bands, automatic messages, enrollment restrictions, fixed outreach capacity, GPA/repeat policy or a threshold inferred from the diagnostic 0.5.

| Situation | Proposed advisor response | Evidence and limits |
|---|---|---|
| Observed overdue work | Review outstanding assessments, ask the student about barriers, and agree on a manageable next step using existing messaging or meetings. | Ground the paragraph in the actual course record. Do not diagnose disengagement or promise that a suggested action changes the probability. |
| Observed late submissions | Discuss timing and workload in context, including any work still outstanding. | Preserve actual observed counts; lateness is not proof of the cause or final outcome. |
| Lower/reassuring model contributors | Continue normal advising and read the complete academic record. | Do not describe the student as guaranteed to pass or exempt from review. |
| Resource-use counts conflict with intuitive engagement | Present the observation neutrally and consider the other recorded evidence. | A model association does not establish that using resources is harmful or itself requires intervention. |
| Incomplete required source coverage | Continue with reliable academic records and identify missing information; do not fabricate a probability. | Unknown coverage is neither zero engagement nor a reason to label a student high risk. |
| Valid score but explanation unavailable | Preserve the valid estimate, state that no verified explanation is available, and rely on the observed record for the conversation. | Do not invent reasons or treat an unexplained score as a decision mandate. |
| Student requests a plan decision | Use the existing Approvals page and academic prechecks. | Approval of course choices is separate from risk assessment, offering confirmation and registration. |

The advisor chooses whether to contact the student, what to say and when to follow up. A message is sent or a meeting booked only by the user through the existing service. No automatic intervention is introduced. Existing notes/messages/meetings can record the agreed step, but this does not establish a separate intervention-outcome tracking system.

Suggested S2-08 acceptance wording for team decision: "The MVP documents which existing evidence prompts advisor review and keeps model estimates advisory. Operational probability thresholds and capacity-based prioritization remain pending validation and approval." If the team requires numeric thresholds to close S2-08, retain it as partial rather than presenting this proposal as numeric-threshold completion.

## External integration verification boundaries

| Capability | What already has local evidence | Required next verification |
|---|---|---|
| Brightspace | Synthetic timing/activity/coverage contracts and actual model wiring. No verified live semantic mapping. | Access remains unavailable by prior project decision. Keep the connector as future scope; do not request regulated data or claim it is connected. |
| SMTP delivery | Off/connected/error handling and local mocked adapter tests; Overview now reflects integration state. | An authorized owner uses an approved test mailbox/server, sends an explicitly authorized test message, and confirms receipt. No credentials belong in chat, code, audit packages or screenshots. |
| Google/Microsoft calendar and external OAuth | Existing local callback/error/authorization contracts and mocked tests. | Authorized owner uses the institution/provider's approved test application and permitted account, checks redirect/consent/token behavior and actual calendar result. Do not claim delivery from HTTP mocks alone. |
| Claude provider | Existing allowed-record tools, topic guard and rules fallback have regression coverage. | LLM owner supplies a permitted runtime configuration and verifies an approved synthetic request plus timeout/fallback. This does not satisfy approved-document retrieval by itself. |

Do not connect or enable providers merely to clear an acceptance checkbox. Real service access and permissions are explicit external dependencies; local software preparation cannot resolve them. Keep provider test evidence separate from the existing synthetic regression evidence.

## Teammate verification package

Use ML_EXPLANATION_SETUP.md with the reviewed source candidate, original model ZIP and separate reference ZIP. The reference installer requires its reviewed loader source, not just a standalone Python attachment. Teammates run installation, pip check and the smoke verification in their own environment, then confirm exact source commit/export provenance and package hashes. The successful local fresh-venv test is not a claim that a teammate has completed this.

Acceptance reply to request from Li/Datta: source revision; Python version; dependency installation/pip-check result; artifact and reference verification; actual inference/explanation smoke result; any error code with a redacted log; local schema/crosswalk version if they test database-backed predictions. Do not request passwords, tokens or real student data.

For now, no automatic messages or files were sent, no corpus or outreach policy was approved on another person's behalf, no external service was contacted, and no commit/push/merge or database change was made.

## Project-document source decision and implementation update

The user authorized project documents for the labeled MVP demonstration. The corpus is now curated and enabled only in the guarded local team host, with opt-in integration for other hosts. Exact server-verified citations appear in the existing AI conversation UI, and source views require authentication. Institutional policy sources remain unapproved. See PROJECT_HELP.md for corpus, routing, additive API behavior, actual 426-pass full backend regression, 14-pass frontend result and live proxy verification. This supersedes the earlier no-corpus/no-API status for the project-demo scope only; it does not close institutional retrieval or approve the follow-up policy.
