from sqlalchemy import select
from psyl.lisp import evaluate
from tshistory.tsio import TimeSerie as BaseTS

from tshistory_formula.schema import formula_schema
from tshistory_formula import formula


class TimeSerie(BaseTS):
    formula_map = None

    def __init__(self, namespace='tsh'):
        super().__init__(namespace)
        self.formula_schema = formula_schema(namespace)
        self.formula_schema.define()
        self.formula_map = {}

    def register_formula(self, cn, name, formula):
        cn.execute(
            self.formula_schema.formula.insert().values(
                name=name,
                text=formula
            )
        )

    def isformula(self, cn, name):
        if name in self.formula_map:
            return True
        table = self.formula_schema.formula
        formula = cn.execute(
            select([table.c.text]).where(
                table.c.name==name
            )
        ).scalar()
        if formula:
            self.formula_map[name] = formula
        return bool(formula)

    def exists(self, cn, name):
        return super().exists(cn, name) or self.isformula(cn, name)

    def get(self, cn, name, **kw):
        if self.isformula(cn, name):
            text = self.formula_map[name]
            formula.THDICT.cn = cn
            formula.THDICT.tsh = self
            return evaluate(text, formula.ENV)

        return super().get(cn, name, **kw)
