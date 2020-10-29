import json
import inspect
from functools import partial

import pandas as pd
from psyl.lisp import (
    Env,
    parse
)

from tshistory_formula.evaluator import (
    pevaluate,
    pexpreval,
    quasiexpreval
)

from tshistory_formula import (
    helper,
    registry
)


def functypes():
    return {
        name: helper.function_types(func)
        for name, func in registry.FUNCS.items()
    }


def jsontypes():
    return json.dumps(functypes())


class Interpreter:
    __slots__ = ('env', 'cn', 'tsh', 'getargs', 'histories', 'vcache', 'auto')
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
        self.histories = {}
        self.vcache = {}
        self.auto = set(registry.AUTO.values())

    def get(self, name, getargs):
        # `getarg` likey comes from self.getargs
        # but we allow it being modified hence
        # it comes back as a parameter there
        return self.tsh.get(self.cn, name, **getargs)

    def evaluate(self, text):
        return pevaluate(text, self.env, self.auto)


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
                self.env,
            ),
            self.env
        )


class HistoryInterpreter(Interpreter):
    __slots__ = ('env', 'cn', 'tsh', 'getargs', 'histories', 'namecache', 'vcache')

    def __init__(self, *args, histories):
        super().__init__(*args)
        self.histories = histories
        self.namecache = {}

    def _find_by_nearest_idate(self, name, idate):
        hist = self.histories[name]
        tzaware = idate.tzinfo is not None
        for date in reversed(list(hist.keys())):
            compdate = date
            if not tzaware:
                compdate = date.replace(tzinfo=None)
            if idate >= compdate:
                return hist[date]

        ts = pd.Series(name=name, dtype='float64')
        return ts

    def get(self, name, _getargs):
        # getargs is moot there because histories
        # have been precomputed
        idate = self.env.get('__idate__')
        # get the nearest inferior or equal for the given
        # insertion date
        assert self.histories
        return self._find_by_nearest_idate(name, idate)

    def history_item(self, name, func, args, kw):
        """ helper for autotrophic series that have pre built their
        history and are asked for one element
        (necessary since they bypass the above .get)
        """
        key = (name, args, tuple(kw.items()))
        hname = self.namecache.get(key)
        if hname is None:
            hname = helper._name_from_signature_and_args(name, func, args, kw)
            self.namecache[key] = hname
        idate = self.env.get('__idate__')
        assert idate
        return self._find_by_nearest_idate(hname, idate)

    def evaluate(self, text, idate, name):
        self.env['__idate__'] = idate
        self.env['__name__'] = name
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


class NullIntepreter(Interpreter):

    def __init__(self):
        pass
