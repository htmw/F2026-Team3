"""Read original OULAD ZIPs and build weekly as-of enrollment snapshots."""
import argparse
import csv
import hashlib
import io
import json
from collections import Counter, defaultdict
from pathlib import Path
from zipfile import ZipFile

KEY = ('code_module', 'code_presentation', 'id_student')
HEADERS = {
    'courses': ['code_module', 'code_presentation', 'module_presentation_length'],
    'studentInfo': [*KEY, 'final_result'],
    'studentRegistration': [*KEY, 'date_registration', 'date_unregistration'],
    'assessments': ['id_assessment', 'code_module', 'code_presentation', 'assessment_type', 'date'],
    'studentAssessment': ['id_assessment', 'id_student', 'date_submitted', 'is_banked', 'score'],
    'studentVle': [*KEY, 'date', 'sum_click'],
}
FEATURES = ['course_day', 'course_progress', 'window_days_28d', 'clicks_7d',
    'clicks_28d', 'active_days_7d', 'active_days_28d', 'engagement_change',
    'days_since_activity', 'no_activity', 'assessments_due', 'submissions_so_far',
    'overdue_assessments', 'late_submission_rate', 'days_since_submission', 'no_submission']
LABELS = {'Fail': 1, 'Withdrawn': 1, 'Pass': 0, 'Distinction': 0}


def key(row):
    return tuple(row[k] for k in KEY)


def integer(value):
    return None if value == '' else int(value)


class Archive:
    def __init__(self, path):
        self.path = Path(path)
        self.counts = Counter()

    def rows(self, table):
        with ZipFile(self.path) as archive:
            matches = [n for n in archive.namelist() if Path(n).name == table + '.csv']
            if len(matches) != 1:
                raise ValueError(f'Expected exactly one {table}.csv')
            with archive.open(matches[0]) as stream:
                reader = csv.DictReader(io.TextIOWrapper(stream, encoding='utf-8-sig'))
                missing = set(HEADERS[table]) - set(reader.fieldnames or [])
                if missing:
                    raise ValueError(f'{table}: missing columns {sorted(missing)}')
                for row in reader:
                    self.counts[table] += 1
                    yield row


def unique(rows, make_key, table):
    result = {}
    for row in rows:
        k = make_key(row)
        if k in result:
            raise ValueError(f'{table}: duplicate key {k}')
        result[k] = row
    return result


def snapshot(day, length, activity, submissions, scheduled):
    """Pure as-of features. Scores and outcomes are deliberately not accepted."""
    daily = {d: clicks for d, clicks in activity.items() if 0 <= d <= day}
    recent = lambda width: {d: c for d, c in daily.items() if d >= max(0, day-width+1)}
    a7, a28 = recent(7), recent(28)
    positive = [d for d, c in daily.items() if c > 0]
    observed = [(aid, submitted, due) for aid, submitted, due in submissions if submitted <= day]
    submitted_ids = {aid for aid, _, _ in observed}
    due_ids = {aid for aid, due in scheduled if due is not None and 0 <= due <= day}
    known_due = [(submitted, due) for _, submitted, due in observed if due is not None]
    last_submission = max((submitted for _, submitted, _ in observed), default=None)
    return dict(zip(FEATURES, [day, day/length, min(28, day+1),
        sum(a7.values()), sum(a28.values()), sum(c > 0 for c in a7.values()),
        sum(c > 0 for c in a28.values()),
        sum(a7.values()) - sum(c for d, c in daily.items() if day-13 <= d <= day-7) if day >= 13 else None,
        day-max(positive) if positive else None, int(not positive), len(due_ids),
        len(submitted_ids), len(due_ids-submitted_ids),
        sum(submitted > due for submitted, due in known_due)/len(known_due) if known_due else None,
        day-last_submission if last_submission is not None else None, int(not observed)]))


def build(source, output):
    """Stream VLE input, aggregate by enrollment/day, emit separate features/labels."""
    if output.exists():
        raise ValueError('Output directory already exists; refusing to overwrite')
    archive = Archive(source)
    courses = unique(archive.rows('courses'), lambda r: (r['code_module'], r['code_presentation']), 'courses')
    students = unique(archive.rows('studentInfo'), key, 'studentInfo')
    registrations = unique(archive.rows('studentRegistration'), key, 'studentRegistration')
    if set(students) != set(registrations):
        raise ValueError('Student and registration keys differ')
    assessments = unique(archive.rows('assessments'), lambda r: r['id_assessment'], 'assessments')
    schedules = defaultdict(list)
    for aid, row in assessments.items():
        if (row['code_module'], row['code_presentation']) not in courses:
            raise ValueError('Assessment references unknown course')
        if row['assessment_type'] != 'Exam':
            schedules[row['code_module'], row['code_presentation']].append((aid, integer(row['date'])))
    submissions = defaultdict(list)
    excluded = Counter()
    seen = set()
    for row in archive.rows('studentAssessment'):
        aid = row['id_assessment']
        if aid not in assessments:
            raise ValueError('Unknown assessment')
        pair = (aid, row['id_student'])
        if pair in seen:
            raise ValueError('Duplicate student assessment')
        seen.add(pair)
        assessment = assessments[aid]
        k = (assessment['code_module'], assessment['code_presentation'], row['id_student'])
        if k not in students:
            raise ValueError('Submission references unknown enrollment')
        if row['is_banked'] not in {'0', '1'}:
            raise ValueError('Invalid banked flag')
        if row['is_banked'] == '1' or assessment['assessment_type'] == 'Exam':
            excluded['banked_or_exam_submissions'] += 1
            continue
        submitted = integer(row['date_submitted'])
        if submitted is None:
            excluded['missing_submission_date'] += 1
            continue
        submissions[k].append((aid, submitted, integer(assessment['date'])))
    activity = defaultdict(Counter)
    for row in archive.rows('studentVle'):
        k = key(row)
        if k not in students:
            raise ValueError('Activity references unknown enrollment')
        day, clicks = int(row['date']), int(row['sum_click'])
        if clicks < 0:
            raise ValueError('Negative clicks')
        if day < 0:
            excluded['negative_day_activity_rows'] += 1
        else:
            activity[k][day] += clicks
    # All required feeds have been read successfully before any output is created.
    output.mkdir(parents=True)
    emitted = Counter()
    outcomes = Counter()
    with (output/'features.csv').open('w', newline='', encoding='utf-8') as f, (output/'labels.csv').open('w', newline='', encoding='utf-8') as l:
        fw = csv.DictWriter(f, fieldnames=[*KEY, 'snapshot_day', *FEATURES])
        lw = csv.DictWriter(l, fieldnames=[*KEY, 'snapshot_day', 'final_result', 'at_risk'])
        fw.writeheader(); lw.writeheader()
        for k in sorted(students):
            student, registration = students[k], registrations[k]
            if student['final_result'] not in LABELS:
                raise ValueError('Unknown outcome')
            if k[:2] not in courses:
                raise ValueError('Enrollment references unknown course')
            length = int(courses[k[:2]]['module_presentation_length'])
            if length <= 0:
                raise ValueError('Nonpositive course length')
            start, end = integer(registration['date_registration']), integer(registration['date_unregistration'])
            if start is None:
                excluded['enrollments_missing_registration_date'] += 1
                continue
            for day in range(7, length, 7):
                if start > day:
                    excluded['snapshots_before_registration'] += 1
                    continue
                if end is not None and end <= day:
                    excluded['snapshots_at_or_after_unregistration'] += 1
                    continue
                identity = {**dict(zip(KEY, k)), 'snapshot_day': day}
                fw.writerow({**identity, **snapshot(day, length, activity.get(k, {}), submissions.get(k, []), schedules[k[:2]])})
                lw.writerow({**identity, 'final_result': student['final_result'], 'at_risk': LABELS[student['final_result']]})
                emitted[str(day)] += 1
                outcomes[student['final_result']] += 1
    with Path(source).open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    report = {'contract_version': '0.2', 'source_sha256': digest,
        'source_counts': dict(archive.counts), 'snapshot_count': sum(emitted.values()),
        'snapshots_by_day': dict(emitted), 'snapshot_outcomes': dict(outcomes),
        'exclusions': dict(excluded), 'features': FEATURES,
        'scores_enabled': False, 'split_status': 'NOT ASSIGNED; do not train on random snapshot splits',
        'limitations': ['Event-day availability assumed; delivery latency unknown',
            'Course length proxies completion time', 'No verified Brightspace mapping',
            'Source present does not establish per-enrollment telemetry completeness']}
    (output/'manifest.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build(args.source, args.output), indent=2))


if __name__ == '__main__':
    main()
