from simplyprint_ws_client import PrinterConfig


def test_config_fields():
    config1 = PrinterConfig.get_blank()
    config2 = PrinterConfig.get_blank()

    assert config1.partial_eq(**config1.as_dict())
    assert config2.partial_eq(**config2.as_dict())

    assert config1.is_empty()
    assert config2.is_default()

    assert config1.as_dict() == config2.as_dict()

    assert config1.as_dict() == {
        "id": 0,
        "token": "0",
        "name": None,
        "in_setup": None,
        "short_id": None,
        "unique_id": config1.unique_id,
        "public_ip": None,
    }

    config1.id = 1

    assert not config1.partial_eq(**config2.as_dict())
    assert not config2.partial_eq(**config1.as_dict())

    assert not config1.is_empty()

    assert not config1.is_pending()

    config2.token = "super_cool_token"
    config2.unique_id = "super_cool_id"

    assert not config2.is_empty()
    assert not config2.is_default()

    assert config2.partial_eq(unique_id="super_cool_id")
    assert config2.partial_eq(token="super_cool_token")

    config3 = PrinterConfig(
        **{
            "id": None,
            "in_setup": None,
            "short_id": None,
            "name": None,
            "public_ip": None,
            "token": None,
            "unique_id": None,
        }
    )
    assert config3.is_empty()

    config4 = PrinterConfig(
        **{
            "id": None,
            "in_setup": None,
            "short_id": None,
            "name": None,
            "public_ip": None,
            "token": None,
            "unique_id": "140686326013968",
        }
    )
    assert not config4.is_empty()
