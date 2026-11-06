"""Secret scrubbing: known token formats, NAME=value pairs, and code left alone.

Fake secrets are built by joining pieces so the repo's secret scanner (gitleaks)
does not flag this file.
"""

from app.core.scrub import MASK, scrub, scrub_obj

OPENAI = "sk-" + "proj-" + "abcDEF1234567890ghijKLMN"
ANTHROPIC = "sk-" + "ant-" + "api03-AbCdEfGh1234567890_xyz"
GH_PAT = "gh" + "p_" + "A1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6Q7r8"
GH_OAUTH = "gh" + "o_" + "A1b2C3d4E5f6G7h8I9j0K1l2"
GH_SERVER = "gh" + "s_" + "A1b2C3d4E5f6G7h8I9j0K1l2"
GH_FINE = "github" + "_pat_" + "11ABCDEFG0123456789_abcdefghijklmnop"
AWS = "AKIA" + "IOSFODNN7EXAMPLE"
PEM = (
    "-----BEGIN " + "RSA PRIVATE KEY-----\n"
    "MIIEowIBAAKCAQEAx1y2z3\nabcdEFGH/+==\n"
    "-----END " + "RSA PRIVATE KEY-----"
)


def test_token_formats_are_masked():
    for secret in (OPENAI, ANTHROPIC, GH_PAT, GH_OAUTH, GH_SERVER, GH_FINE, AWS):
        out = scrub(f"value is {secret} here")
        assert secret not in out, secret
        assert out == f"value is {MASK} here"


def test_anthropic_key_masked_whole():
    # sk-ant- must not leave a tail behind from the shorter sk- pattern.
    assert scrub(ANTHROPIC) == MASK


def test_pem_block_masked_as_one_piece():
    text = f"before\n{PEM}\nafter"
    out = scrub(text)
    assert out == f"before\n{MASK}\nafter"


def test_bearer_token_keeps_word():
    out = scrub("Authorization: Bearer abc.DEF-123_xyz==")
    assert out == f"Authorization: Bearer {MASK}"


def test_env_style_pairs():
    text = "API_KEY=abc123\nGITHUB_TOKEN=xyz\nDB_PASSWORD=hunter2\nCLIENT_SECRET=s3cr3t\nDEBUG=1"
    out = scrub(text)
    assert out == (
        f"API_KEY={MASK}\nGITHUB_TOKEN={MASK}\nDB_PASSWORD={MASK}\nCLIENT_SECRET={MASK}\nDEBUG=1"
    )


def test_name_match_is_case_insensitive_and_quoted_values_keep_quotes():
    assert scrub('api_key = "abc123"') == f'api_key = "{MASK}"'
    assert scrub("password='hunter2'") == f"password='{MASK}'"
    assert scrub("export Secret_Value=abc-def") == f"export Secret_Value={MASK}"


def test_json_pairs():
    text = '{"apiKey": "abc123", "name": "mitra", "refresh_token": "zz"}'
    out = scrub(text)
    assert out == f'{{"apiKey": "{MASK}", "name": "mitra", "refresh_token": "{MASK}"}}'


def test_yaml_long_token_value_masked():
    out = scrub("api_key: abcd1234efgh5678ijkl")
    assert out == f"api_key: {MASK}"


def test_normal_code_left_alone():
    code = (
        "def get_key(): return self.key\n"
        "token = get_token()\n"
        "api_key = self.config.api_key\n"
        "def f(token: str, key: Optional[str] = None):\n"
        "    password = default_password\n"
        "    secret_ok = True\n"
        "    max_tokens = 4096\n"
        "    keys = [k for k in data]\n"
        "    if key in mapping: pass\n"
        "    sk = 'short'\n"
    )
    assert scrub(code) == code


def test_plain_prose_left_alone():
    text = "The key point is that tokens are cheap. Ask for the password reset page."
    assert scrub(text) == text


def test_empty_and_none_like():
    assert scrub("") == ""


def test_scrub_obj_walks_structures_and_blanks_secret_keys():
    data = {
        "api_key": "plain-looking",
        "Authorization": f"Bearer {GH_PAT}",
        "nested": {"password": "x", "note": f"use {AWS}"},
        "items": [OPENAI, "fine", ("t", f"KEY={OPENAI}")],
        "prompt_tokens": 123,
        "empty_secret": "",
        "count": 5,
    }
    out = scrub_obj(data)
    assert out["api_key"] == MASK
    assert out["Authorization"] == f"Bearer {MASK}"
    assert out["nested"] == {"password": MASK, "note": f"use {MASK}"}
    assert out["items"] == [MASK, "fine", ("t", f"KEY={MASK}")]
    # Numbers under token-ish keys are counts, not secrets.
    assert out["prompt_tokens"] == 123
    assert out["empty_secret"] == ""
    assert out["count"] == 5
    # The input is not changed.
    assert data["api_key"] == "plain-looking"


def test_scrub_obj_secret_key_with_dict_value_is_walked():
    out = scrub_obj({"keys": {"name": "a", "token": "b"}})
    assert out == {"keys": {"name": "a", "token": MASK}}


def test_scrub_obj_passes_other_types_through():
    assert scrub_obj(None) is None
    assert scrub_obj(3.5) == 3.5
    assert scrub_obj(True) is True
