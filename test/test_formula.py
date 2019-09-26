import math
import json
from datetime import datetime as dt, timedelta

import pandas as pd
import numpy as np
import pytest

from psyl import lisp
from tshistory.testutil import assert_df, assert_hist

from tshistory_formula.registry import (
    func,
    FUNCS,
    finder
)
from tshistory_formula.interpreter import jsontypes
from tshistory_formula.editor import fancypresenter


def utcdt(*dtargs):
    return pd.Timestamp(dt(*dtargs), tz='UTC')


def test_interpreter(engine):
    form = '(+ 2 3)'
    with pytest.raises(LookupError):
        e = lisp.evaluate(form)

    env = lisp.Env({'+': lambda a, b: a + b})
    e = lisp.evaluate(form, env)
    assert e == 5

    brokenform = '(+ 2 3'
    with pytest.raises(SyntaxError):
        lisp.parse(brokenform)


def test_metadata(engine, tsh):
    naive = pd.Series(
        [1, 2, 3],
        index=pd.date_range(dt(2019, 1, 1), periods=3, freq='D')
    )

    tsh.insert(engine, naive, 'metadata_naive', 'Babar',
               insertion_date=utcdt(2019, 1, 1))

    tsh.register_formula(
        engine,
        'test_meta',
        '(+ (series "metadata_naive") 2)',
    )

    assert tsh.metadata(engine, 'test_meta') == {
        'index_type': 'datetime64[ns]',
        'tzaware': False,
        'value_type': 'float64'
    }

    aware = pd.Series(
        [1, 2, 3],
        index=pd.date_range(utcdt(2019, 1, 1), periods=3, freq='D')
    )
    tsh.insert(engine, aware, 'metadata_tzaware', 'Babar',
               insertion_date=utcdt(2019, 1, 1))


    with pytest.raises(ValueError) as err:
        tsh.register_formula(
            engine,
            'test_meta_mismatch',
            '(add (series "test_meta") (series "metadata_tzaware"))',
        )
    assert err.value.args[0] == (
        "Formula `metadata_tzaware`: mismatching metadata:"
        "`test_meta:{'tzaware': False, "
        "'index_type': 'datetime64[ns]', 'value_type': 'float64'}`, "
        "`metadata_tzaware:{'tzaware': "
        "True, 'index_type': 'datetime64[ns, UTC]', 'value_type': 'float64'}`"
    )

    tsh.register_formula(
        engine,
        'test_meta_primary_plus_formula',
        '(add (series "test_meta") (series "metadata_naive"))',
    )
    meta = tsh.metadata(engine, 'test_meta_primary_plus_formula')
    assert meta == {
        'index_type': 'datetime64[ns]',
        'tzaware': False,
        'value_type': 'float64'
    }


def test_series_options(engine, tsh):
    test = pd.Series(
        [1, 2, 3],
        index=pd.date_range(dt(2019, 1, 1), periods=3, freq='D')
    )
    tsh.insert(engine, test, 'options-a', 'Babar')
    tsh.insert(engine, test, 'options-b', 'Babar')
    tsh.register_formula(
        engine,
        'test_series_option',
        '(add (series "options-a") (series "options-b"))',
    )

    ts = tsh.get(engine, 'test_series_option')
    assert ts.options == {}


def test_base_api(engine, tsh):
    tsh.register_formula(engine, 'test_plus_two', '(+ (series "test") 2)', False)
    tsh.register_formula(engine, 'test_three_plus', '(+ 3 (series "test"))', False)

    with pytest.raises(AssertionError):
        tsh.register_formula(engine, 'test_plus_two', '(+ (series "test") 2)',
                             reject_unknown=False,
                             update=False)
    # accept an update
    tsh.register_formula(engine, 'test_plus_two', '(+ (series "test") 2)',
                         reject_unknown=False,
                         update=True)


    test = pd.Series(
        [1, 2, 3],
        index=pd.date_range(dt(2019, 1, 1), periods=3, freq='D')
    )

    tsh.insert(engine, test, 'test', 'Babar',
               insertion_date=utcdt(2019, 1, 1))

    twomore = tsh.get(engine, 'test_plus_two')
    assert_df("""
2019-01-01    3.0
2019-01-02    4.0
2019-01-03    5.0
""", twomore)

    nope = tsh.get(engine, 'test_plus_two', revision_date=utcdt(2018, 1, 1))
    assert len(nope) == 0

    evenmore = tsh.get(engine, 'test_three_plus')
    assert_df("""
2019-01-01    4.0
2019-01-02    5.0
2019-01-03    6.0
""", evenmore)

    tsh.register_formula(engine, 'test_product_a', '(* (series "test") 1.5)', False)
    tsh.register_formula(engine, 'test_product_b', '(* 2 (series "test"))', False)

    series = tsh.list_series(engine)
    assert series['test'] == 'primary'
    assert series['test_product_a'] == 'formula'

    plus = tsh.get(engine, 'test_product_a')
    assert_df("""
2019-01-01    1.5
2019-01-02    3.0
2019-01-03    4.5
""", plus)

    plus = tsh.get(engine, 'test_product_b')
    assert_df("""
2019-01-01    2.0
2019-01-02    4.0
2019-01-03    6.0
""", plus)

    m = tsh.metadata(engine, 'test_product_a')
    assert m == {
        'index_type': 'datetime64[ns]',
        'tzaware': False,
        'value_type': 'float64'
    }

    tsh.update_metadata(engine, 'test_product_a', {'topic': 'spot price'})
    m = tsh.metadata(engine, 'test_product_a')
    assert m == {
        'index_type': 'datetime64[ns]',
        'tzaware': False,
        'value_type': 'float64',
        'topic': 'spot price'
    }

    tsh.update_metadata(
        engine, 'test_product_a', {
            'topic': 'Spot Price',
            'unit': '€'
        }
    )
    m = tsh.metadata(engine, 'test_product_a')
    assert m == {
        'index_type': 'datetime64[ns]',
        'tzaware': False,
        'value_type': 'float64',
        'topic': 'Spot Price',
        'unit': '€'
    }

    tsh.delete(engine, 'test_plus_two')
    assert not tsh.exists(engine, 'test_plus_two')


def test_linear_combo(engine, tsh):
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

    tsh.insert(engine, x, 'x', 'Babar',
               insertion_date=idate)

    y = pd.Series(
        [7, 8, 9],
        index=pd.date_range(dt(2019, 1, 3), periods=3, freq='D')
    )

    tsh.insert(engine, y, 'y', 'Babar',
               insertion_date=idate)

    z = pd.Series(
        [0],
        index=pd.date_range(dt(2019, 1, 3), periods=1, freq='D')
    )

    tsh.insert(engine, z, 'z', 'Babar',
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

    tsh.insert(engine, x, 'x', 'Babar',
               insertion_date=idate2)

    y = pd.Series(
        [8, 9, 10],
        index=pd.date_range(dt(2019, 1, 3), periods=3, freq='D')
    )

    tsh.insert(engine, y, 'y', 'Babar',
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
    tsh.insert(engine, a, 'div-me', 'Babar')
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

    tsh.insert(engine, real, 'real', 'Babar')
    tsh.insert(engine, nom, 'nom', 'Celeste')
    tsh.insert(engine, fcst, 'fcst', 'Arthur')

    prio = tsh.get(engine, 'test_prio2')

    assert_df("""
2019-01-01      1.0
2019-01-02      1.0
2019-01-03      1.0
2019-01-04     10.0
2019-01-05    100.0
""", prio)


def test_options(engine, tsh):
    @func('dummy')
    def dummy():
        return pd.Series(
            [1, 2, 3],
            index=pd.date_range(dt(2019, 1, 1), periods=3, freq='D')
        )

    tsh.register_formula(
        engine,
        'test_options',
        '(* 3 (dummy))',
        False
    )

    assert_df("""
2019-01-01    3
2019-01-02    6
2019-01-03    9
""", tsh.get(engine, 'test_options'))

    FUNCS.pop('dummy')


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
    tsh.insert(engine, a, 'a', 'Babar')

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


def test_error(engine, tsh):
    with pytest.raises(SyntaxError):
        tsh.register_formula(
            engine,
            'test_error',
            '(clip (series "a")'
        )

    with pytest.raises(ValueError) as err:
        tsh.register_formula(
            engine,
            'test_error',
            '(priority (series "NOPE1") (series "NOPE2" #:prune 1))'
        )
    assert err.value.args[0] == (
        'Formula `test_error` refers to '
        'unknown series `NOPE1`, `NOPE2`'
    )


def test_history(engine, tsh):
    tsh.register_formula(
        engine,
        'h-addition',
        '(add (series "ha") (series "hb"))',
        False
    )

    for day in (1, 2, 3):
        idate = utcdt(2019, 1, day)
        for name in 'ab':
            ts = pd.Series(
                [day] * 3,
            index=pd.date_range(dt(2018, 1, 1), periods=3, freq='D')
            )
            tsh.insert(engine, ts, 'h' + name, 'Babar',
                       insertion_date=idate)

    h = tsh.history(engine, 'h-addition')
    assert_hist("""
insertion_date             value_date
2019-01-01 00:00:00+00:00  2018-01-01    2.0
                           2018-01-02    2.0
                           2018-01-03    2.0
2019-01-02 00:00:00+00:00  2018-01-01    4.0
                           2018-01-02    4.0
                           2018-01-03    4.0
2019-01-03 00:00:00+00:00  2018-01-01    6.0
                           2018-01-02    6.0
                           2018-01-03    6.0
""", h)

    h = tsh.history(
        engine, 'h-addition',
        from_insertion_date=utcdt(2019, 1, 2),
        to_insertion_date=utcdt(2019, 1, 2),
        from_value_date=dt(2018, 1, 2),
        to_value_date=dt(2018, 1, 2)
    )
    assert_hist("""
insertion_date             value_date
2019-01-02 00:00:00+00:00  2018-01-02    4.0
""", h)

    # let's add a priority
    tsh.register_formula(
        engine,
        'h-priority',
        '(priority (series "hz") (series "h-addition"))',
        False
    )
    for day in (1, 2, 3):
        idate = utcdt(2019, 1, day)
        ts = pd.Series(
            [41 + day] * 3,
            index=pd.date_range(dt(2018, 1, 3), periods=3, freq='D')
        )
        tsh.insert(engine, ts, 'hz', 'Babar',
                   insertion_date=idate)

    h = tsh.history(engine, 'h-priority')
    assert_hist("""
insertion_date             value_date
2019-01-01 00:00:00+00:00  2018-01-01     2.0
                           2018-01-02     2.0
                           2018-01-03    42.0
                           2018-01-04    42.0
                           2018-01-05    42.0
2019-01-02 00:00:00+00:00  2018-01-01     4.0
                           2018-01-02     4.0
                           2018-01-03    43.0
                           2018-01-04    43.0
                           2018-01-05    43.0
2019-01-03 00:00:00+00:00  2018-01-01     6.0
                           2018-01-02     6.0
                           2018-01-03    44.0
                           2018-01-04    44.0
                           2018-01-05    44.0
""", h)


def test_staircase(engine, tsh):
    tsh.register_formula(
        engine,
        's-addition',
        '(add (series "sa") (series "sb"))',
        False
    )

    for day in (1, 2, 3, 4, 5):
        idate = utcdt(2018, 1, day)
        for name in 'ab':
            ts = pd.Series(
                [day / 2.] * 5,
                index=pd.date_range(dt(2018, 1, day), periods=5, freq='D')
            )
            tsh.insert(engine, ts, 's' + name, 'Babar',
                       insertion_date=idate)

    ts = tsh.staircase(engine, 's-addition', delta=pd.Timedelta(hours=12))
    assert_df("""
2018-01-02    1.0
2018-01-03    2.0
2018-01-04    3.0
2018-01-05    4.0
2018-01-06    5.0
2018-01-07    5.0
2018-01-08    5.0
2018-01-09    5.0
""", ts)

    # this is not allowed in the staircase fast-path
    # hence we will take the slow path
    @func('identity')
    def identity(series):
        return series

    tsh.register_formula(
        engine,
        'slow-down',
        '(identity (series "sa"))',
        False
    )

    tsh.register_formula(
        engine,
        's-addition-not-fast',
        '(add (series "slow-down") (series "sb"))',
        False
    )
    ts = tsh.staircase(
        engine,
        's-addition-not-fast',
        delta=pd.Timedelta(hours=12)
    )
    assert_df("""
2018-01-02    1.0
2018-01-03    2.0
2018-01-04    3.0
2018-01-05    4.0
2018-01-06    5.0
2018-01-07    5.0
2018-01-08    5.0
2018-01-09    5.0
""", ts)

    # cleanup
    FUNCS.pop('identity')


def test_new_func(engine, tsh):

    @func('identity')
    def identity(series):
        return series

    tsh.register_formula(
        engine,
        'identity',
        '(identity (series "id-a"))',
        False
    )

    ts = pd.Series(
        [1, 2, 3],
        index=pd.date_range(dt(2019, 1, 1), periods=3, freq='D')
    )
    tsh.insert(engine, ts, 'id-a', 'Babar')

    ts = tsh.get(engine, 'identity')
    assert_df("""
2019-01-01    1.0
2019-01-02    2.0
2019-01-03    3.0
""", ts)

    # cleanup
    FUNCS.pop('identity')


def test_ifunc(engine, tsh):

    @func('shifted')
    def shifted(__interpreter__, name, days=0):
        args = __interpreter__.getargs.copy()
        fromdate = args.get('from_value_date')
        todate = args.get('to_value_date')
        if fromdate:
            args['from_value_date'] = fromdate + timedelta(days=days)
        if todate:
            args['to_value_date'] = todate + timedelta(days=days)

        return __interpreter__.get(name, args)

    @finder('shifted')
    def find_series(cn, tsh, stree):
        return {
            stree[1]: tsh.metadata(cn, stree[1])
        }

    tsh.register_formula(
        engine,
        'shifting',
        '(+ 0 (shifted "shiftme" #:days -1))',
        False
    )

    ts = pd.Series(
        [1, 2, 3, 4, 5],
        index=pd.date_range(dt(2019, 1, 1), periods=5, freq='D')
    )
    tsh.insert(
        engine, ts, 'shiftme', 'Babar',
        insertion_date=utcdt(2019, 1, 1)
    )

    ts = tsh.get(engine, 'shifting')
    assert_df("""
2019-01-01    1.0
2019-01-02    2.0
2019-01-03    3.0
2019-01-04    4.0
2019-01-05    5.0
""", ts)

    ts = tsh.get(
        engine, 'shifting',
        from_value_date=dt(2019, 1, 3),
        to_value_date=dt(2019, 1, 4)
    )
    assert_df("""
2019-01-02    2.0
2019-01-03    3.0
""", ts)

    # now, history

    ts = pd.Series(
        [1, 2, 3, 4, 5],
        index=pd.date_range(dt(2019, 1, 2), periods=5, freq='D')
    )
    tsh.insert(
        engine, ts, 'shiftme', 'Babar',
        insertion_date=utcdt(2019, 1, 2)

    )
    hist = tsh.history(
        engine, 'shifting'
    )
    assert_hist("""
insertion_date             value_date
2019-01-01 00:00:00+00:00  2019-01-01    1.0
                           2019-01-02    2.0
                           2019-01-03    3.0
                           2019-01-04    4.0
                           2019-01-05    5.0
2019-01-02 00:00:00+00:00  2019-01-01    1.0
                           2019-01-02    1.0
                           2019-01-03    2.0
                           2019-01-04    3.0
                           2019-01-05    4.0
                           2019-01-06    5.0
""", hist)

    hist = tsh.history(
        engine, 'shifting',
        from_value_date=dt(2019, 1, 3),
        to_value_date=dt(2019, 1, 4)
    )
    assert_hist("""
insertion_date             value_date
2019-01-01 00:00:00+00:00  2019-01-03    3.0
                           2019-01-04    4.0
2019-01-02 00:00:00+00:00  2019-01-03    2.0
                           2019-01-04    3.0
""", hist)

    # cleanup
    FUNCS.pop('shifted')


def test_types(tsh):
    types = jsontypes()
    assert {
        '*': {'a': 'typing.Union[int, float, Series]',
              'b': 'typing.Union[int, float, Series]',
              'return': 'Series'},
        '+': {'a': 'typing.Union[int, float, Series]',
              'b': 'typing.Union[int, float, Series]',
              'return': 'Series'},
        '/': {'a': 'typing.Union[int, float, Series]',
              'b': 'typing.Union[int, float]',
              'return': 'typing.Union[int, float, Series]'},
        'add': {'return': 'Series', 'serieslist': 'Series'},
        'div': {'return': 'Series', 's1': 'Series', 's2': 'Series'},
        'max': {'return': 'Series', 'serieslist': 'Series'},
        'min': {'return': 'Series', 'serieslist': 'Series'},
        'mul': {'return': 'Series', 'serieslist': 'Series'},
        'clip': {'max': 'typing.Union[float, NoneType]',
                 'min': 'typing.Union[float, NoneType]',
                 'return': 'Series',
                 'series': 'Series'},
        'priority': {'return': 'Series', 'serieslist': 'Series'},
        'row-mean': {'return': 'Series', 'serieslist': 'Series'},
        'series': {'fill': 'typing.Union[str, NoneType]',
                   'name': 'str',
                   'prune': 'typing.Union[str, NoneType]',
                   'weight': 'typing.Union[float, NoneType]',
                   'return': 'Series'},
        'slice': {
            'fromdate': 'typing.Union[tshistory_formula.funcs.iso_utc_datetime, NoneType]',
            'return': 'Series',
            'series': 'Series',
            'todate': 'typing.Union[tshistory_formula.funcs.iso_utc_datetime, NoneType]'
        }
    } == json.loads(types)


def test_formula_refers_to_nothing(engine, tsh):
    tsh.register_formula(
        engine,
        'i-cant-work',
        '(+ 1 (series "lol"))',
        False
    )

    with pytest.raises(ValueError) as err:
        tsh.get(engine, 'i-cant-work')
    assert err.value.args[0] == 'No such series `lol`'


def test_rename(engine, tsh):
    ts = pd.Series(
        [1, 2, 3],
        index=pd.date_range(dt(2019, 1, 1), periods=3, freq='D')
    )
    tsh.insert(engine, ts, 'rename-a', 'Babar')

    tsh.register_formula(
        engine,
        'survive-renaming',
        '(+ 1 (series "rename-a" #:fill 0))'
    )
    tsh.register_formula(
        engine,
        'survive-renaming-2',
        '(add (series "survive-renaming") (series "rename-a" #:fill 0))'
    )

    ts = tsh.get(engine, 'survive-renaming')
    assert_df("""
2019-01-01    2.0
2019-01-02    3.0
2019-01-03    4.0
""", ts)

    ts = tsh.get(engine, 'survive-renaming-2')
    assert_df("""
2019-01-01    3.0
2019-01-02    5.0
2019-01-03    7.0
""", ts)

    with engine.begin() as cn:
        tsh.rename(cn, 'rename-a', 'a-renamed')

    ts = tsh.get(engine, 'survive-renaming')
    assert_df("""
2019-01-01    2.0
2019-01-02    3.0
2019-01-03    4.0
""", ts)

    ts = tsh.get(engine, 'survive-renaming-2')
    assert_df("""
2019-01-01    3.0
2019-01-02    5.0
2019-01-03    7.0
""", ts)

    with engine.begin() as cn:
        with pytest.raises(ValueError) as err:
            tsh.rename(cn, 'a-renamed', 'survive-renaming')

    assert err.value.args[0] == 'new name is already referenced by `survive-renaming-2`'

    # rename a formula !
    with engine.begin() as cn:
        tsh.rename(cn, 'survive-renaming', 'survived')
    assert tsh.formula(
        engine, 'survive-renaming-2'
    ) == '(add (series "survived") (series "a-renamed" #:fill 0))'


def test_convert_alias(engine, tsh):
    groundzero = pd.Series(
        [0, 0, 0],
        index=pd.date_range(utcdt(2019, 1, 1), periods=3, freq='D')
    )
    one = pd.Series(
        [1, 1, 1],
        index=pd.date_range(utcdt(2019, 1, 1), periods=3, freq='D')
    )
    two = pd.Series(
        [2, 2, 2, 2, 2],
        index=pd.date_range(utcdt(2019, 1, 1), periods=5, freq='D')
    )

    tsh.insert(engine, groundzero, 'groundzero', 'Babar')
    tsh.insert(engine, one, 'one', 'Babar')
    tsh.insert(engine, two, 'two', 'Babar')

    tsh.build_arithmetic(
        engine, 'ones', {
            'groundzero': round(math.pi, 4),
            'one': 1
        },
        {'groundzero': 'bfill'}
    )
    tsh.build_priority(engine, 'twos', ['ones', 'two'],
                       map_prune={'ones': 1})

    ts = tsh.get(engine, 'twos')
    assert_df("""
2019-01-01 00:00:00+00:00    1.0
2019-01-02 00:00:00+00:00    1.0
2019-01-03 00:00:00+00:00    2.0
2019-01-04 00:00:00+00:00    2.0
2019-01-05 00:00:00+00:00    2.0
""", ts)

    tsh.convert_aliases(engine)

    ts = tsh.get(engine, 'ones')
    assert_df("""
2019-01-01 00:00:00+00:00    1.0
2019-01-02 00:00:00+00:00    1.0
2019-01-03 00:00:00+00:00    1.0
""", ts)

    ts = tsh.get(engine, 'twos')
    assert_df("""
2019-01-01 00:00:00+00:00    1.0
2019-01-02 00:00:00+00:00    1.0
2019-01-03 00:00:00+00:00    2.0
2019-01-04 00:00:00+00:00    2.0
2019-01-05 00:00:00+00:00    2.0
""", ts)

    assert tsh.formula(engine, 'ones') == (
        '(add (* 3.1416 (series "groundzero" #:fill "bfill")) (series "one"))'
    )
    assert tsh.formula(engine, 'twos') == (
        '(priority (series "ones" #:prune 1) (series "two"))'
    )


def test_editor_table_callback(engine, tsh):
    groundzero = pd.Series(
        [0, 0, 0],
        index=pd.date_range(utcdt(2019, 1, 1), periods=3, freq='D')
    )
    one = pd.Series(
        [1, 1, 1],
        index=pd.date_range(utcdt(2019, 1, 1), periods=3, freq='D')
    )
    tsh.insert(engine, groundzero, 'groundzero-a', 'Babar')
    tsh.insert(engine, one, 'one-a', 'Celeste')

    tsh.register_formula(
        engine,
        'editor-1',
        '(add (* 3.1416 (series "groundzero-a" #:fill "bfill" #:prune 1)) (series "one-a"))',
    )

    presenter = fancypresenter(engine, tsh, 'editor-1', {})
    info = [
        {
            k: v for k, v in info.items() if k != 'ts'
        }
        for info in presenter.buildinfo()
    ]
    assert info == [
        {'coef': 'x 3.1416', 'keywords': 'fill:bfill, prune:1',
         'name': 'groundzero-a', 'type': 'primary'},
        {'coef': 'x 1', 'keywords': '-', 'name': 'one-a', 'type': 'primary'},
        {'coef': 'x 1', 'name': 'editor-1', 'type': 'formula: add'}
    ]

    # trigger an empty series
    presenter = fancypresenter(engine, tsh, 'editor-1',
                               {'from_value_date': utcdt(2019, 1, 4)})
    info = [
        {
            k: v for k, v in info.items() if k != 'ts'
        }
        for info in presenter.buildinfo()
    ]
    assert info == [
        {'coef': 'x 3.1416', 'keywords': 'fill:bfill, prune:1',
         'name': 'groundzero-a', 'type': 'primary'},
        {'coef': 'x 1', 'keywords': '-', 'name': 'one-a', 'type': 'primary'},
        {'coef': 'x 1', 'name': 'editor-1', 'type': 'formula: add'}
    ]


def test_editor_no_such_series(engine, tsh):
    with pytest.raises(AssertionError):
        presenter = fancypresenter(engine, tsh, 'no-such-series', {})


def test_editor_new_operator(engine, tsh):
    @func('genrandomseries')
    def genrandomseries():
        return pd.Series(
            [1.0, 2.0, 3.0],
            index=pd.date_range(dt(2019, 1, 1), periods=3, freq='D')
    )

    tsh.register_formula(
        engine,
        'random',
        '(genrandomseries)',
        False
    )

    ts = tsh.get(engine, 'random')
    assert_df("""
2019-01-01    1.0
2019-01-02    2.0
2019-01-03    3.0
""", ts)

    presenter = fancypresenter(engine, tsh, 'random', {})
    info = [
        {
            k: v for k, v in info.items() if k != 'ts'
        }
        for info in presenter.buildinfo()
    ]
    assert info == [
        {'coef': 'x 1', 'name': 'random', 'type': 'formula: genrandomseries'}
    ]

    # cleanup
    FUNCS.pop('genrandomseries')


def test_unknown_operator(engine, tsh):
    with pytest.raises(ValueError) as err:
        tsh.register_formula(
            engine,
            'nope',
            '(bogus-1 (bogus-2))',
            False
        )

    assert err.value.args[0] == (
        'Formula `nope` refers to unknown operators `bogus-1`, `bogus-2`'
    )


def test_custom_metadata(engine, tsh):
    @func('customseries')
    def customseries():
        return pd.Series(
            [1.0, 2.0, 3.0],
            index=pd.date_range(dt(2019, 1, 1), periods=3, freq='D')
        )

    @finder('customseries')
    def find(cn, tsh, tree):
        return {
            tree[0]: {
                'index_type': 'datetime64[ns]',
                'tzaware': False,
                'value_type': 'float64'
            }
        }

    tsh.register_formula(
        engine,
        'custom',
        '(+ 3 (customseries))',
        False
    )

    meta = tsh.metadata(engine, 'custom')
    assert meta == {
        'index_type': 'datetime64[ns]',
        'tzaware': False,
        'value_type': 'float64'
    }

    # cleanup
    FUNCS.pop('customseries')


def test_slice(engine, tsh):
    base = pd.Series(
        [1, 2, 3],
        index=pd.date_range(utcdt(2019, 1, 1), periods=3, freq='D')
    )
    tsh.insert(engine, base, 'test-slice', 'Babar')
    tsh.register_formula(
        engine,
        'slicing-id',
        '(slice (series "test-slice"))',
    )
    tsh.register_formula(
        engine,
        'slicing-from',
        '(slice (series "test-slice") #:fromdate "2019-1-2")',
    )
    tsh.register_formula(
        engine,
        'slicing-fromto',
        '(slice (series "test-slice") #:fromdate "2019-1-2" #:todate "2019-1-2")',
    )
    tsh.register_formula(
        engine,
        'slicing-empty',
        '(slice (series "test-slice") #:fromdate "2018-1-2" #:todate "2018-1-2")',
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
    tsh.insert(engine, base, 'test-slice', 'Babar')
    # options transmissions
    ts = tsh.eval_formula(
        engine,
        '(add (series "test-slice") '
        '     (slice (series "test-slice" #:fill 0) #:fromdate "2019-1-2"))',
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
    tsh.insert(engine, base, 'mul-a', 'Babar')
    tsh.insert(engine, base, 'mul-b', 'Babar')
    tsh.insert(engine, base, 'mul-c', 'Babar')
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
    tsh.insert(engine, base, 'mul-b', 'Babar')

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
    tsh.insert(engine, base, 'div-a', 'Babar')
    tsh.insert(engine, base, 'div-b', 'Babar')
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
    tsh.insert(engine, base, 'div-b', 'Babar')

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

    tsh.insert(engine, station0, 'station0', 'Babar')
    tsh.insert(engine, station1, 'station1', 'Celeste')
    tsh.insert(engine, station2, 'station2', 'Arthur')

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
