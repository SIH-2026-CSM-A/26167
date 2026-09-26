from app.auth.password import hash_password, verify_password


def test_hash_is_not_the_plaintext():
    hashed = hash_password("correct horse battery staple")
    assert hashed != "correct horse battery staple"


def test_verify_true_for_correct_password():
    hashed = hash_password("correct horse battery staple")
    assert verify_password("correct horse battery staple", hashed) is True


def test_verify_false_for_wrong_password():
    hashed = hash_password("correct horse battery staple")
    assert verify_password("wrong password", hashed) is False


def test_hash_made_with_old_default_parameters_still_verifies():
    from argon2 import PasswordHasher

    # Parameters are encoded in each hash, so existing users' hashes keep working.
    legacy_hash = PasswordHasher().hash("correct-horse-battery")
    assert "m=65536" in legacy_hash
    assert verify_password("correct-horse-battery", legacy_hash) is True
    assert verify_password("wrong-password", legacy_hash) is False


def test_new_hashes_use_owasp_minimum_parameters():
    assert "m=19456,t=2,p=1" in hash_password("correct-horse-battery")
