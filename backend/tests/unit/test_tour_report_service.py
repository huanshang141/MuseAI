from app.application.tour_report_service import (
    calculate_radar_scores,
    detect_ceramic_question,
    select_identity_tags,
    get_report_theme,
)


def test_detect_ceramic_question_true():
    assert detect_ceramic_question("这个人面鱼纹盆是做什么的？") is True
    assert detect_ceramic_question("彩陶是怎么烧制的") is True
    assert detect_ceramic_question("尖底瓶的用途") is True


def test_detect_ceramic_question_false():
    assert detect_ceramic_question("半坡人的房屋是怎么建的？") is False
    assert detect_ceramic_question("谁是首领？") is False


def test_radar_scores_all_B():
    stats = {
        "total_duration_minutes": 10,
        "total_questions": 3,
        "total_exhibits_viewed": 2,
        "site_hall_duration_minutes": 5,
        "ceramic_questions": 0,
    }
    scores = calculate_radar_scores(stats)
    assert scores["civilization_resonance"] == 1
    assert scores["imagination_breadth"] == 1
    assert scores["history_collection"] == 1
    assert scores["life_experience"] == 1
    assert scores["ceramic_aesthetics"] == 1


def test_radar_scores_all_A():
    stats = {
        "total_duration_minutes": 45,
        "total_questions": 12,
        "total_exhibits_viewed": 7,
        "site_hall_duration_minutes": 15,
        "ceramic_questions": 1,
    }
    scores = calculate_radar_scores(stats)
    assert scores["civilization_resonance"] == 2
    assert scores["imagination_breadth"] == 2
    assert scores["history_collection"] == 2
    assert scores["life_experience"] == 2
    assert scores["ceramic_aesthetics"] == 2


def test_radar_scores_all_S():
    stats = {
        "total_duration_minutes": 90,
        "total_questions": 20,
        "total_exhibits_viewed": 15,
        "site_hall_duration_minutes": 30,
        "ceramic_questions": 5,
    }
    scores = calculate_radar_scores(stats)
    assert scores["civilization_resonance"] == 3
    assert scores["imagination_breadth"] == 3
    assert scores["history_collection"] == 3
    assert scores["life_experience"] == 3
    assert scores["ceramic_aesthetics"] == 3


def test_select_identity_tags_default():
    scores = {
        "civilization_resonance": 1,
        "imagination_breadth": 1,
        "life_experience": 1,
        "ceramic_aesthetics": 1,
    }
    tags = select_identity_tags(scores)
    assert tags == ["史前细节显微镜", "六千年前的干饭王", "史前第一眼光"]


def test_select_identity_tags_all_S():
    scores = {
        "civilization_resonance": 3,
        "imagination_breadth": 3,
        "life_experience": 3,
        "ceramic_aesthetics": 3,
    }
    tags = select_identity_tags(scores)
    assert tags[0] == "冷酷无情的地层勘探机"
    assert tags[1] == "母系氏族社交悍匪"
    assert tags[2] == "彩陶纹饰解码者"


def test_get_report_theme():
    assert get_report_theme("A") == "archaeology"
    assert get_report_theme("B") == "village"
    assert get_report_theme("C") == "homework"
