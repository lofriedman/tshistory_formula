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
