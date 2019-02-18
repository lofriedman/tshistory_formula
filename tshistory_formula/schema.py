from sqlalchemy import MetaData, Table, Column, Integer, Text
from sqlalchemy.schema import CreateSchema

from tshistory.schema import init as tshinit, reset as tshreset


SCHEMAS = {}

def namespace(basens):
    return f'{basens}-formula'


class formula_schema:

    def __new__(cls, basens='tsh'):
        ns = namespace(basens)
        if ns in SCHEMAS:
            return SCHEMAS[ns]
        return super().__new__(cls)

    def __init__(self, basens='tsh'):
        self.namespace = namespace(basens)

    def define(self, meta=MetaData()):
        if self.namespace in SCHEMAS:
            return
        self.formula = Table(
            'formula', meta,
            Column('id', Integer, primary_key=True),
            Column('name', Text, index=True, unique=True, nullable=False),
            Column('text', Text, nullable=False),
            schema=self.namespace
        )
        SCHEMAS[self.namespace] = self

    def exists(self, engine):
        return self.formula.exists(engine)

    def create(self, engine):
        if self.exists(engine):
            return
        engine.execute(CreateSchema(self.namespace))
        self.formula.create(engine)


def init(engine, meta, basens='tsh'):
    tshinit(engine, meta, basens)
    fschema = formula_schema(basens)
    fschema.define(meta)
    fschema.create(engine)


def reset(engine, basens='tsh'):
    tshreset(engine, basens)
    with engine.begin() as cn:
        cn.execute(f'drop schema if exists "{namespace(basens)}" cascade')
