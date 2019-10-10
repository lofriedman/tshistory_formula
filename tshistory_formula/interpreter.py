import json
import re
import typing
import inspect
from typing import Optional
from functools import partial

import pandas as pd
from psyl.lisp import Env, evaluate, parse

from tshistory_formula import registry


CLS_NAME_PTN = re.compile("<class '([\w\.]+)'>")


def extract_type_name(cls):
    """Search type name inside Python class"""
    str_cls = str(cls)
    mobj = CLS_NAME_PTN.search(str_cls)
    if mobj:
        str_cls = mobj.group(1).split('.')[-1]
    return str_cls


class fjson(json.JSONEncoder):

    def default(self, o):
        try:
            return super().default(o)
        except TypeError:
            stro = extract_type_name(o)
            if 'Union' in stro:
                types = list(o.__args__)
                prefix = 'Union'
                if types[-1] is type(None):
                    prefix = 'Optional'
                    del types[-1]
                stro = prefix + '[%s]' % ', '.join(
                    map(extract_type_name, types)
                )
            return stro


def functypes():
    return {
        name: typing.get_type_hints(func)
        for name, func in registry.FUNCS.items()
    }


def jsontypes():
    return json.dumps(functypes(), cls=fjson)


class Interpreter:
    __slots__ = ('env', 'cn', 'tsh', 'getargs')

    def __init__(self, cn, tsh, getargs):
        self.cn = cn
        self.tsh = tsh
        self.getargs = getargs
        # bind funcs to the interpreter
        funcs = {}
        for name, func in registry.FUNCS.items():
            if '__interpreter__' in inspect.getfullargspec(func).args:
                func = partial(func, self)
            funcs[name] = func
        self.env = Env(funcs)

    def get(self, name, getargs):
        # `getarg` likey comes from self.getargs
        # but we allow it being modified hence
        # it comes back as a parameter there
        return self.tsh.get(self.cn, name, **getargs)

    def evaluate(self, text):
        return evaluate(text, self.env)


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
        ts = evaluate(text, self.env)
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

    op = operators[0]
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
