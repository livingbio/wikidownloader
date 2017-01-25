# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import re
from stanford_segmenter import Segmenter, conv2tw
from pyknp import Juman

cache_seg = dict()


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
        seg = ja.analysis(sent)
        seg_text.append(' '.join([morph.midasi for morph in seg]))
    text = ' '.join(seg_text)
    if len(text) < 10:
        return None
    return text


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
