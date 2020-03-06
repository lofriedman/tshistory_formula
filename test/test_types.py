import json
import itertools
import typing
from numbers import Number

import pytest
import pandas as pd
from psyl import lisp

from tshistory_formula.interpreter import (
    Interpreter,
    jsontypes
)
from tshistory_formula.registry import func
from tshistory_formula.helper import (
    isoftype,
    sametype,
    typecheck
)


NONETYPE = type(None)


def test_dtypes():
    index = pd.date_range(
        pd.Timestamp('2021-1-1'),
        periods=3,
        freq='H'
    )
    assert index.dtype.str == '<M8[ns]'
    index2 = pd.date_range(
        pd.Timestamp('2021-1-1', tz='UTC'),
        periods=3,
        freq='H'
    )
    assert index2.dtype.str == '|M8[ns]'


def test_sametype():
    types = (str, int, float, pd.Series)
    for t1, t2 in itertools.product(types, types):
        if t1 == t2:
            continue
        assert not sametype(t1, t2)

    for t in types:
        assert sametype(t, t)
        assert sametype(typing.Union[NONETYPE, t], t)
        assert sametype(t, typing.Union[NONETYPE, t])
        assert sametype(
            typing.Union[NONETYPE, t],
            typing.Union[NONETYPE, t]
        )

    assert sametype(typing.Union[NONETYPE, int, pd.Series], int)
    assert sametype(typing.Union[NONETYPE, int, pd.Series], pd.Series)
    assert sametype(typing.Union[NONETYPE, int, pd.Series], NONETYPE)

    assert sametype(int, typing.Union[NONETYPE, int, pd.Series])
    assert sametype(pd.Series, typing.Union[NONETYPE, int, pd.Series])
    assert sametype(NONETYPE, typing.Union[NONETYPE, int, pd.Series])

    assert sametype(int, Number)
    assert sametype(Number, int)
    assert sametype(int, typing.Union[Number, pd.Series])
    assert sametype(Number, typing.Union[int, pd.Series])


def test_isoftype():
    assert isoftype(int, 1)
    assert isoftype(Number, 1)
    assert not isoftype(str, 1)
    assert isoftype(typing.Union[NONETYPE, int], 1)
    assert isoftype(typing.Union[NONETYPE, Number], 1)


def test_func_types():
    # prune the types registered from other modules/plugins
    # we want to only show the ones provided by the current package
    opnames = set(
        ('*', '+', '/', 'add', 'div', 'max', 'min', 'mul',
         'clip', 'priority', 'row-mean', 'series', 'slice', 'std',
         'timedelta', 'today')
    )
    types = {
        name: ftype
        for name, ftype in json.loads(jsontypes()).items()
        if name in opnames
    }
    assert {
        '*': {'a': 'Number',
              'b': 'Union[Number, Series]',
              'return': 'Union[Number, Series]'},
        '+': {'a': 'Number',
              'b': 'Union[Number, Series]',
              'return': 'Union[Number, Series]'},
        '/': {'a': 'Union[Number, Series]',
              'b': 'Number',
              'return': 'Union[Number, Series]'},
        'add': {'return': 'Series', 'serieslist': 'Series'},
        'clip': {'max': 'Optional[Number]',
                 'min': 'Optional[Number]',
                 'replacemax': 'Optional[bool]',
                 'replacemin': 'Optional[bool]',
                 'return': 'Series',
                 'series': 'Series'},
        'div': {'return': 'Series', 's1': 'Series', 's2': 'Series'},
        'max': {'return': 'Series', 'serieslist': 'Series'},
        'min': {'return': 'Series', 'serieslist': 'Series'},
        'mul': {'return': 'Series', 'serieslist': 'Series'},
        'priority': {'return': 'Series', 'serieslist': 'Series'},
        'row-mean': {'return': 'Series', 'serieslist': 'Series'},
        'series': {'fill': 'Optional[Union[str, Number]]',
                   'name': 'str',
                   'prune': 'Optional[int]',
                   'return': 'Series',
                   'weight': 'Optional[Number]'},
        'slice': {'fromdate': 'Optional[Timestamp]',
                  'return': 'Series',
                  'series': 'Series',
                  'todate': 'Optional[Timestamp]'},
        'std': {'return': 'Series', 'serieslist': 'Series'},
        'timedelta': {'date': 'Timestamp',
                      'days': 'int',
                      'hours': 'int',
                      'minutes': 'int',
                      'months': 'int',
                      'return': 'Timestamp',
                      'weeks': 'int',
                      'years': 'int'},
        'today': {'naive': 'Optional[bool]',
                  'return': 'Timestamp',
                  'tz': 'Optional[str]'}
    } == types


def test_operators_is_typed():
    def foo(x, *y, z=42):
        return x

    with pytest.raises(TypeError) as err:
        func('foo')(foo)
    assert err.value.args[0] == (
        'operator `foo` has type issues: arguments x are untyped, '
        'vararg y is untyped, return type is not provided'
    )


def test_basic_typecheck():
    def plus(a: int, b: int) -> int:
        return a + b

    env = lisp.Env({'+': plus})
    expr = ('(+ 3 4)')
    typecheck(lisp.parse(expr), env=env)

    expr = ('(+ 3 "hello")')
    with pytest.raises(TypeError):
        typecheck(lisp.parse(expr), env=env)

    def mul(a: int, b: int) -> int:
        return a * b

    env = lisp.Env({'+': plus, '*': mul})
    expr = ('(* 2 (+ 3 "hello"))')
    with pytest.raises(TypeError):
        typecheck(lisp.parse(expr), env=env)


def test_complex_typecheck(engine, tsh):
    expr = ('(add (series "types-a") '
            '     (priority (series "types-a") '
            '               (* 2 (series "types-b"))))'
    )

    i = Interpreter(engine, tsh, {})
    rtype = typecheck(lisp.parse(expr), i.env)
    assert rtype.__name__ == 'Series'


def test_failing_arg(engine, tsh):
    expr = ('(add (series "types-a") '
            '     (priority (series "types-a") '
            '               (* "toto" (series "types-b"))))'
    )

    i = Interpreter(engine, tsh, {})
    with pytest.raises(TypeError) as err:
        typecheck(lisp.parse(expr), i.env)

    assert err.value.args[0] == "'toto' not of <class 'numbers.Number'>"


def test_failing_kw(engine, tsh):
    expr = '(+ 1 (series "types-a" #:fill "ffill" #:prune "toto"))'
    i = Interpreter(engine, tsh, {})
    with pytest.raises(TypeError) as err:
        typecheck(lisp.parse(expr), i.env)

    assert err.value.args[0] == "keyword `prune` = 'toto' not of typing.Union[int, NoneType]"


def test_kw_subexpr(engine, tsh):
    expr = '(+ 1 (series "types-a" #:prune (+ 1 2)))'
    i = Interpreter(engine, tsh, {})
    typecheck(lisp.parse(expr), i.env)


def test_narrowing(engine, tsh):
    i = Interpreter(engine, tsh, {})
    for expr in (
        '(+ 2 (series "foo"))',
        '(* 2 (series "foo"))',
        '(/ (series "foo") 2)'):
        rtype = typecheck(lisp.parse(expr), i.env)
        assert rtype == pd.Series
