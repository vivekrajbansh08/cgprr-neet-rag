"""Institute lookup by id (pins a user's clarify choice). Invented names, no DB."""

from neet_common.schemas import InstituteInfo
from neet_retrieval.core import Catalog, Institute, institute_info
from neet_retrieval.names import IdfIndex, short_name

NAME = "Alpha Medical College, Northtown,Hill Road, Northtown, Somestate, 100001"


def catalog() -> Catalog:
    inst = {1: Institute(id=1, display_name=NAME, state="Somestate")}
    return Catalog(institutes=inst, idf=IdfIndex.build([NAME]))


def test_known_id_returns_name_without_address():
    info = institute_info(catalog(), 1)
    assert info == InstituteInfo(id=1, display_name=NAME, short_name=short_name(NAME), state="Somestate")
    assert info.short_name.startswith("Alpha Medical College, Northtown")
    assert not any(ch.isdigit() for ch in info.short_name)


def test_unknown_id_returns_none():
    assert institute_info(catalog(), 2) is None


def test_institutes_endpoint_200_and_404():
    from fastapi.testclient import TestClient
    from neet_retrieval.app import Deps, app

    app.state.deps = Deps(pool=None, llm=None, http=None, catalog=catalog())  # type: ignore[arg-type]
    try:
        client = TestClient(app)  # no lifespan: no pool is opened
        assert client.get("/institutes/1").json()["id"] == 1
        assert client.get("/institutes/2").status_code == 404
    finally:
        del app.state.deps
