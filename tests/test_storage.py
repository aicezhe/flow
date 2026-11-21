from flow import storage


def test_delete_person_removes_scrobbles(tmp_path):
    c = storage.connect(tmp_path / "t.db")
    storage.add_person(c, "anna", "Anna")
    storage.add_person(c, "bob", "Bob")
    storage.insert_scrobbles(c, "anna", [("a", "t", 1)])
    storage.insert_scrobbles(c, "bob", [("a", "t", 1)])
    assert storage.delete_person(c, "anna") is True
    assert storage.delete_person(c, "anna") is False
    assert [p["username"] for p in storage.list_people(c)] == ["bob"]
    assert storage.all_scrobbles(c) == [("bob", "a", "t", 1)]


def test_existing_scrobbles_become_people(tmp_path):
    path = tmp_path / "t.db"
    c = storage.connect(path)
    storage.insert_scrobbles(c, "old", [("a", "t", 1)])
    c.execute("DELETE FROM people")
    c.commit()
    c2 = storage.connect(path)
    assert [(p["username"], p["plays"]) for p in storage.list_people(c2)] == [("old", 1)]
