from serverwatch.auth import hash_password, verify_password


def test_password_hash_round_trip():
    encoded = hash_password("a-long-test-password", iterations=1_000, salt=b"fixed-test-salt")
    assert verify_password("a-long-test-password", encoded)
    assert not verify_password("wrong-password-value", encoded)


def test_short_password_rejected():
    try:
        hash_password("short")
    except ValueError:
        pass
    else:
        raise AssertionError("short password was accepted")

