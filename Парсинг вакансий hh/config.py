from fake_http_header import FakeHttpHeader
from itertools import cycle


def generate_headers():
    urls = cycle([
        "https://hh.ru/",
        "https://spb.hh.ru/",
        "https://vladivostok.hh.ru/",
        "https://kazan.hh.ru/",
        "https://rostov.hh.ru/",
    ])

    while True:
        referer = next(urls)
        headers = FakeHttpHeader(referer=referer).as_header_dict()
        yield headers

BASE_URL = "https://hh.ru/vacancy/"