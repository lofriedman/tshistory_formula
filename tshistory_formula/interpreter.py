import json
import typing
import inspect
from typing import Optional
from functools import partial

import pandas as pd
from psyl.lisp import Env, evaluate

from tshistory_formula import funcs, registry


class fjson(json.JSONEncoder):

    def default(self, o):
        try:
            return super().default(o)
        except TypeError:
            if o is str:
                return 'str'
            stro = str(o)
            if stro.startswith('typing'):
                stro = stro.replace(
                    'pandas.core.series.Series',
                    'Series'
                )
                return stro
            if 'Series' in stro:
                return 'Series'
            raise


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
