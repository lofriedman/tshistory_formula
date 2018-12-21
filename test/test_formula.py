from datetime import datetime as dt
import pandas as pd

import pytest

from psyl import lisp
from tshistory.testutil import assert_df


def utcdt(*dtargs):
    return pd.Timestamp(dt(*dtargs), tz='UTC')


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

    tsh.register_formula(engine, 'test_product', '(* (series "test") 1.5)')

    plus = tsh.get(engine, 'test_product')
    assert_df("""
2019-01-01    1.5
2019-01-02    3.0
2019-01-03    4.5
""", plus)


def test_linear_combo(engine, tsh):
    tsh.register_formula(
        engine,
        'x_plus_y',
        '(add (list (series "x" #:fill "ffill") (series "y" #:fill "bfill")))')

    idate = utcdt(2019, 1, 1)
    x = pd.Series(
        [1, 2, 3],
        index=pd.date_range(dt(2019, 1, 1), periods=3, freq='D')
    )

    tsh.insert(engine, x, 'x', 'Babar',
               _insertion_date=idate)

    y = pd.Series(
        [7, 8, 9],
        index=pd.date_range(dt(2019, 1, 3), periods=3, freq='D')
    )

    tsh.insert(engine, y, 'y', 'Babar',
               _insertion_date=idate)

    twomore = tsh.get(engine, 'x_plus_y')
    assert_df("""
2019-01-01     8.0
2019-01-02     9.0
2019-01-03    10.0
2019-01-04    11.0
2019-01-05    12.0
""", twomore)

    limited = tsh.get(
        engine, 'x_plus_y',
        from_value_date=dt(2019, 1, 3),
        to_value_date=dt(2019, 1, 4)
    )
    assert_df("""
2019-01-03    10.0
2019-01-04    11.0
""", limited)

    # make some history
    idate2 = utcdt(2019, 1, 2)
    x = pd.Series(
        [2, 3, 4],
        index=pd.date_range(dt(2019, 1, 1), periods=3, freq='D')
    )

    tsh.insert(engine, x, 'x', 'Babar',
               _insertion_date=idate2)

    y = pd.Series(
        [8, 9, 10],
        index=pd.date_range(dt(2019, 1, 3), periods=3, freq='D')
    )

    tsh.insert(engine, y, 'y', 'Babar',
               _insertion_date=idate2)

    twomore = tsh.get(engine, 'x_plus_y')
    assert_df("""
2019-01-01    10.0
2019-01-02    11.0
2019-01-03    12.0
2019-01-04    13.0
2019-01-05    14.0
""", twomore)

    twomore = tsh.get(engine, 'x_plus_y', revision_date=idate)
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
        '(priority (list (series "a") (series "b") (series "c" #:prune 1)))'
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

    limited = tsh.get(
        engine,
        'test_prio',
        from_value_date=dt(2019, 1, 2),
        to_value_date=dt(2019, 1, 3)
    )
    # NOTE that the 1-3 point is now 20 because the 100 (series c)
    #      point has been pruned
    assert_df("""
2019-01-02    10.0
2019-01-03    20.0
""", limited)


def test_outliers(engine, tsh):
    tsh.register_formula(
        engine,
        'test_outliers',
        '(outliers (series "a") #:min 2 #:max 4)'
    )

    a = pd.Series(
        [1, 2, 3, 4, 5],
        index=pd.date_range(dt(2019, 1, 1), periods=5, freq='D')
    )
    tsh.insert(engine, a, 'a', 'Babar')

    cleaned = tsh.get(engine, 'test_outliers')
    assert_df("""
2019-01-02    2.0
2019-01-03    3.0
2019-01-04    4.0
""", cleaned)

    restricted = tsh.get(
        engine,
        'test_outliers',
        from_value_date=dt(2019, 1, 3),
        to_value_date=dt(2019, 1, 3)
    )
    assert_df("""
2019-01-03    3.0
""", restricted)
