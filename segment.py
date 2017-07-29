#! /usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright © 2017 lizongzhe 
#
# Distributed under terms of the MIT license.
from __future__ import unicode_literals
from pyknp import Juman
import string
import re
import signal
import time
from zhconvert import conv2tw
from nltk import word_tokenize
import os

current_path = os.path.dirname(os.path.abspath(__file__))

def timeout_handler(*args):
    raise Exception('timeout')

signal.signal(signal.SIGALRM, timeout_handler)

import logging
from logging.config import fileConfig

fileConfig(os.path.join(current_path, 'logging_config.ini'))

logger = logging.getLogger()


def ja_segment():
    juman = Juman()
    def segment(text):
        seg = juman.analysis(text)
        return [morph.midasi for morph in seg]
    return segment

def zh_segment():
    from stanford_segmenter import Segmenter

    segmenter = Segmenter()
    segmenter.tw_segment('因為第一次載入時間較長，為避免timeout，要先跑一次斷詞')
    def segment(text):
        text = conv2tw(text)
        return segmenter.tw_segment(text)
    return segment

def en_segment():
    def segment(text):
        return word_tokenize(text)
    return segment

mapping = {}
mapping['zh'] = zh_segment
mapping['ja'] = ja_segment
mapping['en'] = en_segment

def segment_text(lang, text):
    cache = getattr(segment_text, "cache", {})
    if not cache.get(lang, None):
        cache[lang] = mapping[lang]()
        setattr(segment_text, 'cache', cache)
    if isinstance(text, str):
        text = text.decode('utf-8')
    lang_segmenter = cache[lang]
    sents = text.strip().split('\n')
    result = []
    for sent in sents:
        if lang in ["ja", "zh"]:
            sent = re.sub("[{}]".format(string.whitespace), "", sent)
        if lang == "zh":
            try:
                text = conv2tw(text)
            except:
                pass
        if not sent:
            continue
        try:
            signal.alarm(60)
            result += lang_segmenter(sent)
            signal.alarm(0)
        except BaseException as e:
            del cache[lang]
            cache[lang] = mapping[lang]()
            logger.exception(e)
            logger.error(sent)
    return result
