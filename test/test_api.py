from datetime import datetime
import pandas as pd
import pytest

from psyl import lisp
from tshistory.testutil import (
    assert_df,
    assert_hist,
    gengroup
)

from tshistory_formula.tsio import timeseries
from tshistory_formula.registry import (
    func,
    finder,
    insertion_dates,
    metadata
)


def test_local_formula_remote_series(tsa):
    rtsh = timeseries('test-mapi-2')
    rtsh.update(
        tsa.engine,
        pd.Series(
            [1, 2, 3],
            index=pd.date_range(pd.Timestamp('2020-1-1'), periods=3, freq='H'),
        ),
        'remote-series',
        'Babar',
        insertion_date=pd.Timestamp('2020-1-1', tz='UTC')
    )

    tsa.register_formula(
        'test-localformula-remoteseries',
        '(+ 1 (series "remote-series"))'
    )

    ts = tsa.get('test-localformula-remoteseries')
    assert_df("""
2020-01-01 00:00:00    2.0
2020-01-01 01:00:00    3.0
2020-01-01 02:00:00    4.0
""", ts)

    hist = tsa.history('test-localformula-remoteseries')
    assert_hist("""
insertion_date             value_date         
2020-01-01 00:00:00+00:00  2020-01-01 00:00:00    2.0
                           2020-01-01 01:00:00    3.0
                           2020-01-01 02:00:00    4.0
""", hist)

    f = tsa.formula('test-localformula-remoteseries')
    assert f == '(+ 1 (series "remote-series"))'

    none = tsa.formula('nosuchformula')
    assert none is None

    # altsource formula
    rtsh.register_formula(
        tsa.engine,
        'remote-formula-remote-series',
        '(+ 2 (series "remote-series"))'
    )
    f = tsa.formula('remote-formula-remote-series')
    assert f == '(+ 2 (series "remote-series"))'

    assert_df("""
2020-01-01 00:00:00    3.0
2020-01-01 01:00:00    4.0
2020-01-01 02:00:00    5.0
""", tsa.get('remote-formula-remote-series'))


    rtsh.register_formula(
        tsa.engine,
        'remote-formula-local-formula',
        '(+ 3 (series "remote-formula-remote-series"))'
    )
    f = tsa.formula('remote-formula-local-formula')
    assert f == '(+ 3 (series "remote-formula-remote-series"))'

    ts = tsa.get('remote-formula-local-formula')
    assert_df("""
2020-01-01 00:00:00    6.0
2020-01-01 01:00:00    7.0
2020-01-01 02:00:00    8.0
""", ts)

    expanded = tsa.formula('remote-formula-local-formula', expanded=True)
    assert expanded == '(+ 3 (+ 2 (series "remote-series")))'


def test_formula_components(tsa):
    series = pd.Series(
        [1, 2, 3],
        index=pd.date_range(pd.Timestamp('2020-6-1'), freq='D', periods=3)
    )
    tsa.update(
        'component-a',
        series,
        'Babar'
    )
    tsa.update(
        'component-b',
        series,
        'Celeste'
    )

    assert tsa.formula_components('component-a') is None

    form = '(add (series "component-a") (series "component-b"))'
    tsa.register_formula(
        'show-components',
        form
    )

    components = tsa.formula_components('show-components')
    parsed = lisp.parse(form)
    assert components == {
        'show-components': ['component-a', 'component-b']
    }

    tsa.register_formula(
        'show-components-squared',
        '(add (* 2 (series "show-components")) (series "component-b"))'
    )
    components = tsa.formula_components(
        'show-components-squared',
        expanded=True
    )
    assert components == {
        'show-components-squared': [
            {'show-components':
             [
                 'component-a',
                 'component-b'
             ]
            },
            'component-b'
        ]
    }

    # formula referencing a remote formula
    rtsh = timeseries('test-mapi-2')
    rtsh.update(
        tsa.engine,
        series,
        'remote-series-compo',
        'Babar',
        insertion_date=pd.Timestamp('2020-1-1', tz='UTC')
    )
    rtsh.register_formula(
        tsa.engine,
        'remote-formula',
        '(+ 1 (series "remote-series-compo"))'
    )

    tsa.register_formula(
        'compo-with-remoteseries',
        '(add (series "show-components-squared") (series "remote-formula"))'
    )
    components = tsa.formula_components(
        'compo-with-remoteseries',
        expanded=True
    )
    assert components == {
        'compo-with-remoteseries': [
            {'show-components-squared': [
                {'show-components': ['component-a',
                                     'component-b']
                },
                'component-b'
            ]},
            {'remote-formula': ['remote-series-compo']}
        ]
    }

    # pure remote formula
    components = tsa.formula_components(
        'remote-formula',
        expanded=True
    )
    assert components == {
        'remote-formula': [
            'remote-series-compo'
        ]
    }

    idates = tsa.insertion_dates('remote-formula')
    assert len(idates) == 1
    assert idates[0] == pd.Timestamp('2020-01-01 00:00:00+0000', tz='UTC')
    idates = tsa.insertion_dates('compo-with-remoteseries')
    assert len(idates) == 3


def test_formula_components_wall(tsa):
    series = pd.Series(
        [1, 2, 3],
        index=pd.date_range(pd.Timestamp('2020-6-1'), freq='D', periods=3)
    )
    tsa.update(
        'comp-a',
        series,
        'Babar'
    )
    tsa.update(
        'comp-b',
        series,
        'Celeste'
    )
    tsa.update(
        'comp-c',
        series,
        'Arthur'
    )

    tsa.register_formula(
        'b-plus-c',
        '(add (series "comp-b") (series "comp-c"))'
    )

    @func('opaque-components', auto=True)
    def custom(__interpreter__, s1name: str, s2name: str) -> pd.Series:
        i = __interpreter__
        s1 = i.get(i.cn, s1name)
        s2 = i.get(i.cn, s2name)
        return s1 + s2


    @finder('opaque-components')
    def custom(cn, tsh, tree):
        return {
            tree[1]: tree,
            tree[2]: tree
        }

    tsa.register_formula(
        'wall',
        '(opaque-components "comp-a" "b-plus-c")'
    )

    comp = tsa.formula_components('wall')
    assert comp == {
        'wall': ['comp-a', 'b-plus-c']
    }

    comp = tsa.formula_components('wall', expanded=True)
    assert comp == {
        'wall': [
            'comp-a',
            {'b-plus-c': [
                'comp-b',
                'comp-c'
            ]}
        ]
    }


def test_autotrophic_idates(tsa):
    # using the fallback path through .history

    @func('autotrophic', auto=True)
    def custom() -> pd.Series:
        return pd.Series(
            [1, 2, 3],
            pd.date_range(utcdt(2020, 1, 1), periods=1, freq='D')
        )

    @finder('autotrophic')
    def custom(cn, tsh, tree):
        return {
            'I HAVE A NAME FOR DISPLAY PURPOSES': tree
        }

    tsa.register_formula(
        'autotrophic-idates',
        '(autotrophic)'
    )

    idates = tsa.insertion_dates('autotrophic-idates')
    assert idates == []


def test_autotrophic_idates2(tsa):
    @func('auto2', auto=True)
    def custom() -> pd.Series:
        return pd.Series(
            [1, 2, 3],
            pd.date_range(utcdt(2020, 1, 1), periods=1, freq='D')
        )

    @finder('auto2')
    def custom(cn, tsh, tree):
        return {
            'I HAVE A NAME FOR DISPLAY PURPOSES': tree
        }

    @insertion_dates('auto2')
    def custom(cn, tsh, tree, fromdate, todate):
        dates = [
            pd.Timestamp('2020-1-1', tz='utc'),
            pd.Timestamp('2020-1-2', tz='utc')
        ]
        fromdate = fromdate or pd.Timestamp('1900-1-1', tz='UTC')
        todate = todate or pd.Timestamp('2100-1-1', tz='UTC')
        return filter(lambda d: fromdate <= d <= todate, dates)

    tsa.register_formula(
        'autotrophic-idates-2',
        '(auto2)'
    )

    idates = tsa.insertion_dates('autotrophic-idates-2')
    assert idates == [
        pd.Timestamp('2020-1-1', tz='utc'),
        pd.Timestamp('2020-1-2', tz='utc')
    ]

    idates = tsa.insertion_dates(
        'autotrophic-idates-2',
        pd.Timestamp('2020-1-2', tz='UTC')
    )
    assert idates == [
        pd.Timestamp('2020-1-2', tz='utc')
    ]

    idates = tsa.insertion_dates(
        'autotrophic-idates-2',
        to_insertion_date=pd.Timestamp('2020-1-1', tz='UTC')
    )
    assert idates == [
        pd.Timestamp('2020-1-1', tz='utc')
    ]


# groups

def test_group_formula(tsa):
    df = gengroup(
        n_scenarios=3,
        from_date=datetime(2015, 1, 1),
        length=5,
        freq='D',
        seed=2
    )

    df.columns = ['a', 'b', 'c']

    tsa.group_replace('groupa', df, 'test')

    plain_ts = pd.Series(
        [1] * 7,
        index=pd.date_range(
            start=datetime(2014, 12, 31),
            freq='D',
            periods=7,
        )
    )

    tsa.update('plain_tsa', plain_ts, 'Babar')

    # start to test

    formula = (
        '(group-add '
        '  (group "groupa") '
        '  (* -1 '
        '    (series "plain_tsa")))'
    )

    tsa.register_group_formula(
        'difference',
        formula
    )
    df = tsa.group_get('difference')
    assert_df("""
              a    b    c
2015-01-01  1.0  2.0  3.0
2015-01-02  2.0  3.0  4.0
2015-01-03  3.0  4.0  5.0
2015-01-04  4.0  5.0  6.0
2015-01-05  5.0  6.0  7.0
""", df)

    # formula of formula
    # we add the same series that was substracted,
    # hence we msut retrieve the original dataframe group1
    formula = (
        '(group-add '
        '  (group "difference")'
        '  (series "plain_tsa"))'
    )

    tsa.register_group_formula(
        'roundtripeda',
        formula
    )

    df_roundtrip = tsa.group_get('roundtripeda')
    df_original = tsa.group_get('groupa')

    assert df_roundtrip.equals(df_original)
