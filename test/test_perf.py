from time import time

import pytest
import numpy as np
import pandas as pd

from tshistory.testutil import utcdt


@pytest.mark.perf
def test_priority(engine, tsh):
    data = np.linspace(0, 100, num=365 * 10, dtype='float64')
    s1 = pd.Series(
        data,
        index=pd.date_range(
            start=utcdt(2020, 1, 1), freq='D', periods=365 * 10
        )
    )
    s2 = pd.Series(
        data,
        index=pd.date_range(
            start=utcdt(2020, 6, 1), freq='D', periods=365 * 10
        )
    )
    s3 = pd.Series(
        data,
        index=pd.date_range(
            start=utcdt(2020, 9, 1), freq='D', periods=365 * 10
        )
    )
    s4 = pd.Series(
        data,
        index=pd.date_range(
            start=utcdt(2020, 12, 1), freq='D', periods=365 * 10
        )
    )

    tsh.update(
        engine,
        s1,
        'prio1',
        'Babar'
    )
    tsh.update(
        engine,
        s2,
        'prio2',
        'Celeste'
    )
    tsh.update(
        engine,
        s3,
        'prio3',
        'Arthur'
    )
    tsh.update(
        engine,
        s4,
        'prio4',
        'Zéphir'
    )

    tsh.register_formula(
        engine,
        'patch',
        '(priority (series "prio4") (series "prio3") (series "prio2") (series "prio1"))'
    )
    t0 = time()
    with engine.begin():
        for _ in range(300):
            patched = tsh.get(engine, 'patch')
    print('100 patches', time() - t0)
