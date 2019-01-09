from typing import Union, Optional

import pandas as pd

from tshistory.util import SeriesServices


def scalar_add(
        a: Union[int, float, pd.Series],
        b: Union[int, float, pd.Series]) -> pd.Series:
    if isinstance(a, (int, float)):
        assert isinstance(b, (int, float, pd.Series))
    if isinstance(b, (int, float)):
        assert isinstance(a, (int, float, pd.Series))

    return a + b


def scalar_prod(
        a: Union[int, float, pd.Series],
        b: Union[int, float, pd.Series]) -> pd.Series:
    if isinstance(a, (int, float)):
        assert isinstance(b, (int, float, pd.Series))
    if isinstance(b, (int, float)):
        assert isinstance(a, (int, float, pd.Series))

    return a * b


def series_add(*serieslist: pd.Series) -> pd.Series:
    assert [
        isinstance(s, pd.Series)
        for s in serieslist
    ]

    df = None
    filloptmap = {}

    for ts in serieslist:
        if ts.options.get('fillopt') is not None:
            filloptmap[ts.name] = ts.options['fillopt']
        if df is None:
            df = ts.to_frame()
            continue
        df = df.join(ts, how='outer')

    for ts, fillopt in filloptmap.items():
        if isinstance(fillopt, str):
            for method in fillopt.split(','):
                df[ts] = df[ts].fillna(method=method.strip())
        else:
            assert isinstance(fillopt, (int, float))
            df[ts] = df[ts].fillna(value=fillopt)

    return df.dropna().sum(axis=1)


def series_priority(*serieslist: pd.Series) -> pd.Series:
    patcher = SeriesServices()
    final = pd.Series()

    for ts in serieslist:
        assert ts.dtype != 'O'
        prune = ts.options.get('prune')
        if prune:
            ts = ts[:-prune]
        final = patcher.patch(final, ts)

    return final


def series_drop_outliers(series: pd.Series,
                         min: Optional[int]=None,
                         max: Optional[int]=None) -> pd.Series:
    if max is not None:
        series = series[series <= max]
    if min is not None:
        series = series[series >= min]
    return series


def series_get(i,
               name: str,
               fill: Optional[str]=None,
               prune: Optional[str]=None) -> pd.Series:
    ts = i.get(name)
    ts.options = {
        'fillopt': fill,
        'prune': prune
    }
    return ts
