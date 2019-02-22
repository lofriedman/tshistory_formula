from sqlalchemy import MetaData, Table, Column, Integer, Text
from sqlalchemy.schema import CreateSchema

from tshistory.schema import register_schema, _delete_schema


def namespace(basens):
    return f'{basens}-formula'


class formula_schema:
    SCHEMAS = {}

    def __new__(cls, basens='tsh'):
        ns = namespace(basens)
        if ns in cls.SCHEMAS:
            return cls.SCHEMAS[ns]
        return super().__new__(cls)

    def __init__(self, basens='tsh'):
        self.namespace = namespace(basens)
        register_schema(self)

    def define(self, meta=MetaData()):
        if self.namespace in self.SCHEMAS:
            return
        self.formula = Table(
            'formula', meta,
            Column('id', Integer, primary_key=True),
            Column('name', Text, index=True, unique=True, nullable=False),
            Column('text', Text, nullable=False),
            schema=self.namespace
        )
        self.SCHEMAS[self.namespace] = self

    def exists(self, engine):
        return engine.execute(
            'select exists('
            '  select schema_name '
            '  from information_schema.schemata '
            '  where schema_name = %(name)s'
            ')',
            name=self.namespace
        ).scalar()

    def create(self, engine):
        if self.exists(engine):
            return
        engine.execute(CreateSchema(self.namespace))
        self.formula.create(engine)

    def destroy(self, engine):
        _delete_schema(engine, self.namespace)
        self.SCHEMAS.pop(self.namespace, None)
