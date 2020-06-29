import pandas as pd

from psyl import lisp
from tshistory.testutil import (
    assert_df,
    assert_hist
)

from tshistory_formula.tsio import timeseries
from tshistory_formula.registry import (
    func,
    finder,
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

    form = '(add (series "component-a") (series "component-b"))'
    mapi.register_formula(
        'show-components',
        form
    )

    components = mapi.formula_components('show-components')
    parsed = lisp.parse(form)
    assert components['component-a'] == parsed[1]
    assert components['component-b'] == parsed[2]

    mapi.register_formula(
        'show-components-squared',
        '(add (* 2 (series "show-components")) (series "component-b"))'
    )
    components = mapi.formula_components(
        'show-components-squared',
        expanded=True
    )
    assert 'component-a' in components
    assert 'component-b' in components

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
    assert 'component-a' in components
    assert 'component-b' in components
    assert 'remote-series-compo' in components

    # pure remote formula
    components = mapi.formula_components(
        'remote-formula',
        expanded=True
    )
    assert 'remote-series-compo' in components
    assert len(components) == 1

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

    @func('custom')
    def custom(__interpreter__, s1name: str, s2name: str) -> pd.Series:
        i = __interpreter__
        s1 = i.get(i.cn, s1name)
        s2 = i.get(i.cn, s2name)
        return s1 + s2


    @finder('custom')
    def custom(cn, tsh, tree):
        return {
            tree[1]: tree,
            tree[2]: tree
        }

    mapi.register_formula(
        'wall',
        '(custom "comp-a" "b-plus-c")'
    )

    comp = mapi.formula_components('wall')
    assert comp == {
        'comp-a': ['custom', 'comp-a', 'b-plus-c'],
        'b-plus-c': ['custom', 'comp-a', 'b-plus-c']
    }
    comp = mapi.formula_components('wall', expanded=True)
    assert comp == {
        'b-plus-c': ['custom', 'comp-a', 'b-plus-c'],
        'comp-a': ['custom', 'comp-a', 'b-plus-c'],
        'comp-b': ['series', 'comp-b'],
        'comp-c': ['series', 'comp-c']
    }
