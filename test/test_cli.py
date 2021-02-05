from datetime import datetime as dt

import pandas as pd
from tshistory.testutil import assert_df


def utcdt(*dtargs):
    return pd.Timestamp(dt(*dtargs), tz='UTC')


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


def test_update_metadata(engine, cli, tsh):
    x = pd.Series(
        [1, 2, 3],
        index=pd.date_range(utcdt(2020, 1, 1), periods=3, freq='D')
    )
    tsh.update(engine, x, 'tzaware', 'Babar')

    tsh.register_formula(
        engine,
        'tzaware-form',
        '(series "tzaware")',
    )

    tsh.register_formula(
        engine,
        'tznaive-form',
        '(+ 1 (naive (series "tzaware-form") "Europe/Paris"))',
    )

    m1 = tsh.metadata(engine, 'tzaware-form')
    assert m1['tzaware']
    m2 = tsh.metadata(engine, 'tznaive-form')
    assert not m2['tzaware']

    # let's do shit to the metadata
    tsh.update_metadata(engine, 'tzaware-form', tsh.default_meta(False))
    tsh.update_metadata(engine, 'tznaive-form', tsh.default_meta(True))

    # flipped :o
    m1 = tsh.metadata(engine, 'tzaware-form')
    assert not m1['tzaware']
    m2 = tsh.metadata(engine, 'tznaive-form')
    assert m2['tzaware']

    cli('update-formula-metadata', str(engine.url))

    # flipped back o:
    m1 = tsh.metadata(engine, 'tzaware-form')
    assert m1['tzaware']
    m2 = tsh.metadata(engine, 'tznaive-form')
    assert not m2['tzaware']
