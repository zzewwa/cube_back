import re

# List of normalized profanity roots in Cyrillic and Latin/translit forms.
_BAD_ROOTS = {
    'говн',
    'govn',
    'хуй',
    'хуе',
    'хуйло',
    'hui',
    'huy',
    'xui',
    'xuy',
    'еб',
    'eb',
    'ebat',
    'eban',
    'ебан',
    'ебат',
    'бля',
    'blya',
    'пидор',
    'пидар',
    'pidor',
    'pidar',
    'сука',
    'suka',
    'мудак',
    'mudak',
    'долбоеб',
    'dolboeb',
    'shit',
    'fuck',
}

_CYR_TO_LAT = {
    'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'e', 'ж': 'zh',
    'з': 'z', 'и': 'i', 'й': 'i', 'к': 'k', 'л': 'l', 'м': 'm', 'н': 'n', 'о': 'o',
    'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u', 'ф': 'f', 'х': 'h', 'ц': 'c',
    'ч': 'ch', 'ш': 'sh', 'щ': 'sch', 'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu',
    'я': 'ya',
}

_LEET_MAP = {
    '0': 'o', '1': 'i', '2': 'z', '3': 'e', '4': 'a', '5': 's', '6': 'b', '7': 't', '8': 'v', '9': 'g',
}


def _compact(value):
    return re.sub(r'[^0-9a-zA-Zа-яА-ЯёЁ]+', '', (value or '').lower())


def _normalize_leet(value):
    return ''.join(_LEET_MAP.get(char, char) for char in value)


def _to_latin(value):
    return ''.join(_CYR_TO_LAT.get(char, char) for char in value)


def contains_profanity(value):
    compact = _normalize_leet(_compact(value))
    if not compact:
        return False

    latin = _to_latin(compact)
    variants = {compact, latin}

    for variant in variants:
        for bad_root in _BAD_ROOTS:
            if bad_root in variant:
                return True
    return False
