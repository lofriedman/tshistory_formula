from psyl.lisp import parse, serialize

from tshistory_formula.registry import FINDERS


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
