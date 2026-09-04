from zoho_mail_mcp.html_text import html_to_text, truncate


def test_tags_are_stripped_and_entities_decoded():
    assert html_to_text("<p>Ahoj&nbsp;Jano &amp; spol.</p>") == "Ahoj Jano & spol."


def test_scripts_and_styles_are_dropped():
    html = "<style>p{color:red}</style><script>alert(1)</script><p>text</p>"
    assert html_to_text(html) == "text"


def test_block_elements_become_line_breaks():
    assert html_to_text("<div>prvý</div><div>druhý</div>") == "prvý\n\ndruhý"


def test_list_items_are_separated():
    assert html_to_text("<ul><li>a</li><li>b</li></ul>") == "a\n\nb"


def test_blank_lines_are_collapsed():
    assert html_to_text("<p>a</p><br><br><br><p>b</p>") == "a\n\nb"


def test_empty_input():
    assert html_to_text("") == ""
    assert html_to_text(None) == ""


def test_plain_text_survives_untouched():
    assert html_to_text("bez značiek") == "bez značiek"


def test_truncate_reports_whether_it_cut():
    assert truncate("abcdef", 3) == ("abc", True)
    assert truncate("abcdef", 100) == ("abcdef", False)
    assert truncate("abcdef", 0) == ("abcdef", False)
