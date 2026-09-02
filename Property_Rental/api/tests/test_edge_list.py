"""Adversarial tests on the search, the filters and the paging."""

import pytest

from tests.conftest import make_request


@pytest.fixture
def jobs(db, unit, manager):
    for text in (
        "Boiler making a noise",
        "boiler serviced last winter",
        "Tap dripping 50% of the time",
        "Window_latch broken",
        "Nothing to do with heating",
    ):
        make_request(db, unit, manager, text)
    return unit


def find(client, **params):
    query = "&".join(f"{k}={v}" for k, v in params.items())
    response = client.get(f"/api/requests?{query}")
    assert response.status_code == 200, response.text
    return response.json()


def test_search_is_case_insensitive(as_manager, jobs):
    assert find(as_manager, q="BOILER")["total"] == 2
    assert find(as_manager, q="boiler")["total"] == 2


def test_a_percent_sign_in_the_search_is_a_literal_not_a_wildcard(as_manager, jobs):
    """`%` is the LIKE wildcard. Passed straight through, a search for "%" matches every row and
    a search for "50%" matches anything starting "50". Users type percent signs."""
    everything = find(as_manager)["total"]
    assert everything == 5

    # Treated as a wildcard, "%" matches all five. Treated as text, it matches only the one
    # description that actually contains a percent sign.
    assert find(as_manager, q="%25")["total"] == 1  # %25 is an encoded %
    assert find(as_manager, q="50%25")["total"] == 1  # "50% of the time"
    assert find(as_manager, q="99%25")["total"] == 0


def test_an_underscore_in_the_search_is_a_literal_not_a_single_character_wildcard(
    as_manager, jobs
):
    assert find(as_manager, q="Window_latch")["total"] == 1
    # As a wildcard, "_" matches any single character and so matches all five rows. As text it
    # matches only the description containing an actual underscore.
    assert find(as_manager, q="_")["total"] == 1
    # And a wildcard would let this match "Window_latch"; as text it must not.
    assert find(as_manager, q="Window_atch")["total"] == 0


def test_a_backslash_in_the_search_does_not_break_the_query(as_manager, jobs):
    assert find(as_manager, q="back%5Cslash")["total"] == 0  # %5C is a backslash


def test_sql_metacharacters_in_the_search_are_just_text(as_manager, jobs):
    for probe in ("'", "''", "--", "%3B%20DROP%20TABLE%20units", "%27%20OR%201%3D1"):
        body = find(as_manager, q=probe)
        assert body["total"] == 0
    # And the table is still there afterwards.
    assert find(as_manager)["total"] == 5


def test_an_empty_search_is_the_same_as_no_search(as_manager, jobs):
    assert find(as_manager, q="")["total"] == 5


def test_a_page_past_the_end_is_empty_but_the_total_is_still_right(as_manager, jobs):
    body = find(as_manager, page=99, page_size=10)
    assert body["items"] == []
    assert body["total"] == 5  # the total describes the match, not the page


def test_page_size_is_clamped(as_manager, jobs):
    assert as_manager.get("/api/requests?page_size=1000").status_code == 422
    assert as_manager.get("/api/requests?page_size=0").status_code == 422
    assert as_manager.get("/api/requests?page=0").status_code == 422


def test_filters_that_match_nothing_return_zero_rather_than_everything(as_manager, jobs):
    assert find(as_manager, unit_id=9999)["total"] == 0
    assert find(as_manager, contractor_id=9999)["total"] == 0
    assert find(as_manager, q="boiler", priority="urgent")["total"] == 0


def test_an_invalid_filter_value_is_refused(as_manager, jobs):
    assert as_manager.get("/api/requests?status=finished").status_code == 422
    assert as_manager.get("/api/requests?priority=critical").status_code == 422
    assert as_manager.get("/api/requests?unit_id=abc").status_code == 422


def test_the_total_matches_the_number_of_rows_you_can_actually_page_through(as_manager, jobs):
    total = find(as_manager, q="boiler")["total"]
    collected = []
    page = 1
    while True:
        items = find(as_manager, q="boiler", page=page, page_size=1)["items"]
        if not items:
            break
        collected += items
        page += 1
        assert page < 20, "paging did not terminate"
    assert len(collected) == total
