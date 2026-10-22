from __future__ import annotations

from app.services.transcription.detect import (
    choose_language,
    is_devanagari_transliterated_english,
)


def test_choose_language_empty() -> None:
    assert choose_language({}) is None


def test_choose_language_prefers_english_when_top() -> None:
    # Typical Whisper detection for Indian English: en is top, hi and ur also get some probability
    probs = {"en": 0.38, "hi": 0.28, "ur": 0.14, "te": 0.05}
    assert choose_language(probs) == "en"


def test_choose_language_prefers_english_when_significant_english_present() -> None:
    # Even if hi+ur sum is slightly higher, significant English probability means it's English speech
    probs = {"hi": 0.32, "en": 0.30, "ur": 0.15}
    assert choose_language(probs) == "en"


def test_choose_language_chooses_hindi_when_decisively_hindi() -> None:
    # Real Hindi speech has negligible English and high Hindi probability
    probs = {"hi": 0.70, "ur": 0.20, "en": 0.03}
    assert choose_language(probs) == "hi"


def test_choose_language_third_language() -> None:
    probs = {"ta": 0.65, "hi": 0.15, "en": 0.10}
    assert choose_language(probs) == "ta"


def test_is_devanagari_transliterated_english_positive_cases() -> None:
    # Real examples from the database of English transcribed in Devanagari:
    transliterated_samples = [
        "व्हाट इज कस्टमर लाइफटाइम वैल्यू आल्सो नोन एज एलटीबी? दिस इज द टोटल रेवेन्यू दैट अ बिजनेस कैन",
        "क्लोज माय आइज़ एंड टॉक टू गॉड, पीस ऑफ माय हैंड, आई एम सिंगिंग दिस सॉन्ग एंड इट गोज",
        "मैन हो स्पेंड एन आवर इंसल्टिंग अ मोंक, द मोंक नेवर रिएक्टेड, कन्फ्यूज्ड द मैन",
        "अ यंग मैन वंस ट्रैवल्ड अक्रॉस जापान टू लर्न फ्रॉम द ग्रेटेस्ट स्वॉर्टस्मिथ",
        "मास्टर द माइंडसेट ऑफ दीस थ्री एनिमल्स एंड यू विल बिकम अनस्टॉपेबल। एवरी मैन शुड",
        "आई जस्ट हर्ड समवन से द लास्ट लेवल ऑफ इंटेलिजेंस इज नोइंग टू यूज इट ओनली व्हेन इट",
        "लेट मी टेल यू सम फन फैक्ट्स अबाउट न्यूमेरोलॉजी एंड नरेंद्र मोदी",
        "डस योर बॉयफ्रेंड लव यू? यस। 100%. यू वांट टू टेस्ट इट आउट?",
    ]
    for sample in transliterated_samples:
        assert is_devanagari_transliterated_english(sample) is True, f"Failed on: {sample}"


def test_is_devanagari_transliterated_english_negative_cases() -> None:
    # Real genuine Hindi samples:
    hindi_samples = [
        "आपकी कुंडली में 12 हाउस होते हैं, उसमें सबसे महंगा हाउस है चौथा घर क्योंकि इसी में आप अपनी",
        "बाबा ने इतना दिया, इतना दिया कि पूछो मत कि कितना दिया। दो महीनों पहले अपनी शादी",
        "अगर आप भी चाहते हैं विवाह में आ रही बाधाओं से राहत और जीवन में संतुलन",
        "अरे यार ये नेट ही नहीं चल रहा। भाई नेट कब चलेगा ऋषि? भाई 10 मिनट में चल जाएगा",
        "सब लोग अलेक्जेंडर द ग्रेट को याद रखते हैं कि उसने पूरी दुनिया पर राज किया",
        "तुम नर्वस होना हमेशा के लिए कैसे बंद कर सकते हो और नहीं मैं तुम्हें कोई ज्ञान नहीं दूंगा",
        "पांच शब्द बोलने पर देवता आपके साथ हो जाएगा, आपका ईष्ट सदा आपकी रक्षा करेगा",
    ]
    for sample in hindi_samples:
        assert is_devanagari_transliterated_english(sample) is False, f"Failed on: {sample}"


def test_is_devanagari_transliterated_english_short_text() -> None:
    assert is_devanagari_transliterated_english("नमस्ते") is False
    assert is_devanagari_transliterated_english("हेलो") is False
