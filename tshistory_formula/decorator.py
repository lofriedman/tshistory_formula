# #########################     LICENSE     ############################ #

# Copyright (c) 2005-2020, Michele Simionato
# All rights reserved.

# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are
# met:

#   Redistributions of source code must retain the above copyright
#   notice, this list of conditions and the following disclaimer.
#   Redistributions in bytecode form must reproduce the above copyright
#   notice, this list of conditions and the following disclaimer in
#   the documentation and/or other materials provided with the
#   distribution.

# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
# A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
# HOLDERS OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT,
# INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING,
# BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS
# OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
# ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR
# TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE
# USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH
# DAMAGE.

"""
Decorator module, see
https://github.com/micheles/decorator/blob/master/docs/documentation.md
for the documentation.
"""

import re
import sys
import inspect
import itertools

from inspect import getfullargspec

def get_init(cls):
    return cls.__init__


DEF = re.compile(r'\s*def\s*([_\w][_\w\d]*)\s*\(')


# basic functionality
class FunctionMaker:
    """
    An object with the ability to create functions with a given signature.
    It has attributes name, doc, module, signature, defaults, dict and
    methods update and make.
    """

    # Atomic get-and-increment provided by the GIL
    _compile_count = itertools.count()

    # make pylint happy
    args = varargs = varkw = defaults = kwonlyargs = kwonlydefaults = ()

    def __init__(self, func):
        # func can be a class or a callable, but not an instance method
        self.name = func.__name__
        if self.name == '<lambda>':  # small hack for lambda functions
            self.name = '_lambda_'
        self.doc = func.__doc__
        self.module = func.__module__
        argspec = getfullargspec(func)
        self.annotations = getattr(func, '__annotations__', {})
        for a in ('args', 'varargs', 'varkw', 'defaults', 'kwonlyargs',
                  'kwonlydefaults'):
            setattr(self, a, getattr(argspec, a))
        for i, arg in enumerate(self.args):
            setattr(self, 'arg%d' % i, arg)
        allargs = list(self.args)
        allshortargs = list(self.args)
        if self.varargs:
            allargs.append('*' + self.varargs)
            allshortargs.append('*' + self.varargs)
        elif self.kwonlyargs:
            allargs.append('*')  # single star syntax
        for a in self.kwonlyargs:
            allargs.append('%s=None' % a)
            allshortargs.append('%s=%s' % (a, a))
        if self.varkw:
            allargs.append('**' + self.varkw)
            allshortargs.append('**' + self.varkw)
        self.signature = ', '.join(allargs)
        self.shortsignature = ', '.join(allshortargs)
        self.dict = func.__dict__.copy()

    def update(self, func, **kw):
        "Update the signature of func with the data in self"
        func.__name__ = self.name
        func.__doc__ = getattr(self, 'doc', None)
        func.__dict__ = getattr(self, 'dict', {})
        func.__defaults__ = self.defaults
        func.__kwdefaults__ = self.kwonlydefaults or None
        func.__annotations__ = getattr(self, 'annotations', None)
        frame = sys._getframe(3)
        callermodule = frame.f_globals.get('__name__', '?')
        func.__module__ = getattr(self, 'module', callermodule)
        func.__dict__.update(kw)

    def make(self, src_templ, evaldict, **attrs):
        "Make a new function from a given template and update the signature"
        src = src_templ % vars(self)  # expand name and signature
        evaldict = evaldict or {}
        mo = DEF.search(src)
        if mo is None:
            raise SyntaxError('not a valid function template\n%s' % src)
        name = mo.group(1)  # extract the function name
        names = set([name] + [arg.strip(' *') for arg in
                              self.shortsignature.split(',')])
        for n in names:
            if n in ('_func_', '_call_'):
                raise NameError('%s is overridden in\n%s' % (n, src))

        # Ensure each generated function has a unique filename for profilers
        # (such as cProfile) that depend on the tuple of (<filename>,
        # <definition line>, <function name>) being unique.
        filename = '<decorator-gen-%d>' % next(self._compile_count)
        try:
            code = compile(src, filename, 'single')
            exec(code, evaldict)
        except Exception:
            print('Error in generated code:', file=sys.stderr)
            print(src, file=sys.stderr)
            raise
        func = evaldict[name]
        self.update(func, **attrs)
        return func

    @classmethod
    def create(cls, func, body, evaldict, **attrs):
        self = cls(func)
        ibody = '\n'.join('    ' + line for line in body.splitlines())
        body = 'def %(name)s(%(signature)s):\n' + ibody
        return self.make(body, evaldict, **attrs)


def decorate(func, caller):
    """
    decorate(func, caller) decorates a function using a caller.
    """
    evaldict = dict(_call_=caller, _func_=func)
    fun = FunctionMaker.create(
        func, "return _call_(_func_, %(shortsignature)s)",
        evaldict, __wrapped__=func
    )
    if hasattr(func, '__qualname__'):
        fun.__qualname__ = func.__qualname__
    return fun
