from math import log10
from contextlib import contextmanager
from pprint import pprint

import pandas as pd
import dash_html_components as html
from psyl.lisp import parse, serialize

from tshistory_formula import interpreter
from tshistory_formula.registry import editor_info, EDITORINFOS


MAX_LENGTH = 15


def roundup(ts):
    avg = ts.mean()
    if avg != 0 and not pd.isnull(avg):
        ts = ts.round(max(2, int(-log10(abs(avg)))))
    return ts


@editor_info('__default__')
def default(builder, expr):
    return


def arith(builder, expr):
    # non-leaf
    operator = expr[0]
    omap = {'+': '+', '*': 'x'}
    if isinstance(expr[1], (int, float)):
        builder.lastinfo['coef'] = f'{omap[operator]} {float(expr[1])}'
        builder.handle_rest(expr)
    else:
        return default(builder, expr)

editor_info('+')(arith)
editor_info('*')(arith)


def allargsareseries(builder, expr):
    # non-leaf
    for subexpr in expr[1:]:
        with builder.series_scope(subexpr):
            builder.buildinfo_expr(subexpr)

editor_info('add')(allargsareseries)
editor_info('priority')(allargsareseries)
editor_info('mul')(allargsareseries)
editor_info('div')(allargsareseries)
editor_info('row-mean')(allargsareseries)
editor_info('mean')(allargsareseries)
editor_info('max')(allargsareseries)
editor_info('std')(allargsareseries)


@editor_info('series')
def series(builder, expr):
    # leaf, because we're lazy
    name = expr[1]
    rest = expr[2:]
    kw = ', '.join(
        f'{k}:{v}'
        for k, v in dict(
                zip(rest[::2], rest[1::2])
        ).items()
    )
    builder.lastinfo['keywords'] = kw or '-'
    builder.lastinfo['name'] = name
    stype = builder.tsh.type(builder.engine, name)
    if stype == 'formula':
        # extra mile: compute the top-level operator
        formula = builder.tsh.formula(builder.engine, name)
        op = parse(formula)[0]
        stype = f'{stype}: {builder.opmap.get(op, op)}'
    builder.lastinfo['type'] = stype


class fancypresenter:
    opmap = {'*': 'x'}
    __slots__ = ('engine', 'tsh', 'name', 'i', 'stack', 'infos')

    def __init__(self, engine, tsh, seriesname, kw):
        assert tsh.exists(engine, seriesname)
        self.engine = engine
        self.tsh = tsh
        self.name = seriesname
        self.i = interpreter.Interpreter(
            engine, tsh, kw
        )
        self.stack = []
        self.infos = []

    # api

    def buildinfo(self):
        formula = self.tsh.formula(self.engine, self.name)
        parsed = parse(formula)
        print(formula)
        pprint(parsed)
        with self.series_scope(parsed):
            op = parsed[0]
            self.lastinfo.update({
                'name': self.name,
                'type': f'formula: {self.opmap.get(op, op)}',
            })
            self.buildinfo_expr(parsed)
        return self.infos

    # /api, now the code walker

    @property
    def lastinfo(self):
        return self.stack[-1] if self.stack else None

    @contextmanager
    def series_scope(self, expr):
        self.stack.append({'coef': 'x 1'})
        yield
        infos = self.stack.pop()
        infos['ts'] = roundup(self.i.evaluate(serialize(expr)))
        infos['ts'].name = infos['name']
        self.infos.append(infos)

    def handle_rest(self, expr):
        for subexpr in expr[1:]:
            self.buildinfo_expr(subexpr)

    def buildinfo_expr(self, expr):
        if not isinstance(expr, list):
            # leaf node, we have nothing to do
            return
        operator = expr[0]
        if operator in EDITORINFOS:
            EDITORINFOS[operator](self, expr)
        else:
            EDITORINFOS['__default__'](self, expr)



def build_url(base_url, name, fromdate, todate, author):
    url = base_url + '?name=%s' % name
    if fromdate:
        url = url + '&startdate=%s' % fromdate
    if todate:
        url = url + '&enddate=%s' % todate
    if author:
        url = url + '&author=%s' % author
    return url


def short_div(content):
    if len(content) > MAX_LENGTH:
        shortcontent = content[:MAX_LENGTH] + '(…)'
        return html.Div(
            shortcontent,
            title=content,
            style={'font-size':'small'}
        )
    else:
        return html.Div(
            content,
            style={'font-size':'small'}
        )


def build_div_header(engine, info, href, more_info=None):
    add = [
        html.Div(
            info.get(key, '-'),
            style={'font-size':'small'}
        )
        for key in ['type', 'keywords', 'coef']
    ]
    name = [
        html.A(
            href=href,
            children=info['name'],
            target="_blank",
            style={'font-size':'small', 'word-wrap': 'break-word'}
        )
    ]
    header = name + add
    if more_info is not None:
        info_metadata = more_info(engine, info['name'])
        if info_metadata:
            metadata = [
                short_div(info.lower().capitalize())
                for _, info in info_metadata.items()
            ]
            header = metadata + header
    return html.Div(header)


def components_table(engine, tsh, id_serie,
                     fromdate=None, todate=None,
                     author=None, additionnal_info=None,
                     base_url=''):
    " function used as callback for tseditor to handle formula "
    kind = tsh.type(engine, id_serie)
    if kind != 'formula':
        return None

    presenter = fancypresenter(
        engine, tsh, id_serie, {
            'from_value_date': fromdate,
            'to_value_date': todate
        }
    )
    infos = presenter.buildinfo()
    head = infos.pop()
    infos.insert(0, head)

    pprint([
        {
            k: v for k,v in info.items()
            if k != 'ts'
        }
        for info in infos
    ])

    # collect base series
    df = infos[0]['ts'].to_frame()
    for info in infos[1:]:
        df = df.join(info['ts'], how='outer')

    header_css = {
        'max-width': f'{MAX_LENGTH + 3}em',
        'min-width': f'{MAX_LENGTH + 3}em',
        'width': f'{MAX_LENGTH + 3}em',
        'position': 'sticky',
        'top': '0',
        'background-color': 'white'
    }
    corner_css = {
        'left': '0',
        'top':'0',
        'background-color': 'white'
    }
    dates_css = {
        'position': 'sticky',
        'left': '0',
        'background-color': 'white'
    }

    corner = html.Th('', style=corner_css)
    header = html.Tr([corner] + [
        html.Th(
            build_div_header(
                engine, info,
                build_url(
                    base_url, info['name'],
                    fromdate, todate, author
                ),
                additionnal_info
            ),
            style=header_css
        )
        for info in infos
    ])

    table = [header]
    for i in range(len(df)):
        new_line = [
            html.Th(
                df.index[i],
                style=dates_css
            )
        ]
        for info in infos:
            name = info['name']
            new_line.append(
                html.Td(
                    df.iloc[i][name]
                )
            )
        table.append(html.Tr(new_line))
    return html.Table(table)
