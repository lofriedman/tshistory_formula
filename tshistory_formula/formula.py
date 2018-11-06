from threading import local

import pandas as pd

from psyl.lisp import Env, evaluate, parse


THDICT = local()


def add(a, b):
    if isinstance(a, (int, float)):
        assert isinstance(b, (int, float, pd.Series))
    if isinstance(b, (int, float)):
        assert isinstance(a, (int, float, pd.Series))

    return a + b


def series(name):
    assert 'cn' in THDICT.__dict__
    assert 'tsh' in THDICT.__dict__
    cn = THDICT.cn
    tsh = THDICT.tsh
    return tsh.get(cn, name)


ENV = Env({
    '+': add,
    'series': series
})


