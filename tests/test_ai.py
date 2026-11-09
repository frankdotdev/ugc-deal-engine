from ugc_engine import ai


def test_rejects_creator_self_promotion(settings):
    item = {"title": "UGC creator here", "snippet": "Hire me, check my portfolio", "platform": "X (Twitter)", "niche": "x"}
    assert ai.qualify(item, settings) is None


def test_rule_based_accepts_buyer_post(settings):
    item = {"title": "Founder", "snippet": "We are hiring UGC creators, paid $200/video. hi@brand.com",
            "platform": "X (Twitter)", "niche": "skincare"}
    out = ai.qualify(item, settings)
    assert out and out["intent_score"] >= 80 and out["step1_body"] and out["step3_body"]


def test_rule_based_rejects_irrelevant(settings):
    assert ai.qualify({"title": "Cat photos", "snippet": "look at my cat", "platform": "X (Twitter)", "niche": "x"}, settings) is None
