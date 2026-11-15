# Frontend regression fixtures

`plan-feedback.json` contains synthetic plan, degree-audit and degree-progress API responses for the returned-plan workflow. It was reduced from the existing synthetic demonstration example: the unused available-course catalogue is empty. There are no real student identities, passwords, cookies, model outputs or database connection details.

The fixture deliberately represents a historical **Changes requested** state, even when the running demo now shows **Approved**. It is test input, not a live academic record or an authoritative academic policy. Keep the completed/current/planned courses and 21/30 credit totals consistent when editing it.

`main-plan-feedback.test.js` reads this file relative to its own source, then changes its in-memory copy to Approved. It verifies feedback placement, resubmission availability, feedback removal, approved course labels and prevention of duplicate submission. It does not replay advisor decisions, read the local saved fixture or access a database.

The rendered integration test still needs the prepared team frontend because this branch keeps the team UI in the isolated main export. From the repository root, with frontend dependencies installed:

```powershell
$env:ACADMATE_MAIN_SNAPSHOT = Join-Path $PWD 'ml/outputs/main-integration/8c4b0843368b'
node --test frontend/tests/main-plan-feedback.test.js
```

The saved `plan-feedback-fixture.json` under that export is no longer required. Consolidating the team app setup is a separate integration task with Li.

For the combined team page, set `ACADMATE_EXPECT_DEGREE_PROGRESS=true` to additionally assert the degree-progress summary. Completed credits are 21/30; 9 remain before the current 3-credit course is completed, and 6 remain afterward.
