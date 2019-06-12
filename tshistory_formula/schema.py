from pathlib import Path

from sqlhelp import sqlfile
from tshistory_alias.schema import alias_schema


SCHEMA = Path(__file__).parent / 'schema.sql'


class formula_schema(alias_schema):

    def create(self, engine):
        super().create(engine)
        with engine.begin() as cn:
            cn.execute(sqlfile(SCHEMA, ns=self.namespace))
