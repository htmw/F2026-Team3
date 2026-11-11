import csv
import io
import json
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile
from acadmate_ml.features import Archive, HEADERS, build, snapshot


class SnapshotTests(unittest.TestCase):
    def test_future_events_do_not_change_features(self):
        before = snapshot(14, 100, {7: 2, 14: 3}, [('a', 10, 8)], [('a', 8), ('b', 12)])
        after = snapshot(14, 100, {7: 2, 14: 3, 15: 999}, [('a', 10, 8), ('b', 15, 12)], [('a', 8), ('b', 12)])
        self.assertEqual(before, after)
        self.assertEqual(after['overdue_assessments'], 1)

    def test_boundaries_and_windows(self):
        row = snapshot(14, 100, {0: 100, 1: 2, 7: 3, 8: 4, 14: 5, 15: 999, -1: 999}, [], [])
        self.assertEqual(row['clicks_7d'], 9)
        self.assertEqual(row['clicks_28d'], 114)
        self.assertEqual(row['engagement_change'], 4)
        self.assertEqual(row['active_days_7d'], 2)

    def test_absence_is_not_zero_score(self):
        row = snapshot(7, 100, {}, [], [])
        self.assertIsNone(row['days_since_activity'])
        self.assertIsNone(row['late_submission_rate'])
        self.assertEqual(row['no_submission'], 1)
        self.assertNotIn('score_mean_so_far', row)
        self.assertIsNone(row['engagement_change'])

    def test_missing_due_date_and_submission_boundary(self):
        row = snapshot(7, 100, {7: 0}, [('a', 7, None), ('b', 7, 6)], [('a', None), ('b', 6)])
        self.assertEqual(row['submissions_so_far'], 2)
        self.assertEqual(row['late_submission_rate'], 1)
        self.assertEqual(row['overdue_assessments'], 0)
        self.assertEqual(row['days_since_submission'], 0)
        self.assertEqual(row['no_activity'], 1)


class BuildTests(unittest.TestCase):
    def fixture(self, path, outcome='Pass', score='0', missing=None, future=False):
        tables = {
            'courses': [['AAA', '2013J', '22']],
            'studentInfo': [['AAA', '2013J', '1', outcome], ['AAA', '2013J', '2', 'Fail'], ['AAA', '2013J', '3', 'Pass'], ['AAA', '2013J', '4', 'Pass']],
            'studentRegistration': [['AAA', '2013J', '1', '0', ''], ['AAA', '2013J', '2', '0', '7'], ['AAA', '2013J', '3', '15', ''], ['AAA', '2013J', '4', '', '']],
            'assessments': [['a', 'AAA', '2013J', 'TMA', '6'], ['b', 'AAA', '2013J', 'TMA', '5'], ['c', 'AAA', '2013J', 'Exam', '6']],
            'studentAssessment': [['a', '1', '7', '0', score], ['b', '1', '5', '1', '100'], ['c', '1', '6', '0', '100']],
            'studentVle': [['AAA', '2013J', '1', '7', '2']],
        }
        if future:
            tables['studentVle'].append(['AAA', '2013J', '1', '99', '999'])
        with ZipFile(path, 'w') as z:
            for name, rows in tables.items():
                if name == missing:
                    continue
                stream = io.StringIO(newline='')
                writer = csv.writer(stream)
                writer.writerow(HEADERS[name]); writer.writerows(rows)
                z.writestr(name+'.csv', stream.getvalue())

    def test_eligibility_banked_exam_and_counts(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); source = root/'data.zip'; out = root/'out'
            self.fixture(source)
            report = build(source, out)
            with (out/'features.csv').open(encoding='utf-8') as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual(len(rows), 4)
            self.assertEqual({r['id_student'] for r in rows}, {'1', '3'})
            self.assertEqual(rows[0]['submissions_so_far'], '1')
            self.assertEqual(rows[0]['overdue_assessments'], '1')
            self.assertEqual(report['exclusions']['banked_or_exam_submissions'], 2)
            self.assertEqual(report['exclusions']['enrollments_missing_registration_date'], 1)
            self.assertFalse(report['scores_enabled'])
            with self.assertRaises(ValueError):
                build(source, out)

    def test_labels_scores_and_future_activity_do_not_change_features(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.fixture(root/'a.zip')
            self.fixture(root/'b.zip', outcome='Fail', score='100', future=True)
            build(root/'a.zip', root/'a'); build(root/'b.zip', root/'b')
            self.assertEqual((root/'a/features.csv').read_bytes(), (root/'b/features.csv').read_bytes())
            self.assertNotEqual((root/'a/labels.csv').read_bytes(), (root/'b/labels.csv').read_bytes())

    def test_missing_feed_fails_without_output(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.fixture(root/'data.zip', missing='studentVle')
            with self.assertRaisesRegex(ValueError, 'studentVle'):
                build(root/'data.zip', root/'out')
            self.assertFalse((root/'out').exists())


if __name__ == '__main__':
    unittest.main()
