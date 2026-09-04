import pytest
from conftest import BASE_ENV

from zoho_mail_mcp.config import DATA_CENTERS, SCOPE_STRING, Config
from zoho_mail_mcp.errors import ConfigError


def test_eu_data_center_maps_to_eu_hosts():
    config = Config.from_env(BASE_ENV)
    assert config.api_base == "https://mail.zoho.eu"
    assert config.accounts_base == "https://accounts.zoho.eu"


@pytest.mark.parametrize("dc", sorted(DATA_CENTERS))
def test_every_data_center_resolves(dc):
    config = Config.from_env({**BASE_ENV, "ZOHO_DC": dc})
    assert config.api_base.startswith("https://mail.")
    assert config.accounts_base.startswith("https://accounts.")


def test_missing_credentials_are_named():
    with pytest.raises(ConfigError) as excinfo:
        Config.from_env({"ZOHO_DC": "eu"})
    message = str(excinfo.value)
    assert "ZOHO_CLIENT_ID" in message
    assert "ZOHO_REFRESH_TOKEN" in message


def test_missing_data_center_is_not_guessed():
    env = {key: value for key, value in BASE_ENV.items() if key != "ZOHO_DC"}
    with pytest.raises(ConfigError, match="ZOHO_DC"):
        Config.from_env(env)


def test_unknown_data_center_rejected():
    with pytest.raises(ConfigError, match="Neznáme ZOHO_DC"):
        Config.from_env({**BASE_ENV, "ZOHO_DC": "atlantis"})


def test_scope_string_is_read_only():
    assert SCOPE_STRING == (
        "ZohoMail.accounts.READ,ZohoMail.folders.READ,ZohoMail.messages.READ"
    )
    assert "ALL" not in SCOPE_STRING
    assert "CREATE" not in SCOPE_STRING


def test_allowed_accounts_parsed_and_lowercased():
    config = Config.from_env(
        {**BASE_ENV, "ZOHO_ALLOWED_ACCOUNTS": " Jan@Onoff.sk , info@onoff.sk "}
    )
    assert config.allowed_accounts == {"jan@onoff.sk", "info@onoff.sk"}
    assert config.account_allowed("JAN@onoff.sk")
    assert not config.account_allowed("kto@inde.sk")


def test_empty_whitelist_allows_everything():
    config = Config.from_env(BASE_ENV)
    assert config.account_allowed("hocikto@example.com")
    assert config.account_allowed(None)


def test_whitelist_rejects_account_without_address():
    config = Config.from_env({**BASE_ENV, "ZOHO_ALLOWED_ACCOUNTS": "jan@onoff.sk"})
    assert not config.account_allowed(None)


def test_numeric_setting_must_be_a_number():
    with pytest.raises(ConfigError, match="ZOHO_TIMEOUT"):
        Config.from_env({**BASE_ENV, "ZOHO_TIMEOUT": "chvíľu"})


def test_api_base_override_wins():
    config = Config.from_env({**BASE_ENV, "ZOHO_API_BASE": "https://proxy.local/"})
    assert config.api_base == "https://proxy.local"
