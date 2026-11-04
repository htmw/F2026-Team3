"""Validation-only weekly review and paired student-cluster percentile bootstrap."""
import argparse
import json
from pathlib import Path

import joblib
import numpy as np
from threadpoolctl import threadpool_limits

from .features import FEATURES
from .splits import digest
from .train import load_partition, metrics


class Ranking:
    """Cache score ordering/ties; calculate weighted AP/AUC without re-sorting."""
    def __init__(self,y,p):
        self.order=np.argsort(-p,kind='stable')
        self.y=y[self.order]
        scores=p[self.order]
        self.ends=np.r_[np.flatnonzero(np.diff(scores)),len(scores)-1]

    def calculate(self,weights):
        w=np.asarray(weights,dtype=float)[self.order]
        tp=np.cumsum(w*self.y)[self.ends]
        fp=np.cumsum(w*(1-self.y))[self.ends]
        positive,negative=tp[-1],fp[-1]
        if positive<=0 or negative<=0:
            return np.array([np.nan,np.nan])
        precision=np.divide(tp,tp+fp,out=np.zeros_like(tp),where=(tp+fp)>0)
        ap=np.sum(np.diff(np.r_[0,tp])*precision)/positive
        auc=np.sum(np.diff(np.r_[0,fp])*(tp+np.r_[0,tp[:-1]])/2)/(positive*negative)
        return np.array([ap,auc])


def interval(samples,point):
    samples=np.asarray(samples,dtype=float)
    good=samples[np.isfinite(samples)]
    return {'estimate':float(point), 'lower_95':float(np.quantile(good,.025)) if len(good) else None,
            'upper_95':float(np.quantile(good,.975)) if len(good) else None,
            'valid_replicates':len(good)}


def cluster_multipliers(student_ids,rng):
    """Resample unique students, retaining all their courses and snapshots."""
    students,inverse=np.unique(student_ids,return_inverse=True)
    multiplicity=rng.multinomial(len(students),np.full(len(students),1/len(students)))
    return multiplicity[inverse]


def analyze(splits,artifacts,output,repeats=300,seed=42):
    if repeats<100:
        raise ValueError('Use at least 100 bootstrap replicates')
    if output.exists():
        raise ValueError('Output exists; refusing to overwrite')
    baseline=json.loads((artifacts/'validation_metrics.json').read_text(encoding='utf-8'))
    # Verify provenance before loading trusted local models. Test files are never opened.
    for name in ['features','labels']:
        if digest(splits/'validation'/(name+'.csv'))!=baseline['inputs']['validation/'+name+'.csv']:
            raise ValueError('Validation provenance mismatch')
    if digest(splits/'manifest.json')!=baseline['split_manifest_sha256']:
        raise ValueError('Split provenance mismatch')
    X,y,identities,weights,_=load_partition(splits/'validation')
    students=np.array([i[2] for i in identities])
    days=np.array([int(i[3]) for i in identities])
    predictions={}
    hashes={}
    with threadpool_limits(limits=2):
        for name in baseline['validation_ranking']:
            path=artifacts/(name+'.joblib')
            hashes[name]=digest(path)
            artifact=joblib.load(path)
            if artifact['features']!=FEATURES:
                raise ValueError('Model feature mismatch')
            predictions[name]=artifact['pipeline'].predict_proba(X)[:,1]
    selected=baseline['selected_model']
    ranks={name:Ranking(y,p) for name,p in predictions.items()}
    points={name:rank.calculate(weights) for name,rank in ranks.items()}
    weekly={}
    for day in sorted(set(days)):
        mask=days==day
        weekly[int(day)]={'mask':mask,'rank':Ranking(y[mask],predictions[selected][mask]),'samples':[]}
    samples={name:[] for name in predictions}
    rng=np.random.default_rng(seed)
    for repeat in range(repeats):
        multiplier=cluster_multipliers(students,rng)
        for name,rank in ranks.items():
            samples[name].append(rank.calculate(weights*multiplier))
        for day,entry in weekly.items():
            # Within-week metrics use one vote per enrollment, not inverse lifetime.
            entry['samples'].append(entry['rank'].calculate(multiplier[entry['mask']]))
        if (repeat+1)%50==0:
            print(f'Bootstrap {repeat+1}/{repeats}',flush=True)
    result={'test_accessed':False,'model_refitted':False,'selected_model':selected,
        'bootstrap':{'unit':'student ID across all courses and snapshots','replicates':repeats,'seed':seed,
            'method':'paired percentile intervals; same student draw for all models and weeks'},
        'validation_students':len(set(students)),'validation_snapshots':len(y),
        'model_sha256':hashes,'baseline_metrics_sha256':digest(artifacts/'validation_metrics.json'),
        'validation_input_sha256':{name:digest(splits/'validation'/(name+'.csv')) for name in ['features','labels']},
        'pooled_enrollment_balanced':{},'paired_ap_difference_selected_minus_other':{},'weekly_selected':{},
        'limitations':['Conditional on already-fitted models and observed validation cohort; no training variability',
            'Selection used this same validation cohort; intervals do not correct winner-selection bias',
            'Intervals are pointwise, not simultaneous and not formal multiple-comparison tests',
            'Only one validation presentation; no course/institution-level uncertainty captured',
            'Validation begins at day 28; no evidence for days 7-21',
            'Future trajectory determines pooled inverse-snapshot evaluation weights, not predictor values',
            'Chronology retains documented course-end outcome-availability proxy',
            'No calibration fit, threshold tuning or test evaluation performed']}
    for name in predictions:
        values=np.array(samples[name])
        result['pooled_enrollment_balanced'][name]={metric:interval(values[:,index],points[name][index])
                                                  for index,metric in enumerate(['average_precision','roc_auc'])}
        if name!=selected:
            differences=np.array(samples[selected])[:,0]-values[:,0]
            result['paired_ap_difference_selected_minus_other'][name]=interval(differences,points[selected][0]-points[name][0])
    for day,entry in weekly.items():
        mask=entry['mask']
        probability=predictions[selected][mask]
        point=metrics(y[mask],probability)
        values=np.array(entry['samples'])
        point['students']=len(set(students[mask]))
        point['ap_lift_over_prevalence']=point['average_precision']-point['prevalence'] if point['average_precision'] is not None else None
        point['average_precision_interval']=interval(values[:,0],point['average_precision']) if point['average_precision'] is not None else None
        point['roc_auc_interval']=interval(values[:,1],point['roc_auc']) if point['roc_auc'] is not None else None
        point['mean_probability']=float(probability.mean())
        result['weekly_selected'][str(day)]=point
    output.mkdir(parents=True)
    (output/'weekly_uncertainty.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--splits',type=Path,required=True)
    parser.add_argument('--artifacts',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--replicates',type=int,default=300)
    args=parser.parse_args()
    result=analyze(args.splits,args.artifacts,args.output,args.replicates)
    print(json.dumps({'pooled':result['pooled_enrollment_balanced'],'paired_differences':result['paired_ap_difference_selected_minus_other']},indent=2))


if __name__=='__main__': main()
