# Advisor risk and explanation audit ? 2026-11-12

## Result

All 100 students across all four CSV advisors were audited. No calculation, identity-link or SHAP reconstruction mismatch was found. The work corrected explanation semantics; it did not retrain, recalibrate or improve measured predictive accuracy. Sarah (advisor 201) is the detailed review below. Snapshot: 2027-02-16 end-of-day UTC.

## Verified scope

- 100 student records, 800 enrollments, 179 current real-model predictions/explanations and 621 correctly unscored historical enrollments.
- Independent UTC calculations matched all 16 model features for every current course. 8788 future-dated activity/submission records were excluded.
- All SHAP raw-score sums and reconstructed calibrated probabilities matched the actual model; maximum raw reconstruction error 4.44e-16.
- Forced recomputation and cached responses agreed. Every source feature/input and received/late submission count matched the explanation payload. Dashboard/list/report attention counts and reasons agreed.
- Model and calibration hashes still match FINAL_EXPERIMENT_V1.json. All 44 of Sarah's probabilities are exactly unchanged from the pre-fix audit.

## Explanation defects corrected

1. Positive resource-use contributions could produce a concern paragraph even when they did not establish difficulty. Resource-count-only counterpoints now remain neutral in all 27 such current courses across the population. Other strongest evidence remains visible; contributions are not hidden or re-signed.
2. Lateness rates based on small samples were displayed only as percentages. Verified descriptive counts now support statements such as All 3 received submissions were late, without changing model features.
3. A null lateness rate when no submissions existed was incorrectly described as missing records. Complete-feed no-submission cases now explicitly say no submissions have been received, preserve overdue-work follow-up, and do not imply reassurance.
4. Zero-day recency used awkward 0 days earlier wording. The paragraph now identifies the day covered by the assessment. Weekly resource-use changes now state whether counts rose, fell or were unchanged.
5. The former main concern sentence could overstate the ranking when lateness outweighed overdue work. The paragraph now describes both issues without making that ranking claim.

## Sarah: every assigned record

The attention label is the shared administrative/evidence rule, not a probability band. Historical GPA and failed/repeated attempts do not enter this frozen model. Different course probabilities and academic flags are therefore not automatically inconsistent.

| Student | Academic review | Enrollments | Current course estimates | Source evidence by current course |
|---|---|---:|---|---|
| [Santos Shel](http://127.0.0.1:5178/advisor/advisees/101) | Needs attention | 8 | CS620: 59.3% | CS620: 1 overdue; 3/3 received late; 15 active days / 28 |
| [Dara Vale](http://127.0.0.1:5178/advisor/advisees/10003) | Needs attention | 10 | CS799: 54.4% | CS799: 2 overdue; 0/2 received late; 8 active days / 28 |
| [Harper Vale](http://127.0.0.1:5178/advisor/advisees/10007) | Needs attention | 10 | CS799: 90.0% | CS799: 3 overdue; 1/1 received late; 5 active days / 28 |
| [Avery Brook](http://127.0.0.1:5178/advisor/advisees/10011) | No current flags | 10 | CS799: 18.8% | CS799: 0 overdue; 1/4 received late; 23 active days / 28 |
| [Ember Brook](http://127.0.0.1:5178/advisor/advisees/10015) | Needs attention | 10 | CS799: 64.8%; CS721: 28.0% | CS799: 3 overdue; 0/1 received late; 10 active days / 28; CS721: 0 overdue; 0/4 received late; 8 active days / 28 |
| [Indigo Brook](http://127.0.0.1:5178/advisor/advisees/10019) | Needs attention | 10 | CS799: 57.2%; CS725: 76.4% | CS799: 1 overdue; 2/3 received late; 10 active days / 28; CS725: 2 overdue; 2/2 received late; 11 active days / 28 |
| [Briar Cove](http://127.0.0.1:5178/advisor/advisees/10023) | Needs attention | 8 | CS701: 37.8%; CS702: 34.6% | CS701: 1 overdue; 0/3 received late; 12 active days / 28; CS702: 0 overdue; 1/4 received late; 6 active days / 28 |
| [Finley Cove](http://127.0.0.1:5178/advisor/advisees/10027) | Needs attention | 8 | CS705: 14.6%; CS706: 62.3% | CS705: 0 overdue; 0/4 received late; 24 active days / 28; CS706: 1 overdue; 3/3 received late; 15 active days / 28 |
| [Jules Cove](http://127.0.0.1:5178/advisor/advisees/10031) | Needs attention | 8 | CS709: 71.0%; CS710: 40.1% | CS709: 2 overdue; 2/2 received late; 19 active days / 28; CS710: 1 overdue; 1/3 received late; 14 active days / 28 |
| [Cedar Moss](http://127.0.0.1:5178/advisor/advisees/10035) | Needs attention | 8 | CS713: 74.6%; CS714: 29.2% | CS713: 2 overdue; 0/2 received late; 2 active days / 28; CS714: 0 overdue; 1/4 received late; 12 active days / 28 |
| [Gray Moss](http://127.0.0.1:5178/advisor/advisees/10039) | No current flags | 8 | CS717: 36.1%; CS718: 15.5% | CS717: 0 overdue; 1/4 received late; 7 active days / 28; CS718: 0 overdue; 0/4 received late; 23 active days / 28 |
| [Kit Moss](http://127.0.0.1:5178/advisor/advisees/10043) | Needs attention | 8 | CS721: 55.2%; CS722: 21.3% | CS721: 1 overdue; 3/3 received late; 17 active days / 28; CS722: 0 overdue; 0/4 received late; 13 active days / 28 |
| [Dara Ridge](http://127.0.0.1:5178/advisor/advisees/10047) | Needs attention | 8 | CS725: 56.0%; CS726: 71.0% | CS725: 1 overdue; 3/3 received late; 16 active days / 28; CS726: 2 overdue; 1/2 received late; 4 active days / 28 |
| [Harper Ridge](http://127.0.0.1:5178/advisor/advisees/10051) | Needs attention | 8 | CS703: 24.6%; CS704: 53.0% | CS703: 0 overdue; 1/4 received late; 17 active days / 28; CS704: 1 overdue; 1/3 received late; 7 active days / 28 |
| [Avery Wren](http://127.0.0.1:5178/advisor/advisees/10055) | Needs attention | 8 | CS707: 19.6%; CS708: 17.6% | CS707: 0 overdue; 1/4 received late; 22 active days / 28; CS708: 0 overdue; 0/4 received late; 20 active days / 28 |
| [Ember Wren](http://127.0.0.1:5178/advisor/advisees/10059) | Needs attention | 8 | CS711: 28.1%; CS712: 44.1% | CS711: 0 overdue; 1/4 received late; 14 active days / 28; CS712: 1 overdue; 2/3 received late; 21 active days / 28 |
| [Indigo Wren](http://127.0.0.1:5178/advisor/advisees/10063) | Needs attention | 8 | CS715: 44.8%; CS716: 15.7% | CS715: 1 overdue; 0/3 received late; 7 active days / 28; CS716: 0 overdue; 0/4 received late; 24 active days / 28 |
| [Briar Hollow](http://127.0.0.1:5178/advisor/advisees/10067) | Needs attention | 8 | CS719: 18.5%; CS720: 85.1% | CS719: 0 overdue; 1/4 received late; 24 active days / 28; CS720: 3 overdue; 0/1 received late; 2 active days / 28 |
| [Finley Hollow](http://127.0.0.1:5178/advisor/advisees/10071) | Needs attention | 8 | CS723: 40.9%; CS724: 55.1% | CS723: 1 overdue; 0/3 received late; 10 active days / 28; CS724: 1 overdue; 3/3 received late; 20 active days / 28 |
| [Jules Hollow](http://127.0.0.1:5178/advisor/advisees/10075) | Needs attention | 8 | CS701: 56.7%; CS702: 44.6% | CS701: 1 overdue; 3/3 received late; 16 active days / 28; CS702: 1 overdue; 1/3 received late; 12 active days / 28 |
| [Cedar Reed](http://127.0.0.1:5178/advisor/advisees/10079) | Needs attention | 8 | CS705: 31.0% | CS705: 1 overdue; 1/3 received late; 24 active days / 28 |
| [Gray Reed](http://127.0.0.1:5178/advisor/advisees/10083) | Needs attention | 8 | CS709: 70.6% | CS709: 1 overdue; 3/3 received late; 11 active days / 28 |
| [Kit Reed](http://127.0.0.1:5178/advisor/advisees/10087) | No current flags | 8 | CS713: 16.6% | CS713: 0 overdue; 0/4 received late; 21 active days / 28 |
| [Dara Grove](http://127.0.0.1:5178/advisor/advisees/10091) | Needs attention | 4 | CS714: 66.1% | CS714: 2 overdue; 0/2 received late; 4 active days / 28 |
| [Harper Grove](http://127.0.0.1:5178/advisor/advisees/10095) | Needs attention | 4 | CS501: 14.5%; CS510: 17.9%; CS620: 29.8%; CS718: 56.7% | CS501: 0 overdue; 0/4 received late; 25 active days / 28; CS510: 0 overdue; 1/4 received late; 24 active days / 28; CS620: 1 overdue; 0/3 received late; 17 active days / 28; CS718: 1 overdue; 3/3 received late; 15 active days / 28 |

## Sarah: reviewed course paragraphs

### Santos Shel ? 101

Shared academic review reason: 1 assessment remains overdue across active courses. Review the course record and discuss any barriers to completion.

**CS620 ? enrollment 303**

All 3 received submissions were late, and 1 assessment was overdue. Both late submissions and outstanding work need follow-up. Ask what is getting in the way of completing the overdue work and agree on a manageable catch-up plan.

### Dara Vale ? 10003

Shared academic review reason: 2 assessments remain overdue across active courses. Review the course record and discuss any barriers to completion.

**CS799 ? enrollment 20044**

2 assessments were overdue. Alongside this, all 2 received submissions were on time. Work that has been received does not account for the assessments still outstanding. Ask what is getting in the way of completing the overdue work and agree on a manageable catch-up plan.

### Harper Vale ? 10007

Shared academic review reason: 3 assessments remain overdue across active courses. Review the course record and discuss any barriers to completion.

**CS799 ? enrollment 20084**

3 assessments were overdue, and the received submission was late. Both late submissions and outstanding work need follow-up. Ask what is getting in the way of completing the overdue work and agree on a manageable catch-up plan.

### Avery Brook ? 10011

Shared academic review reason: No concern identified by current rules.

**CS799 ? enrollment 20124**

Learning activity was recorded on 23 days over the past four weeks. Resource-use counts point the other way in this assessment, but this does not mean that using learning resources is harmful. Counts alone do not show whether the student understands the material. Review assignment progress before deciding whether a follow-up is needed.

### Ember Brook ? 10015

Shared academic review reason: 3 assessments remain overdue across active courses. Review the course record and discuss any barriers to completion.

**CS799 ? enrollment 20163**

3 assessments were overdue. Alongside this, the received submission was on time. Work that has been received does not account for the assessments still outstanding. Ask what is getting in the way of completing the overdue work and agree on a manageable catch-up plan.

**CS721 ? enrollment 20164**

Learning activity was recorded on 8 days over the past four weeks. Alongside this, all 4 received submissions were on time. This assessment highlights the activity or submission pattern as something to explore, rather than proof that the student is disengaged. Ask how the student is managing the coursework before deciding what support would help.

### Indigo Brook ? 10019

Shared academic review reason: 3 assessments remain overdue across active courses. Review the course record and discuss any barriers to completion.

**CS799 ? enrollment 20203**

2 of 3 received submissions were late, and 1 assessment was overdue. Both late submissions and outstanding work need follow-up. Ask what is getting in the way of completing the overdue work and agree on a manageable catch-up plan.

**CS725 ? enrollment 20204**

2 assessments were overdue, and all 2 received submissions were late. Both late submissions and outstanding work need follow-up. Ask what is getting in the way of completing the overdue work and agree on a manageable catch-up plan.

### Briar Cove ? 10023

Shared academic review reason: 1 assessment remains overdue across active courses. Review the course record and discuss any barriers to completion.

**CS701 ? enrollment 20235**

1 assessment was overdue. Alongside this, all 3 received submissions were on time. Work that has been received does not account for the assessment still outstanding. Ask what is getting in the way of completing the overdue work and agree on a manageable catch-up plan.

**CS702 ? enrollment 20236**

Learning activity was recorded on 6 days over the past four weeks. Alongside this, 4 submissions were recorded. This assessment highlights the activity or submission pattern as something to explore, rather than proof that the student is disengaged. Ask how the student is managing the coursework before deciding what support would help.

### Finley Cove ? 10027

Shared academic review reason: 1 assessment remains overdue across active courses. Review the course record and discuss any barriers to completion.

**CS705 ? enrollment 20267**

Learning activity was recorded on 24 days over the past four weeks. Resource-use counts point the other way in this assessment, but this does not mean that using learning resources is harmful. Counts alone do not show whether the student understands the material. Review assignment progress before deciding whether a follow-up is needed.

**CS706 ? enrollment 20268**

All 3 received submissions were late, and 1 assessment was overdue. Both late submissions and outstanding work need follow-up. Ask what is getting in the way of completing the overdue work and agree on a manageable catch-up plan.

### Jules Cove ? 10031

Shared academic review reason: 3 assessments remain overdue across active courses. Review the course record and discuss any barriers to completion.

**CS709 ? enrollment 20299**

2 assessments were overdue, and all 2 received submissions were late. Both late submissions and outstanding work need follow-up. Ask what is getting in the way of completing the overdue work and agree on a manageable catch-up plan.

**CS710 ? enrollment 20300**

1 assessment was overdue, and 1 of 3 received submissions were late. Both late submissions and outstanding work need follow-up. Ask what is getting in the way of completing the overdue work and agree on a manageable catch-up plan.

### Cedar Moss ? 10035

Shared academic review reason: 2 assessments remain overdue across active courses. Review the course record and discuss any barriers to completion.

**CS713 ? enrollment 20331**

2 assessments were overdue, and learning activity was recorded on 2 days over the past four weeks. Work that has been received does not account for the assessments still outstanding. Ask what is getting in the way of completing the overdue work and agree on a manageable catch-up plan.

**CS714 ? enrollment 20332**

4 submissions were recorded, and a submission was recorded on the day covered by this assessment. These are reassuring parts of the activity and submission record, but they do not guarantee a successful outcome.

### Gray Moss ? 10039

Shared academic review reason: No concern identified by current rules.

**CS717 ? enrollment 20363**

Learning activity was recorded on 7 days over the past four weeks. Alongside this, 4 submissions were recorded. This assessment highlights the activity or submission pattern as something to explore, rather than proof that the student is disengaged. Ask how the student is managing the coursework before deciding what support would help.

**CS718 ? enrollment 20364**

Learning activity was recorded on 23 days over the past four weeks. Resource-use counts point the other way in this assessment, but this does not mean that using learning resources is harmful. Counts alone do not show whether the student understands the material. Review assignment progress before deciding whether a follow-up is needed.

### Kit Moss ? 10043

Shared academic review reason: 1 assessment remains overdue across active courses. Review the course record and discuss any barriers to completion.

**CS721 ? enrollment 20395**

All 3 received submissions were late, and 1 assessment was overdue. Both late submissions and outstanding work need follow-up. Ask what is getting in the way of completing the overdue work and agree on a manageable catch-up plan.

**CS722 ? enrollment 20396**

All 4 received submissions were on time, and 4 submissions were recorded. These are reassuring parts of the activity and submission record, but they do not guarantee a successful outcome.

### Dara Ridge ? 10047

Shared academic review reason: Cumulative GPA is 1.57, below 3.0.

**CS725 ? enrollment 20427**

All 3 received submissions were late, and 1 assessment was overdue. Both late submissions and outstanding work need follow-up. Ask what is getting in the way of completing the overdue work and agree on a manageable catch-up plan.

**CS726 ? enrollment 20428**

2 assessments were overdue, and learning activity was recorded on 4 days over the past four weeks. Work that has been received does not account for the assessments still outstanding. Ask what is getting in the way of completing the overdue work and agree on a manageable catch-up plan.

### Harper Ridge ? 10051

Shared academic review reason: Cumulative GPA is 1.57, below 3.0.

**CS703 ? enrollment 20459**

Learning activity was recorded on 17 days over the past four weeks. Resource-use counts point the other way in this assessment, but this does not mean that using learning resources is harmful. Counts alone do not show whether the student understands the material. Review assignment progress before deciding whether a follow-up is needed.

**CS704 ? enrollment 20460**

1 assessment was overdue, and learning activity was recorded on 7 days over the past four weeks. Work that has been received does not account for the assessment still outstanding. Ask what is getting in the way of completing the overdue work and agree on a manageable catch-up plan.

### Avery Wren ? 10055

Shared academic review reason: Term GPA fell from 1.9 to 1.4.

**CS707 ? enrollment 20491**

Learning activity was recorded on 22 days over the past four weeks. Resource-use counts point the other way in this assessment, but this does not mean that using learning resources is harmful. Counts alone do not show whether the student understands the material. Review assignment progress before deciding whether a follow-up is needed.

**CS708 ? enrollment 20492**

Learning activity was recorded on 20 days over the past four weeks, and all 4 received submissions were on time. These are reassuring parts of the activity and submission record, but they do not guarantee a successful outcome.

### Ember Wren ? 10059

Shared academic review reason: Term GPA fell from 2.9 to 1.5.

**CS711 ? enrollment 20523**

4 submissions were recorded. Resource-use counts point the other way in this assessment, but this does not mean that using learning resources is harmful. Counts alone do not show whether the student understands the material. Review assignment progress before deciding whether a follow-up is needed.

**CS712 ? enrollment 20524**

2 of 3 received submissions were late. Alongside this, learning activity was recorded on 21 days over the past four weeks. The timing of submissions is the issue to discuss, even where participation is continuing. Ask about barriers to meeting deadlines and agree on the next assignment to focus on.

### Indigo Wren ? 10063

Shared academic review reason: Term GPA fell from 2.9 to 1.5.

**CS715 ? enrollment 20555**

1 assessment was overdue. Alongside this, all 3 received submissions were on time. Work that has been received does not account for the assessment still outstanding. Ask what is getting in the way of completing the overdue work and agree on a manageable catch-up plan.

**CS716 ? enrollment 20556**

Learning activity was recorded on 24 days over the past four weeks. Resource-use counts point the other way in this assessment, but this does not mean that using learning resources is harmful. Counts alone do not show whether the student understands the material. Review assignment progress before deciding whether a follow-up is needed.

### Briar Hollow ? 10067

Shared academic review reason: Term GPA fell from 2.9 to 1.5.

**CS719 ? enrollment 20587**

Learning activity was recorded on 24 days over the past four weeks. Resource-use counts point the other way in this assessment, but this does not mean that using learning resources is harmful. Counts alone do not show whether the student understands the material. Review assignment progress before deciding whether a follow-up is needed.

**CS720 ? enrollment 20588**

3 assessments were overdue, and learning activity was recorded on 2 days over the past four weeks. Work that has been received does not account for the assessments still outstanding. Ask what is getting in the way of completing the overdue work and agree on a manageable catch-up plan.

### Finley Hollow ? 10071

Shared academic review reason: Cumulative GPA is 2.45, below 3.0.

**CS723 ? enrollment 20619**

1 assessment was overdue. Alongside this, all 3 received submissions were on time. Work that has been received does not account for the assessment still outstanding. Ask what is getting in the way of completing the overdue work and agree on a manageable catch-up plan.

**CS724 ? enrollment 20620**

All 3 received submissions were late, and 1 assessment was overdue. Both late submissions and outstanding work need follow-up. Ask what is getting in the way of completing the overdue work and agree on a manageable catch-up plan.

### Jules Hollow ? 10075

Shared academic review reason: Cumulative GPA is 2.45, below 3.0.

**CS701 ? enrollment 20651**

All 3 received submissions were late, and 1 assessment was overdue. Both late submissions and outstanding work need follow-up. Ask what is getting in the way of completing the overdue work and agree on a manageable catch-up plan.

**CS702 ? enrollment 20652**

1 assessment was overdue, and 1 of 3 received submissions were late. Both late submissions and outstanding work need follow-up. Ask what is getting in the way of completing the overdue work and agree on a manageable catch-up plan.

### Cedar Reed ? 10079

Shared academic review reason: 1 assessment remains overdue across active courses. Review the course record and discuss any barriers to completion.

**CS705 ? enrollment 20684**

1 assessment was overdue. Alongside this, learning activity was recorded on 24 days over the past four weeks. Work that has been received does not account for the assessment still outstanding. Ask what is getting in the way of completing the overdue work and agree on a manageable catch-up plan.

### Gray Reed ? 10083

Shared academic review reason: 1 assessment remains overdue across active courses. Review the course record and discuss any barriers to completion.

**CS709 ? enrollment 20716**

All 3 received submissions were late, and 1 assessment was overdue. Both late submissions and outstanding work need follow-up. Ask what is getting in the way of completing the overdue work and agree on a manageable catch-up plan.

### Kit Reed ? 10087

Shared academic review reason: No concern identified by current rules.

**CS713 ? enrollment 20748**

Learning activity was recorded on 21 days over the past four weeks. Resource-use counts point the other way in this assessment, but this does not mean that using learning resources is harmful. Counts alone do not show whether the student understands the material. Review assignment progress before deciding whether a follow-up is needed.

### Dara Grove ? 10091

Shared academic review reason: Term GPA fell from 3.0 to 2.3.

**CS714 ? enrollment 20768**

2 assessments were overdue, and learning activity was recorded on 4 days over the past four weeks. Work that has been received does not account for the assessments still outstanding. Ask what is getting in the way of completing the overdue work and agree on a manageable catch-up plan.

### Harper Grove ? 10095

Shared academic review reason: 2 assessments remain overdue across active courses. Review the course record and discuss any barriers to completion.

**CS501 ? enrollment 20781**

Learning activity was recorded on 25 days over the past four weeks. Resource-use counts point the other way in this assessment, but this does not mean that using learning resources is harmful. Counts alone do not show whether the student understands the material. Review assignment progress before deciding whether a follow-up is needed.

**CS510 ? enrollment 20782**

Learning activity was recorded on 24 days over the past four weeks. Resource-use counts point the other way in this assessment, but this does not mean that using learning resources is harmful. Counts alone do not show whether the student understands the material. Review assignment progress before deciding whether a follow-up is needed.

**CS620 ? enrollment 20783**

1 assessment was overdue. Alongside this, learning activity was recorded on 17 days over the past four weeks. Work that has been received does not account for the assessment still outstanding. Ask what is getting in the way of completing the overdue work and agree on a manageable catch-up plan.

**CS718 ? enrollment 20784**

All 3 received submissions were late, and 1 assessment was overdue. Both late submissions and outstanding work need follow-up. Ask what is getting in the way of completing the overdue work and agree on a manageable catch-up plan.

## Predictive accuracy: what is known

The original final OULAD report was reviewed, not rerun for model selection. The reserved test cohort has already been consumed. Pooled ROC-AUC was 0.85348 and AP 0.83876, but these pooled values must not be represented as early-course accuracy. At day 28, the relevant stage for this demo, ROC-AUC was 0.66905, AP 0.59799 and Brier loss 0.24077. Mean predicted risk was 0.53355 versus observed outcomes 0.39115: early overestimation remains a material limitation. These are OULAD results, not AcadMate institutional results.

Synthetic activity patterns were generated independently of academic outcomes. There is no outcome truth for these current synthetic course trajectories. Accuracy, precision, recall, calibration or advisor-impact claims cannot be calculated meaningfully for them by treating scenario labels or historical grades as future outcomes. No probabilities, coefficients, calibration maps or thresholds were adjusted. Meaningful future model improvement needs an approved training/evaluation plan and a fresh held-out evaluation, not tuning against this demo or the consumed test cohort.

## Remaining review points

- GPA/repeat handling remains the existing backend convention and requires team policy confirmation. The model has no GPA or score inputs; changing those academic policies would not fix its transfer/calibration limitations.
- Timely received work and overdue unreceived work can coexist. Paragraphs now preserve this distinction.
- Suggestions are advisor discussion prompts, not proven interventions or causal explanations. No automated alert cutoff is introduced.
- Synthetic source coverage is complete by construction; real institutional source coverage and transfer validity are not established.

## Checks and reproduction

Backend regression run: 361 passed; the additional CSV login-scope test initially exposed a subprocess import-path issue, which was fixed and then passed separately. ML suite: 52 passed. Existing frontend inference tests: 3 passed. Exhaustive actual-narrative test: 1 passed, covering all 179 current explanations plus edge cases. Production build passed with the existing chunk-size warning.

```powershell
$snapshot = 'ml/outputs/main-integration/8c4b0843368b'
$python = '.\ml\outputs\main-integration\8c4b0843368b\.venv\Scripts\python.exe'
& $python tools/audit_csv_advisor.py --snapshot $snapshot --advisor-id 201
```

Ignored machine-readable reports are advisor-201-audit.json, the other advisor audit JSONs and reviewed-course-narratives.json under the isolated snapshot. Academic data was read-only during the audit; normal local login/session records were created by API tests. No commits or pushes.
