from status import KINDS, MESSAGES, classify_error


class FakeRequestError(Exception):
    """Mimics databricks.sql.exc.RequestError: a message plus a `context` dict."""

    def __init__(self, message, context):
        super().__init__(message)
        self.context = context


# Messages below are the real ones captured from databricks-sql-connector 4.2.6 on 2026-10-22.


def test_rejected_token_is_token_rejected():
    exc = FakeRequestError("Error during request to server: : Invalid access token.. ", {"http-code": "403"})
    assert classify_error(exc) == "token-rejected"


def test_unauthorized_status_is_token_rejected():
    assert classify_error(FakeRequestError("Error during request to server", {"http-code": "401"})) == "token-rejected"


def test_quota_block_is_compute_blocked():
    msg = "Error during request to server: BAD_REQUEST: Cannot create the resource, please try again later.."
    assert classify_error(FakeRequestError(msg, {"http-code": "400"})) == "compute-blocked"


def test_gatekeeper_reason_is_compute_blocked():
    assert classify_error(Exception("denyReason INACTIVE reason DENY_NEW_AND_EXISTING_RESOURCES")) == "compute-blocked"


def test_error_without_context_is_query_failed():
    assert classify_error(TimeoutError("timed out")) == "query-failed"


def test_sql_error_is_query_failed():
    assert classify_error(Exception("[TABLE_OR_VIEW_NOT_FOUND] gold_dbt.fct_orders")) == "query-failed"


def test_every_kind_has_a_message():
    assert set(MESSAGES) == set(KINDS)
