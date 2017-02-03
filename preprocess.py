# -*- coding: utf-8 -*-
from __future__ import unicode_literals, print_function
import re
from zhconvert._conv2tw_data import trad, simp
from stanford_segmenter import Segmenter, conv2tw
from pyknp import Juman

cache_seg = dict()
simp_to_trad = dict((ord(s), ord(t)) for s, t in zip(simp, trad))
trad_to_simp = dict((ord(t), ord(s)) for t, s in zip(trad, simp))

ja_only_words = '乗亜仏値仮働価倹児両剰剤剣効勅労勲勧匁巻呉咲啓単厳圏囲円図団増圧塁壊壱奨姉姫娯嬢実' \
                '寛専対峠巣帯廃広庁弾従徴徳恵悪悩応懐戦戯戸払抜拝掲揺捜択撃拠挙拡摂収晩暦暁査栄楽様' \
                '検桜権歓歩歳歴帰毎気氷汚渉涙浄渇満渋沢済滝瀬焼営犠猟獣産畑畳疎発碁砕稲穂穏窓粧粋絶' \
                '経緑縁県縦総絵継続繊聴粛脳臓舎舗荘菓薫蔵薬処衆裏覚覧観説謡訳読変譲弐売頼賛軽転込逓' \
                '遅辺郷酔醸釈鋭録銭錬鉄鋳鉱閲関陥隣険隠隷雑霊顔顕騒駆験駅髄髪闘鶏塩黒黙斎歯齢'


def detect_lang(text):
    text = text.lower()
    english = ''.join([ch for ch in text if ord(ch) < 0x7F])
    latin = ''.join([ch for ch in text if ord(ch) < 0x200 and ord(ch) > 0x7F])
    nonlatin = ''.join([ch for ch in text if ord(ch) > 0x200])
    len_all = float(len(text))
    len_english = float(len(english))
    len_latin = float(len(latin))
    len_nonlatin = float(len(nonlatin))

    if len_english / len_all > 0.95 and len_latin / len_all < 0.01:
        return 'en'

    if (len_english + len_latin) / len_all > 0.95:
        if sum([latin.count(ch) for ch in 'čďěňřšťůž']) / len_latin > 0.1:
            return 'cs'  # Czech
        if sum([latin.count(ch) for ch in 'ąćęłńśźż']) / len_latin > 0.2:
            return 'pl'  # Polish
        if sum([latin.count(ch) for ch in 'ãô']) / len_latin > 0.05:
            return 'pt'  # Portuguese
        if sum([latin.count(ch) for ch in 'æø']) / len_latin > 0.05:
            return 'da'  # Danish
        if sum([latin.count(ch) for ch in 'áíñóú']) / len_latin > 0.1:
            return 'es'  # Spanish
        if sum([latin.count(ch) for ch in 'âœéêëîïô']) / len_latin > 0.3:
            return 'fr'  # French
        if sum([latin.count(ch) for ch in 'å']) / len_latin > 0.2:
            return 'sv'  # Swedish
        if sum([latin.count(ch) for ch in 'çğş']) / len_latin > 0.2:
            return 'tr'  # Turkish
        if sum([latin.count(ch) for ch in 'àèìù']) / len_latin > 0.05:
            return 'it'  # Italian
        if sum([latin.count(ch) for ch in 'ßü']) / len_latin > 0.05:
            return 'de'  # German
        if sum([latin.count(ch) for ch in 'äö']) / len_latin > 0.2:
            return 'fi'  # Finnish
        return 'nl'

    if sum([ord(ch) >= 0x3040 and ord(ch) <= 0x30FF for ch in nonlatin]) / len_nonlatin > 0.1 or \
       sum([ch in ja_only_words for ch in nonlatin]) / len_nonlatin > 0.02:
        return 'ja'  # Japenese
    if sum([ord(ch) >= 0xAC00 and ord(ch) <= 0xD7AF for ch in nonlatin]) / len_nonlatin > 0.3:
        return 'ko'  # Korean
    if sum([ord(ch) >= 0x400 and ord(ch) <= 0x4FF for ch in nonlatin]) / len_nonlatin > 0.3:
        return 'ru'  # Russian

    tw_prop = sum([ch == cht for ch, cht in zip(nonlatin, nonlatin.translate(simp_to_trad))]) / len_nonlatin
    cn_prop = sum([ch == chs for ch, chs in zip(nonlatin, nonlatin.translate(trad_to_simp))]) / len_nonlatin
    if tw_prop > cn_prop:
        return 'zh-tw'
    else:
        return 'zh-cn'


def zh_segment(text):
    """
    為了讓 word segmentation function 可替換，需要有共同的interface。
    所有的 word segmentation，統一以空白字元作為斷詞符號。
    輸入是 "今天天氣不錯" --> 輸出是 "今天 天氣 不 錯"。
    所以 zh_segment('今天天氣不錯').split() --> ['今天', '天氣', '不', '錯']
    如果未來要替換 segmenter，只需要修改這三個函式，讓輸出符合規格即可
    """
    if 'zh' not in cache_seg:
        cache_seg['zh'] = Segmenter()
    zh = cache_seg['zh']
    if len(text) < 10:
        return None
    out_text = []
    while len(text):
        if len(text) > 1000:
            i = text.find(' ', 1000)
            if i < 0:
                i = len(text)
        else:
            i = len(text)
        try:
            out_text.extend(zh.tw_segment(text[:(i + 1)]))
        except:
            raise
        text = text[(i + 1):]
    return ' '.join(out_text)


def ja_segment(text):
    if 'ja' not in cache_seg:
        cache_seg['ja'] = Juman()
    ja = cache_seg['ja']
    seg_text = []
    for sent in text.split('\n'):
        if len(sent) < 2:
            continue
        try:
            seg = ja.analysis(sent)
            seg_text.append(' '.join([morph.midasi for morph in seg]))
        except IndexError:
            seg_text.append(sent)
    text = ' '.join(seg_text)
    if len(text) < 10:
        return None
    return text


def clear_cache():
    cache_seg.clear()


def isKatakana(char):
    return ord(char) >= 0x30A0 and ord(char) <= 0x30FF


def to_half_word(text):
    '''Transfer double-width character to single-width character.'''
    return ''.join([chr(ord(ch) - 0xff00 + 0x20)
                    if ord(ch) >= 0xff01 and ord(ch) <= 0xff5e else ch
                    for ch in text])


def remove_private_use_area(text):
    return ''.join([ch for ch in text if not (ord(ch) >= 0xE000 and ord(ch) <= 0xF8FF)])


def remove_reference_or_internal(text):
    index = []
    text = text.replace('== ', '==').replace(' ==', '==')
    index.append(text.find('==內部連結=='))
    index.append(text.find('==內部鏈結=='))
    index.append(text.find('==參考文獻=='))
    index.append(text.find('==參考資料=='))
    index.append(text.find('==參考鏈接=='))
    index.append(text.find('==參見=='))
    index.append(text.find('==參考=='))
    index.append(text.find('==外部連接=='))
    index.append(text.find('==外部鏈接=='))
    index.append(text.find('==注釋=='))
    index.append(text.find('==注=='))
    index.append(text.find('==参照=='))
    index.append(text.find('==参考文献=='))
    index.append(text.find('==脚注=='))
    index.append(text.find('==関連項目=='))
    index.append(text.find('==外部リンク=='))
    index.append(text.find('==內部リンク=='))
    index.append(text.find('==See Also=='))
    index.append(text.find('==References=='))
    index.append(text.find('==Further Reading=='))
    index.append(text.find('==External Links=='))
    index = [i for i in index if i > 0]
    if len(index) == 0:
        return text
    min_index = min(index)
    return text[:min_index]


def remove_image_and_file(text):
    new_blocks = []
    delete_next = False
    for item in re.split('\[\[([Ii]mage|[Cc]ategory|[Ff]ile|ファイル):', text):
        if item in ('Category', 'Image', 'File', 'category', 'image', 'file', 'ファイル'):
            delete_next = True
            level = 1
        elif delete_next:
            delete_next = False
            for i in range(len(item) - 1):
                if item[i] == '[' and item[i+1] == '[':
                    level += 1
                elif item[i] == ']' and item[i+1] == ']':
                    level -= 1
                if level == 0:
                    new_blocks.append(item[(i + 2):])
                    break
        else:
            delete_next = False
            new_blocks.append(item)
    return ''.join(new_blocks)


def remove_ref_or_tags(text):
    text = re.sub('\[[Hh]ttp.*?\]', '', text, flags=re.DOTALL)
    text = re.sub('<[Rr]ef[^/]*?/>', '', text, flags=re.DOTALL)
    text = re.sub('<[Rr]ef.*?</[Rr]ef>', '', text, flags=re.DOTALL)
    text = text.replace('<big>', '').replace('</big>', '')
    text = re.sub('<[Dd]iv.*</[Dd]iv>', '', text, flags=re.DOTALL)
    text = re.sub('<[Gg]allery.*</[Gg]allery>', '', text, flags=re.DOTALL)
    text = re.sub('<[Nn]oinclude.*?</[Nn]oinclude>', '', text, flags=re.DOTALL)
    text = re.sub('<!--.*?-->', '', text, flags=re.DOTALL)
    text = re.sub('([Hh]ttp|[Hh]ttps|[Ff]tp|[Ff]tps)://[\w\.\?=_/-]+', '', text)
    return text


def remove_double_bracket(text):
    t = ''
    level = 0
    start = 0
    for i in range(len(text)):
        if text[i] == '{':
            if level == 0:
                t += text[start:i]
            level += 1
        elif text[i] == '}':
            level -= 1
            if level == 0:
                start = i + 1
    t += text[start:]
    return ''.join(t)


def remove_title_and_parenth(text):
    text = re.sub('（.*?）', '', text, flags=re.DOTALL)
    text = re.sub('\(.*?\)', '', text, flags=re.DOTALL)
    text = re.sub('={2,}.*?={2,}', '', text, flags=re.DOTALL)
    text = re.sub('^[ \*]+', '', text)
    text = re.sub('\[\[[^\|\]]*?\|(.*?)\]\]', ' \\1 ', text)
    return text


def remove_nonlatin_words(text):
    return ''.join([ch for ch in text if ord(ch) < 0x2000])


_quotes = {
    ord('《'): ' ',
    ord('》'): ' ',
    ord('〈'): ' ',
    ord('〉'): ' ',
    ord('「'): ' ',
    ord('」'): ' ',
    ord('『'): ' ',
    ord('』'): ' ',
    ord('“'): ' ',
    ord('”'): ' ',
}

_puncts = {
    ord('。'): ' ',
    ord('；'): ' ',
    ord('，'): ' ',
    ord('、'): ' ',
    ord('：'): ' ',
    ord('*'): ' ',
    ord('？'): ' ',
    ord('！'): ' ',
    ord('!'): ' ',
    ord('?'): ' ',
    ord(','): ' ',
    ord(':'): ' ',
    ord(';'): ' ',
    ord('/'): ' ',
    ord('~'): ' ',
    ord('\r'): ' ',
    0x2010: ' ',
    0x2012: ' ',
    0x2013: ' ',
    0x2014: ' ',
    0x2015: ' ',
    0x2018: ' ',
    0x2019: ' ',
    0x201a: ' ',
    0x201b: ' ',
    0x201c: ' ',
    0x201d: ' ',
    0x201e: ' ',
    0x201f: ' ',
    0x2024: ' ',
}


def remove_quotes_and_punct(text):
    text = text.translate(_quotes)
    text = text.replace("'''", ' ').replace("''", ' ')
    text = text.translate(_puncts)
    return text
