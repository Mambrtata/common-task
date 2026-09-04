import pytest

from zoho_mail_mcp.search import SearchKeyError, build_search_key, zoho_date


def test_single_condition():
    assert build_search_key(text="faktúra") == "entire:faktúra"


def test_conditions_are_joined_with_and():
    key = build_search_key(subject="faktúra", sender="jan@onoff.sk", has="attachment")
    assert key == "subject:faktúra::sender:jan@onoff.sk::has:attachment"


def test_or_joins_text_conditions():
    key = build_search_key(sender="jan@onoff.sk", to="jan@onoff.sk", match="or")
    assert key == "sender:jan@onoff.sk:or:to:jan@onoff.sk"


def test_dates_are_always_appended_with_and():
    key = build_search_key(subject="a", sender="b@c.sk", match="or", from_date="2026-01-01")
    assert key == "subject:a:or:sender:b@c.sk::fromDate:01-Jan-2026"


def test_date_only_search_is_valid():
    assert build_search_key(from_date="2026-01-31", to_date="2026-02-01") == (
        "fromDate:31-Jan-2026::toDate:01-Feb-2026"
    )


@pytest.mark.parametrize(
    "iso,expected",
    [
        ("2026-01-05", "05-Jan-2026"),
        ("2026-09-04", "04-Sep-2026"),
        ("2026-12-31", "31-Dec-2026"),
    ],
)
def test_date_format_matches_zoho(iso, expected):
    assert zoho_date(iso) == expected


def test_bad_date_is_rejected_with_a_hint():
    with pytest.raises(SearchKeyError, match="RRRR-MM-DD"):
        build_search_key(from_date="4.9.2026")


def test_separator_in_a_value_is_rejected():
    with pytest.raises(SearchKeyError, match="oddeľovače"):
        build_search_key(subject="a::b")
    with pytest.raises(SearchKeyError, match="oddeľovače"):
        build_search_key(subject="a:or:b")


def test_empty_value_is_rejected():
    with pytest.raises(SearchKeyError, match="prázdny"):
        build_search_key(subject="   ")


def test_no_conditions_is_rejected():
    with pytest.raises(SearchKeyError, match="aspoň jednu podmienku"):
        build_search_key()


def test_flags_are_rendered_as_true_false():
    key = build_search_key(text="x", include_spam_trash=True)
    assert key == "entire:x::inclspamtrash:true"


def test_unknown_match_mode_is_rejected():
    with pytest.raises(SearchKeyError, match="'and' alebo 'or'"):
        build_search_key(text="x", match="nor")
