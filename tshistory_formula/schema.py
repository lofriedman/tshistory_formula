from sqlalchemy import MetaData, Table, Column, Integer, Text

from tshistory.schema import init as tshinit, reset as tshreset


SCHEMAS = {}

class formula_schema:
    namespace = 'tsh'

    def __new__(cls, ns='tsh'):
        if ns in SCHEMAS:
            return SCHEMAS[ns]
        return super().__new__(cls)

    def __init__(self, namespace='tsh'):
        self.namespace = namespace

    def define(self, meta=MetaData()):
        if self.namespace in SCHEMAS:
            return
        self.formula = Table(
            'formula', meta,
            Column('id', Integer, primary_key=True),
            Column('name', Text, index=True, nullable=True),
            Column('text', Text, nullable=False),
            schema=self.namespace
        )
        SCHEMAS[self.namespace] = self

    def exists(self, engine):
        return self.formula.exists(engine)

    def create(self, engine):
        if self.exists(engine):
            return
        self.formula.create(engine)


def init(engine, meta, ns='tsh'):
    tshinit(engine, meta, ns)
    fschema = formula_schema(ns)
    fschema.define(meta)
    fschema.create(engine)


def reset(engine, ns='tsh'):
    tshreset(engine, ns)
