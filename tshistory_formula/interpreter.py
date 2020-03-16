import json
import re
import typing
import inspect
from functools import partial

import pandas as pd
from psyl.lisp import (
    Env,
    parse,
    pevaluate,
    pexpreval,
    quasiexpreval
)

from tshistory_formula import (
    helper,
    registry
)


class fjson(json.JSONEncoder):

    def default(self, o):
        try:
            return super().default(o)
        except TypeError:
            typename = extract_type_name(o)
            if 'Union' in typename:
                typename = normalize_union_types(o)
            return typename


def functypes():
    return {
        name: helper.function_types(func)
        for name, func in registry.FUNCS.items()
    }


def jsontypes():
    return json.dumps(functypes())


class Interpreter:
    __slots__ = ('env', 'cn', 'tsh', 'getargs')
    FUNCS = None

    @property
    def operators(self):
        if Interpreter.FUNCS is None:
            Interpreter.FUNCS = registry.FUNCS
        return Interpreter.FUNCS

    def __init__(self, cn, tsh, getargs):
        self.cn = cn
        self.tsh = tsh
        self.getargs = getargs
        # bind funcs to the interpreter
        funcs = {}
        for name, func in self.operators.items():
            if '__interpreter__' in inspect.getfullargspec(func).args:
                func = partial(func, self)
            funcs[name] = func
        funcs['#t'] = True
        funcs['#f'] = False
        self.env = Env(funcs)

    def get(self, name, getargs):
        # `getarg` likey comes from self.getargs
        # but we allow it being modified hence
        # it comes back as a parameter there
        return self.tsh.get(self.cn, name, **getargs)

    def evaluate(self, text):
        return pevaluate(text, self.env)


class OperatorHistory(Interpreter):
    __slots__ = ('env', 'cn', 'tsh', 'getargs')
    FUNCS = None

    @property
    def operators(self):
        if OperatorHistory.FUNCS is None:
            OperatorHistory.FUNCS = {**registry.FUNCS, **registry.HISTORY}
        return OperatorHistory.FUNCS

    def evaluate_history(self, tree):
        return pexpreval(
            quasiexpreval(
                tree,
                env=self.env
            ),
            env=self.env
        )


class HistoryInterpreter(Interpreter):
    __slots__ = ('env', 'cn', 'tsh', 'getargs', 'histories')

    def __init__(self, *args, histories):
        super().__init__(*args)
        self.histories = histories

    def get(self, name, _getargs):
        # getargs is moot there because histories
        # have been precomputed
        idate = self.env.get('__idate__')
        # get the nearest inferior or equal for the given
        # insertion date
        assert self.histories
        hist = self.histories[name]
        tzaware = idate.tzinfo is not None
        for date in reversed(list(hist.keys())):
            compdate = date
            if not tzaware:
                compdate = date.replace(tzinfo=None)
            if idate >= compdate:
                return hist[date]

        ts = pd.Series(name=name)
        return ts

    def evaluate(self, text, idate, name):
        self.env['__idate__'] = idate
        ts = pevaluate(text, self.env)
        ts.name = name
        return ts


# staircase fast path


def has_compatible_operators(cn, tsh, tree, good_operators):
    operators = [tree[0]]
    for param in tree[1:]:
        if isinstance(param, list):
            operators.append(param[0])
    if any(op not in good_operators
           for op in operators):
        return False

    names = tsh.find_series(cn, tree)
    for name in names:
        formula = tsh.formula(cn, name)
        if formula:
            tree = parse(formula)
            if not has_compatible_operators(
                    cn, tsh, tree, good_operators):
                return False

    return True


class FastStaircaseInterpreter(Interpreter):
    __slots__ = ('env', 'cn', 'tsh', 'getargs', 'delta')

    def __init__(self, cn, tsh, getargs, delta):
        assert delta is not None
        super().__init__(cn, tsh, getargs)
        self.delta = delta

    def get(self, name, getargs):
        if self.tsh.type(self.cn, name) == 'primary':
            return self.tsh.staircase(
                self.cn, name, delta=self.delta, **getargs
            )
        return self.tsh.get(
            self.cn, name, **getargs,
            __interpreter__=self
        )
