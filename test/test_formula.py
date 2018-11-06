from datetime import datetime as dt
import pandas as pd

import pytest

from psyl import lisp
from tshistory.testutil import assert_df


def test_interpreter(engine):
    form = '(+ 2 3)'
    from psyl.lisp import evaluate
    with pytest.raises(LookupError):
        e = evaluate(form)

    env = lisp.Env({'+': lambda a, b: a + b})
    e = evaluate(form, env)
    assert e == 5


def test_base_api(engine, tsh):
    tsh.register_formula(engine, 'test_plus_two', '(+ (series "test") 2)')

    test = pd.Series(
        [1, 2, 3],
        index=pd.date_range(dt(2019, 1, 1), periods=3, freq='D')
    )

    tsh.insert(engine, test, 'test', 'Babar')

    twomore = tsh.get(engine, 'test_plus_two')
    assert_df("""
2019-01-01    3.0
2019-01-02    4.0
2019-01-03    5.0
""", twomore)
