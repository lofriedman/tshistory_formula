from psyl.lisp import parse, serialize
from tshistory_formula.helper import rewrite_slice


def test_rewrite_slice():
    form = '(* 3 (slice (series "42") #:fromdate "2020-1-1" #:todate (today)))'
    newform = serialize(rewrite_slice(parse(form)))
    assert newform == (
        '(* 3 (slice (series "42") #:fromdate (date "2020-1-1") #:todate (today)))'
    )
