from threading import Thread

from psyl.lisp import (
    buildargs,
    parse,
    Symbol
)

# parallel evaluator

class future:
    __slots__ = ('_t', '_value')

    def __init__(self, func, args=(), kw={}):
        def dofunc():
            try:
                self._value = func(*args, **kw)
            except Exception as e:
                self._value = e
        self._t = Thread(target=dofunc)
        self._t.start()

    @property
    def value(self):
        self._t.join()
        if isinstance(self._value, Exception):
            raise self._value
        return self._value


def pexpreval(tree, env):
    if not isinstance(tree, list):
        # atom, we're done there as quasiexpreval
        # did the heavy lifting
        return tree

    # // thing: if we have at least two computable sub-expressions
    #    let's shine
    if [type(item) for item in tree[1:]].count(list) > 1:
        # // compute
        newtree = []
        for arg in tree:
            if isinstance(arg, list):
                newtree.append(future(pexpreval, (arg, env)))
            else:
                newtree.append(pexpreval(arg, env))
        # collect results
        newtree = [
            arg.value if isinstance(arg, future) else arg
            for arg in newtree
        ]
        proc = tree[0]
        posargs, kwargs = buildargs(newtree[1:])
    else:
        exps = [pexpreval(exp, env) for exp in tree]
        proc = exps[0]
        posargs, kwargs = buildargs(exps[1:])
    return proc(*posargs, **kwargs)


def quasiexpreval(tree, env):
    if isinstance(tree, map):
        tree = list(tree)
    if isinstance(tree, Symbol):
        return env.find(tree)

    if not isinstance(tree, list):
        return tree
    exps = [quasiexpreval(exp, env) for exp in tree]
    proc = exps[0]
    posargs, kwargs = buildargs(exps[1:])
    newtree = [proc, *posargs]
    for name, arg in kwargs.items():
        newtree.append(name)
        newtree.append(arg)
    return newtree


def pevaluate(expr, env):
    newtree = quasiexpreval(parse(expr), env=env)
    return pexpreval(newtree, env=env)
