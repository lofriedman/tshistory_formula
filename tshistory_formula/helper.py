import abc
import typing
import inspect
import itertools
import re
from numbers import Number

import pandas as pd
from psyl.lisp import (
    Env,
    evaluate,
    expreval,
    Keyword,
    parse,
    serialize
)

from tshistory_formula.registry import (
    METAS,
    FUNCS
)


NONETYPE = type(None)


def expanded(tsh, cn, tree):
    # base case: check the current operation
    op = tree[0]
    metas = METAS.get(op)
    seriesmeta = metas(cn, tsh, tree) if metas else None
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


# signature building

def _name_from_signature_and_args(name, func, a, kw):
    sig = inspect.signature(func)
    out = [name]
    for idx, (pname, param) in enumerate(sig.parameters.items()):
        if pname == '__interpreter__':
            continue
        if param.default is inspect._empty:
            # almost pure positional
            if idx < len(a):
                out.append(f'{pname}={a[idx]}')
                continue
        try:
            # let's check out if fed as positional
            val = a[idx]
            out.append(f'{pname}={val}')
            continue
        except:
            pass
        # we're in keyword land
        if pname in kw:
            val = kw[pname]
        else:
            val = param.default
        out.append(f'{pname}={val}')
    return '-'.join(out)


def _extract_from_expr(expr, env):
    from tshistory_formula.interpreter import NullIntepreter

    fname = str(expr[0])
    func = FUNCS[fname]
    args = [NullIntepreter()]
    kwargs = {}
    kw = None
    for a in expr[1:]:
        if isinstance(a, Keyword):
            kw = a
            continue
        if isinstance(a, list):
            # a subepression ! let's evaluate it ...
            a = expreval(a, env=env)
        if kw:
            kwargs[str(kw)] = a
            kw = None
            continue
        args.append(a)
    return fname, func, args, kwargs


# typing

def assert_typed(func):
    signature = inspect.signature(func)
    badargs = []
    badreturn = False
    for param in signature.parameters.values():
        if param.name == '__interpreter__':
            continue
        if param.annotation is inspect._empty:
            badargs.append(param.name)
    if signature.return_annotation is inspect._empty:
        badreturn = True

    if not (badargs or badreturn):
        return

    msg = []
    if badargs:
        msg.append(f'arguments {", ".join(badargs)} are untyped')
    if badreturn:
        msg.append(f'return type is not provided')

    raise TypeError(
        f'operator `{func.__name__}` has type issues: {", ".join(msg)}'
    )


def isoftype(typespec, val):
    return sametype(typespec, type(val))


def sametype(supertype, atype):
    # base case, because issubclass of Number vs concrete number types
    # does not work :/
    if supertype is Number:
        if isinstance(atype, (type, abc.ABCMeta)):
            return atype in (int, float, Number)
        return any(sametype(supertype, subt)
                   for subt in atype.__args__)

    # supertype is type/abcmeta
    if isinstance(supertype, type):
        if isinstance(atype, (type, abc.ABCMeta)):
            # supertype = atype (standard python types or abc.Meta)
            if issubclass(supertype, atype):
                return True
        elif atype.__origin__ is typing.Union:
            # supertype ∈ atype (type vs typing)
            if any(sametype(supertype, subt)
                   for subt in atype.__args__):
                return True
    else:
        # supertype is typing crap
        if isinstance(atype, type):
            # atype ∈ supertype (type vs typing)
            if supertype.__origin__ is typing.Union:
                if any(sametype(supert, atype)
                       for supert in supertype.__args__):
                    return True
        elif atype.__origin__ is typing.Union:
            # typing vs typing
            # supertype ∩ atype
            for supert, subt in itertools.product(supertype.__args__,
                                                  atype.__args__):
                if sametype(supert, subt):
                    return True
    return False


def findtype(signature, argidx=None, argname=None):
    if argidx is not None:
        # in general we can have [<p1>, <p2>, ... <vararg>, <kw1W, ... ]
        # difficulty is catching the varag situation correctly
        # first, lookup the possible vararg
        varargidx = None
        params = list(signature.parameters.values())
        for idx, param in enumerate(params):
            if param.kind == inspect.Parameter.VAR_POSITIONAL:
                varargidx = idx
                break
        if varargidx is not None:
            if argidx >= varargidx:
                argidx = varargidx  # it is being absorbed
            return params[argidx].annotation
        # let's catch vararg vs kwarg vs plain bogus idx
        param = params[argidx]
        if param.kind in (inspect.Parameter.KEYWORD_ONLY,
                          inspect.Parameter.VAR_KEYWORD):
            raise TypeError(f'could not find arg {argidx} in {signature}')
        return params[argidx].annotation

    assert argname is not None
    return signature.parameters[argname].annotation


CLS_NAME_PTN = re.compile(r"<class '([\w\.]+)'>")

def extract_type_name(cls):
    """Search type name inside Python class"""
    str_cls = str(cls)
    mobj = CLS_NAME_PTN.search(str_cls)
    if mobj:
        str_cls = mobj.group(1).split('.')[-1]
    return str_cls


def normalize_union_types(obj):
    types = list(obj.__args__)
    unionwrapper = '{}'
    if len(types) > 1:
        unionwrapper = 'Union[{}]'
    return unionwrapper.format(
            ", ".join(
                map(extract_type_name, types)
            )
        )


def typename(typespec):
    if isinstance(typespec, type):
        return extract_type_name(typespec.__name__)
    # if a Union over NoneType, remove the later
    typespec = typespec.copy_with(
        tuple(
            tspec
            for tspec in typespec.__args__
            if tspec is not NONETYPE
        )
    )
    if len(typespec.__args__) == 1:
        return typename(typespec.__args__[0])
    strtype = str(typespec)
    if 'Union' in strtype:
        return normalize_union_types(typespec)
    if strtype.startswith('typing.'):
        strtype = strtype[7:]
    return strtype


def function_types(func):
    sig = inspect.signature(func)
    types = {
        'return': typename(sig.return_annotation)
    }
    for par in sig.parameters.values():
        if par.name == '__interpreter__':
            continue
        atype = typename(par.annotation)
        if par.default is not inspect._empty:
            default = par.default
            if isinstance(default, str):
                default = f'"{default}"'
            atype = f'Default[{atype}={default}]'
        types[par.name] = atype
    return types


def narrow_arg(typespec, arg):
    """try to replace typespec by the most specific type info using arg
    itself

    """
    if not isinstance(arg, list):
        return type(arg)
    folded = constant_fold(arg)
    if not isinstance(folded, list):
        return type(folded)
    return typespec


def most_specific_num_type(t1, t2):
    if float in (t1, t2):
        return float
    if int in (t1, t2):
        return int
    return Number


def narrow_types(op, typespec, argstypes):
    """try to suppress an union using more specific args
    we currently hard-code some operators

    """
    strop = str(op)
    if strop in ('*', '+'):
        if argstypes[1] != pd.Series:
            return most_specific_num_type(*argstypes[:2])
        return pd.Series
    if strop == '/':
        if argstypes[0] != pd.Series:
            return most_specific_num_type(*argstypes[:2])
        return pd.Series

    return typespec  # no narrowing was possible


def typecheck(tree, env=FUNCS):
    op = tree[0]
    try:
        func = env[op]
    except KeyError:
        expr = serialize(tree)
        raise TypeError(
            f'expression `{expr}` refers to unknown operator `{op}`'
        )
    signature = inspect.signature(func)
    if signature.return_annotation is inspect._empty:
        raise TypeError(
            f'operator `{op}` does not specify its return type'
        )
    returntype = signature.return_annotation
    # build args list and kwargs dict
    # unfortunately args vs kwargs separation is only
    # clean in python 3.8 -- see PEP 570
    posargs = []
    posargstypes = []
    kwargs = {}
    kwargstypes = {}
    kw = None
    for idx, arg in enumerate(tree[1:]):
        # keywords
        if isinstance(arg, Keyword):
            kw = arg
            continue
        if kw:
            kwargs[kw] = arg
            kwargstypes[kw] = findtype(signature, argname=kw)
            kw = None
            continue
        # positional
        posargs.append(arg)
        posargstypes.append(
            findtype(signature, argidx=idx)
        )

    narrowed_argstypes = []
    for idx, (arg, expecttype) in enumerate(zip(tree[1:], posargstypes)):
        if isinstance(arg, list):
            exprtype = typecheck(arg, env)
            if not sametype(expecttype, exprtype):
                raise TypeError(
                    f'item {idx}: expect {expecttype}, got {exprtype}'
                )
            narrowed_argstypes.append(
                narrow_arg(exprtype, arg)
            )
        else:
            if not isoftype(expecttype, arg):
                raise TypeError(f'{repr(arg)} not of {expecttype}')
            narrowed_argstypes.append(
                narrow_arg(expecttype, arg)
            )

    for name, val in kwargs.items():
        expecttype = kwargstypes[name]
        if isinstance(val, list):
            exprtype = typecheck(val, env)
            if not sametype(expecttype, exprtype):
                raise TypeError(
                    f'item {idx}: expect {expecttype}, got {exprtype}'
                )
        elif not isoftype(expecttype, val):
            raise TypeError(
                f'keyword `{name}` = {repr(val)} not of {expecttype}'
            )

    returntype = narrow_types(
        op, returntype, narrowed_argstypes
    )
    return returntype
