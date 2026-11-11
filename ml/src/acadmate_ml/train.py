"""Train fixed baseline models on training only; evaluate validation, never test."""
import argparse
import csv
import json
import platform
from collections import Counter
from pathlib import Path
from time import perf_counter

import joblib
import numpy as np
import sklearn
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (average_precision_score, brier_score_loss, precision_score,
                            recall_score, f1_score, roc_auc_score)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from threadpoolctl import threadpool_limits

from .features import FEATURES, KEY, LABELS
from .splits import digest


def load_partition(folder):
    """Only explicitly requested partition files are opened; IDs never enter X."""
    identities, values, targets, outcomes = [], [], [], []
    counts = Counter()
    seen = set()
    with (folder/'features.csv').open(newline='', encoding='utf-8') as f, (folder/'labels.csv').open(newline='', encoding='utf-8') as l:
        fr, lr = csv.DictReader(f), csv.DictReader(l)
        if fr.fieldnames != [*KEY, 'snapshot_day', *FEATURES] or lr.fieldnames != [*KEY, 'snapshot_day', 'final_result', 'at_risk']:
            raise ValueError('Unexpected training input schema')
        for feature in fr:
            label = next(lr, None)
            identity = tuple(feature[c] for c in [*KEY, 'snapshot_day'])
            if label is None or identity != tuple(label[c] for c in [*KEY, 'snapshot_day']):
                raise ValueError('Feature/label alignment mismatch')
            if identity in seen:
                raise ValueError('Duplicate snapshot')
            seen.add(identity)
            outcome = label['final_result']
            if outcome not in LABELS or str(LABELS[outcome]) != label['at_risk']:
                raise ValueError('Invalid outcome')
            row = [float(feature[c]) if feature[c] else np.nan for c in FEATURES]
            if any(np.isinf(row)):
                raise ValueError('Infinite feature')
            identities.append(identity)
            values.append(row)
            targets.append(LABELS[outcome]); outcomes.append(outcome)
            counts[identity[:3]] += 1
        if next(lr, None) is not None:
            raise ValueError('Extra label rows')
    if len(set(targets)) != 2:
        raise ValueError('Training/evaluation partition requires both classes')
    weights = np.array([1/counts[i[:3]] for i in identities])
    return np.array(values), np.array(targets), identities, weights, np.array(outcomes)


def models():
    def pipeline(classifier, scale=False):
        steps = [('imputer', SimpleImputer(strategy='median', add_indicator=True, keep_empty_features=True))]
        if scale:
            steps.append(('scaler', StandardScaler()))
        return Pipeline([*steps, ('classifier', classifier)])
    return {
        'dummy_prior': pipeline(DummyClassifier(strategy='prior')),
        'logistic_regression': pipeline(LogisticRegression(max_iter=2000, random_state=42), True),
        'random_forest': pipeline(RandomForestClassifier(n_estimators=100, max_depth=12,
                                min_samples_leaf=20, n_jobs=2, random_state=42)),
        'hist_gradient_boosting': pipeline(HistGradientBoostingClassifier(max_iter=100,
                            max_leaf_nodes=15, l2_regularization=1, early_stopping=False, random_state=42)),
    }


def metrics(y, probability, weights=None):
    has_both = len(np.unique(y)) == 2
    predicted = probability >= 0.5
    return {'rows': len(y), 'prevalence': float(np.average(y, weights=weights)),
        'average_precision': float(average_precision_score(y, probability, sample_weight=weights)) if has_both else None,
        'roc_auc': float(roc_auc_score(y, probability, sample_weight=weights)) if has_both else None,
        'brier': float(brier_score_loss(y, probability, sample_weight=weights)),
        'precision_at_0_5': float(precision_score(y, predicted, sample_weight=weights, zero_division=0)),
        'recall_at_0_5': float(recall_score(y, predicted, sample_weight=weights, zero_division=0)),
        'f1_at_0_5': float(f1_score(y, predicted, sample_weight=weights, zero_division=0))}


def calibration(y, probability, weights):
    bins = []
    for low in np.arange(0, 1, 0.1):
        mask = (probability >= low) & (probability < low+0.1 if low < 0.85 else probability <= 1)
        if mask.any():
            bins.append({'lower': round(float(low),1), 'rows': int(mask.sum()),
                'mean_probability': float(np.average(probability[mask], weights=weights[mask])),
                'observed_rate': float(np.average(y[mask], weights=weights[mask]))})
    return bins


def outreach(identities, y, probability):
    """Hypothetical weekly student outreach, max active-course probability."""
    weeks = {}
    for identity, target, score in zip(identities, y, probability):
        week, student = identity[3], identity[2]
        students = weeks.setdefault(week, {})
        old = students.get(student, (0,0.0))
        students[student] = (max(old[0],int(target)), max(old[1],float(score)))
    results = {}
    for fraction in [0.1,0.2]:
        results[str(fraction)] = {}
        for week, students in sorted(weeks.items(), key=lambda item:int(item[0])):
            ranked = sorted(students.items(), key=lambda item:(-item[1][1], item[0]))
            k = max(1, int(np.ceil(len(ranked)*fraction)))
            positives = sum(v[0] for v in students.values())
            hits = sum(v[0] for _,v in ranked[:k])
            results[str(fraction)][week] = {'students':len(ranked), 'contacts':k,
                'precision':hits/k, 'recall':hits/positives if positives else None}
    return results


def run(splits, output):
    if output.exists():
        raise ValueError('Output exists; refusing to overwrite')
    manifest = json.loads((splits/'manifest.json').read_text(encoding='utf-8'))
    if any(manifest['student_overlap_counts'].values()):
        raise ValueError('Split manifest reports student overlap')
    train = load_partition(splits/'train')
    validation = load_partition(splits/'validation')
    X,y,ids,weights,_ = train
    VX,VY,vids,vweights,voutcomes = validation
    if {i[2] for i in ids} & {i[2] for i in vids}:
        raise ValueError('Student overlap in actual training/validation files')
    for name,data in [('train',train),('validation',validation)]:
        if len(data[1]) != manifest['partitions'][name]['snapshots']:
            raise ValueError('Snapshot count differs from split manifest')
    # Normalize for regularization/minimum-weight behavior; each enrollment has equal total weight.
    fitting_weights = weights / weights.mean()
    output.mkdir(parents=True)
    report = {'test_accessed': False, 'selection_rule':'highest enrollment-balanced validation average precision; ties by model name',
        'threshold':0.5, 'threshold_tuned':False, 'probability_calibration_fitted':False,
        'features':FEATURES, 'versions':{'python':platform.python_version(),'numpy':np.__version__,'sklearn':sklearn.__version__},
        'inputs': {f'{part}/{name}.csv':digest(splits/part/(name+'.csv')) for part in ['train','validation'] for name in ['features','labels']},
        'split_manifest_sha256':digest(splits/'manifest.json'),
        'models':{}, 'limitations': ['Validation begins at day 28', 'Course-end outcome availability proxy, not verified release dates',
            'Unseen modules and temporal shift coexist', 'No group bootstrap confidence intervals yet',
            '0.5 threshold and 10%/20% outreach capacities are diagnostic, not operational policy',
            'Calibration is measured, not corrected; probabilities are research estimates']}
    familiar = {i[0] for i in ids}
    with threadpool_limits(limits=2):
        for name,model in models().items():
            print('Fitting '+name, flush=True)
            start = perf_counter()
            model.fit(X,y,classifier__sample_weight=fitting_weights)
            probability = model.predict_proba(VX)[:,1]
            detail = {'fit_and_predict_seconds':perf_counter()-start,
                'enrollment_balanced':metrics(VY,probability,vweights), 'snapshot_weighted':metrics(VY,probability),
                'calibration_enrollment_balanced':calibration(VY,probability,vweights),
                'by_week':{}, 'by_module':{}, 'by_module_coverage':{},
                'outcome_recall_at_0_5': {o:float(np.average(probability[voutcomes==o]>=0.5, weights=vweights[voutcomes==o]))
                                        for o in ['Fail','Withdrawn'] if (voutcomes==o).any()},
                'hypothetical_student_outreach':outreach(vids,VY,probability)}
            for field,index in [('by_week',3),('by_module',0)]:
                categories = np.array([i[index] for i in vids])
                for value in sorted(set(categories)):
                    mask = categories==value
                    detail[field][value]=metrics(VY[mask],probability[mask],vweights[mask])
            known = np.array([i[0] in familiar for i in vids])
            for value,mask in [('familiar',known),('unseen',~known)]:
                if mask.any(): detail['by_module_coverage'][value]=metrics(VY[mask],probability[mask],vweights[mask])
            report['models'][name]=detail
            joblib.dump({'pipeline':model,'features':FEATURES,'research_only':True},output/(name+'.joblib'))
            print(name+' validation AP='+str(detail['enrollment_balanced']['average_precision']), flush=True)
    ranked=sorted(report['models'],key=lambda n:(-report['models'][n]['enrollment_balanced']['average_precision'],n))
    report['selected_model']=ranked[0]
    report['validation_ranking']=ranked
    (output/'validation_metrics.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--splits',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    report=run(args.splits,args.output)
    print('Selected on validation only: '+report['selected_model'])


if __name__=='__main__': main()
