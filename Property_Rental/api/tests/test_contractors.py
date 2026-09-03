"""The contractors list. Narrow on purpose — see `routers/users.py`."""


def test_a_manager_gets_contractors_by_name(as_manager, contractor, second_contractor):
    body = as_manager.get("/api/contractors").json()
    assert [c["name"] for c in body] == ["Amara Diallo", "Tomas Vidal"], body


def test_it_returns_only_a_name_and_an_id(as_manager, contractor):
    body = as_manager.get("/api/contractors").json()
    assert set(body[0]) == {"id", "name"}, f"the response leaks {set(body[0]) - {'id', 'name'}}"


def test_managers_are_not_in_it(as_manager, manager, contractor):
    ids = {c["id"] for c in as_manager.get("/api/contractors").json()}
    assert manager.id not in ids


def test_a_contractor_cannot_list_the_workforce(as_contractor):
    assert as_contractor.get("/api/contractors").status_code == 403


def test_signed_out_gets_401(client):
    assert client.get("/api/contractors").status_code == 401
