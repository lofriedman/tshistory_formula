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


def test_linear_combo(engine, tsh):
    tsh.register_formula(
        engine,
        'x_plus_y',
        '(add (list (series "x" #:fill "ffill") (series "y" #:fill "bfill")))')

    x = pd.Series(
        [1, 2, 3],
        index=pd.date_range(dt(2019, 1, 1), periods=3, freq='D')
    )

    tsh.insert(engine, x, 'x', 'Babar')

    y = pd.Series(
        [7, 8, 9],
        index=pd.date_range(dt(2019, 1, 3), periods=3, freq='D')
    )

    tsh.insert(engine, y, 'y', 'Babar')

    twomore = tsh.get(engine, 'x_plus_y')
    assert_df("""
2019-01-01     8.0
2019-01-02     9.0
2019-01-03    10.0
2019-01-04    11.0
2019-01-05    12.0
""", twomore)


def test_priority(engine, tsh):
    tsh.register_formula(
        engine,
        'test_prio',
        '(priority (list (series "a") (series "b") (series "c" #:prune #t)))'
    )

    a = pd.Series(
        [1, 2, 3],
        index=pd.date_range(dt(2019, 1, 1), periods=3, freq='D')
    )
    b = pd.Series(
        [10, 20, 30],
        index=pd.date_range(dt(2019, 1, 2), periods=3, freq='D')
    )
    c = pd.Series(
        [100, 200, 300],
        index=pd.date_range(dt(2019, 1, 3), periods=3, freq='D')
    )

    tsh.insert(engine, a, 'a', 'Babar')
    tsh.insert(engine, b, 'b', 'Celeste')
    tsh.insert(engine, c, 'c', 'Arthur')

    prio = tsh.get(engine, 'test_prio')

    assert_df("""
2019-01-01      1.0
2019-01-02     10.0
2019-01-03    100.0
2019-01-04    200.0
""", prio)
