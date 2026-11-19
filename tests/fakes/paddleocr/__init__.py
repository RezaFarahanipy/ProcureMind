"""Fake `paddleocr` for tests. Use with PYTHONPATH=tests/fakes"""
import time


class PaddleOCR:
    def __init__(self, lang="en", **kw):
        self.lang = lang
        time.sleep(0.3)

    def predict(self, img):
        return [{"rec_texts": ["خط اول", "خط دوم 123"], "rec_scores": [0.9, 0.8]}]
