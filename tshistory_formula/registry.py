
FUNCS = {}
FINDERS = {}


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
