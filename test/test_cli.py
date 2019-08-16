from datetime import datetime as dt

import pandas as pd
from tshistory.testutil import assert_df


def utcdt(*dtargs):
    return pd.Timestamp(dt(*dtargs), tz='UTC')


def test_convert(engine, cli, tsh):
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

    tsh.insert(engine, groundzero, 'groundzero-conv', 'Babar')
    tsh.insert(engine, one, 'one-conv', 'Babar')
    tsh.insert(engine, two, 'two-conv', 'Babar')

    tsh.build_arithmetic(
        engine, 'ones-conv', {
            'groundzero-conv': 1,
            'one-conv': 1
        }
    )
    tsh.build_priority(engine, 'twos-conv', ['ones-conv', 'two-conv'])

    ts = tsh.get(engine, 'twos-conv')
    assert_df("""
2019-01-01 00:00:00+00:00    1.0
2019-01-02 00:00:00+00:00    1.0
2019-01-03 00:00:00+00:00    1.0
2019-01-04 00:00:00+00:00    2.0
2019-01-05 00:00:00+00:00    2.0
""", ts)

    cli('convert-aliases',
        engine.url,
        namespace=tsh.namespace)

    ts = tsh.get(engine, 'ones-conv')
    assert_df("""
2019-01-01 00:00:00+00:00    1.0
2019-01-02 00:00:00+00:00    1.0
2019-01-03 00:00:00+00:00    1.0
""", ts)

    ts = tsh.get(engine, 'twos-conv')
    assert_df("""
2019-01-01 00:00:00+00:00    1.0
2019-01-02 00:00:00+00:00    1.0
2019-01-03 00:00:00+00:00    1.0
2019-01-04 00:00:00+00:00    2.0
2019-01-05 00:00:00+00:00    2.0
""", ts)


def test_ingest(engine, cli, tsh, datadir):
    out = cli('ingest-formulas',
              engine.url,
              datadir / 'formula.csv',
              strict=True,
              namespace=tsh.namespace)

    assert out.exception.args[0] == (
        'Formula `ones-imported` refers to '
        'unknown series `groundzero-cli`, `one-cli`'
    )

    out = cli('ingest-formulas',
              engine.url,
              datadir / 'formula.csv',
              namespace=tsh.namespace)

    assert tsh.formula(engine, 'ones-imported')
    assert tsh.formula(engine, 'twos-imported')
