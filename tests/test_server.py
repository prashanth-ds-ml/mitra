"""`mitra dashboard` on localhost (D-042): serves the page, caches it, rebuilds on Refresh or when the store grows."""
import threading
import urllib.error
import urllib.request

import pytest

from app.core import loop as L
from app.core import server as S


@pytest.fixture
def served(tmp_path):
    srv = S.make_server(port=0, roots=[tmp_path])  # port 0: any free port
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    base = f"http://127.0.0.1:{srv.server_address[1]}"
    yield srv, base, tmp_path
    srv.shutdown()
    srv.server_close()


def _get(url):
    with urllib.request.urlopen(url, timeout=10) as r:
        return r.status, r.read().decode("utf-8")


def test_serves_the_page_with_a_refresh_button_and_health(served):
    srv, base, _ = served
    code, page = _get(base + "/")
    assert code == 200 and "Mitra dashboard" in page and "href='/?refresh=1'" in page
    assert _get(base + "/health") == (200, "mitra dashboard")
    with pytest.raises(urllib.error.HTTPError) as err:
        _get(base + "/../secrets")
    assert err.value.code == 404


def test_cached_until_the_store_changes_and_refresh_always_rebuilds(served):
    srv, base, tmp = served
    _get(base + "/")
    _get(base + "/")
    assert srv.pages.builds == 1  # nothing changed: served from cache
    L.Recorder(tmp / "proj" / ".mitra" / "runs" / "chat-1.jsonl").write("turn_start", turn=1, user="hello there")
    code, page = _get(base + "/")
    assert srv.pages.builds == 2 and "hello there" in page
    code, page = _get(base + "/?refresh=1")  # the button: rebuild, then back to /
    assert code == 200 and srv.pages.builds == 3 and "Mitra dashboard" in page


def test_binds_to_localhost_only(served):
    srv, _, _ = served
    assert srv.server_address[0] == "127.0.0.1"


def test_running_is_false_when_nothing_listens():
    assert S.running(port=9) is False
