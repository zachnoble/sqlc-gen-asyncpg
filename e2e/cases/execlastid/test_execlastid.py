from cases.execlastid.gen import query


def test_only_constant_generated() -> None:
    assert query._X.startswith("-- name: X :execlastid\n")
    assert not hasattr(query, "x")
