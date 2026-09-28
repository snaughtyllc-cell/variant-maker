from variant_maker.server.experience import resolve_experience


def test_missing_is_agency():
    assert resolve_experience(workspace_experience=None, email="a@b.com", environ={}) == "agency"


def test_workspace_solo():
    assert resolve_experience(workspace_experience="solo", email="a@b.com", environ={}) == "solo"


def test_email_list_overrides_workspace():
    env = {"VARIANT_SOLO_EMAILS": "va@x.com, other@x.com"}
    assert resolve_experience(workspace_experience="agency", email="VA@x.com", environ=env) == "solo"
    env2 = {"VARIANT_AGENCY_EMAILS": "jeff@x.com"}
    assert resolve_experience(workspace_experience="solo", email="jeff@x.com", environ=env2) == "agency"
