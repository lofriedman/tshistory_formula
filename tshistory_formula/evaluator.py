import inspect

from concurrent.futures import (
    Future,
    ThreadPoolExecutor
)

from psyl.lisp import (
    buildargs,
    parse,
    quasiexpreval,
    Symbol
)


def funcid(func):
    return hash(inspect.getsource(func))

# parallel evaluator

def pexpreval(tree, env, asyncfuncs=(), pool=None):
    if not isinstance(tree, list):
        # atom, we're done there as quasiexpreval
        # did the heavy lifting
        return tree

    exps = [
        pexpreval(exp, env, asyncfuncs, pool)
        for exp in tree
    ]
    newargs = [
        arg.result() if isinstance(arg, Future) else arg
        for arg in exps[1:]
    ]
    proc = exps[0]
    posargs, kwargs = buildargs(newargs)

    # open partials to find the true operator ...
    if hasattr(proc, 'func'):
        func = proc.func
    else:
        func = proc
    # ... on which we can decide to go async
    if funcid(func) in asyncfuncs and pool:
        return pool.submit(proc, *posargs, **kwargs)

    return proc(*posargs, **kwargs)


def pevaluate(expr, env, asyncfuncs=(), concurrency=16):
    newtree = quasiexpreval(expr, env=env)
    if asyncfuncs:
        with ThreadPoolExecutor(concurrency) as pool:
            val = pexpreval(newtree, env, {funcid(func) for func in asyncfuncs}, pool)
            if isinstance(val, Future):
                val = val.result()
    else:
        val = pexpreval(newtree, env, asyncfuncs)
    return val
