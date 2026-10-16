"""Mutation tests for the fixed-data validator; temporary CSV copies, no DB access."""
import csv
import hashlib
import importlib.util
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
DATASET = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('fixed_dataset_validator', DATASET / 'validate_dataset.py')
validator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(validator)


class ValidatorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='acadmate-validator-')
        self.directory = Path(self.temp.name)
        for path in DATASET.glob('*.csv'):
            shutil.copyfile(path, self.directory / path.name)
        shutil.copyfile(DATASET / 'DATASET_MANIFEST.json', self.directory / 'DATASET_MANIFEST.json')

    def tearDown(self):
        self.temp.cleanup()

    def mutate(self, table, change):
        path = self.directory / f'{table}.csv'
        with path.open(newline='', encoding='utf-8') as stream:
            reader = csv.DictReader(stream)
            fields = reader.fieldnames
            rows = list(reader)
        change(rows)
        with path.open('w', newline='', encoding='utf-8') as stream:
            writer = csv.DictWriter(stream, fieldnames=fields, lineterminator='\n')
            writer.writeheader()
            writer.writerows(rows)

    def rejected(self, category):
        result = validator.validate(self.directory, verify_hashes=False)
        self.assertFalse(result['passed'])
        self.assertIn(category, {error['check'] for error in result['errors']}, result['errors'])

    def test_valid_dataset_and_no_writes(self):
        before = {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in self.directory.iterdir()}
        first = validator.validate(self.directory)
        second = validator.validate(self.directory)
        after = {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in self.directory.iterdir()}
        self.assertTrue(first['passed'], first['errors'])
        self.assertEqual(first, second)
        self.assertEqual(before, after)

    def test_wrong_record_count(self):
        self.mutate('enrollments', lambda rows: rows.pop())
        self.rejected('Record counts')

    def test_duplicate_primary_key(self):
        self.mutate('enrollments', lambda rows: rows[-1].update(enrollment_id=rows[-2]['enrollment_id']))
        self.rejected('Primary keys')

    def test_unresolved_foreign_key(self):
        self.mutate('enrollments', lambda rows: rows[-1].update(course_id='999999'))
        self.rejected('Foreign keys')

    def test_duplicate_email(self):
        self.mutate('users', lambda rows: rows[-1].update(email=rows[-2]['email']))
        self.rejected('Unique emails and fields')

    def test_duplicate_course_code(self):
        self.mutate('courses', lambda rows: rows[-1].update(course_code=rows[-2]['course_code']))
        self.rejected('Unique emails and fields')

    def test_wrong_status_spelling(self):
        self.mutate('enrollments', lambda rows: rows[-1].update(status='inprogress'))
        self.rejected('SQLAlchemy compatibility')

    def test_grade_point_mismatch(self):
        self.mutate('enrollments', lambda rows: rows[0].update(grade_points='2.0'))
        self.rejected('Grade-point combinations')

    def test_inprogress_grade_rejected(self):
        self.mutate('enrollments', lambda rows: rows[-1].update(grade='A', grade_points='4.0'))
        self.rejected('Grade-point combinations')

    def test_invalid_course_credits(self):
        self.mutate('courses', lambda rows: rows[-1].update(credits='-3'))
        self.rejected('Course credits')

    def test_unknown_term(self):
        self.mutate('enrollments', lambda rows: rows[-1].update(term='Winter 2027'))
        self.rejected('Enrollment chronology')

    def test_same_term_repeat_rejected(self):
        def change(rows):
            attempts = [row for row in rows if row['student_id'] == '10079' and row['course_id'] == '11']
            attempts[1]['term'] = attempts[0]['term']
        self.mutate('enrollments', change)
        self.rejected('Repeated courses')

    def test_workload_convention(self):
        def change(rows):
            attempts = [row for row in rows if row['student_id'] == '10000' and row['term'] == 'Spring 2026']
            for row in attempts[:2]:
                row['term'] = 'Fall 2025'
        self.mutate('enrollments', change)
        self.rejected('Enrollment chronology')

    def test_missing_assignment(self):
        self.mutate('advisor_student_assignments', lambda rows: rows[-1].update(student_id=rows[-2]['student_id']))
        self.rejected('Advisor assignments')

    def test_requirement_total(self):
        self.mutate('program_requirements', lambda rows: rows[1].update(required_credits='17'))
        self.rejected('Program requirement totals')

    def test_unknown_eligible_course(self):
        self.mutate('program_requirements', lambda rows: rows[-1].update(eligible_course_ids='[999999]'))
        self.rejected('Eligible course references')

    def test_modified_seed(self):
        self.mutate('students', lambda rows: rows[0].update(name='Altered seed name'))
        self.rejected('Seed preservation')

    def test_preserved_dynamic_assignment_timestamp(self):
        self.mutate('advisor_student_assignments', lambda rows: rows[0].update(updated_at='2026-10-14T00:00:00+00:00'))
        self.rejected('Seed preservation')

    def test_extra_calculated_column_rejected(self):
        path = self.directory / 'students.csv'
        lines = path.read_text(encoding='utf-8').splitlines()
        path.write_text(lines[0] + ',gpa\n' + '\n'.join(line + ',3.5' for line in lines[1:]) + '\n', encoding='utf-8')
        self.rejected('SQLAlchemy compatibility')

    def test_malformed_array(self):
        self.mutate('program_requirements', lambda rows: rows[-1].update(eligible_course_ids='not JSON'))
        self.rejected('SQLAlchemy compatibility')

    def test_inconsistent_scenario_counts(self):
        self.mutate('student_scenarios', lambda rows: rows[1].update(scenario='average_performing'))
        self.rejected('Scenario coverage')

    def test_declining_scenario_has_real_trend(self):
        def change(rows):
            for row in rows:
                if row['student_id'] == '10059' and row['term'] == 'Fall 2026':
                    row.update(grade='A', grade_points='4.0')
        self.mutate('enrollments', change)
        self.rejected('Scenario coverage')

    def test_new_student_no_completed_courses(self):
        self.mutate('enrollments', lambda rows: rows[-1].update(status='completed', term='Fall 2026', grade='B', grade_points='3.0'))
        self.rejected('Scenario coverage')

    def test_semantically_identical_file_edit_detected(self):
        self.mutate('enrollments', lambda rows: rows[0].update(grade_points='4.000'))
        result = validator.validate(self.directory)
        self.assertFalse(result['passed'])
        self.assertIn('Fixed-file integrity', {error['check'] for error in result['errors']})


    def test_canonical_target_model(self):
        enrollment = validator.Base.metadata.tables['enrollments']
        self.assertEqual(enrollment.columns['status'].type.enums, ['in_progress', 'completed', 'failed', 'withdrawn'])
        requirement = validator.Base.metadata.tables['program_requirements']
        self.assertEqual(list(requirement.columns.keys()), ['requirement_id', 'program_id', 'group_name', 'required_credits', 'eligible_course_ids'])

    def test_legacy_requirement_header_rejected(self):
        path = self.directory / 'program_requirements.csv'
        path.write_text(path.read_text(encoding='utf-8').replace('eligible_course_ids', 'eligible_courses_ids'), encoding='utf-8')
        self.rejected('SQLAlchemy compatibility')

    def test_removed_course_ids_column_rejected(self):
        path = self.directory / 'program_requirements.csv'
        with path.open(newline='', encoding='utf-8') as stream:
            reader = csv.DictReader(stream)
            fields = reader.fieldnames + ['course_ids']
            rows = list(reader)
        with path.open('w', newline='', encoding='utf-8') as stream:
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            writer.writerows([{**row, 'course_ids': ''} for row in rows])
        self.rejected('SQLAlchemy compatibility')

    def test_original_seed_audit_rejects_unapproved_change(self):
        import json
        path = self.directory / 'DATASET_MANIFEST.json'
        manifest = json.loads(path.read_text(encoding='utf-8'))
        manifest['original_preserved_seed_records']['users'][0]['name'] = 'Changed original seed'
        path.write_text(json.dumps(manifest), encoding='utf-8')
        self.rejected('Seed preservation')

    def test_reference_source_checksum_rejected(self):
        from unittest.mock import patch
        reference = self.directory / 'schema_reference'
        reference.mkdir()
        for path in validator.REFERENCE.glob('*.py'):
            shutil.copyfile(path, reference / path.name)
        path = reference / 'seed_data.py'
        path.write_bytes(path.read_bytes() + b'\n')
        with patch.object(validator, 'REFERENCE', reference):
            self.rejected('SQLAlchemy compatibility')


    def test_actual_checkout_models_are_verified(self):
        from unittest.mock import patch
        root = self.directory / 'checkout-model-check'
        backend = root / 'backend'
        backend.mkdir(parents=True)
        shutil.copyfile(validator.ROOT / 'backend' / 'seed_data.py', backend / 'seed_data.py')
        source = (validator.ROOT / 'backend' / 'models.py').read_text(encoding='utf-8')
        (backend / 'models.py').write_text(source.replace('"in_progress"', '"inprogress"'), encoding='utf-8')
        with patch.object(validator, 'ROOT', root):
            self.rejected('SQLAlchemy compatibility')

    def test_actual_checkout_seed_is_verified(self):
        from unittest.mock import patch
        root = self.directory / 'checkout-seed-check'
        backend = root / 'backend'
        backend.mkdir(parents=True)
        shutil.copyfile(validator.ROOT / 'backend' / 'models.py', backend / 'models.py')
        source = (validator.ROOT / 'backend' / 'seed_data.py').read_text(encoding='utf-8')
        (backend / 'seed_data.py').write_text(source.replace('Santos Shel', 'Altered original student'), encoding='utf-8')
        with patch.object(validator, 'ROOT', root):
            self.rejected('Seed preservation')


if __name__ == '__main__':
    unittest.main()
