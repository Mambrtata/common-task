from zoho_mail_mcp.envfile import parse_env_text, update_env_text

SAMPLE = """# konfigurácia
ZOHO_DC=eu
ZOHO_CLIENT_ID=
ZOHO_CLIENT_SECRET=stary

# sieť
ZOHO_MCP_AUTH_TOKEN=tajne
"""


def test_existing_values_are_replaced_in_place():
    result = update_env_text(SAMPLE, {"ZOHO_CLIENT_ID": "1000.AAA"})
    assert "ZOHO_CLIENT_ID=1000.AAA" in result
    assert result.index("ZOHO_CLIENT_ID") < result.index("ZOHO_CLIENT_SECRET")


def test_other_lines_survive_untouched():
    result = update_env_text(SAMPLE, {"ZOHO_CLIENT_ID": "x"})
    assert "# konfigurácia" in result
    assert "# sieť" in result
    assert "ZOHO_MCP_AUTH_TOKEN=tajne" in result


def test_missing_key_is_appended():
    result = update_env_text(SAMPLE, {"ZOHO_REFRESH_TOKEN": "1000.RRR"})
    assert result.rstrip().endswith("ZOHO_REFRESH_TOKEN=1000.RRR")


def test_comments_are_not_mistaken_for_settings():
    text = "# ZOHO_CLIENT_ID=zakomentovane\nZOHO_CLIENT_ID=skutocne\n"
    result = update_env_text(text, {"ZOHO_CLIENT_ID": "nove"})
    assert "# ZOHO_CLIENT_ID=zakomentovane" in result
    assert "ZOHO_CLIENT_ID=nove" in result
    assert "skutocne" not in result


def test_several_values_at_once():
    result = update_env_text(
        SAMPLE, {"ZOHO_CLIENT_ID": "a", "ZOHO_CLIENT_SECRET": "b", "ZOHO_DC": "us"}
    )
    assert "ZOHO_DC=us" in result
    assert "ZOHO_CLIENT_ID=a" in result
    assert "ZOHO_CLIENT_SECRET=b" in result


def test_file_always_ends_with_newline():
    assert update_env_text("ZOHO_DC=eu", {"ZOHO_DC": "us"}).endswith("\n")


def test_parse_reads_values_and_skips_comments():
    values = parse_env_text(SAMPLE)
    assert values["ZOHO_DC"] == "eu"
    assert values["ZOHO_CLIENT_SECRET"] == "stary"
    assert values["ZOHO_CLIENT_ID"] == ""
    assert "# konfigurácia" not in values


def test_parse_strips_surrounding_quotes():
    values = parse_env_text('ZOHO_CLIENT_SECRET="tajne"\nZOHO_DC=\'eu\'\n')
    assert values["ZOHO_CLIENT_SECRET"] == "tajne"
    assert values["ZOHO_DC"] == "eu"


def test_parse_ignores_commented_out_keys():
    values = parse_env_text("# ZOHO_DC=us\nZOHO_DC=eu\n")
    assert values["ZOHO_DC"] == "eu"
