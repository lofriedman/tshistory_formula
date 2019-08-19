

def find_series(cn, tsh, stree):
    smap = {}
    if stree[0] == 'series':
        name = stree[1]
        smap[name] = tsh.metadata(cn, name)
        return smap

    for arg in stree[1:]:
        if isinstance(arg, list):
            smap.update(find_series(cn, tsh, arg))

    return smap
