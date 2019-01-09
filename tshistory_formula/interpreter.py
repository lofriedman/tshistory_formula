from functools import partial

import pandas as pd
from psyl.lisp import Env, evaluate

from tshistory_formula import funcs


class Interpreter:
    __slots__ = ('env', 'cn', 'tsh', 'getargs',
                 'histories')

    def __init__(self, cn, tsh, getargs, histories=None):
        self.cn = cn
        self.tsh = tsh
        self.getargs = getargs
        self.histories = histories
        self.env = Env({
            '+': funcs.scalar_add,
            '*': funcs.scalar_prod,
            'add': funcs.series_add,
            'priority': funcs.series_priority,
            'outliers': funcs.series_drop_outliers,
            'series': partial(funcs.series_get, self)
        })

    def get(self, name):
        idate = self.env.get('__idate__')
        if not idate:
            return self.tsh.get(self.cn, name, **self.getargs)

        # get the nearest inferior or equal for the given
        # insertion date
        assert self.histories
        hist = self.histories[name]
        for date in reversed(list(hist.keys())):
            if idate >= date:
                return hist[date]

        ts = pd.Series(name=name)
        return ts

    def evaluate(self, text, idate=None):
        self.env['__idate__'] = idate
        return evaluate(text, self.env)
