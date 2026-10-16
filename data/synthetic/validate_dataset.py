"""Read-only validation of the fixed Sprint 1 CSVs; no generation or database access."""
import argparse
import ast
from collections import Counter, defaultdict
import csv
from datetime import datetime
from decimal import Decimal, InvalidOperation
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
# Validate this checkout's actual models, with the pinned upstream copy as provenance.
# Neither database.py nor seed_data.py is imported or executed.
REFERENCE = Path(__file__).resolve().parent / 'schema_reference'
model_spec = importlib.util.spec_from_file_location('acadmate_fixed_checkout_models', ROOT / 'backend' / 'models.py')
checkout_models = importlib.util.module_from_spec(model_spec)
model_spec.loader.exec_module(checkout_models)
Base = checkout_models.Base
from sqlalchemy import Boolean, DateTime, Enum, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import ARRAY

COUNTS = {'users': 105, 'programs': 1, 'students': 100, 'advisors': 4,
          'advisor_student_assignments': 100, 'courses': 30, 'enrollments': 800,
          'program_requirements': 3}
SCENARIOS = {'high_performing': 20, 'average_performing': 25, 'low_performing': 15,
             'declining': 10, 'improving': 10, 'failed_and_repeated': 10,
             'withdrawals': 5, 'new_without_completed': 5}
GRADES = {'A': Decimal('4.0'), 'A-': Decimal('3.7'), 'B+': Decimal('3.3'),
          'B': Decimal('3.0'), 'B-': Decimal('2.7'), 'C+': Decimal('2.3'),
          'C': Decimal('2.0'), 'C-': Decimal('1.7'), 'D': Decimal('1.0'), 'F': Decimal('0.0')}
TERMS = ('Fall 2025', 'Spring 2026', 'Summer 2026', 'Fall 2026', 'Spring 2027')
CATEGORIES = (
    'Record counts', 'Primary keys', 'Foreign keys', 'Unique emails and fields',
    'Enrollment statuses', 'Grade-point combinations', 'Course credits',
    'Enrollment chronology', 'Repeated courses', 'Advisor assignments',
    'Program requirement totals', 'Eligible course references', 'Seed preservation',
    'SQLAlchemy compatibility', 'Scenario coverage', 'Fixed-file integrity',
)


def typed_value(value, column):
    if value == '':
        if not column.nullable:
            raise ValueError('required field is NULL')
        return None
    kind = column.type
    if isinstance(kind, ARRAY):
        parsed = json.loads(value)
        if not isinstance(parsed, list) or any(type(item) is not int or not -(2**31) <= item < 2**31 for item in parsed):
            raise ValueError('expected JSON integer array')
        return parsed
    if isinstance(kind, Boolean):
        if value not in ('true', 'false'):
            raise ValueError('expected true or false')
        return value == 'true'
    if isinstance(kind, Integer):
        if not re.fullmatch(r'-?\d+', value):
            raise ValueError('expected integer')
        number = int(value)
        if not -(2**31) <= number < 2**31:
            raise ValueError('integer out of range')
        return number
    if isinstance(kind, Numeric):
        number = Decimal(value)
        if not number.is_finite():
            raise ValueError('expected finite decimal')
        return number
    if isinstance(kind, DateTime):
        result = datetime.fromisoformat(value)
        if kind.timezone and (result.tzinfo is None or result.utcoffset() is None):
            raise ValueError('expected timezone-aware ISO timestamp')
        return result
    if isinstance(kind, Enum) and value not in kind.enums:
        raise ValueError('unknown enum value')
    if isinstance(kind, String) and kind.length and len(value) > kind.length:
        raise ValueError('string exceeds model length')
    return value


def seed_literals(seed_path):
    """Inspect constructors with AST, never execute the seed/import scripts."""
    class_tables = {mapper.class_.__name__: mapper.local_table for mapper in Base.registry.mappers}
    result = defaultdict(list)
    for node in ast.walk(ast.parse(seed_path.read_text(encoding='utf-8'))):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name) or node.func.id not in class_tables:
            continue
        table = class_tables[node.func.id]
        row = {column.name: None for column in table.columns if column.nullable}
        for keyword in node.keywords:
            if keyword.arg == 'updated_at':
                continue  # Dynamic seed timestamp must match the captured live seed snapshot.
            try:
                row[keyword.arg] = ast.literal_eval(keyword.value)
            except (ValueError, TypeError):
                raise ValueError('Unexpected nonliteral seed field')
        result[table.name].append(row)
    return result


def validate(directory, *, verify_hashes=True):
    errors = []
    data = {}
    indexes = {}
    def fail(category, message):
        errors.append({'check': category, 'message': message})
    manifest_path = directory / 'DATASET_MANIFEST.json'
    try:
        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    except (OSError, ValueError) as exc:
        return {'passed': False, 'errors': [{'check': 'Fixed-file integrity', 'message': f'Manifest unreadable ({type(exc).__name__})'}]}
    if manifest.get('record_counts') != COUNTS or manifest.get('scenario_counts') != SCENARIOS:
        fail('Fixed-file integrity', 'Manifest counts differ from the fixed Sprint 1 specification')
    if manifest.get('terms') != list(TERMS) or manifest.get('grade_scale') != {key: str(value) for key, value in GRADES.items()}:
        fail('Fixed-file integrity', 'Manifest vocabulary/grade scale differs from the documented provisional specification')

    for name, count in COUNTS.items():
        table = Base.metadata.tables.get(name)
        if table is None:
            fail('SQLAlchemy compatibility', f'Model missing: {name}')
            continue
        path = directory / f'{name}.csv'
        try:
            with path.open(newline='', encoding='utf-8-sig') as stream:
                reader = csv.DictReader(stream)
                if reader.fieldnames != list(table.columns.keys()):
                    fail('SQLAlchemy compatibility', f'{name}: headers/order differ from current model')
                    continue
                raw_rows = list(reader)
        except (OSError, csv.Error) as exc:
            fail('SQLAlchemy compatibility', f'{name}: file unreadable ({type(exc).__name__})')
            continue
        if len(raw_rows) != count:
            fail('Record counts', f'{name}: expected {count}, found {len(raw_rows)}')
        rows = []
        for number, raw in enumerate(raw_rows, 2):
            if None in raw or any(value is None for value in raw.values()):
                fail('SQLAlchemy compatibility', f'{name}:{number}: wrong field count')
                continue
            converted = {}
            for column in table.columns:
                try:
                    converted[column.name] = typed_value(raw[column.name], column)
                except (ValueError, TypeError, InvalidOperation) as exc:
                    fail('SQLAlchemy compatibility', f'{name}:{number}:{column.name}: {type(exc).__name__}')
            if len(converted) == len(table.columns):
                rows.append(converted)
        data[name] = rows
        primary = tuple(column.name for column in table.primary_key)
        index = {}
        for row in rows:
            key = tuple(row[column] for column in primary)
            if key in index:
                fail('Primary keys', f'{name}: duplicate primary key {key}')
            index[key] = row
        indexes[name] = index
        for column in table.columns:
            if column.unique:
                values = [row[column.name] for row in rows if row[column.name] is not None]
                if len(values) != len(set(values)):
                    fail('Unique emails and fields', f'{name}.{column.name}: duplicates')

    if set(data) != set(COUNTS) or any(len(data.get(name, [])) != count for name, count in COUNTS.items()):
        # Return clear structural errors instead of misleading downstream tracebacks.
        return summary(data, errors, {}, manifest)

    def record(table, value):
        return indexes[table].get((value,))
    for name, rows in data.items():
        table = Base.metadata.tables[name]
        for row in rows:
            for column in table.columns:
                for foreign_key in column.foreign_keys:
                    target = foreign_key.column
                    if not any(candidate[target.name] == row[column.name] for candidate in data[target.table.name]):
                        fail('Foreign keys', f'{name}.{column.name}: unresolved value for key {row[list(table.primary_key)[0].name]}')

    roles = Counter(row['role'] for row in data['users'])
    if roles != Counter(student=100, advisor=4, admin=1):
        fail('Record counts', 'User roles must be 100 students, 4 advisors and 1 administrator')
    for name, role in (('students', 'student'), ('advisors', 'advisor')):
        for row in data[name]:
            user = record('users', row['user_id'])
            if not user or user['role'] != role:
                fail('Foreign keys', f'{name}: user role inconsistent')
            if name == 'students':
                if row['program_id'] != 1:
                    fail('Foreign keys', 'Every student must reference program 1')
                if user and (row['name'] != user['name'] or row['email'] != user['email']):
                    fail('Unique emails and fields', f'Student {row["student_id"]}: identity differs from linked user')
    student_users = {row['user_id'] for row in data['students']}
    advisor_users = {row['user_id'] for row in data['advisors']}
    if student_users & advisor_users:
        fail('Foreign keys', 'Student and advisor accounts overlap')
    for row in data['users']:
        if row['user_id'] not in (1, 2) and not row['email'].endswith('@example.invalid'):
            fail('Unique emails and fields', 'New fictional users must use example.invalid')

    for row in data['courses']:
        if row['credits'] != Decimal('3'):
            fail('Course credits', f'Course {row["course_id"]}: fixed dataset uses 3-credit courses')
    histories = defaultdict(list)
    pairs = defaultdict(list)
    triplets = Counter()
    workload = Counter()
    for row in data['enrollments']:
        histories[row['student_id']].append(row)
        pairs[row['student_id'], row['course_id']].append(row)
        triplets[row['student_id'], row['course_id'], row['term']] += 1
        workload[row['student_id'], row['term']] += 1
        status = row['status']
        if status not in ('in_progress', 'completed', 'failed', 'withdrawn'):
            fail('Enrollment statuses', 'Unknown enrollment status')
        if row['term'] not in TERMS:
            fail('Enrollment chronology', f'Enrollment {row["enrollment_id"]}: unknown term')
        elif status == 'in_progress' and row['term'] != TERMS[-1]:
            fail('Enrollment chronology', 'In-progress records must be in the synthetic snapshot term Spring 2027')
        elif status != 'in_progress' and row['term'] == TERMS[-1]:
            fail('Enrollment chronology', 'Finished/withdrawn attempt cannot occur after the synthetic snapshot cutoff')
        if status in ('in_progress', 'withdrawn'):
            if row['grade'] is not None or row['grade_points'] is not None:
                fail('Grade-point combinations', 'In-progress/withdrawn must have NULL grade and grade_points')
        elif status == 'failed':
            if row['grade'] != 'F' or row['grade_points'] != Decimal('0'):
                fail('Grade-point combinations', 'Failed record must be F/0.0 under the provisional scale')
        elif status == 'completed':
            if row['grade'] not in GRADES or row['grade'] == 'F' or row['grade_points'] != GRADES.get(row['grade']):
                fail('Grade-point combinations', 'Completed record must have a passing provisional grade/point pair')
    if any(count > 1 for count in triplets.values()):
        fail('Repeated courses', 'Duplicate student/course/term attempt')
    if any(count > 4 for count in workload.values()):
        fail('Enrollment chronology', 'Dataset workload convention exceeded: at most four 3-credit courses per term')
    repeated = {}
    for key, attempts in pairs.items():
        if len(attempts) > 1:
            repeated[key] = attempts
            if len({row['term'] for row in attempts}) != len(attempts):
                fail('Repeated courses', 'Repeat attempts must occur in different terms')

    assigned = Counter(row['student_id'] for row in data['advisor_student_assignments'])
    if assigned != Counter({row['student_id']: 1 for row in data['students']}):
        fail('Advisor assignments', 'Every student must have exactly one assignment')
    if any(row['updated_at'].utcoffset() is None for row in data['advisor_student_assignments']):
        fail('Advisor assignments', 'Assignment timestamp lacks timezone')

    requirements = {row['group_name']: row for row in data['program_requirements']}
    if set(requirements) != {'Core', 'Electives', 'Capstone'}:
        fail('Program requirement totals', 'Expected exactly Core, Electives, Capstone')
    credits = {key: row['required_credits'] for key, row in requirements.items()}
    if credits != {'Core': Decimal('9'), 'Electives': Decimal('18'), 'Capstone': Decimal('3')}:
        fail('Program requirement totals', 'Provisional requirement allocation differs from 9/18/3')
    if sum(row['required_credits'] for row in data['program_requirements']) != Decimal('30'):
        fail('Program requirement totals', 'Requirement total is not 30')
    program = record('programs', 1)
    if not program or program['program_name'] != 'MS Computer Science' or program['total_required_credits'] != Decimal('30'):
        fail('Program requirement totals', 'Program 1 differs from the existing seed')
    all_eligible = []
    for row in data['program_requirements']:
        if row['program_id'] != 1:
            fail('Foreign keys', 'Requirement must reference program 1')
        ids = row['eligible_course_ids']
        if not ids:
            fail('Eligible course references', 'Eligible course list must not be empty')
        if len(ids) != len(set(ids)) or any(record('courses', item) is None for item in ids):
            fail('Eligible course references', 'Duplicate/unresolved course ID in requirement array')
        all_eligible.extend(row['eligible_course_ids'])
    if len(all_eligible) != len(set(all_eligible)) or set(all_eligible) != {row['course_id'] for row in data['courses']}:
        fail('Eligible course references', 'Each catalog course must occur in exactly one provisional eligibility group')

    try:
        literals = seed_literals(ROOT / 'backend' / 'seed_data.py')
        for name, rows in literals.items():
            table = Base.metadata.tables[name]
            for row in rows:
                key = tuple(row[column.name] for column in table.primary_key)
                actual = indexes[name].get(key)
                if actual is None:
                    fail('Seed preservation', f'{name}: seed {key} missing')
                    continue
                for column, expected in row.items():
                    if isinstance(table.columns[column].type, Numeric) and expected is not None:
                        expected = Decimal(str(expected))
                    if actual[column] != expected:
                        fail('Seed preservation', f'{name}: seed {key} column {column} changed')
        for name, rows in manifest.get('preserved_seed_records', {}).items():
            if name not in COUNTS:
                fail('Seed preservation', 'Unknown preserved seed table')
                continue
            table = Base.metadata.tables[name]
            for row in rows:
                expected = {column.name: typed_value(csv_value(row[column.name]), column) for column in table.columns}
                key = tuple(expected[column.name] for column in table.primary_key)
                if indexes[name].get(key) != expected:
                    fail('Seed preservation', f'{name}: captured seed {key} changed, including dynamic fields')
    except (OSError, ValueError, KeyError, TypeError) as exc:
        fail('Seed preservation', f'Seed comparison could not complete ({type(exc).__name__})')
    seed_counts = {name: len(rows) for name, rows in manifest.get('preserved_seed_records', {}).items()}
    if seed_counts != {'users': 2, 'programs': 1, 'students': 1, 'advisors': 1, 'courses': 3,
                      'enrollments': 3, 'advisor_student_assignments': 1, 'program_requirements': 1}:
        fail('Seed preservation', 'Captured seed snapshot is incomplete')

    labels = {}
    try:
        with (directory / 'student_scenarios.csv').open(newline='', encoding='utf-8-sig') as stream:
            reader = csv.DictReader(stream)
            if reader.fieldnames != ['student_id', 'scenario']:
                fail('Scenario coverage', 'Scenario manifest headers must be student_id,scenario')
            for row in reader:
                student_id = int(row['student_id'])
                if student_id in labels:
                    fail('Scenario coverage', 'Student has multiple labels')
                labels[student_id] = row['scenario']
    except (OSError, csv.Error, ValueError, KeyError, TypeError) as exc:
        fail('Scenario coverage', f'Scenario manifest unreadable ({type(exc).__name__})')
    if Counter(labels.values()) != Counter(SCENARIOS) or set(labels) != {row['student_id'] for row in data['students']}:
        fail('Scenario coverage', 'Scenario counts/coverage differ from the eight mutually exclusive groups')
    credit_totals = Counter()
    no_gpa = 0
    near_completion = 0
    for student in data['students']:
        student_id = student['student_id']
        history = histories[student_id]
        scenario = labels.get(student_id)
        expected_length = {'high_performing': 10, 'withdrawals': 4, 'new_without_completed': 4}.get(scenario, 8)
        if len(history) != expected_length:
            fail('Scenario coverage', f'Student {student_id}: enrollment count differs from fixed scenario plan')
        completed = [row for row in history if row['status'] == 'completed' and row['grade_points'] is not None]
        total_credits = sum(record('courses', row['course_id'])['credits'] for row in completed if record('courses', row['course_id']))
        quality = sum(record('courses', row['course_id'])['credits'] * row['grade_points'] for row in completed if record('courses', row['course_id']))
        gpa = quality / total_credits if total_credits else None
        credit_totals[str(total_credits)] += 1
        no_gpa += gpa is None
        near_completion += total_credits == Decimal('27')
        if scenario == 'high_performing' and (gpa is None or not Decimal('3.7') <= gpa <= 4):
            fail('Scenario coverage', 'High-performing scenario falls outside its provisional test band')
        if scenario == 'average_performing' and (gpa is None or not Decimal('2.5') <= gpa <= Decimal('3.5')):
            fail('Scenario coverage', 'Average-performing scenario falls outside its provisional test band')
        if scenario == 'low_performing' and (gpa is None or not Decimal('1') <= gpa <= Decimal('2.3')):
            fail('Scenario coverage', 'Low-performing scenario falls outside its provisional test band')
        if scenario in ('declining', 'improving'):
            by_term = defaultdict(list)
            for row in completed:
                by_term[row['term']].append(row['grade_points'])
            trend = [sum(by_term[term]) / len(by_term[term]) for term in TERMS if by_term[term]]
            direction = -1 if scenario == 'declining' else 1
            if len(trend) < 3 or not all((right - left) * direction > 0 for left, right in zip(trend, trend[1:])):
                fail('Scenario coverage', f'{scenario}: expected at least three strictly directional graded terms')
        failures = [row for row in history if row['status'] == 'failed']
        withdrawals = [row for row in history if row['status'] == 'withdrawn']
        student_repeats = [attempts for (owner, _), attempts in repeated.items() if owner == student_id]
        if scenario == 'failed_and_repeated':
            recovered = any(any(row['status'] == 'failed' and row['term'] in TERMS and later['status'] == 'completed'
                                and later['term'] in TERMS and TERMS.index(later['term']) > TERMS.index(row['term'])
                                for row in attempts for later in attempts) for attempts in student_repeats)
            if not failures or not recovered:
                fail('Scenario coverage', 'Failed/repeated student lacks a later completed repeat of a failed course')
        elif failures or student_repeats:
            fail('Scenario coverage', 'Failure/repeat outside its assigned primary scenario')
        if scenario == 'withdrawals' and not withdrawals:
            fail('Scenario coverage', 'Withdrawal student lacks withdrawal history')
        elif scenario != 'withdrawals' and withdrawals:
            fail('Scenario coverage', 'Withdrawal outside its assigned primary scenario')
        if scenario == 'new_without_completed':
            if completed or gpa is not None or any(row['status'] != 'in_progress' for row in history):
                fail('Scenario coverage', 'New student must have only in_progress records and no GPA')
        elif len({row['term'] for row in history}) < 2:
            fail('Enrollment chronology', 'Returning student must have a multi-term history')
    if no_gpa != 5 or near_completion < 1 or len(credit_totals) < 4:
        fail('Scenario coverage', 'Missing no-GPA, 27-credit, or varied earned-credit scenarios')

    expected_files = {f'{name}.csv' for name in COUNTS} | {'student_scenarios.csv'}
    if set(manifest.get('csv_sha256', {})) != expected_files:
        fail('Fixed-file integrity', 'Checksum manifest does not cover exactly the fixed CSVs')
    if verify_hashes:
        for name in expected_files:
            path = directory / name
            if not path.exists() or hashlib.sha256(path.read_bytes()).hexdigest() != manifest.get('csv_sha256', {}).get(name):
                fail('Fixed-file integrity', f'{name}: fixed-file checksum mismatch')
    source = manifest.get('schema_reference', {})
    if source.get('branch') != 'feature/backend-integration':
        fail('SQLAlchemy compatibility', 'Target schema reference branch differs from the reviewed branch')
    for name in ('models.py', 'seed_data.py'):
        path = REFERENCE / name
        expected = source.get(name, {})
        content = path.read_bytes()
        blob = hashlib.sha1(f'blob {len(content)}\0'.encode() + content).hexdigest()
        if hashlib.sha256(content).hexdigest() != expected.get('sha256') or blob != expected.get('git_blob_sha'):
            fail('SQLAlchemy compatibility', f'{name}: target reference differs from reviewed GitHub contents')
    original = manifest.get('original_preserved_seed_records')
    if original is None:
        fail('Seed preservation', 'Original seed snapshot required for audited schema transition')
    else:
        normalized = json.loads(json.dumps(original))
        for row in normalized.get('enrollments', []):
            if row.get('status') == 'inprogress':
                row['status'] = 'in_progress'
        for row in normalized.get('program_requirements', []):
            if row.pop('course_ids', None) is not None:
                fail('Seed preservation', 'Removed seed course_ids was not NULL')
            if 'eligible_courses_ids' in row:
                row['eligible_course_ids'] = row.pop('eligible_courses_ids')
        if normalized != manifest.get('preserved_seed_records'):
            fail('Seed preservation', 'Seed changes exceed the three approved canonical schema updates')
    # Creation hashes describe the OLD ZIP workspace, not this real checkout.
    # Replace that location-dependent gate with direct source/seed compatibility checks.
    try:
        current_model = ast.dump(ast.parse((ROOT / 'backend' / 'models.py').read_text(encoding='utf-8-sig')), include_attributes=False)
        reviewed_model = ast.dump(ast.parse((REFERENCE / 'models.py').read_text(encoding='utf-8-sig')), include_attributes=False)
        if current_model != reviewed_model:
            fail('SQLAlchemy compatibility', 'Current checkout models differ from the pinned canonical schema; review required')
        if seed_literals(ROOT / 'backend' / 'seed_data.py') != seed_literals(REFERENCE / 'seed_data.py'):
            fail('Seed preservation', 'Current checkout seed literals differ from the pinned canonical seed')
    except (OSError, ValueError, SyntaxError) as exc:
        fail('SQLAlchemy compatibility', f'Checkout schema/seed comparison could not complete ({type(exc).__name__})')
    return summary(data, errors, {
        'scenario_counts': dict(Counter(labels.values())), 'students_without_gpa': no_gpa,
        'students_with_27_completed_credits': near_completion,
        'completed_credit_distribution': dict(credit_totals),
        'status_counts': dict(Counter(row['status'] for row in data['enrollments'])),
        'repeated_student_course_pairs': len(repeated),
        'students_with_multiple_completed_attempts_of_one_course': len({owner for (owner, _), attempts in repeated.items()
            if sum(row['status'] == 'completed' for row in attempts) > 1}),
    }, manifest)


def csv_value(value):
    if value is None:
        return ''
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, list):
        return json.dumps(value)
    return str(value)


def summary(data, errors, coverage, manifest):
    return {'passed': not errors, 'counts': {name: len(rows) for name, rows in data.items()},
            'checks': {category: 'FAIL' if any(item['check'] == category for item in errors) else ('PASS' if not errors else 'PASS_OR_NOT_REACHED') for category in CATEGORIES},
            'coverage': coverage, 'errors': errors}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, default=Path(__file__).parent)
    args = parser.parse_args()
    try:
        result = validate(args.directory)
        print(json.dumps(result, indent=2))
        return 0 if result['passed'] else 1
    except Exception as exc:
        print(json.dumps({'passed': False, 'error': type(exc).__name__, 'message': 'Validation could not complete; CSVs and database were not modified.'}))
        return 1


if __name__ == '__main__':
    sys.exit(main())
