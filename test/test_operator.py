from datetime import datetime as dt

import pytz
import pytest

import numpy as np
import pandas as pd
from psyl import lisp

from tshistory.testutil import (
    assert_df,
    utcdt
)
from tshistory_formula.registry import (
    finder,
    func
)
from tshistory_formula.interpreter import Interpreter


def test_naive_tzone(engine, tsh):
    x = pd.Series(
        [1, 2, 3],
        index=pd.date_range(utcdt(2020, 1, 1), periods=3, freq='D')
    )
    tsh.update(engine, x, 'non-naive', 'Babar')

    tsh.register_formula(
        engine,
        'to-naive',
        '(naive (series "non-naive") "Europe/Paris")',
    )
    ts = tsh.get(engine, 'to-naive')
    assert_df("""
2020-01-01 01:00:00    1.0
2020-01-02 01:00:00    2.0
2020-01-03 01:00:00    3.0
""", ts)

    meta = tsh.metadata(engine, 'to-naive')
    assert meta['tzaware'] == False

    tsh.update(
        engine,
        pd.Series(
            range(5),
            pd.date_range(utcdt(2020, 10, 25), periods=5, freq='H')
        ),
        'non-naive',
        'Celeste'
    )
    ts = tsh.get(engine, 'to-naive')
    assert_df("""
2020-01-01 01:00:00    1.0
2020-01-02 01:00:00    2.0
2020-01-03 01:00:00    3.0
2020-10-25 02:00:00    0.5
2020-10-25 03:00:00    2.0
2020-10-25 04:00:00    3.0
2020-10-25 05:00:00    4.0
""", ts)

    @func('tzaware-autotrophic')
    def tzauto() -> pd.Series:
        return pd.Series(
            [1., 2., 3., 4., 5.],
            index=pd.date_range(utcdt(2020, 10, 25), periods=5, freq='H')
        )

    @finder('tzaware-autotrophic')
    def tzauto(cn, tsh, tree):
        return {
            'tzaware-autotrophic' : {
                'tzaware': True,
                'index_type': 'datetime64[ns, UTC]',
                'value_type': 'float64',
                'index_dtype': '|M8[ns]',
                'value_dtype': '<f8'
            }
        }

    tsh.update(
        engine,
        pd.Series(
            [1., 2., 3., 4., 5],
            index=pd.date_range(dt(2020, 10, 25), periods=5, freq='H')
        ),
        'really-naive',
        'Celeste'
    )

    with pytest.raises(ValueError):
        tsh.register_formula(
            engine,
            'combine-naive-non-naive',
            '(add (series "really-naive")'
            '     (naive (tzaware-autotrophic) "Europe/Paris"))'
        )


def test_add(engine, tsh):
    tsh.register_formula(
        engine,
        'addseries',
        '(add '
        '  (series "x" #:fill "ffill")'
        '  (series "y" #:fill "bfill")'
        '  (series "z" #:fill 0))',
        False
    )

    idate = utcdt(2019, 1, 1)
    x = pd.Series(
        [1, 2, 3],
        index=pd.date_range(dt(2019, 1, 1), periods=3, freq='D')
    )

    tsh.update(engine, x, 'x', 'Babar',
               insertion_date=idate)

    y = pd.Series(
        [7, 8, 9],
        index=pd.date_range(dt(2019, 1, 3), periods=3, freq='D')
    )

    tsh.update(engine, y, 'y', 'Babar',
               insertion_date=idate)

    z = pd.Series(
        [0],
        index=pd.date_range(dt(2019, 1, 3), periods=1, freq='D')
    )

    tsh.update(engine, z, 'z', 'Babar',
               insertion_date=idate)

    ts = tsh.get(engine, 'addseries')
    assert_df("""
2019-01-01     8.0
2019-01-02     9.0
2019-01-03    10.0
2019-01-04    11.0
2019-01-05    12.0
""", ts)

    limited = tsh.get(
        engine, 'addseries',
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

    tsh.update(engine, x, 'x', 'Babar',
               insertion_date=idate2)

    y = pd.Series(
        [8, 9, 10],
        index=pd.date_range(dt(2019, 1, 3), periods=3, freq='D')
    )

    tsh.update(engine, y, 'y', 'Babar',
               insertion_date=idate2)

    ts = tsh.get(engine, 'addseries')
    assert_df("""
2019-01-01    10.0
2019-01-02    11.0
2019-01-03    12.0
2019-01-04    13.0
2019-01-05    14.0
""", ts)

    ts = tsh.get(engine, 'addseries', revision_date=idate)
    assert_df("""
2019-01-01     8.0
2019-01-02     9.0
2019-01-03    10.0
2019-01-04    11.0
2019-01-05    12.0
""", ts)


def test_scalar_div(engine, tsh):
    a = pd.Series(
        [1, 2, 3],
        index=pd.date_range(dt(2019, 1, 1), periods=3, freq='D')
    )
    tsh.update(engine, a, 'div-me', 'Babar')
    ts = tsh.eval_formula(
        engine,
        '(/ (series "div-me") (/ 3 2))'
    )
    assert_df("""
2019-01-01    0.666667
2019-01-02    1.333333
2019-01-03    2.000000
""", ts)


def test_priority(engine, tsh):
    tsh.register_formula(
        engine,
        'test_prio',
        '(priority (series "c" #:prune 1) (series "b") (series "a"))',
        False
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

    tsh.update(engine, a, 'a', 'Babar')
    tsh.update(engine, b, 'b', 'Celeste')
    tsh.update(engine, c, 'c', 'Arthur')

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

    # type
    assert tsh.type(engine, 'no-such-series') == 'primary'
    assert tsh.type(engine, 'test_prio') == 'formula'
    assert tsh.type(engine, 'a') == 'primary'
    assert not tsh.exists(engine, 'no-such-series')
    assert tsh.type(engine, 'test_prio')
    assert tsh.type(engine, 'a')


def test_priority2(engine, tsh):
    tsh.register_formula(
        engine,
        'test_prio2',
        '(priority (series "real") (series "nom") (series "fcst"))',
        False
    )

    real = pd.Series(
        [1, 1, 1],
        index=pd.date_range(dt(2019, 1, 1), periods=3, freq='D')
    )
    nom = pd.Series(
        [10, 10, 10, 10],
        index=pd.date_range(dt(2019, 1, 1), periods=4, freq='D')
    )
    fcst = pd.Series(
        [100, 100, 100, 100, 100],
        index=pd.date_range(dt(2019, 1, 1), periods=5, freq='D')
    )

    tsh.update(engine, real, 'real', 'Babar')
    tsh.update(engine, nom, 'nom', 'Celeste')
    tsh.update(engine, fcst, 'fcst', 'Arthur')

    prio = tsh.get(engine, 'test_prio2')

    assert_df("""
2019-01-01      1.0
2019-01-02      1.0
2019-01-03      1.0
2019-01-04     10.0
2019-01-05    100.0
""", prio)


def test_clip(engine, tsh):
    tsh.register_formula(
        engine,
        'test_clip',
        '(clip (series "a") #:min 2 #:max 4)'
    )

    a = pd.Series(
        [1, 2, 3, 4, 5],
        index=pd.date_range(dt(2019, 1, 1), periods=5, freq='D')
    )
    tsh.update(engine, a, 'a', 'Babar')

    cleaned = tsh.get(engine, 'test_clip')
    assert_df("""
2019-01-02    2.0
2019-01-03    3.0
2019-01-04    4.0
""", cleaned)

    restricted = tsh.get(
        engine,
        'test_clip',
        from_value_date=dt(2019, 1, 3),
        to_value_date=dt(2019, 1, 3)
    )
    assert_df("""
2019-01-03    3.0
""", restricted)

    tsh.register_formula(
        engine,
        'test_clip_replaced',
        '(clip (series "a") #:min 2 #:max 4 #:replacemin #t #:replacemax #t)'
    )

    replaced = tsh.get(engine, 'test_clip_replaced')
    assert_df("""
2019-01-01    2.0
2019-01-02    2.0
2019-01-03    3.0
2019-01-04    4.0
2019-01-05    4.0
""", replaced)


def test_slice(engine, tsh):
    base = pd.Series(
        [1, 2, 3],
        index=pd.date_range(utcdt(2019, 1, 1), periods=3, freq='D')
    )
    tsh.update(engine, base, 'test-slice', 'Babar')
    tsh.register_formula(
        engine,
        'slicing-id',
        '(slice (series "test-slice"))',
    )
    tsh.register_formula(
        engine,
        'slicing-from',
        '(slice (series "test-slice") #:fromdate (date "2019-1-2"))',
    )
    tsh.register_formula(
        engine,
        'slicing-fromto',
        '(slice (series "test-slice") '
        ' #:fromdate (date "2019-1-2") '
        ' #:todate (date "2019-1-2")'
        ')',
    )
    tsh.register_formula(
        engine,
        'slicing-empty',
        '(slice (series "test-slice") '
        ' #:fromdate (date "2018-1-2") '
        ' #:todate (date "2018-1-2")'
        ')',
    )

    assert_df("""
2019-01-01 00:00:00+00:00    1.0
2019-01-02 00:00:00+00:00    2.0
2019-01-03 00:00:00+00:00    3.0
""", tsh.get(engine, 'slicing-id'))

    assert_df("""
2019-01-02 00:00:00+00:00    2.0
2019-01-03 00:00:00+00:00    3.0
""", tsh.get(engine, 'slicing-from'))

    assert_df("""
2019-01-02 00:00:00+00:00    2.0
""", tsh.get(engine, 'slicing-fromto'))

    assert len(tsh.get(engine, 'slicing-empty')) == 0


def test_slice_options(engine, tsh):
    base = pd.Series(
        [1, 2, 3],
        index=pd.date_range(utcdt(2019, 1, 1), periods=3, freq='D')
    )
    tsh.update(engine, base, 'test-slice', 'Babar')
    # options transmissions
    ts = tsh.eval_formula(
        engine,
        '(add (series "test-slice") '
        '     (slice (series "test-slice" #:fill 0) #:fromdate (date "2019-1-2")))',
    )
    assert_df("""
2019-01-01 00:00:00+00:00    1.0
2019-01-02 00:00:00+00:00    4.0
2019-01-03 00:00:00+00:00    6.0
""", ts)


def test_mul(engine, tsh):
    base = pd.Series(
        [1, 2, 3],
        index=pd.date_range(utcdt(2019, 1, 1), periods=3, freq='D')
    )
    tsh.update(engine, base, 'mul-a', 'Babar')
    tsh.update(engine, base, 'mul-b', 'Babar')
    tsh.update(engine, base, 'mul-c', 'Babar')
    tsh.register_formula(
        engine,
        'multiply-aligned',
        '(mul (series "mul-a") (series "mul-b") (series "mul-c"))',
    )

    ts = tsh.get(engine, 'multiply-aligned')
    assert_df("""
2019-01-01 00:00:00+00:00     1.0
2019-01-02 00:00:00+00:00     8.0
2019-01-03 00:00:00+00:00    27.0
""", ts)

    base = pd.Series(
        [1, 2, np.nan],
        index=pd.date_range(utcdt(2019, 1, 1), periods=3, freq='D')
    )
    tsh.update(engine, base, 'mul-b', 'Babar')

    ts = tsh.get(engine, 'multiply-aligned')
    assert_df("""
2019-01-01 00:00:00+00:00    1.0
2019-01-02 00:00:00+00:00    8.0
""", ts)

    tsh.register_formula(
        engine,
        'multiply-aligned',
        '(mul (series "mul-a") (series "mul-b" #:fill 1) (series "mul-c"))',
        update=True
    )
    ts = tsh.get(engine, 'multiply-aligned')
    assert_df("""
2019-01-01 00:00:00+00:00    1.0
2019-01-02 00:00:00+00:00    8.0
2019-01-03 00:00:00+00:00    9.0
""", ts)


def test_div(engine, tsh):
    base = pd.Series(
        [1, 2, 3],
        index=pd.date_range(utcdt(2019, 1, 1), periods=3, freq='D')
    )
    tsh.update(engine, base, 'div-a', 'Babar')
    tsh.update(engine, base, 'div-b', 'Babar')
    tsh.register_formula(
        engine,
        'divide',
        '(div (series "div-a") (series "div-b"))',
    )

    ts = tsh.get(engine, 'divide')
    assert_df("""
2019-01-01 00:00:00+00:00    1.0
2019-01-02 00:00:00+00:00    1.0
2019-01-03 00:00:00+00:00    1.0
""", ts)

    base = pd.Series(
        [2, 1, np.nan],
        index=pd.date_range(utcdt(2019, 1, 1), periods=3, freq='D')
    )
    tsh.update(engine, base, 'div-b', 'Babar')

    ts = tsh.get(engine, 'divide')
    assert_df("""
2019-01-01 00:00:00+00:00    0.5
2019-01-02 00:00:00+00:00    2.0
""", ts)

    tsh.register_formula(
        engine,
        'divide',
        '(div (series "div-a") (series "div-b" #:fill 3))',
        update=True
    )
    ts = tsh.get(engine, 'divide')
    assert_df("""
2019-01-01 00:00:00+00:00    0.5
2019-01-02 00:00:00+00:00    2.0
2019-01-03 00:00:00+00:00    1.0
""", ts)


def test_row_mean(engine, tsh):
    dates = pd.date_range(
        start=utcdt(2015, 1, 1),
        freq='D',
        periods=7
    )

    station0 = pd.Series([0] * 7, index=dates)
    station1 = pd.Series([1] * 7, index=dates)
    station2 = pd.Series([2] * 7, index=dates)

    # we add some perturbations:
    station1 = station1.drop(station0.index[2])
    station0 = station0.drop(station0.index[4])
    station2 = station2.drop(station2.index[4])

    summary = pd.concat(
        [station0, station1, station2],
        axis=1
    )

    assert_df("""
                             0    1    2
2015-01-01 00:00:00+00:00  0.0  1.0  2.0
2015-01-02 00:00:00+00:00  0.0  1.0  2.0
2015-01-03 00:00:00+00:00  0.0  NaN  2.0
2015-01-04 00:00:00+00:00  0.0  1.0  2.0
2015-01-05 00:00:00+00:00  NaN  1.0  NaN
2015-01-06 00:00:00+00:00  0.0  1.0  2.0
2015-01-07 00:00:00+00:00  0.0  1.0  2.0
""", summary)

    tsh.update(engine, station0, 'station0', 'Babar')
    tsh.update(engine, station1, 'station1', 'Celeste')
    tsh.update(engine, station2, 'station2', 'Arthur')

    formula = (
        '(row-mean '
        '  (series "station0") '
        '  (series "station1") '
        '  (series "station2" #:weight 2))'
    )

    tsh.register_formula(
        engine,
        'weather_index',
        formula
    )

    avg_index = tsh.get(engine, 'weather_index')
    assert_df("""
2015-01-01 00:00:00+00:00    1.250000
2015-01-02 00:00:00+00:00    1.250000
2015-01-03 00:00:00+00:00    1.333333
2015-01-04 00:00:00+00:00    1.250000
2015-01-05 00:00:00+00:00    1.000000
2015-01-06 00:00:00+00:00    1.250000
2015-01-07 00:00:00+00:00    1.250000
""", avg_index)

    formula = '(min (series "station0") (series "station1") (series "station2"))'
    tsh.register_formula(
        engine,
        'weather_min',
        formula
    )

    assert_df("""
2015-01-01 00:00:00+00:00    0.0
2015-01-02 00:00:00+00:00    0.0
2015-01-03 00:00:00+00:00    0.0
2015-01-04 00:00:00+00:00    0.0
2015-01-05 00:00:00+00:00    1.0
2015-01-06 00:00:00+00:00    0.0
2015-01-07 00:00:00+00:00    0.0
""", tsh.get(engine, 'weather_min'))


    formula = '(max (series "station0") (series "station1") (series "station2"))'
    tsh.register_formula(
        engine,
        'weather_max',
        formula
    )

    assert_df("""
2015-01-01 00:00:00+00:00    2.0
2015-01-02 00:00:00+00:00    2.0
2015-01-03 00:00:00+00:00    2.0
2015-01-04 00:00:00+00:00    2.0
2015-01-05 00:00:00+00:00    1.0
2015-01-06 00:00:00+00:00    2.0
2015-01-07 00:00:00+00:00    2.0
""", tsh.get(engine, 'weather_max'))

    formula = '(std (series "station0") (series "station1") (series "station2"))'
    tsh.register_formula(
        engine,
        'weather_std',
        formula
    )

    assert_df("""
2015-01-01 00:00:00+00:00    1.000000
2015-01-02 00:00:00+00:00    1.000000
2015-01-03 00:00:00+00:00    1.414214
2015-01-04 00:00:00+00:00    1.000000
2015-01-06 00:00:00+00:00    1.000000
2015-01-07 00:00:00+00:00    1.000000
""", tsh.get(engine, 'weather_std'))


def test_date(engine, tsh):
    e1 = '(date "2018-1-1")'
    e2 = '(date "2018-1-1" #:naive #t)'
    e3 = '(date "2018-1-1 12:00:00" #:naive #t #:tz "Europe/Moscow")'
    e4 = '(date "2018-1-1" #:naive #f)'
    e5 = '(date "2018-1-1 12:00:00" #:naive #f #:tz "Europe/Moscow")'
    e6 = '(date "2020-1-1 06:42:30")'
    e7 = '(date "2020-1-1" #:tz "Gondwana/Chandrapore")'

    i = Interpreter(engine, tsh, {})
    a = lisp.evaluate(e1, i.env)
    b = lisp.evaluate(e2, i.env)
    with pytest.raises(AssertionError) as err:
        lisp.evaluate(e3, i.env)
    assert err.value.args[0] == 'date cannot be naive and have a tz'
    d = lisp.evaluate(e4, i.env)
    e = lisp.evaluate(e5, i.env)
    f = lisp.evaluate(e6, i.env)
    with pytest.raises(pytz.UnknownTimeZoneError) as err:
        lisp.evaluate(e7, i.env)
    assert err.value.args[0] == 'Gondwana/Chandrapore'

    assert a == pd.Timestamp('2018-01-01 00:00:00+0000', tz='UTC')
    assert b == pd.Timestamp('2018-01-01 00:00:00')
    assert d == pd.Timestamp('2018-01-01 00:00:00+0000', tz='UTC')
    assert e == pd.Timestamp('2018-01-01 12:00:00+0300', tz='Europe/Moscow')
    assert f == pd.Timestamp('2020-01-01 06:42:30+0000', tz='UTC')


def test_timedelta(engine, tsh):
    e1 = '(timedelta (date "2020-1-1"))'  # null
    e2 = '(timedelta (date "2020-1-1") #:years 1)'
    e3 = '(timedelta (date "2020-1-1") #:months 1) '
    e4 = '(timedelta (date "2020-1-1") #:weeks 1)'
    e5 = '(timedelta (date "2020-1-1") #:days 1)'
    e6 = '(timedelta (date "2020-1-1") #:hours 1)'
    e7 = '(timedelta (date "2020-1-1") #:minutes 1)'

    i = Interpreter(engine, tsh, {})
    a = lisp.evaluate(e1, i.env)
    b = lisp.evaluate(e2, i.env)
    c = lisp.evaluate(e3, i.env)
    d = lisp.evaluate(e4, i.env)
    e = lisp.evaluate(e5, i.env)
    f = lisp.evaluate(e6, i.env)
    g = lisp.evaluate(e7, i.env)

    assert a == pd.Timestamp('2020-01-01 00:00:00+0000', tz='UTC')
    assert b == pd.Timestamp('2021-01-01 00:00:00+0000', tz='UTC')
    assert c == pd.Timestamp('2020-02-01 00:00:00+0000', tz='UTC')
    assert d == pd.Timestamp('2020-01-08 00:00:00+0000', tz='UTC')
    assert e == pd.Timestamp('2020-01-02 00:00:00+0000', tz='UTC')
    assert f == pd.Timestamp('2020-01-01 01:00:00+0000', tz='UTC')
    assert g == pd.Timestamp('2020-01-01 00:01:00+0000', tz='UTC')


def test_today(engine, tsh):
    e1 = '(today)'
    e2 = '(today #:naive #t)'
    e3 = '(today #:naive #t #:tz "Europe/Moscow")'
    e4 = '(today #:naive #f)'
    e5 = '(today #:naive #f #:tz "Europe/Moscow")'
    e6 = '(today #:tz "Gondwana/Chandrapore")'

    i = Interpreter(engine, tsh, {})
    a = lisp.evaluate(e1, i.env)
    b = lisp.evaluate(e2, i.env)
    with pytest.raises(AssertionError) as err:
        lisp.evaluate(e3, i.env)
    assert err.value.args[0] == 'date cannot be naive and have a tz'
    d = lisp.evaluate(e4, i.env)
    e = lisp.evaluate(e5, i.env)
    with pytest.raises(pytz.UnknownTimeZoneError) as err:
        lisp.evaluate(e6, i.env)
    assert err.value.args[0] == 'Gondwana/Chandrapore'

    assert a.tz == pytz.utc
    assert b.tz is None
    assert d.tz == pytz.utc
    assert e.tz.zone == 'Europe/Moscow'


def test_resample(engine, tsh):
    hourly = pd.Series(
        list(range(36)),
        index=pd.date_range(utcdt(2020, 1, 1), periods=36, freq='H')
    )

    gasday = pd.Series(
        [1, 2, 3],
        index=pd.date_range(utcdt(2020, 1, 1, 5), periods=3, freq='D')
    )

    tsh.update(engine, hourly, 'hourly', 'Babar')
    tsh.update(engine, gasday, 'gasday', 'Celeste')

    tsh.register_formula(
        engine,
        'hourly2daily',
        '(resample (series "hourly") "D")'
    )
    tsh.register_formula(
        engine,
        'hourly2dailysum',
        '(resample (series "hourly") "D" "sum")'
    )
    tsh.register_formula(
        engine,
        'gasdaytoday',
        '(resample (series "gasday") "D")'
    )
    tsh.register_formula(
        engine,
        'badmethod',
        '(resample (series "gasday") "D" "NO-SUCH-METHOD")'
    )

    assert_df("""
2020-01-01 00:00:00+00:00    11.5
2020-01-02 00:00:00+00:00    29.5
""", tsh.get(engine, 'hourly2daily'))

    assert_df("""
2020-01-01 00:00:00+00:00    276.0
2020-01-02 00:00:00+00:00    354.0
""", tsh.get(engine, 'hourly2dailysum'))

    assert_df("""
2020-01-01 00:00:00+00:00    1.0
2020-01-02 00:00:00+00:00    2.0
2020-01-03 00:00:00+00:00    3.0
""", tsh.get(engine, 'gasdaytoday'))

    with pytest.raises(ValueError) as err:
        tsh.get(engine, 'badmethod')
    assert err.value.args[0] == 'bad resampling method `NO-SUCH-METHOD`'

    gasday['2020-1-2'] = np.nan
    tsh.update(engine, gasday, 'gasday', 'Celeste')
    assert_df("""
2020-01-01 00:00:00+00:00    1.0
2020-01-03 00:00:00+00:00    3.0
""", tsh.get(engine, 'gasdaytoday'))


def test_cumsum(engine, tsh):
    series = pd.Series(
        [1, 2, 3],
        index=pd.date_range(utcdt(2020, 1, 1), periods=3, freq='D')
    )

    tsh.update(
        engine,
        series,
        'sum-me',
        'Babar'
    )

    tsh.register_formula(
        engine,
        'test-cumsum',
        '(cumsum (series "sum-me"))'
    )

    s1 = tsh.get(engine, 'test-cumsum')
    assert_df("""
2020-01-01 00:00:00+00:00    1.0
2020-01-02 00:00:00+00:00    3.0
2020-01-03 00:00:00+00:00    6.0
""", s1)


def test_shift(engine, tsh):
    series = pd.Series(
        [1, 2, 3],
        index=pd.date_range(utcdt(2020, 1, 1), periods=3, freq='D')
    )

    tsh.update(
        engine,
        series,
        'shifted',
        'Babar'
    )

    tsh.register_formula(
        engine,
        'test-shift',
        '(shift (series "shifted") #:days 2 #:hours 7)'
    )

    s1 = tsh.get(engine, 'test-shift')
    assert_df("""
2020-01-03 07:00:00+00:00    1.0
2020-01-04 07:00:00+00:00    2.0
2020-01-05 07:00:00+00:00    3.0
""", s1)
