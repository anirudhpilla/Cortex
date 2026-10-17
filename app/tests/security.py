from app.security import digest_token, new_opaque_token

def test_opaque_tokens_are_unique():
    assert new_opaque_token() != new_opaque_token()

def test_token_digest_is_deterministic():
    token = new_opaque_token()

    assert digest_token(token) == digest_token(token)
    assert digest_token(token) != token
