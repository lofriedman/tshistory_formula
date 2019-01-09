from functools import partial

from psyl.lisp import Env, evaluate

from tshistory_formula import funcs


class Interpreter:
    __slots__ = ('env', 'cn', 'tsh', 'getargs')

    def __init__(self, cn, tsh, getargs):
        self.cn = cn
        self.tsh = tsh
        self.getargs = getargs
        self.env = Env({
            '+': funcs.scalar_add,
            '*': funcs.scalar_prod,
            'list': funcs.pylist,
            'add': funcs.series_add,
            'priority': funcs.series_priority,
            'outliers': funcs.series_drop_outliers,
            'series': partial(funcs.series_get, self)
        })

    def evaluate(self, text):
        return evaluate(text, self.env)
