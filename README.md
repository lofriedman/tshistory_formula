TSHISTORY FORMULA
=================

# Purpose

This [tshistory][tshistory] component provides a formula language to
build computed series.

Formulas are defined using a simple lisp-like syntax, using a
pre-defined function library.

Formulas are read-only series (you can't `update` or `replace`
values).

They also have an history, which is built, time stamps wise, using the
union of all constituent time stamps, and value wise, by applying the
formula.

Because of this the `staircase` operator is available on formulae.
Some `staircase` operations can have a very fast implementation if the
formula obeys commutativity rules.

[tshistory]: https://hg.sr.ht/~pythonian/tshistory


# Formula

## General Syntax

Formulas are expressed in a lisp-like syntax using `operators`,
positional (mandatory) parameters and keyword (optional) parameters.

The general form is:

 `(<operator> <param1> ... <paramN> #:<keyword1> <value1> ... #:<keywordN> <valueN>)`

Here are a couple examples:

* `(add (series "wallonie") (series "bruxelles") (series "flandres"))`

Here we see the two fundamental `add` and `series` operators at work.

This would form a new synthetic series out of three base series (which
can be either raw series or formulas themselves).

Some notes:

* operator names can contain dashes or arbitrary caracters

* literal values can be: `3` (integer), `5.2` (float), `"hello"`
  (string) and `#t` or `#f` (true ot false)


## Pre-defined operators

### *

Performs a scalar product on a series.

Example: `(* -1 (series "positive-things"))`

### +

Add a constant quantity to a series.

Example: `(+ 42 (series "i-feel-undervalued"))`

### /

Perform a scalar division between numbers or a series and a scalar.

Example: `(/ (series "div-me") (/ 3 2))`

### add

Linear combination of two or more series. Takes a variable number
of series as input.

Example: `(add (series "wallonie") (series "bruxelles") (series "flandres"))`

To specify the behaviour of the `add` operation in the face of missing
data, the series can be built with the `fill` keyword. This option is
only really applied when several series are combined. By default, if
an input series has missing values for a given time stamp, the
resulting series has no value for this timestamp (unless a fill rule
is provided).

### clip

Set an upper/lower threashold for a series. Takes a series as
positional parameter and accepts two optional keywords `min` and `max`
which must be numbers (integers or floats).

Example: `(clip (series "must-be-positive") #:min 0)`

### date

Produces an utc timestamp from its input string date in iso format.

The `tz` keyword allows to specify an alternate time zone.
The `naive` keyword forces production of a naive timestamp.
Both `tz` and `naive` keywords are mutually exlcusive.

### div

Element wise division of two series.

Example: `(div (series "$-to-€") (series "€-to-£"))`

### min

Computes the row-wise minimum of its input series.

Example: `(min (series "station0") (series "station1") (series "station2"))`

### max

Computes the row-wise maximum of its input series.

Example: `(max (series "station0") (series "station1") (series "station2"))`

### mul

Element wise multiplication of series. Takes a variable number of series
as input.

Example: `(mul (series "banana-spot-price ($)") (series "$-to-€" #:fill 'ffill'))`

This might convert a series priced in dollars to a series priced in
euros, using a currency exchange rate series with a forward-fill
option.

### naive

Allow demoting a series from a tz-aware index (strongly recommended)
to a tz-naive index (unfortunately sometimes unavoidable for interop
with other tz-naive series).

One must provide a country code and a target timezone.

Example: `(naive (series "tz-aware-series-from-poland") "PL" "Europe/Warsaw")`

### priority

The priority operator combines its input series as layers. For each
timestamp in the union of all series time stamps, the value comes from
the first series that provides a value.

Example: `(priority (series "realized") (series "nominated") (series "forecasted"))`

Here `realized` values show up first, and any missing values come from
`nominated` first and then only from `forecasted`.

### resample

Resamples its input series using `freq` and the aggregation method
`method` (as described in the pandas documentation).

Example: `(resample (series "hourly") "D")`

### row-mean

This operator computes the row-wise mean of its input series using the
series `weight` option if present. The missing points are handled as
if the whole series were absent.

Example: `(row-mean (series "station0") (series "station1" #:weight 2) (series "station2"))`

Weights are provided as a keyword to `series`. No weight is
interpreted as 1.

### series

The `series` operator accepts several keywords:

* `fill` to specify a filling policy to avoid `nans` when the series
  will be `add`ed with others; accepted values are `"ffill"`
  (forward-fill), `"bfill"` (backward-fill) or any floating value.

* `prune` to indicate how many points must be truncated from the tail
  end (useful for priorities).

For instance in `(add (series "a" #:fill 0) (series "b")` will make
sure that series `a`, if shorter than series `b` will get zeroes
instead of nans where `b` provides values.

In `(series "realized" #:prune 3)` we would drop the last three points.

### slice

This allows cutting a series at date points. It takes one positional
parameter (the series) and two optional keywords `fromdate` and
`todate` which must be strings in the [iso8601][iso8601] format.

Example: `(slice (series "cut-me") #:fromdate "2018-01-01")`

[iso8601]: https://en.wikipedia.org/wiki/ISO_8601

### std

Computes the standard deviation over its input series.

Example: `(std (series "station0") (series "station1") (series "station2"))`

### timedelta

Takes a timestamp and a number of years, months, weekds, days,
hours, minutes (int) and computes a new date according to the asked
delta elements.

Example: `(timedelta (date "2020-1-1") #:weeks 1 #:hours 2)`

### today

Produces a timezone-aware timestamp as of today

The `tz` keyword allows to specify an alternate time zone.
The `naive` keyword forces production of a naive timestamp.
Both `tz` and `naive` keywords are mutually exlcusive.

Example: `(today)`


# Registering new operators

This is a fundamental need. Operators are fixed python functions
exposed through a lispy syntax. Applications need a variety of fancy
operators.

## declaring a new operator

One just needs to decorate a python with the `func` decorator:

```python
  from tshistory_formula.registry import func

  @func('identity')
  def identity(series):
      return series
```

The operator will be known to the outer world by the name given to
`@func`, not the python function name (which can be arbitrary).

This is enough to get a working transformation operator.  However
operators built to construct series rather than just transform
pre-existing series are more complicated.

## custom series operator

We start with an example, a `shifted` operator that gets a series with shifted
from_value_date/to_value_date boundaries by a constant `delta` amount.

We would use it like this: `(shifted "shiftme" #:days -1)`

As we can see the standard `series` operator won't work there, that is
applying a shift operator (`(shift (series "shiftme"))`) *after* the
call to series is too late. The from/to implicit parameters have
already been handled by `series` itself and there is nothing left to
*shift*.

Hence `shifted` must be understood as an alternative to `series` itself.
Here is a possible implementation:

```python
  from tshistory_formula.registry import func, finder

  @func('shifted')
  def shifted(__interpreter__, name, days=0):
      args = __interpreter__.getargs.copy()
      fromdate = args.get('from_value_date')
      todate = args.get('to_value_date')
      if fromdate:
          args['from_value_date'] = fromdate + timedelta(days=days)
      if todate:
          args['to_value_date'] = todate + timedelta(days=days)

      return __interpreter__.get(name, args)

  @finder('shifted')
  def find_series(cn, tsh, tree):
      return {
          tree[1]: tsh.metadata(cn, tree[1])
      }
```

As we can see, we use a new `finder` protocol. But first let's examine
how the `shiftme` operator is implemented.

First it takes a special `__interpreter__` parameter, which will
receive the formula interpreter object, providing access to an
important internal API of the evaluation process.

Indeed from the interpreter we can read the `getargs` attribute, which
contains a dictionary of the actual query mapping. We are specially
interested in the `from_value_date` and `to_value_date` items in our
example, but all the parameters of `tshistory.get` are available
there.

Once we have shifted the from/to value date parameter we again use the
interpreter to make a call to `get` which will in turn perform a call
to the underlying `tshistory.get` (which, we don't know in advance,
may yield a primary series or another formula computed series).

Implementing the operator this way, we actually miss two important
pieces of information:

* the system cannot determine a series is _produced_ by the `shifted`
  operator like it can with `series`

* and because of this it cannot know the technical metadata of the
  produced series (e.g. the `tzaware` attribute)

This is where the `finder` protocol and its decorator function comes
into play. For `shifted` we define a finder. It is a function that
takes the db connection (`cn`), time series protocol handler (`tsh`)
and formula syntax tree (`tree`), and must return a mapping from
series name to its metadata.

The tree is an obvious Python data structure representing a use of the
operator in a formula.

For instance because of the `shifted` python signature, any use will
be like that:

* in lisp `... (shifted "shift-me" #:hours +1) ... ` (the dots
  indicate that it can be part of a larger formula)

* tree in python: `['shifted', "shift-me", 'hours', 1]`

The name is always in position 1 in the list. Hence the implementation
of the shifted *finder*:

```python
      return {
          tree[1]: tsh.metadata(cn, tree[1])
      }
```

For the metadata we delegate the computation to the underlying series metadata.

We might want to provide an ad-hoc metadata dictionary if we had a
proxy operator that would forward the series from an external source:

```python
  @func('proxy')
  def proxy(
          __interpreter__,
          series_uid: str,
          default_start: date,
          default_end : date) -> pd.Series:
      i = __interpreter__
      args = i.getargs.copy()
      from_value_date = args.get('from_value_date') or default_start
      to_value_date = args.get('to_value_date') or default_end

      proxy = ProxyClient()
      return proxy.get(
          series_uid,
          from_value_date,
          to_value_date,
      )

  @finder('proxy')
  def proxy(cn, tsh, tree):
      return {
          tree[1]: {
              'index_type': 'datetime64[ns]',
              'tzaware': False,
              'value_type': 'float64'
          }
      }
```

Here, because we have no other means to know (and the proxy provides
some useful documentation), we write the metadata ourselves
explicitly.

Also note how accessing the `__interpreter__` again is used to forward
the query arguments.


## Editor Infos

The `tshistory_formula` package provides a custom callback for the
`editor` capabilities of [tshistory_editor][tshistory_editor].

A dedicated protocol is available to inform the editor on the way
to decompose/display a formula.

Example of such a function:

```python
 from tshistory_formula.registry import editor_info

 @editor_info
 def operator_with_series(builder, expr):
     for subexpr in expr[1:]:
         with builder.series_scope(subexpr):
             builder.buildinfo_expr(subexpr)

```

The exact ways to use the builder will be provided soon.

[tshistory_editor]: https://hg.sr.ht/~pythonian/tshistory_editor


# Series API

A few api calls are added to the `tshistory` base:

* `.register_formula` to define a formula

* `.eval_formula` to evaluate on-the-fly a formula (useful to check
  that it computes before registering it)

## register_formula

Exemple:

```python
  tsh.register_formula(
      cn,
      'my-sweet-formula',
      '(* 3.14 (series "going-round"))',
      reject_unkown=True,
      update=True
  )
```

First comes the db connection object, second the formula name, last
the actual expression.

The `reject_unknown` parameter, which is True by default, makes the
method fail if one constituent of the formula does not exist
(e.g. "going-round" is neither a primary series or a formula).

The `update` parameter tells wether an existing formula can be
overwritten (False by default).

# eval_formula

Example:

```python
 >>> tsh.eval_formula(cn, '(* 3.14 (series "going-round"))')
 ...
 2020-01-01    3.14
 2020-01-02    6.28
 2020-01-03    9.42
 dtype: float64
```

# Command line

The `tsh` command carries formula specific subcommands. The output
below shows only the specific formula subcommands:

```shell
$ tsh
Usage: tsh [OPTIONS] COMMAND [ARGS]...

Options:
  --help  Show this message and exit.

Commands:
  ingest-formulas           ingest a csv file of formulas Must be a...
```
