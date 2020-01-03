import json
import pytest
from psyl import lisp
import pandas as pd

from tshistory.testutil import utcdt

from tshistory_formula.interpreter import (
    Interpreter,
    jsontypes
)
from tshistory_formula.registry import func
from tshistory_formula.helper import (
    typecheck
)


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


def test_types(tsh):
    # prune the types registered from other modules/plugins
    # we want to only show the ones provided by the current package
    opnames = set(
        ('*', '+', '/', 'add', 'div', 'max', 'min', 'mul',
         'clip', 'priority', 'row-mean', 'series', 'slice', 'std')
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
        'clip': {'max': 'Optional[Union[Number]]',
                 'min': 'Optional[Union[Number]]',
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
                   'prune': 'Optional[Union[int]]',
                   'return': 'Series',
                   'weight': 'Optional[Union[Number]]'},
        'slice': {'fromdate': 'Optional[Union[Timestamp]]',
                  'return': 'Series',
                  'series': 'Series',
                  'todate': 'Optional[Union[Timestamp]]'},
        'std': {'return': 'Series', 'serieslist': 'Series'}
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
    typecheck(lisp.parse(expr), i.env)


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
