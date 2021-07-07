from typing import Union, Optional

import pandas as pd

from tshistory_formula.registry import gfunc


@gfunc('group')
def group(__interpreter__, name: str)-> pd.DataFrame:
    """
    The `group` operator retrieves a group (from local storage,
    formula or bound formula).

    """
    return __interpreter__.tsh.group_get(
        __interpreter__.cn, name,  **__interpreter__.getargs
    )


@gfunc('group_add')
def group_add(*grouplist: Union[pd.DataFrame, pd.Series]) -> pd.DataFrame:
    """
    Linear combination of two or more groups. Takes a variable number
    of groups and series as input. At least one group must be supplied.

    Example: `(group-add (group "wallonie") (group "bruxelles") (group "flandres"))`

    """
    dfs = [
        df for df in grouplist
        if isinstance(df, pd.DataFrame)
    ]
    tss = [
        ts for ts in grouplist
        if isinstance(ts, pd.Series)
    ]

    if not len(dfs):
        raise Exception('group_add: at least one argument must be a group')

    sumdf = sum(dfs)
    sumts = sum(tss)

    return sumdf.add(sumts, axis=0).dropna()
