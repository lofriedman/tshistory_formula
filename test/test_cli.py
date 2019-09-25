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
