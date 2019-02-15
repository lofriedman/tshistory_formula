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

    tsh.insert(engine, groundzero, 'groundzero-cli', 'Babar')
    tsh.insert(engine, one, 'one-cli', 'Babar')
    tsh.insert(engine, two, 'two-cli', 'Babar')

    tsh.build_arithmetic(
        engine, 'ones-cli', {
            'groundzero-cli': 1,
            'one-cli': 1
        }
    )
    tsh.build_priority(engine, 'twos-cli', ['ones-cli', 'two-cli'])

    ts = tsh.get(engine, 'twos-cli')
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

    tsh._resetcaches()

    ts = tsh.get(engine, 'ones-cli')
    assert_df("""
2019-01-01 00:00:00+00:00    1.0
2019-01-02 00:00:00+00:00    1.0
2019-01-03 00:00:00+00:00    1.0
""", ts)

    ts = tsh.get(engine, 'twos-cli')
    assert_df("""
2019-01-01 00:00:00+00:00    1.0
2019-01-02 00:00:00+00:00    1.0
2019-01-03 00:00:00+00:00    1.0
2019-01-04 00:00:00+00:00    2.0
2019-01-05 00:00:00+00:00    2.0
""", ts)
