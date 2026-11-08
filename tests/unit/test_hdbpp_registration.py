from scripts.hdbpp.register_hdbpp_devices import build_plan, parse_tango_host


def test_plan_keeps_database_credentials_out_of_tango_properties():
    plan = build_plan(
        vm_hostname="elyse-hdbpp",
        database_host="10.20.30.202",
        database_port=3307,
        database_name="hdbpp",
    )

    serialized = repr(plan).lower()
    assert "password" not in serialized
    assert "user=" not in serialized
    assert "host=10.20.30.202" in serialized
    assert "port=3307" in serialized


def test_plan_registers_starter_and_hdbpp_devices_on_same_host():
    plan = build_plan(
        vm_hostname="elyse-hdbpp",
        database_host="10.20.30.202",
        database_port=3307,
        database_name="hdbpp",
    )

    assert [item.name for item in plan] == [
        "tango/admin/elyse-hdbpp",
        "archiving/hdbpp/es01",
        "archiving/hdbpp/cm",
    ]
    assert plan[2].properties["ArchiverList"] == ["archiving/hdbpp/es01"]


def test_tango_host_parser_allows_ipv4_or_hostname():
    assert parse_tango_host("10.20.30.202:10000") == ("10.20.30.202", 10000)
    assert parse_tango_host("everest:10000") == ("everest", 10000)
