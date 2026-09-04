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


OUTLOOK = """<html xmlns:v="urn:schemas-microsoft-com:vml"><head>
<meta http-equiv="Content-Type" content="text/html; charset=utf-8">
<meta name="Generator" content="Microsoft Word 15">
<link rel="File-List" href="cid:filelist.xml">
<style>p.MsoNormal {margin:0cm;}</style>
</head><body lang="SK">
<p class=MsoNormal>Dobrý deň pán Architekt</p>
<p class=MsoNormal>Mám zopár otázok ohľadom detailov.</p>
<img src="cid:image001.png">
</body></html>"""


def test_outlook_mail_keeps_its_text():
    """<meta> a <link> koncovú značku nemajú; kedysi zhltli celé telo."""
    text = html_to_text(OUTLOOK)
    assert "Dobrý deň pán Architekt" in text
    assert "Mám zopár otázok ohľadom detailov." in text
    assert "MsoNormal" not in text


def test_void_tags_do_not_swallow_what_follows():
    for void in ("<meta charset='utf-8'>", "<link rel='x'>", "<br>", "<img src='x'>"):
        assert "text" in html_to_text(f"<html><head>{void}</head><body><p>text</p></body></html>")


def test_unclosed_style_still_yields_the_text():
    # Rozbité HTML nesmie skončiť tichým prázdnym telom.
    assert "text napriek tomu" in html_to_text("<style>x{color:red}<p>text napriek tomu")


def test_unclosed_script_still_yields_the_text():
    assert "text napriek tomu" in html_to_text("<script>zly()<p>text napriek tomu")


def test_well_formed_script_and_style_are_still_dropped():
    text = html_to_text("<style>p{color:red}</style><script>zly()</script><p>text</p>")
    assert text == "text"


def test_genuinely_empty_body_stays_empty():
    assert html_to_text("<html><body></body></html>") == ""
    assert html_to_text("<html><body><img src='cid:x'></body></html>") == ""
