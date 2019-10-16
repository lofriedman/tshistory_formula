import typing
import inspect

from psyl.lisp import (
    Env,
    evaluate,
    parse,
    serialize
)

from tshistory_formula.registry import (
    FINDERS,
    FUNCS
)


def expanded(tsh, cn, tree):
    newtree = []
    op = tree[0]
    finder = FINDERS.get(op)
    seriesmeta = finder(cn, tsh, tree) if finder else None
    if seriesmeta:
        name, meta = seriesmeta.popitem()
        if tsh.type(cn, name) == 'formula':
            formula = tsh.formula(cn, name)
            subtree = parse(formula)
            return expanded(tsh, cn, subtree)

    for item in tree:
        if isinstance(item, list):
            newtree.append(expanded(tsh, cn, item))
        else:
            newtree.append(item)
    return newtree


_CFOLDENV = Env({
    '+': lambda a, b: a + b,
    '*': lambda a, b: a * b,
    '/': lambda a, b: a / b
})


def constant_fold(tree):
    op = tree[0]
    if op in '+*/':
        # immediately foldable
        if (isinstance(tree[1], (int, float)) and
            isinstance(tree[2], (int, float))):
            return evaluate(serialize(tree), _CFOLDENV)

    newtree = [op]
    for arg in tree[1:]:
        if isinstance(arg, list):
            newtree.append(constant_fold(arg))
        else:
            newtree.append(arg)

    if op in '+*/':
        # maybe foldable after arguments rewrite
        if (isinstance(newtree[1], (int, float)) and
            isinstance(newtree[2], (int, float))):
            return evaluate(serialize(newtree), _CFOLDENV)

    return newtree


# typing

def isoftype(val, typespec):
    if isinstance(typespec, type):
        return isinstance(val, typespec)

    if typespec.__origin__ is typing.Union:
        return isinstance(val, typespec.__args__)


def typecheck(tree, env=FUNCS):
    op = tree[0]
    func = env[op]
    optypes = inspect.getfullargspec(func)
    returntype = optypes.annotations['return']
    expectedargtypes = [
        optypes.annotations[elt]
        for elt in optypes.args
    ]
    if optypes.varargs:
        atype = optypes.annotations[optypes.varargs]
        for arg in tree[1+len(expectedargtypes):]:
            expectedargtypes.append(atype)

    # unfortunately args vs kwargs separation is only
    # clean in python 3.8 -- see PEP 570
    assert len(expectedargtypes) >= len(tree[1:])
    for arg, argtype in zip(tree[1:], expectedargtypes):
        if isinstance(arg, list):
            atype = typecheck(arg, env)
        else:
            atype = type(arg)
            if not isoftype(arg, argtype):
                raise TypeError(f'{repr(arg)} not of {argtype}')

    return returntype
