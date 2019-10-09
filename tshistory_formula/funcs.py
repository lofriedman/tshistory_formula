from typing import Union, Optional

import numpy as np
import pandas as pd

from tshistory.util import SeriesServices
from tshistory_formula.registry import func, finder


def options(series):
    return getattr(series, 'options', {})


@func('series')
def series(__interpreter__,
           name: str,
           fill: Optional[str]=None,
           prune: Optional[str]=None,
           weight: Optional[float]=None) -> pd.Series:
    i = __interpreter__
    ts = i.get(name, i.getargs)
    if ts is None:
        if not i.tsh.exists(i.cn, name):
            raise ValueError(f'No such series `{name}`')
        ts = pd.Series(name=name)
    if prune:
        ts = ts[:-prune]
    ts.options = {
        'fill': fill
    }
    if weight is not None:
        ts.options['weight'] = weight
    return ts


@finder('series')
def find_series(cn, tsh, stree):
    name = stree[1]
    return {name: tsh.metadata(cn, name)}


@func('+')
def scalar_add(
        a: Union[int, float, pd.Series],
        b: Union[int, float, pd.Series]) -> pd.Series:
    if isinstance(a, pd.Series):
        assert isinstance(b, (int, float))
        opts = options(a)
    else:
        assert isinstance(a, (int, float))
        opts = options(b)

    ts = a + b
    # we did a series + scalar and want to propagate
    # the original series options
    ts.options = opts
    return ts


@func('*')
def scalar_prod(
        a: Union[int, float, pd.Series],
        b: Union[int, float, pd.Series]) -> pd.Series:
    if isinstance(a, pd.Series):
        assert isinstance(b, (int, float))
        opts = options(a)
    else:
        assert isinstance(a, (int, float))
        opts = options(b)

    ts = a * b
    # we did a series * scalar and want to propagate
    # the original series options
    ts.options = opts
    return ts


@func('/')
def scalar_div(
        a: Union[int, float, pd.Series],
        b: Union[int, float]) -> Union[int, float, pd.Series]:
    opts = None
    if isinstance(a, pd.Series):
        assert isinstance(b, (int, float))
        opts = options(a)

    res = a / b
    if opts is not None:
        res.options = opts
    return res



def _fill(df, colname, fillopt):
    """ in-place application of the series fill policies
    which can be a int/float or a coma separated string
    like e.g. 'ffill,bfill'
    """
    if isinstance(fillopt, str):
        for method in fillopt.split(','):
            df[colname] = df[colname].fillna(
                method=method.strip()
            )
    elif isinstance(fillopt, (int, float)):
        df[colname] = df[colname].fillna(
            value=fillopt
        )


def _group_series(*serieslist):
    df = None
    opts = {}

    # join everything
    for ts in serieslist:
        while ts.name in opts:
            ts.name = f'{id(ts)}'  # do something unique
        fillopt = (
            ts.options['fill']
            if ts.options.get('fill') is not None
            else None
        )
        opts[ts.name] = fillopt
        if df is None:
            df = ts.to_frame()
            continue
        df = df.join(ts, how='outer')

    # apply the filling rules
    for name, fillopt in opts.items():
        _fill(df, name, fillopt)

    return df


@func('add')
def series_add(*serieslist: pd.Series) -> pd.Series:
    assert [
        isinstance(s, pd.Series)
        for s in serieslist
    ]

    return _group_series(*serieslist).dropna().sum(axis=1)


@func('mul')
def series_multiply(*serieslist: pd.Series) -> pd.Series:
    assert [
        isinstance(s, pd.Series)
        for s in serieslist
    ]

    df = _group_series(*serieslist)

    res = None
    for col in df.columns:
        if res is None:
            res = df[col].to_frame()
            continue
        res = res.multiply(df[col], axis=0)

    return res[res.columns[0]].dropna()


@func('div')
def series_div(s1: pd.Series, s2: pd.Series) -> pd.Series:
    df = _group_series(*(s1, s2))

    c1, c2 = df.columns
    return (df[c1] / df[c2]).dropna()


@func('priority')
def series_priority(*serieslist: pd.Series) -> pd.Series:
    patcher = SeriesServices()
    final = pd.Series()

    for ts in reversed(serieslist):
        assert ts.dtype != 'O'
        final = patcher.patch(final, ts)

    return final


@func('clip')
def series_clip(series: pd.Series,
                min: Optional[float]=None,
                max: Optional[float]=None) -> pd.Series:
    if max is not None:
        series = series[series <= max]
    if min is not None:
        series = series[series >= min]
    return series


class iso_utc_datetime(str):

    def to_datetime(self):
        return pd.Timestamp(self, tz='UTC')


@func('slice')
def slice(series: pd.Series,
          fromdate: Optional[iso_utc_datetime]=None,
          todate: Optional[iso_utc_datetime]=None) -> pd.Series:
    fromdate = fromdate and iso_utc_datetime(fromdate) or None
    todate = todate and iso_utc_datetime(todate) or None
    sliced = series.loc[fromdate:todate]
    sliced.options = series.options
    return sliced


@func('row-mean')
def row_mean(*serieslist: pd.Series) -> pd.Series:
    """Computes element-wise weighted mean of the input series list

    Missing points are handled as missing series.
    """

    weights = [
        series.options.get('weight', 1)
        for series in serieslist
    ]

    allseries = pd.concat(serieslist, axis=1)
    weights_in_vertical_matrix = np.array(
        [[w] for w in weights]
    )
    weighted_sum = allseries.fillna(0).values.dot(
        weights_in_vertical_matrix
    )
    denominator = (~allseries.isnull()).values.dot(
        weights_in_vertical_matrix
    )

    return pd.Series(
        (weighted_sum / denominator).flatten(),
        index=allseries.index
    )


@func('min')
def row_min(*serieslist: pd.Series) -> pd.Series:
    allseries = pd.concat(serieslist, axis=1)
    return allseries.min(axis=1)


@func('max')
def row_max(*serieslist: pd.Series) -> pd.Series:
    allseries = pd.concat(serieslist, axis=1)
    return allseries.max(axis=1)


@func('std')
def row_std(*serieslist: pd.Series) -> pd.Series:
    allseries = pd.concat(serieslist, axis=1)
    return allseries.std(axis=1).dropna()
