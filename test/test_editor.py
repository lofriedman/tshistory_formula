from datetime import datetime as dt

import pytest
import pandas as pd

from tshistory.testutil import (
    assert_df,
    utcdt
)

from tshistory_formula.registry import (
    finder,
    func,
    FUNCS
)
from tshistory_formula.editor import fancypresenter


def test_editor_table_callback(engine, tsh):
    groundzero = pd.Series(
        [0, 0, 0],
        index=pd.date_range(utcdt(2019, 1, 1), periods=3, freq='D')
    )
    one = pd.Series(
        [1, 1, 1],
        index=pd.date_range(utcdt(2019, 1, 1), periods=3, freq='D')
    )
    tsh.update(engine, groundzero, 'groundzero-a', 'Babar')
    tsh.update(engine, one, 'one-a', 'Celeste')

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


def test_editor_pure_scalar_op(engine, tsh):
    ts = pd.Series(
        [1, 2, 3],
        index=pd.date_range(utcdt(2020, 1, 1), periods=3, freq='D')
    )
    tsh.update(engine, ts, 'pure-scalar-ops', 'Babar')
    tsh.register_formula(
        engine,
        'formula-pure-scalar-ops',
        '(+ (* 3 (/ 6 2)) (series "pure-scalar-ops"))'
    )
    presenter = fancypresenter(engine, tsh, 'formula-pure-scalar-ops',
                               {'from_value_date': utcdt(2019, 1, 4)})
    info = [
        {
            k: v for k, v in info.items() if k != 'ts'
        }
        for info in presenter.buildinfo()
    ]
    assert info == [
        {'coef': '+ 9.0', 'keywords': '-', 'name': 'pure-scalar-ops', 'type': 'primary'}
    ]


def test_editor_new_operator(engine, tsh):
    @func('genrandomseries')
    def genrandomseries() -> pd.Series:
        return pd.Series(
            [1.0, 2.0, 3.0],
            index=pd.date_range(dt(2019, 1, 1), periods=3, freq='D')
    )

    @finder('genrandomseries')
    def genrandomseries(cn, tsh, tree):
        return {
            tree[0]: {
                'index_dtype': '<M8[ns]',
                'index_type': 'datetime64[ns]',
                'tzaware': False,
                'value_dtype': '<f8',
                'value_type': 'float64'
            }
        }

    @func('frobulated')
    def frobulate(a: str, b: str) -> pd.Series:
        sa = tsh.get(engine, a)
        sb = tsh.get(engine, b)
        return (sa + 1) * sb

    tsh.register_formula(
        engine,
        'random',
        '(genrandomseries)',
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

    tsh.update(
        engine,
        pd.Series(
            [1, 2, 3],
            index=pd.date_range(dt(2019, 1, 1), periods=3, freq='D')
        ),
        'new-op',
        'Baabar'
    )

    tsh.register_formula(
        engine,
        'frobulating',
        '(* 2 (add (series "random")'
        '          (frobulated "new-op" "new-op")))'
    )
    presenter = fancypresenter(engine, tsh, 'frobulating', {})
    info = [
        {
            k: v for k, v in info.items() if k != 'ts'
        }
        for info in presenter.buildinfo()
    ]
    assert info == [
        {'coef': 'x 1', 'keywords': '-', 'name': 'random',
         'type': 'formula: genrandomseries'},
        {'coef': 'x 1', 'name': '(frobulated "new-op" "new-op")'},
        {'coef': 'x 2.0', 'name': 'frobulating', 'type': 'formula: x'}
    ]

    # cleanup
    FUNCS.pop('genrandomseries')
    FUNCS.pop('frobulated')
