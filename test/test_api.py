import pandas as pd
import pytest

from psyl import lisp
from tshistory.testutil import (
    assert_df,
    assert_hist
)

from tshistory_formula.tsio import timeseries
from tshistory_formula.registry import (
    func,
    finder,
    insertion_dates,
    metadata
)


def test_local_formula_remote_series(mapi):
    rtsh = timeseries('test-mapi-2')
    rtsh.update(
        mapi.engine,
        pd.Series(
            [1, 2, 3],
            index=pd.date_range(pd.Timestamp('2020-1-1'), periods=3, freq='H'),
        ),
        'remote-series',
        'Babar',
        insertion_date=pd.Timestamp('2020-1-1', tz='UTC')
    )

    mapi.register_formula(
        'test-localformula-remoteseries',
        '(+ 1 (series "remote-series"))'
    )

    ts = mapi.get('test-localformula-remoteseries')
    assert_df("""
2020-01-01 00:00:00    2.0
2020-01-01 01:00:00    3.0
2020-01-01 02:00:00    4.0
""", ts)

    hist = mapi.history('test-localformula-remoteseries')
    assert_hist("""
insertion_date             value_date         
2020-01-01 00:00:00+00:00  2020-01-01 00:00:00    2.0
                           2020-01-01 01:00:00    3.0
                           2020-01-01 02:00:00    4.0
""", hist)

    f = mapi.formula('test-localformula-remoteseries')
    assert f == '(+ 1 (series "remote-series"))'

    none = mapi.formula('nosuchformula')
    assert none is None

    # altsource formula
    rtsh.register_formula(
        mapi.engine,
        'remote-formula-remote-series',
        '(+ 2 (series "remote-series"))'
    )
    f = mapi.formula('remote-formula-remote-series')
    assert f == '(+ 2 (series "remote-series"))'

    assert_df("""
2020-01-01 00:00:00    3.0
2020-01-01 01:00:00    4.0
2020-01-01 02:00:00    5.0
""", mapi.get('remote-formula-remote-series'))


    rtsh.register_formula(
        mapi.engine,
        'remote-formula-local-formula',
        '(+ 3 (series "remote-formula-remote-series"))'
    )
    f = mapi.formula('remote-formula-local-formula')
    assert f == '(+ 3 (series "remote-formula-remote-series"))'

    ts = mapi.get('remote-formula-local-formula')
    assert_df("""
2020-01-01 00:00:00    6.0
2020-01-01 01:00:00    7.0
2020-01-01 02:00:00    8.0
""", ts)

    expanded = mapi.formula('remote-formula-local-formula', expanded=True)
    assert expanded == '(+ 3 (+ 2 (series "remote-series")))'


def test_formula_components(mapi):
    series = pd.Series(
        [1, 2, 3],
        index=pd.date_range(pd.Timestamp('2020-6-1'), freq='D', periods=3)
    )
    mapi.update(
        'component-a',
        series,
        'Babar'
    )
    mapi.update(
        'component-b',
        series,
        'Celeste'
    )

    assert mapi.formula_components('component-a') is None

    form = '(add (series "component-a") (series "component-b"))'
    mapi.register_formula(
        'show-components',
        form
    )

    components = mapi.formula_components('show-components')
    parsed = lisp.parse(form)
    assert components == {
        'show-components': ['component-a', 'component-b']
    }

    mapi.register_formula(
        'show-components-squared',
        '(add (* 2 (series "show-components")) (series "component-b"))'
    )
    components = mapi.formula_components(
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
        mapi.engine,
        series,
        'remote-series-compo',
        'Babar',
        insertion_date=pd.Timestamp('2020-1-1', tz='UTC')
    )
    rtsh.register_formula(
        mapi.engine,
        'remote-formula',
        '(+ 1 (series "remote-series-compo"))'
    )

    mapi.register_formula(
        'compo-with-remoteseries',
        '(add (series "show-components-squared") (series "remote-formula"))'
    )
    components = mapi.formula_components(
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
    components = mapi.formula_components(
        'remote-formula',
        expanded=True
    )
    assert components == {
        'remote-formula': [
            'remote-series-compo'
        ]
    }

    idates = mapi.insertion_dates('remote-formula')
    assert len(idates) == 1
    assert idates[0] == pd.Timestamp('2020-01-01 00:00:00+0000', tz='UTC')
    idates = mapi.insertion_dates('compo-with-remoteseries')
    assert len(idates) == 3


def test_formula_components_wall(mapi):
    series = pd.Series(
        [1, 2, 3],
        index=pd.date_range(pd.Timestamp('2020-6-1'), freq='D', periods=3)
    )
    mapi.update(
        'comp-a',
        series,
        'Babar'
    )
    mapi.update(
        'comp-b',
        series,
        'Celeste'
    )
    mapi.update(
        'comp-c',
        series,
        'Arthur'
    )

    mapi.register_formula(
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

    mapi.register_formula(
        'wall',
        '(opaque-components "comp-a" "b-plus-c")'
    )

    comp = mapi.formula_components('wall')
    assert comp == {
        'wall': ['comp-a', 'b-plus-c']
    }

    comp = mapi.formula_components('wall', expanded=True)
    assert comp == {
        'wall': [
            'comp-a',
            {'b-plus-c': [
                'comp-b',
                'comp-c'
            ]}
        ]
    }


def test_autotrophic_idates(mapi):
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

    mapi.register_formula(
        'autotrophic-idates',
        '(autotrophic)'
    )

    idates = mapi.insertion_dates('autotrophic-idates')
    assert idates == []



def test_autotrophic_idates2(mapi):
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
    def custom(cn, tsh, tree):
        return [
            pd.Timestamp('2020-1-1', tz='utc'),
            pd.Timestamp('2020-1-2', tz='utc')
        ]

    mapi.register_formula(
        'autotrophic-idates-2',
        '(auto2)'
    )

    idates = mapi.insertion_dates('autotrophic-idates-2')
    assert idates == [
        pd.Timestamp('2020-1-1', tz='utc'),
        pd.Timestamp('2020-1-2', tz='utc')
    ]
