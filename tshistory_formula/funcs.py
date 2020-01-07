from datetime import datetime
from typing import Union, Optional
from numbers import Number

import numpy as np
import pandas as pd
import pytz
from dateutil.relativedelta import relativedelta

from tshistory.util import SeriesServices
from tshistory_formula.registry import func, finder


NONETYPE = type(None)



@func('series')
def series(__interpreter__,
           name: str,
           fill: Union[str, Number, NONETYPE]=None,
           prune: Optional[int]=None,
           weight: Optional[Number]=None) -> pd.Series:
    """
    The `series` operator accepts several keywords:

    * `fill` to specify a filling policy to avoid `nans` when the
      series will be `add`ed with others; accepted values are
      `"ffill"` (forward-fill), `"bfill"` (backward-fill) or any
      floating value.

    * `prune` to indicate how many points must be truncated from the
      tail end (useful for priorities).

    For instance in `(add (series "a" #:fill 0) (series "b")` will
    make sure that series `a`, if shorter than series `b` will get
    zeroes instead of nans where `b` provides values.

    In `(series "realized" #:prune 3)` we would drop the last three points.
    """
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
    meta = tsh.metadata(cn, name)
    # alt sources lookup
    if meta is None and tsh.othersources:
        meta = tsh.othersources.metadata(name, all=True)
    if meta:
        meta['expandable'] = True
    return {name: meta}


@func('naive')
def naive(series: pd.Series, tzone: str) -> pd.Series:
    """
    Allow demoting a series from a tz-aware index to a tz-naive index.

    One must provide a target timezone.

    Example: `(naive (series "tz-aware-series-from-poland") "Europe/Warsaw")`

    """
    series.index = series.index.tz_convert(tzone).tz_localize(None)
    return series


@finder('naive')
def find_holidays(cn, tsh, tree):
    return {
        'naive': {
            'index_dtype': '<M8[ns]',
            'index_type': 'datetime64[ns]',
            'tzaware': False,
            'value_dtype': '<f8',
            'value_type': 'float64'
        }
    }


@func('date')
def timestamp(strdate: str,
              naive: bool=False,
              tz: Optional[str]=None) -> pd.Timestamp:
    """
    Produces an utc timestamp from its input string date in iso format.

    The `tz` keyword allows to specify an alternate time zone.
    The `naive` keyword forces production of a naive timestamp.
    Both `tz` and `naive` keywords are mutually exlcusive.
    """
    if tz:
        assert not naive, f'date cannot be naive and have a tz'
        pytz.timezone(tz)
    if naive:
        return pd.Timestamp(strdate)
    return pd.Timestamp(strdate, tz=tz or 'utc')


@func('timedelta')
def timedelta_eval(date: pd.Timestamp,
                   years: int=0,
                   months: int=0,
                   weeks: int=0,
                   days: int=0,
                   hours: int=0,
                   minutes: int=0) -> pd.Timestamp:
    """
    Takes a timestamp and a number of years, months, weekds, days,
    hours, minutes (int) and computes a new date according to the asked
    delta elements.

    Example: `(timedelta (date "2020-1-1") #:weeks 1 #:hours 2)`

    """
    return date + relativedelta(
        years=years,
        months=months,
        weeks=weeks,
        days=days,
        hours=hours,
        minutes=minutes
    )


@func('today')
def today(naive: bool=False,
          tz:Optional[str]=None) -> pd.Timestamp:
    """
    Produces a timezone-aware timestamp as of today

    The `tz` keyword allows to specify an alternate time zone.
    The `naive` keyword forces production of a naive timestamp.
    Both `tz` and `naive` keywords are mutually exlcusive.

    Example: `(today)`
    """
    if tz:
        assert not naive, f'date cannot be naive and have a tz'
        pytz.timezone(tz)
        tz = pytz.timezone(tz)
    if naive:
        return pd.Timestamp(datetime.today())
    return pd.Timestamp(datetime.today(), tz=tz or 'utc')


@func('+')
def scalar_add(
        a: Number,
        b: Union[Number, pd.Series]) -> Union[Number, pd.Series]:
    """
    Add a constant quantity to a series.

    Example: `(+ 42 (series "i-feel-undervalued"))`
    """
    opts = None
    if isinstance(b, pd.Series):
        assert isinstance(a, (int, float))
        opts = b.options

    res = a + b
    if opts is not None:
        # we did a series + scalar and want to propagate
        # the original series options
        res.options = opts
    return res


@func('*')
def scalar_prod(
        a: Number,
        b: Union[Number, pd.Series]) -> Union[Number, pd.Series]:
    """
    Performs a scalar product on a series.

    Example: `(* -1 (series "positive-things"))`
    """
    opts = None
    if isinstance(b, pd.Series):
        assert isinstance(a, (int, float))
        opts = b.options

    res = a * b
    if opts is not None:
        # we did a series * scalar and want to propagate
        # the original series options
        res.options = opts
    return res


@func('/')
def scalar_div(
        a: Union[Number, pd.Series],
        b: Number) -> Union[Number, pd.Series]:
    """
    Perform a scalar division between numbers or a series and a scalar.

    Example: `(/ (series "div-me") (/ 3 2))`
    """
    opts = None
    if isinstance(a, pd.Series):
        assert isinstance(b, (int, float))
        opts = a.options

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
    dfs = []
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
        dfs.append(ts)

    df = pd.concat(dfs, axis=1, join='outer')

    # apply the filling rules
    for name, fillopt in opts.items():
        _fill(df, name, fillopt)

    return df


@func('add')
def series_add(*serieslist: pd.Series) -> pd.Series:
    """
    Linear combination of two or more series. Takes a variable number
    of series as input.

    Example: `(add (series "wallonie") (series "bruxelles") (series "flandres"))`

    To specify the behaviour of the `add` operation in the face of
    missing data, the series can be built with the `fill`
    keyword. This option is only really applied when several series
    are combined. By default, if an input series has missing values
    for a given time stamp, the resulting series has no value for this
    timestamp (unless a fill rule is provided).

    """
    assert [
        isinstance(s, pd.Series)
        for s in serieslist
    ]

    return _group_series(*serieslist).dropna().sum(axis=1)


@func('mul')
def series_multiply(*serieslist: pd.Series) -> pd.Series:
    """
    Element wise multiplication of series. Takes a variable number of
    series as input.

    Example: `(mul (series "banana-spot-price ($)") (series "$-to-€" #:fill 'ffill'))`

    This might convert a series priced in dollars to a series priced
    in euros, using a currency exchange rate series with a
    forward-fill option.
    """
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
    """
    Element wise division of two series.

    Example: `(div (series "$-to-€") (series "€-to-£"))`
    """
    df = _group_series(*(s1, s2))

    c1, c2 = df.columns
    return (df[c1] / df[c2]).dropna()


@func('priority')
def series_priority(*serieslist: pd.Series) -> pd.Series:
    """
    The priority operator combines its input series as layers. For
    each timestamp in the union of all series time stamps, the value
    comes from the first series that provides a value.

    Example: `(priority (series "realized") (series "nominated") (series "forecasted"))`

    Here `realized` values show up first, and any missing values come
    from `nominated` first and then only from `forecasted`.
    """
    patcher = SeriesServices()
    final = pd.Series()

    for ts in reversed(serieslist):
        assert ts.dtype != 'O'
        final = patcher.patch(final, ts)

    return final


@func('clip')
def series_clip(series: pd.Series,
                min: Optional[Number]=None,
                max: Optional[Number]=None) -> pd.Series:
    """
    Set an upper/lower threashold for a series. Takes a series as
    positional parameter and accepts two optional keywords `min` and
    `max` which must be numbers (integers or floats).

    Example: `(clip (series "must-be-positive") #:min 0)`
    """
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
          fromdate: Optional[pd.Timestamp]=None,
          todate: Optional[pd.Timestamp]=None) -> pd.Series:
    """
    This allows cutting a series at date points. It takes one
    positional parameter (the series) and two optional keywords
    `fromdate` and `todate` which must be strings in the
    iso8601 format.

    Example: `(slice (series "cut-me") #:fromdate (date "2018-01-01"))`
    """
    sliced = series.loc[fromdate:todate]
    sliced.options = series.options
    return sliced


@func('row-mean')
def row_mean(*serieslist: pd.Series) -> pd.Series:
    """
    This operator computes the row-wise mean of its input series using
    the series `weight` option if present. The missing points are
    handled as if the whole series were absent.

    Example: `(row-mean (series "station0") (series "station1" #:weight 2) (series "station2"))`

    Weights are provided as a keyword to `series`. No weight is
    interpreted as 1.
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
    """
    Computes the row-wise minimum of its input series.

    Example: `(min (series "station0") (series "station1") (series "station2"))`
    """
    allseries = pd.concat(serieslist, axis=1)
    return allseries.min(axis=1)


@func('max')
def row_max(*serieslist: pd.Series) -> pd.Series:
    """
    Computes the row-wise maximum of its input series.

    Example: `(max (series "station0") (series "station1") (series "station2"))`
    """
    allseries = pd.concat(serieslist, axis=1)
    return allseries.max(axis=1)


@func('std')
def row_std(*serieslist: pd.Series) -> pd.Series:
    """
    Computes the standard deviation over its input series.

    Example: `(std (series "station0") (series "station1") (series "station2"))`
    """
    allseries = pd.concat(serieslist, axis=1)
    return allseries.std(axis=1).dropna()
