import json
import pytest
from psyl import lisp
import pandas as pd

from tshistory.testutil import utcdt

from tshistory_formula.interpreter import (
    Interpreter,
    jsontypes
)
from tshistory_formula.helper import (
    typecheck
)


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
        '*': {'a': 'Union[int, float]',
              'b': 'Union[int, float, Series]',
              'return': 'Union[int, float, Series]'},
        '+': {'a': 'Union[int, float]',
              'b': 'Union[int, float, Series]',
              'return': 'Union[int, float, Series]'},
        '/': {'a': 'Union[int, float, Series]',
              'b': 'Union[int, float]',
              'return': 'Union[int, float, Series]'},
        'add': {'return': 'Series', 'serieslist': 'Series'},
        'div': {'return': 'Series', 's1': 'Series', 's2': 'Series'},
        'max': {'return': 'Series', 'serieslist': 'Series'},
        'min': {'return': 'Series', 'serieslist': 'Series'},
        'mul': {'return': 'Series', 'serieslist': 'Series'},
        'clip': {'max': 'Optional[float, int]',
                 'min': 'Optional[float, int]',
                 'return': 'Series',
                 'series': 'Series'},
        'priority': {'return': 'Series', 'serieslist': 'Series'},
        'row-mean': {'return': 'Series', 'serieslist': 'Series'},
        'series': {'fill': 'Optional[str, int, float]',
                   'name': 'str',
                   'prune': 'Optional[int]',
                   'weight': 'Optional[float, int]',
                   'return': 'Series'},
        'slice': {
            'fromdate': 'Optional[str]',
            'return': 'Series',
            'series': 'Series',
            'todate': 'Optional[str]'
        },
        'std': {'return': 'Series', 'serieslist': 'Series'}
    } == types


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

    assert err.value.args[0] == "'toto' not of typing.Union[int, float]"


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
