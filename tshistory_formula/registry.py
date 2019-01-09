
FUNCS = {}


def func(name):

    def decorator(func):
        FUNCS[name] = func
        return func

    return decorator

