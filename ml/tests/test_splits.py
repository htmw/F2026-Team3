import unittest
from datetime import date
from acadmate_ml.splits import plan, eligible_snapshot, start_bounds


class SplitTests(unittest.TestCase):
    def setup_data(self):
        students = {('AAA',p,s): {} for p,s in [('2013B','1'),('2013B','2'),('2013J','1'),('2013J','3'),('2014J','3'),('2014J','4'),('2014B','5')]}
        courses = {('AAA',p): {'module_presentation_length':'240'} for _,p,_ in students}
        return students, courses

    def test_disjoint_ownership_and_unused_cohort(self):
        assignments, excluded, gates = plan(*self.setup_data())
        self.assertEqual(set(assignments.values()), {'train','validation','test'})
        self.assertNotIn(('AAA','2013J','1'), assignments)
        self.assertNotIn(('AAA','2014J','3'), assignments)
        self.assertNotIn(('AAA','2014B','5'), assignments)
        self.assertEqual(excluded['validation_repeated_student_enrollments'],1)
        sets = {p:{k[2] for k,v in assignments.items() if v==p} for p in ['train','validation','test']}
        self.assertFalse(sets['train'] & sets['validation'])
        self.assertFalse(sets['validation'] & sets['test'])

    def test_labels_do_not_change_assignments(self):
        students,courses = self.setup_data()
        before = plan(students,courses)
        for row in students.values():
            row['final_result'] = 'Fail'
        self.assertEqual(before, plan(students,courses))

    def test_month_bounds_and_leap_year(self):
        self.assertEqual(start_bounds('2013B'),(date(2013,2,1),date(2013,2,28)))
        self.assertEqual(start_bounds('2012B')[1],date(2012,2,29))
        self.assertEqual(start_bounds('2013J')[0],date(2013,10,1))
        with self.assertRaises(ValueError): start_bounds('2013X')

    def test_maturity_boundary_strict_and_order_independent(self):
        self.assertFalse(eligible_snapshot('2013J',7,date(2013,10,8)))
        self.assertTrue(eligible_snapshot('2013J',14,date(2013,10,8)))
        students,courses = self.setup_data()
        self.assertEqual(plan(students,courses),plan(dict(reversed(list(students.items()))),courses))

    def test_missing_partition_rejected(self):
        students,courses = self.setup_data()
        with self.assertRaises(ValueError):
            plan({k:v for k,v in students.items() if k[1]!='2014J'},courses)


if __name__ == '__main__': unittest.main()

class SplitFileTests(unittest.TestCase):
    def make_inputs(self, root):
        import csv, io, json
        from zipfile import ZipFile
        from acadmate_ml.features import FEATURES, HEADERS, KEY
        from acadmate_ml.splits import digest
        source = root/'data.zip'
        student_rows = []
        course_rows = []
        for index,presentation in enumerate(['2013B','2013J','2014J']):
            course_rows.append(['AAA',presentation,'240'])
            for offset,outcome in enumerate(['Pass','Fail']):
                student_rows.append(['AAA',presentation,str(index*2+offset+1),outcome])
        with ZipFile(source,'w') as archive:
            for table,rows in [('studentInfo',student_rows),('courses',course_rows)]:
                stream = io.StringIO(newline='')
                writer = csv.writer(stream); writer.writerow(HEADERS[table]); writer.writerows(rows)
                archive.writestr(table+'.csv',stream.getvalue())
        snapshots = root/'snapshots'; snapshots.mkdir()
        for name,fields in [('features',[*KEY,'snapshot_day',*FEATURES]),('labels',[*KEY,'snapshot_day','final_result','at_risk'])]:
            with (snapshots/(name+'.csv')).open('w',newline='',encoding='utf-8') as stream:
                writer = csv.DictWriter(stream,fieldnames=fields); writer.writeheader()
                for module,presentation,student,outcome in student_rows:
                    for day in [7,28]:
                        row = dict(zip(KEY,[module,presentation,student])); row['snapshot_day']=day
                        if name=='features': row.update({f:0 for f in FEATURES})
                        else: row.update(final_result=outcome,at_risk=int(outcome=='Fail'))
                        writer.writerow(row)
        (snapshots/'manifest.json').write_text(json.dumps({'source_sha256':digest(source),'snapshot_count':12}),encoding='utf-8')
        return source,snapshots

    def test_end_to_end_alignment_weights_and_no_overwrite(self):
        import csv,tempfile
        from pathlib import Path
        from acadmate_ml.splits import build_splits
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); source,snapshots=self.make_inputs(root)
            report=build_splits(source,snapshots,root/'out')
            self.assertEqual(report['partitions']['train']['snapshots'],4)
            self.assertEqual(report['partitions']['validation']['snapshots'],2)
            self.assertEqual(report['exclusions']['validation_snapshots_before_label_maturity_proxy'],2)
            self.assertEqual(report['student_overlap_counts'],{'train_validation':0,'train_test':0,'validation_test':0})
            with (root/'out/train/enrollments.csv').open() as stream:
                for row in csv.DictReader(stream):
                    self.assertAlmostEqual(int(row['snapshot_count'])*float(row['per_snapshot_weight']),1)
            with self.assertRaises(ValueError): build_splits(source,snapshots,root/'out')

    def test_bad_provenance_rejected_before_output(self):
        import tempfile,json
        from pathlib import Path
        from acadmate_ml.splits import build_splits
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); source,snapshots=self.make_inputs(root)
            (snapshots/'manifest.json').write_text(json.dumps({'source_sha256':'wrong'}))
            with self.assertRaisesRegex(ValueError,'provenance'): build_splits(source,snapshots,root/'out')
            self.assertFalse((root/'out').exists())

    def test_misaligned_labels_rejected(self):
        import tempfile
        from pathlib import Path
        from acadmate_ml.splits import build_splits
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); source,snapshots=self.make_inputs(root)
            path=snapshots/'labels.csv'
            lines=path.read_text().splitlines()
            lines[1],lines[2]=lines[2],lines[1]
            path.write_text('\n'.join(lines)+'\n')
            with self.assertRaisesRegex(ValueError,'alignment'): build_splits(source,snapshots,root/'out')
