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
              'b': 'Union[Series, int, float]',
              'return': 'Series'},
        '+': {'a': 'Union[int, float]',
              'b': 'Union[Series, int, float]',
              'return': 'Series'},
        '/': {'a': 'Union[Series, int, float]',
              'b': 'Union[int, float]',
              'return': 'Union[int, float, Series]'},
        'add': {'return': 'Series', 'serieslist': 'Series'},
        'div': {'return': 'Series', 's1': 'Series', 's2': 'Series'},
        'max': {'return': 'Series', 'serieslist': 'Series'},
        'min': {'return': 'Series', 'serieslist': 'Series'},
        'mul': {'return': 'Series', 'serieslist': 'Series'},
        'clip': {'max': 'Optional[float]',
                 'min': 'Optional[float]',
                 'return': 'Series',
                 'series': 'Series'},
        'priority': {'return': 'Series', 'serieslist': 'Series'},
        'row-mean': {'return': 'Series', 'serieslist': 'Series'},
        'series': {'fill': 'Optional[str]',
                   'name': 'str',
                   'prune': 'Optional[str]',
                   'weight': 'Optional[float]',
                   'return': 'Series'},
        'slice': {
            'fromdate': 'Optional[iso_utc_datetime]',
            'return': 'Series',
            'series': 'Series',
            'todate': 'Optional[iso_utc_datetime]'
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
    ts = pd.Series(
        [1, 2, 3],
        index=pd.date_range(utcdt(2020, 1, 1), freq='D', periods=3)
    )

    tsh.update(engine, ts, 'types-a', 'Babar')
    tsh.update(engine, ts, 'types-b', 'Celeste')

    expr = ('(add (series "types-a") '
            '     (priority (series "types-a") '
            '               (* 2 (series "types-b"))))'
    )

    i = Interpreter(engine, tsh, {})
    typecheck(lisp.parse(expr), i.env)

    expr = ('(add (series "types-a") '
            '     (priority (series "types-a") '
            '               (* "toto" (series "types-b"))))'
    )

    i = Interpreter(engine, tsh, {})
    with pytest.raises(TypeError) as err:
        typecheck(lisp.parse(expr), i.env)

    assert err.value.args[0] == "'toto' not of typing.Union[int, float]"
