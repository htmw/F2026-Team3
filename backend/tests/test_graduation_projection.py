from datetime import date
import pytest
from risk_mvp.graduation import project

@pytest.mark.parametrize("required,earned,current,day,pace,expected", [
    (30,18,6,date(2027,2,16),9,"December 2027"),
    (30,24,6,date(2027,2,16),9,"May 2027"),
    (30,0,9,date(2027,2,16),9,"December 2028"),
    (30,0,9,date(2027,2,16),12,"May 2028"),
    (30,21,0,date(2027,2,16),9,"December 2027"),
    (30,21,0,date(2027,6,1),9,"December 2027"),
    (30,21,0,date(2027,10,1),9,"May 2028"),
    (30,21,9,date(2027,12,31),9,"December 2027"),
    (30,30,0,date(2027,2,16),9,"Credits complete"),
    (30,33,0,date(2027,2,16),9,"Credits complete"),
])
def test_projection(required,earned,current,day,pace,expected):
    assert project(required,earned,current,day,pace) == expected

@pytest.mark.parametrize("values", [(0,0,0,9),(30,-1,0,9),(30,0,-1,9),(30,0,0,0),(float("nan"),0,0,9)])
def test_invalid(values):
    required,earned,current,pace=values
    with pytest.raises(ValueError):
        project(required,earned,current,date(2027,2,16),pace)
