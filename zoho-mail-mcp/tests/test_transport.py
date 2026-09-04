from zoho_mail_mcp.transport import HttpResponse, request_with_retries


class Responder:
    def __init__(self, statuses, headers=None):
        self.statuses = list(statuses)
        self.headers = headers or {}
        self.count = 0

    def __call__(self, method, url, headers=None, body=None, timeout=30):
        self.count += 1
        status = self.statuses.pop(0) if self.statuses else 200
        return HttpResponse(status=status, headers=self.headers, body="{}")


def test_success_is_not_retried():
    responder = Responder([200])
    delays = []
    request_with_retries(responder, "GET", "https://x/y", sleep=delays.append)
    assert responder.count == 1
    assert delays == []


def test_client_errors_are_not_retried():
    responder = Responder([400])
    delays = []
    request_with_retries(responder, "GET", "https://x/y", sleep=delays.append)
    assert responder.count == 1
    assert delays == []


def test_server_errors_are_retried_with_backoff():
    responder = Responder([503, 503, 200])
    delays = []
    response = request_with_retries(responder, "GET", "https://x/y", sleep=delays.append)
    assert response.status == 200
    assert delays == [1.0, 2.0]


def test_retries_are_capped():
    responder = Responder([503, 503, 503, 503, 503])
    delays = []
    response = request_with_retries(
        responder, "GET", "https://x/y", max_retries=2, sleep=delays.append
    )
    assert response.status == 503
    assert responder.count == 3  # prvý pokus + dva opakované


def test_retry_after_header_wins_when_longer():
    responder = Responder([429, 200], headers={"Retry-After": "9"})
    delays = []
    request_with_retries(responder, "GET", "https://x/y", sleep=delays.append)
    assert delays == [9.0]


def test_retry_after_as_http_date_falls_back_to_backoff():
    responder = Responder([429, 200], headers={"Retry-After": "Wed, 21 Oct 2026 07:28:00 GMT"})
    delays = []
    request_with_retries(responder, "GET", "https://x/y", sleep=delays.append)
    assert delays == [1.0]


def test_header_lookup_is_case_insensitive():
    response = HttpResponse(status=200, headers={"retry-after": "3"})
    assert response.header("Retry-After") == "3"
    assert response.header("missing") is None
