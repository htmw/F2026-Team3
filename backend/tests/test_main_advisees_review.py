"""Independent attention/graduation filters and consistent list counts."""
from unittest.mock import patch
from types import SimpleNamespace
from services import advisees

def test_graduation_does_not_hide_attention():
    row={'status':'Graduating','risk':'High'}
    assert advisees.matches_filter(row,'Needs attention')
    assert advisees.matches_filter(row,'Graduating')
    assert not advisees.matches_filter(row,'On track')
    row['risk']='Low'
    assert advisees.matches_filter(row,'On track')
    assert advisees.matches_filter(row,'Graduating')
    assert not advisees.matches_filter(row,'Needs attention')

def test_count_search_and_priority_use_same_independent_filter():
    def rows():
        return [dict(studentId=i,fullName=name,status=status,risk=risk,_sort=(name,),_student=None,_riskFlag=None)
                for i,name,status,risk in [(1,'Graduate Example','Graduating','High'),(2,'Other Example','Needs attention','Medium'),(3,'Clear Example','On track','Low')]]
    with patch.object(advisees,'caseload',side_effect=lambda *args:(rows(),None)):
        result=advisees.list_for(None,SimpleNamespace(department="Computer Science"),'Needs attention')
        assert [r['studentId'] for r in result['rows']]==[1,2]
        assert next(t['count'] for t in result['tabs'] if t['label']=='Needs attention')==2
        searched=advisees.list_for(None,SimpleNamespace(department="Computer Science"),'Needs attention','graduate')
        assert [r['studentId'] for r in searched['rows']]==[1]
        assert searched['tabs']==result['tabs']
        assert searched['total']==3
