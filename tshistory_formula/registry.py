
FUNCS = {}
FINDERS = {}
EDITORINFOS = {}


def func(name):

    def decorator(func):
        FUNCS[name] = func
        return func

    return decorator


def finder(name):

    def decorator(func):
        FINDERS[name] = func
        return func

    return decorator


def editor_info(name):

    def decorator(func):
        EDITORINFOS[name] = func
        return func

    return decorator
