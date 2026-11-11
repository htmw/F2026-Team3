"""Deterministic student-disjoint temporal partitions for OULAD snapshots."""
import argparse
import calendar
import csv
import hashlib
import json
from collections import Counter
from contextlib import ExitStack
from datetime import date, timedelta
from pathlib import Path

from .features import Archive, FEATURES, KEY, LABELS, key, unique

COHORTS = {'2013B': 'train', '2013J': 'validation', '2014J': 'test'}
ORDER = ['train', 'validation', 'test']


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def start_bounds(presentation):
    if len(presentation) != 5 or presentation[-1] not in {'B', 'J'}:
        raise ValueError(f'Unsupported presentation: {presentation}')
    year = int(presentation[:4])
    month = 2 if presentation[-1] == 'B' else 10
    return date(year, month, 1), date(year, month, calendar.monthrange(year, month)[1])


def plan(students, courses):
    """Assign students before examining labels. Earlier cohorts own repeated IDs."""
    owners = {}
    for presentation, partition in COHORTS.items():
        for k in sorted(students):
            if k[1] == presentation:
                owners.setdefault(k[2], partition)
    assignments = {}
    exclusions = Counter()
    ends = {}
    for k in sorted(students):
        partition = COHORTS.get(k[1])
        if partition is None:
            exclusions['unselected_presentation_enrollments'] += 1
            continue
        if owners[k[2]] != partition:
            exclusions[partition + '_repeated_student_enrollments'] += 1
            continue
        if k[:2] not in courses:
            raise ValueError('Unknown course in enrollment')
        length = int(courses[k[:2]]['module_presentation_length'])
        if length <= 0:
            raise ValueError('Invalid presentation length')
        assignments[k] = partition
        latest_end = start_bounds(k[1])[1] + timedelta(days=length)
        ends[partition] = max(ends.get(partition, latest_end), latest_end)
    if set(ends) != set(ORDER):
        raise ValueError('Each partition requires enrollments')
    # Treat all earlier selected outcomes as unavailable until latest course end.
    gates = {'train': None, 'validation': ends['train'],
             'test': max(ends['train'], ends['validation'])}
    return assignments, exclusions, gates


def eligible_snapshot(presentation, day, gate):
    earliest_snapshot = start_bounds(presentation)[0] + timedelta(days=day)
    return gate is None or earliest_snapshot > gate


def build_splits(source, snapshots, output):
    if output.exists():
        raise ValueError('Output directory exists; refusing to overwrite')
    manifest = json.loads((snapshots/'manifest.json').read_text(encoding='utf-8'))
    source_hash = digest(source)
    if manifest['source_sha256'] != source_hash:
        raise ValueError('Source archive differs from snapshot provenance')
    archive = Archive(source)
    students = unique(archive.rows('studentInfo'), key, 'studentInfo')
    courses = unique(archive.rows('courses'), lambda r: (r['code_module'], r['code_presentation']), 'courses')
    assignments, exclusions, gates = plan(students, courses)
    counts = {p: Counter() for p in ORDER}
    labels = {p: Counter() for p in ORDER}
    modules = {p: Counter() for p in ORDER}
    ids = {p: set() for p in ORDER}
    enrollments = {p: Counter() for p in ORDER}
    last_days = {}
    output.mkdir(parents=True)
    with ExitStack() as stack:
        readers = []
        for name in ['features', 'labels']:
            stream = stack.enter_context((snapshots/(name+'.csv')).open(newline='', encoding='utf-8'))
            readers.append(csv.DictReader(stream))
        expected = [*KEY, 'snapshot_day', *FEATURES]
        if readers[0].fieldnames != expected or readers[1].fieldnames != [*KEY, 'snapshot_day', 'final_result', 'at_risk']:
            raise ValueError('Unexpected snapshot schema')
        writers = {}
        for partition in ORDER:
            folder = output/partition
            folder.mkdir()
            writers[partition] = []
            for name, reader in zip(['features', 'labels'], readers):
                stream = stack.enter_context((folder/(name+'.csv')).open('w', newline='', encoding='utf-8'))
                writer = csv.DictWriter(stream, fieldnames=reader.fieldnames)
                writer.writeheader()
                writers[partition].append(writer)
        total = 0
        for feature in readers[0]:
            label = next(readers[1], None)
            if label is None or [feature[c] for c in [*KEY, 'snapshot_day']] != [label[c] for c in [*KEY, 'snapshot_day']]:
                raise ValueError('Feature/label row alignment mismatch')
            k = key(feature)
            day = int(feature['snapshot_day'])
            if k not in students or day <= last_days.get(k, 0) or day % 7:
                raise ValueError('Unknown enrollment or duplicate/unordered/invalid snapshot')
            if day >= int(courses[k[:2]]['module_presentation_length']):
                raise ValueError('Snapshot at/after course end')
            last_days[k] = day
            outcome = students[k]['final_result']
            if label['final_result'] != outcome or outcome not in LABELS or label['at_risk'] != str(LABELS[outcome]):
                raise ValueError('Outcome mismatch')
            total += 1
            partition = assignments.get(k)
            if partition is None:
                exclusions['unassigned_snapshots'] += 1
                continue
            if not eligible_snapshot(k[1], day, gates[partition]):
                exclusions[partition+'_snapshots_before_label_maturity_proxy'] += 1
                continue
            for writer, row in zip(writers[partition], [feature, label]):
                writer.writerow(row)
            counts[partition][str(day)] += 1
            labels[partition][outcome] += 1
            modules[partition][k[0]] += 1
            ids[partition].add(k[2])
            enrollments[partition][k] += 1
        if next(readers[1], None) is not None or total != manifest['snapshot_count']:
            raise ValueError('Snapshot counts differ from manifest or label rows')
    overlaps = {a+'_'+b: len(ids[a] & ids[b]) for a,b in [('train','validation'),('train','test'),('validation','test')]}
    if any(overlaps.values()):
        raise ValueError('Student overlap')
    for p in ORDER:
        if not enrollments[p] or not (labels[p]['Fail']+labels[p]['Withdrawn']) or not (labels[p]['Pass']+labels[p]['Distinction']):
            raise ValueError('Partition empty or lacks both classes')
        # Export weights separately, allowing each retained enrollment total weight 1.
        with (output/p/'enrollments.csv').open('w', newline='', encoding='utf-8') as stream:
            writer = csv.writer(stream)
            writer.writerow([*KEY, 'snapshot_count', 'per_snapshot_weight'])
            for k,n in sorted(enrollments[p].items()):
                writer.writerow([*k, n, 1/n])
    report = {'cohort_mapping': COHORTS, 'source_sha256': source_hash,
        'input_sha256': {name: digest(snapshots/name) for name in ['features.csv','labels.csv','manifest.json']},
        'source_snapshot_count': total, 'student_overlap_counts': overlaps,
        'label_maturity_gates': {p: v.isoformat() if v else None for p,v in gates.items()},
        'exclusions': dict(exclusions), 'partitions': {p: {
            'snapshots': sum(counts[p].values()), 'students': len(ids[p]), 'enrollments': len(enrollments[p]),
            'snapshots_by_day': dict(counts[p]), 'snapshot_outcomes': dict(labels[p]),
            'snapshot_modules': dict(modules[p]),
            'modules_absent_from_train': sorted(set(modules[p])-set(modules['train']))} for p in ORDER},
        'chronology_status': 'PASS under conservative month bounds and course-end label proxy; actual outcome availability unverified',
        'limitations': ['No exact start dates; B=February, J=October; entire-month bounds used',
            'Final labels assumed available by latest possible course end; no verified outcome-release timestamps',
            'Earlier-cohort student ownership uses IDs only, including enrollments without snapshots',
            '2014B intentionally held out of this three-cohort experiment',
            'No tuning, threshold selection or model training performed']}
    (output/'manifest.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--snapshots', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build_splits(args.source, args.snapshots, args.output), indent=2))


if __name__ == '__main__':
    main()
