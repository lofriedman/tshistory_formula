import abc
import typing
import inspect
import itertools

from psyl.lisp import (
    Env,
    evaluate,
    Keyword,
    parse,
    serialize,
    Symbol
)

from tshistory_formula.registry import (
    FINDERS,
    FUNCS
)


def expanded(tsh, cn, tree):
    # base case: check the current operation
    op = tree[0]
    finder = FINDERS.get(op)
    seriesmeta = finder(cn, tsh, tree) if finder else None
    if seriesmeta:
        # hidden assumption: true series operators
        # operate one series at a time (e.g.  `series`)
        # hence we can be brutal ...
        if len(seriesmeta) == 1:  # if not: unexpandable
            name, meta = seriesmeta.popitem()
            if meta.get('expandable', False):
                if tsh.type(cn, name) == 'formula':
                    formula = tsh.formula(cn, name)
                    subtree = parse(formula)
                    return expanded(tsh, cn, subtree)

    newtree = []
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

def assert_typed(func):
    types = inspect.getfullargspec(func)
    badargs = []
    badvararg = None
    badreturn = False
    for arg in types.args:
        if arg == '__interpreter__':
            continue
        if arg not in types.annotations:
            badargs.append(arg)
    if types.varargs and types.varargs not in types.annotations:
        badvararg = types.varargs
    if 'return' not in types.annotations:
        badreturn = True

    if not (badargs or badvararg or badreturn):
        return

    msg = []
    if badargs:
        msg.append(f'arguments {", ".join(badargs)} are untyped')
    if badvararg:
        msg.append(f'vararg {badvararg} is untyped')
    if badreturn:
        msg.append(f'return type is not provided')

    raise TypeError(
        f'operator `{func.__name__}` has type issues: {", ".join(msg)}'
    )


def isoftype(val, typespec):
    return sametype(type(val), typespec)


def sametype(basetype, atype):
    if isinstance(basetype, type):
        if isinstance(atype, (type, abc.ABCMeta)):
            # basetype = atype (standard python types or abc.Meta)
            if issubclass(basetype, atype):
                return True
        elif atype.__origin__ is typing.Union:
            # basetype ∈ atype (type vs typing)
            if any(issubclass(basetype, sometype)
                   for sometype in atype.__args__):
                return True
    else:
        if isinstance(atype, type):
            # atype ∈ basetype (type vs typing)
            if basetype.__origin__ is typing.Union:
                if atype in basetype.__args__:
                    return True
        elif atype.__origin__ is typing.Union:
            # typing vs typing
            # basetype ∩ atype
            for subtype, supertype in itertools.product(basetype.__args__,
                                                        atype.__args__):
                if issubclass(subtype, supertype):
                    return True
    return False


def findtype(typeinfo, argidx=None, argname=None):
    if argidx is not None:
        if typeinfo.args and argidx < len(typeinfo.args):
            name = typeinfo.args[argidx]
            return typeinfo.annotations[name]
        else:
            return typeinfo.annotations[typeinfo.varargs]

    assert argname is not None
    return typeinfo.annotations[argname]


def typecheck(tree, env=FUNCS):
    op = tree[0]
    func = env[op]
    optypes = inspect.getfullargspec(func)
    if 'return' not in optypes.annotations:
        raise TypeError(
            f'operator `{op}` does not specify its return type'
        )
    returntype = optypes.annotations['return']
    # build args list and kwargs dict
    # unfortunately args vs kwargs separation is only
    # clean in python 3.8 -- see PEP 570
    treeargs = []
    kwargs = {}
    treeargstypes = []
    kwargstypes = {}
    kw = None
    for idx, arg in enumerate(tree[1:]):
        if isinstance(arg, Keyword):
            kw = arg
            continue
        if kw:
            kwargs[kw] = arg
            kwargstypes[kw] = findtype(optypes, argname=kw)
            kw = None
            continue
        treeargs.append(arg)
        treeargstypes.append(
            findtype(optypes, argidx=idx)
        )

    for idx, (arg, expecttype) in enumerate(zip(tree[1:], treeargstypes)):
        if isinstance(arg, list):
            exprtype = typecheck(arg, env)
            if not sametype(expecttype, exprtype):
                raise TypeError(
                    f'item {idx}: expect {expecttype}, got {exprtype}'
                )
        else:
            if not isoftype(arg, expecttype):
                raise TypeError(f'{repr(arg)} not of {expecttype}')

    for name, val in kwargs.items():
        expecttype = kwargstypes[name]
        if isinstance(val, list):
            exprtype = typecheck(val, env)
            if not sametype(expecttype, exprtype):
                raise TypeError(
                    f'item {idx}: expect {expecttype}, got {exprtype}'
                )
        elif not isoftype(val, expecttype):
            raise TypeError(
                f'keyword `{name}` = {repr(val)} not of {expecttype}'
            )

    return returntype


# migration

def rewrite_slice(tree):
    """
    help migrate from `(slice (series ...) #:fromdate "2020-1-1")`
    to `(slice (series ...) #:fromdate (date "2020-1-1"))`
    """
    if tree[0] != 'slice':
        newtree = []
        for item in tree:
            if isinstance(item, list):
                newtree.append(rewrite_slice(item))
            else:
                newtree.append(item)
        return newtree

    newtree = [tree[0]]
    for item in tree[1:]:
        if isinstance(item, list):
            newtree.append(rewrite_slice(item))
        elif isinstance(item, Keyword):
            newtree.append(item)
        elif isinstance(item, str):
            newtree.append([Symbol('date'), item])  # <- patch
        else:
            raise Exception('wat ?')
    return newtree
