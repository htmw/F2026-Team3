"""Validate synthetic MVP LMS inputs and derive existing as-of features. No inference."""
import argparse
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path
from .features import snapshot


def unique(rows,field):
    result={}
    for row in rows:
        value=row[field]
        if not isinstance(value,str) or not value or value in result: raise ValueError('Invalid/duplicate '+field)
        result[value]=row
    return result


def day(value):
    if type(value) is not int or value<0: raise ValueError('Expected nonnegative integer day/count')
    return value


def build(document,academic):
    if document['schema_version']!='1.0' or document['source_kind']!='synthetic_lms_demo':
        raise ValueError('Expected versioned synthetic demo input')
    as_of=day(document['as_of_day'])
    if as_of<7 or as_of%7: raise ValueError('Expected weekly snapshot day >=7')
    tables={}
    hashes={}
    for name,id_field in [('enrollments','enrollment_id'),('courses','course_id'),('students','student_id')]:
        path=academic/(name+'.csv')
        hashes[name+'.csv']=hashlib.sha256(path.read_bytes()).hexdigest()
        with path.open(newline='',encoding='utf-8-sig') as stream: tables[name]=unique(csv.DictReader(stream),id_field)
    courses=unique(document['courses'],'course_id')
    enrollments=unique(document['enrollments'],'enrollment_id')
    assessments=unique(document['assessments'],'assessment_id')
    coverage=unique(document['coverage'],'enrollment_id')
    if set(coverage)!=set(enrollments): raise ValueError('Coverage must match enrollments exactly')
    unique(document['activity'],'event_id');unique(document['submissions'],'submission_id')
    for cid,row in courses.items():
        if cid not in tables['courses'] or day(row['length_days'])<=as_of: raise ValueError('Unknown/ended course')
        day(row['available_day'])
    for eid,row in enrollments.items():
        reference=tables['enrollments'].get(eid)
        if reference is None or any(row[f]!=reference[f] for f in ['student_id','course_id']): raise ValueError('Enrollment linkage mismatch')
        if row['student_id'] not in tables['students'] or row['course_id'] not in courses: raise ValueError('Unknown student/course')
        if reference['status']!='in_progress': raise ValueError('Fixture must link to in_progress enrollment')
        day(row['registered_day']);day(row['available_day'])
    for assessment in assessments.values():
        if assessment['course_id'] not in courses: raise ValueError('Assessment course mismatch')
        day(assessment['due_day']);day(assessment['available_day'])
    for event in document['activity']:
        if event['enrollment_id'] not in enrollments: raise ValueError('Unknown activity enrollment')
        if day(event['available_day'])<day(event['day']): raise ValueError('Activity available before event')
        day(event['activity_count'])
    pairs=set()
    for submission in document['submissions']:
        eid,aid=submission['enrollment_id'],submission['assessment_id']
        if eid not in enrollments or aid not in assessments or enrollments[eid]['course_id']!=assessments[aid]['course_id']:
            raise ValueError('Submission linkage mismatch')
        if (eid,aid) in pairs: raise ValueError('Only one submission per enrollment/assessment supported in v1')
        pairs.add((eid,aid))
        if day(submission['available_day'])<day(submission['submitted_day']): raise ValueError('Submission available before event')
        if 'score' in submission or 'grade' in submission: raise ValueError('Score inputs excluded in v1')
    rows=[]
    for eid,enrollment in enrollments.items():
        cov=coverage[eid];cid=enrollment['course_id']
        for f in ['start_day','through_day','available_day']: day(cov[f])
        for f in ['activity_complete','submissions_complete','schedule_complete']:
            if type(cov[f]) is not bool: raise ValueError('Coverage flags must be boolean')
        complete=cov['start_day']==0 and cov['through_day']>=as_of and cov['available_day']<=as_of and all(cov[f] for f in ['activity_complete','submissions_complete','schedule_complete'])
        available=enrollment['registered_day']<=as_of and enrollment['available_day']<=as_of and courses[cid]['available_day']<=as_of
        row={'enrollment_id':eid,'student_id':enrollment['student_id'],'course_id':cid,'as_of_day':as_of,
            'case':enrollment['case'],'source_kind':'synthetic_lms_demo','status':'ready' if complete and available else 'unavailable',
            'features':None,'reason':None if complete and available else 'Insufficient observed coverage or enrollment/course unavailable as of snapshot'}
        if row['status']=='ready':
            schedule=[(aid,a['due_day']) for aid,a in assessments.items() if a['course_id']==cid and a['available_day']<=as_of]
            known={aid for aid,_ in schedule}
            daily=Counter()
            for event in document['activity']:
                if event['enrollment_id']==eid and event['day']<=as_of and event['available_day']<=as_of:
                    daily[event['day']]+=event['activity_count']
            submissions=[(s['assessment_id'],s['submitted_day'],assessments[s['assessment_id']]['due_day'])
                for s in document['submissions'] if s['enrollment_id']==eid and s['assessment_id'] in known and s['submitted_day']<=as_of and s['available_day']<=as_of]
            row['features']=snapshot(as_of,courses[cid]['length_days'],daily,submissions,schedule)
        rows.append(row)
    return {'schema_version':'1.0','source_kind':'synthetic_lms_demo','as_of_day':as_of,
        'academic_input_sha256':hashes,'rows':rows,'model_inference_performed':False,
        'warning':'Synthetic software-flow fixtures only; no Brightspace schema verification or predictive accuracy evidence'}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input',type=Path,required=True)
    parser.add_argument('--academic',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    result=build(json.loads(args.input.read_text(encoding='utf-8-sig')),args.academic)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open('x',encoding='utf-8') as stream: json.dump(result,stream,indent=2,allow_nan=False)
    print(json.dumps({'cases':len(result['rows']),'ready':sum(r['status']=='ready' for r in result['rows']),
        'unavailable':sum(r['status']=='unavailable' for r in result['rows'])},indent=2))


if __name__=='__main__':main()
