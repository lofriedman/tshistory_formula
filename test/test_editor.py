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
    FUNCS,
    metadata
)
from tshistory_formula.editor import (
    components_table,
    fancypresenter
)

def test_editor_table_callback(tsa):
    groundzero = pd.Series(
        [0, 0, 0],
        index=pd.date_range(utcdt(2019, 1, 1), periods=3, freq='D')
    )
    one = pd.Series(
        [1, 1, 1],
        index=pd.date_range(utcdt(2019, 1, 1), periods=3, freq='D')
    )
    tsa.update('groundzero-a', groundzero, 'Babar')
    tsa.update('one-a', one, 'Celeste')

    tsa.register_formula(
        'editor-1',
        '(add (* 3.1416 (series "groundzero-a" #:fill "bfill" #:prune 1)) (series "one-a"))',
    )

    presenter = fancypresenter(tsa, 'editor-1', {})
    info = [
        {
            k: v for k, v in info.items() if k != 'ts'
        }
        for info in presenter.infos
    ]
    assert info == [
        {'name': 'editor-1', 'type': 'formula'},
        {'name': 'groundzero-a', 'type': 'primary'},
        {'name': 'one-a', 'type': 'primary'}
    ]

    # trigger an empty series
    presenter = fancypresenter(tsa, 'editor-1',
                               {'from_value_date': utcdt(2019, 1, 4)})
    info = [
        {
            k: v for k, v in info.items() if k != 'ts'
        }
        for info in presenter.infos
    ]
    assert info == [
        {'name': 'editor-1', 'type': 'formula'},
        {'name': 'groundzero-a', 'type': 'primary'},
        {'name': 'one-a', 'type': 'primary'}
    ]


def test_editor_no_such_series(tsa):
    with pytest.raises(AssertionError):
        fancypresenter(tsa, 'no-such-series', {})


def test_editor_pure_scalar_op(tsa):
    ts = pd.Series(
        [1, 2, 3],
        index=pd.date_range(utcdt(2020, 1, 1), periods=3, freq='D')
    )
    tsa.update('pure-scalar-ops', ts, 'Babar')
    tsa.register_formula(
        'formula-pure-scalar-ops',
        '(+ (* 3 (/ 6 2)) (series "pure-scalar-ops"))'
    )
    presenter = fancypresenter(tsa, 'formula-pure-scalar-ops',
                               {'from_value_date': utcdt(2019, 1, 4)})
    info = [
        {
            k: v for k, v in info.items() if k != 'ts'
        }
        for info in presenter.infos
    ]
    assert info == [
        {'name': 'formula-pure-scalar-ops', 'type': 'formula'},
        {'name': 'pure-scalar-ops', 'type': 'primary'}
    ]


def test_editor_new_operator(tsa):
    @func('genrandomseries', auto=True)
    def genrandomseries() -> pd.Series:
        return pd.Series(
            [1.0, 2.0, 3.0],
            index=pd.date_range(dt(2019, 1, 1), periods=3, freq='D')
    )

    @finder('genrandomseries')
    def genrandomseries(_cn, _tsh, tree):
        return {
            tree[0]: tree
        }

    @metadata('genrandomseries')
    def genrandomseries(_cn, _tsh, tree):
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
        sa = tsa.get(a)
        sb = tsa.get(b)
        return (sa + 1) * sb

    tsa.register_formula(
        'random',
        '(genrandomseries)',
    )

    ts = tsa.get('random')
    assert_df("""
2019-01-01    1.0
2019-01-02    2.0
2019-01-03    3.0
""", ts)

    presenter = fancypresenter(tsa, 'random', {})
    info = [
        {
            k: v for k, v in info.items() if k != 'ts'
        }
        for info in presenter.infos
    ]
    assert info == [
        {'name': 'random', 'type': 'formula'},
        {'name': 'genrandomseries', 'type': 'autotrophic'}
    ]

    tsa.update(
        'new-op',
        pd.Series(
            [1, 2, 3],
            index=pd.date_range(dt(2019, 1, 1), periods=3, freq='D')
        ),
        'Baabar'
    )

    tsa.register_formula(
        'frobulating',
        '(* 2 (add (series "random")'
        '          (frobulated "new-op" "new-op")))'
    )
    presenter = fancypresenter(tsa, 'frobulating', {})
    info = [
        {
            k: v for k, v in info.items() if k != 'ts'
        }
        for info in presenter.infos
    ]
    assert info == [
        {'name': 'frobulating', 'type': 'formula'},
        {'name': 'random', 'type': 'formula'}
    ]

    # cleanup
    FUNCS.pop('genrandomseries')
    FUNCS.pop('frobulated')


def test_complicated_thing(tsa):
    groundzero = pd.Series(
        [0, 0, 0],
        index=pd.date_range(utcdt(2019, 1, 1), periods=3, freq='D')
    )
    one = pd.Series(
        [1, 1, 1],
        index=pd.date_range(utcdt(2019, 1, 1), periods=3, freq='D')
    )
    tsa.update('groundzero-b', groundzero, 'Babar')
    tsa.update('one-b', one, 'Celeste')

    tsa.register_formula(
        'complicated',
        '(add (* 3.1416 (series "groundzero-b" #:fill "bfill" #:prune 1))'
        '     (* 2 (min (+ 1 (series "groundzero-b")) (series "one-b"))))',
    )

    presenter = fancypresenter(tsa, 'complicated', {})
    info = [
        {
            k: v for k, v in info.items() if k != 'ts'
        }
        for info in presenter.infos
    ]
    assert info == [
        {'name': 'complicated', 'type': 'formula'},
        {'name': 'groundzero-b', 'type': 'primary'},
        {'name': 'one-b', 'type': 'primary'}
    ]


def test_autotrophic_operator(tsa):
    @func('auto', auto=True)
    def auto() -> pd.Series:
        return pd.Series(
            [1, 2, 3],
            index=pd.date_range(utcdt(2020, 1, 1), utcdt(2020, 1, 3), freq='D')
        )

    @finder('auto')
    def auto(cn, tsh, tree):
        return {
            'my-little-constant-series': tree
        }

    @metadata('auto')
    def auto(_cn, _tsh, tree):
        return {
            tree[0]: {
                'tzaware': True,
                'index_type': 'datetime64[ns, UTC]',
                'value_type': 'float64',
                'index_dtype': '|M8[ns]',
                'value_dtype': '<f8'
            }
        }

    tsa.register_formula(
        'present-auto',
        '(auto)'
    )

    presenter = fancypresenter(tsa, 'present-auto', {})
    info = [
        {
            k: v for k, v in info.items() if k != 'ts'
        }
        for info in presenter.infos
    ]
    assert info == [
        {'name': 'present-auto', 'type': 'formula'},
        {'name': 'my-little-constant-series', 'type': 'autotrophic'}
    ]

    assert len(presenter.infos[1]['ts']) == 3
    assert presenter.infos[1]['ts'].name == 'my-little-constant-series'

    tsa.update(
        'too-naive',
        pd.Series(
            [1, 2, 3],
            index=pd.date_range(dt(2020, 1, 1), dt(2020, 1, 3), freq='D')
        ),
        'Babar'
    )

    tsa.register_formula(
        'mixed-naive-tzaware',
        '(add (series "too-naive") (naive (auto) "CET"))'
    )

    # not crash any more :)
    components_table(tsa, 'mixed-naive-tzaware')
