from threading import local

import pandas as pd

from psyl.lisp import Env, evaluate, parse
from tshistory.util import SeriesServices


THDICT = local()


def scalar_add(a, b):
    if isinstance(a, (int, float)):
        assert isinstance(b, (int, float, pd.Series))
    if isinstance(b, (int, float)):
        assert isinstance(a, (int, float, pd.Series))

    return a + b


def pylist(*args):
    return args


def series_add(serieslist):
    assert [
        isinstance(s, pd.Series)
        for s in serieslist
    ]

    df = None
    filloptmap = {}

    for ts in serieslist:
        if ts.options.get('fillopt'):
            filloptmap[ts.name] = ts.options['fillopt']
        if df is None:
            df = ts.to_frame()
            continue
        df = df.join(ts, how='outer')

    for ts, fillopt in filloptmap.items():
        for method in fillopt.split(','):
            df[ts] = df[ts].fillna(method=method.strip())

    return df.dropna().sum(axis=1)


def series_priority(serieslist):
    patcher = SeriesServices()
    final = pd.Series()

    for ts in serieslist:
        assert ts.dtype != 'O'
        prune = ts.options.get('prune')
        if prune:
            ts = ts[:-prune]
        final = patcher.patch(final, ts)

    return final


def series_get(name, fill=None, prune=None):
    assert 'cn' in THDICT.__dict__
    assert 'tsh' in THDICT.__dict__
    cn = THDICT.cn
    tsh = THDICT.tsh
    ts = tsh.get(cn, name)
    ts.options = {
        'fillopt': fill,
        'prune': prune
    }
    return ts


ENV = Env({
    '+': scalar_add,
    'list': pylist,
    'add': series_add,
    'priority': series_priority,
    'series': series_get
})


