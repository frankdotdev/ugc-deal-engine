from ugc_engine.enrichment import clean_domain, extract_email


def test_extract_email_skips_junk():
    assert extract_email("mail noreply@brand.com or hello@brand.com") == "hello@brand.com"
    assert extract_email("logo@2x.png") == ""


def test_clean_domain_drops_social_hosts():
    assert clean_domain("https://www.acme.com/shop") == "acme.com"
    assert clean_domain("https://x.com/acme/status/1") == ""
    assert clean_domain("https://l.instagram.com/x") == ""
    assert clean_domain("") == ""
