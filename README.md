TSHISTORY FORMULA
=================

# Purpose

This [tshistory][tshistory] component provides a formula language to
build computed series.

Using `csv` definition files, one can define formula using a simple
lisp-like syntax, using a pre-defined function library.

Amongst the predefined functions we find:

* filters for `outliers` elimination (fixed min/max values)

* composition of series by arithmetic combination

* scalar sum/product of series

* composition of series by stacking series onto each others
  (named `priority`)


A `priority` is defined by a list of series, the first series
providing baseline values, and the nexts completing missing values of
the previous combination (up to the baseline).

For instance one could use the realised solar output as a baseline of
a `priority` which would be completed by a forecast series.

It is not possible to `.insert` data into a formula.

[tshistory]: https://bitbucket.org/pythonian/tshistory


# Formula

Formulas are expressed in a lisp-like syntax using `operators`,
mandatory parameters and keyword (optional) parameters.

The general form is:

 `(<operator> <param1> ... <paramN> #:<keyword1> <value1> ... #:<keywordN> <valueN>)`

Here are a couple examples:

* `(add (series "wallonie") (series "bruxelles") (series "flandres"))`

Here we see the two fundamental `add` and `series` operators at work.

This would form a new synthetic series out of three base series (which
can be either raw series or formulas themselves).

A `priority` will be written like this:

* `(priority (series "realized") (series "nominated") (series "forecasted"))`

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


# API

A few api calls are added to the `tshistory` base:

* `.register_formula` to define a formula

* `.convert_aliases` to convert aliases to formulas (see the
  superceded [tshistory_alias][tshistory_alias] component)

[tshistory_alias]: https://bitbucket.org/pythonian/tshistory_alias


# Command line

A few commands are provided to deal with the specifics of aliases. The
`tsh` command carries them. The output below shows only the specific
aliases subcommands:

```shell
$ tsh
Usage: tsh [OPTIONS] COMMAND [ARGS]...

Options:
  --help  Show this message and exit.

Commands:
  convert-aliases
  ingest-formulas           ingest a csv file of formulas Must be a...
```
