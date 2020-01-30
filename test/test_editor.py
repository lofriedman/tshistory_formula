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


def test_editor_table_callback(mapi):
    groundzero = pd.Series(
        [0, 0, 0],
        index=pd.date_range(utcdt(2019, 1, 1), periods=3, freq='D')
    )
    one = pd.Series(
        [1, 1, 1],
        index=pd.date_range(utcdt(2019, 1, 1), periods=3, freq='D')
    )
    mapi.update('groundzero-a', groundzero, 'Babar')
    mapi.update('one-a', one, 'Celeste')

    mapi.register_formula(
        'editor-1',
        '(add (* 3.1416 (series "groundzero-a" #:fill "bfill" #:prune 1)) (series "one-a"))',
    )

    presenter = fancypresenter(mapi, 'editor-1', {})
    info = [
        {
            k: v for k, v in info.items() if k != 'ts'
        }
        for info in presenter.infos
    ]
    assert info == [
        {'name': 'editor-1'},
        {'name': 'groundzero-a'},
        {'name': 'one-a'}
    ]

    # trigger an empty series
    presenter = fancypresenter(mapi, 'editor-1',
                               {'from_value_date': utcdt(2019, 1, 4)})
    info = [
        {
            k: v for k, v in info.items() if k != 'ts'
        }
        for info in presenter.infos
    ]
    assert info == [
        {'name': 'editor-1'},
        {'name': 'groundzero-a'},
        {'name': 'one-a'}
    ]


def test_editor_no_such_series(mapi):
    with pytest.raises(AssertionError):
        presenter = fancypresenter(mapi, 'no-such-series', {})


def test_editor_pure_scalar_op(mapi):
    ts = pd.Series(
        [1, 2, 3],
        index=pd.date_range(utcdt(2020, 1, 1), periods=3, freq='D')
    )
    mapi.update('pure-scalar-ops', ts, 'Babar')
    mapi.register_formula(
        'formula-pure-scalar-ops',
        '(+ (* 3 (/ 6 2)) (series "pure-scalar-ops"))'
    )
    presenter = fancypresenter(mapi, 'formula-pure-scalar-ops',
                               {'from_value_date': utcdt(2019, 1, 4)})
    info = [
        {
            k: v for k, v in info.items() if k != 'ts'
        }
        for info in presenter.infos
    ]
    assert info == [
        {'name': 'formula-pure-scalar-ops'},
        {'name': 'pure-scalar-ops'}
    ]


def test_editor_new_operator(mapi):
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
        sa = mapi.get(a)
        sb = mapi.get(b)
        return (sa + 1) * sb

    mapi.register_formula(
        'random',
        '(genrandomseries)',
    )

    ts = mapi.get('random')
    assert_df("""
2019-01-01    1.0
2019-01-02    2.0
2019-01-03    3.0
""", ts)

    presenter = fancypresenter(mapi, 'random', {})
    info = [
        {
            k: v for k, v in info.items() if k != 'ts'
        }
        for info in presenter.infos
    ]
    assert info == [
        {'name': 'random'},
        {'name': 'genrandomseries'}
    ]

    mapi.update(
        'new-op',
        pd.Series(
            [1, 2, 3],
            index=pd.date_range(dt(2019, 1, 1), periods=3, freq='D')
        ),
        'Baabar'
    )

    mapi.register_formula(
        'frobulating',
        '(* 2 (add (series "random")'
        '          (frobulated "new-op" "new-op")))'
    )
    presenter = fancypresenter(mapi, 'frobulating', {})
    info = [
        {
            k: v for k, v in info.items() if k != 'ts'
        }
        for info in presenter.infos
    ]
    assert info == [
        {'name': 'frobulating'},
        {'name': 'random'}
    ]

    # cleanup
    FUNCS.pop('genrandomseries')
    FUNCS.pop('frobulated')


def test_complicated_thing(mapi):
    groundzero = pd.Series(
        [0, 0, 0],
        index=pd.date_range(utcdt(2019, 1, 1), periods=3, freq='D')
    )
    one = pd.Series(
        [1, 1, 1],
        index=pd.date_range(utcdt(2019, 1, 1), periods=3, freq='D')
    )
    mapi.update('groundzero-b', groundzero, 'Babar')
    mapi.update('one-b', one, 'Celeste')

    mapi.register_formula(
        'complicated',
        '(add (* 3.1416 (series "groundzero-b" #:fill "bfill" #:prune 1))'
        '     (* 2 (min (+ 1 (series "groundzero-b")) (series "one-b"))))',
    )

    presenter = fancypresenter(mapi, 'complicated', {})
    info = [
        {
            k: v for k, v in info.items() if k != 'ts'
        }
        for info in presenter.infos
    ]
    assert info == [
        {'name': 'complicated'},
        {'name': 'groundzero-b'},
        {'name': 'one-b'}
    ]
