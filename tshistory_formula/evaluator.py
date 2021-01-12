import inspect

from concurrent.futures import (
    Future
)

from psyl.lisp import (
    buildargs,
    parse,
    quasiexpreval,
    Symbol
)

from tshistory_formula.helper import ThreadPoolExecutor



def funcid(func):
    return hash(inspect.getsource(func))


# parallel evaluator

def pexpreval(tree, env, asyncfuncs=(), pool=None, hist=False):
    if not isinstance(tree, list):
        return quasiexpreval(tree, env)

    exps = [
        pexpreval(exp, env, asyncfuncs, pool, hist)
        for exp in tree
    ]
    newargs = [
        arg.result() if isinstance(arg, Future) else arg
        for arg in exps[1:]
    ]
    proc = exps[0]
    posargs, kwargs = buildargs(newargs)

    # open partials to find the true operator on which we can decide
    # to go async
    if hasattr(proc, 'func'):
        func = proc.func
    else:
        func = proc

    # for autotrophic operators: prepare to pass the tree if present
    funkey = funcid(func)
    if hist and funkey in asyncfuncs:
        kwargs['__tree__'] = tree

    if funkey in asyncfuncs and pool:
        return pool.submit(proc, *posargs, **kwargs)

    return proc(*posargs, **kwargs)


def pevaluate(expr, env, asyncfuncs=(), concurrency=16, hist=False):
    if asyncfuncs:
        with ThreadPoolExecutor(concurrency) as pool:
            val = pexpreval(
                expr, env,
                {funcid(func) for func in asyncfuncs},
                pool,
                hist
            )
            if isinstance(val, Future):
                val = val.result()
        return val

    return pexpreval(expr, env, asyncfuncs, hist)
