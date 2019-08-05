from typing import Union, Optional

import pandas as pd

from tshistory.util import SeriesServices
from tshistory_formula.registry import func


@func('series')
def series(__interpreter__,
           name: str,
           fill: Optional[str]=None,
           prune: Optional[str]=None) -> pd.Series:
    i = __interpreter__
    ts = i.get(name, i.getargs)
    if ts is None:
        if not i.tsh.exists(i.cn, name):
            raise ValueError(f'No such series `{name}`')
        ts = pd.Series(name=name)
    if prune:
        ts = ts[:-prune]
    ts.options = {
        'fillopt': fill
    }
    return ts


@func('+')
def scalar_add(
        a: Union[int, float, pd.Series],
        b: Union[int, float, pd.Series]) -> pd.Series:
    if isinstance(a, pd.Series):
        assert isinstance(b, (int, float))
        options = a.options
    else:
        assert isinstance(a, (int, float))
        options = b.options

    ts = a + b
    # we did a series + scalar and want to propagate
    # the original series options
    ts.options = options
    return ts


@func('*')
def scalar_prod(
        a: Union[int, float, pd.Series],
        b: Union[int, float, pd.Series]) -> pd.Series:
    if isinstance(a, pd.Series):
        assert isinstance(b, (int, float))
        options = a.options
    else:
        assert isinstance(a, (int, float))
        options = b.options

    ts = a * b
    # we did a series * scalar and want to propagate
    # the original series options
    ts.options = options
    return ts


@func('add')
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


@func('priority')
def series_priority(*serieslist: pd.Series) -> pd.Series:
    patcher = SeriesServices()
    final = pd.Series()

    for ts in reversed(serieslist):
        assert ts.dtype != 'O'
        final = patcher.patch(final, ts)

    return final


@func('outliers')
def series_drop_outliers(series: pd.Series,
                         min: Optional[int]=None,
                         max: Optional[int]=None) -> pd.Series:
    if max is not None:
        series = series[series <= max]
    if min is not None:
        series = series[series >= min]
    return series
