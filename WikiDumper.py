#! /usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright © 2017 lizongzhe 
#
# Distributed under terms of the MIT license.

import gevent
from gevent import monkey
monkey.patch_all()
import requests
from bs4 import *
import os

from datetime import datetime as dt
import re
import numpy as np
from gevent.pool import Pool
try:
    from urllib import urlretrieve
except ImportError:
    from urllib.request import urlretrieve

import urlparse

def prepare_wiki_url(lang):
    """分析 WikiMedia 網站，傳回要下載的檔案清單，包含日期及大小。
    日期及大小會用來核對檔案是否需要重新下載，只要日期或大小不同，就會重新下載。

    'href': 要下載的檔案名稱 (副檔名應為 bz2)
    'date': 檔案在server上的日期
    'size': 檔案大小
    """

    base_url = 'https://dumps.wikimedia.org/{}wiki/latest/'.format(lang)

    try:
        html = requests.get(base_url).content
    except Exception as e:
        exit(1)  # 如果連網路都連不上，就不用作下去了

    bhtml = BeautifulSoup(html, 'lxml')
    # 我們只要抓檔名中包含 pages-articles 的檔案
    tag_a = bhtml.find_all('a', {'href': re.compile(r'.*pages-articles\d.*bz2$')})
    if len(tag_a) == 0:
        tag_a = bhtml.find_all('a', {'href': re.compile(r'.*pages-articles\.xml\.bz2$')})
    s = [tag.next.next.split() for tag in tag_a]

    href = np.array([urlparse.urljoin(base_url, tag['href']) for tag in tag_a], dtype=np.str)
    date = np.array([dt.strptime(d[0] + ' ' + d[1], '%d-%b-%Y %H:%M') for d in s])
    size = np.array([int(d[2]) for d in s], dtype=np.int64)

    # 同名檔案會包含一個 xml 檔及一個 bz2，我們只需要抓 bz2
    href = href[size > 100000]
    date = date[size > 100000]
    size = size[size > 100000]
    # 用檔案大小排序，方便作 multi-processing
    descOrder = np.argsort(size)[::-1]
    href = href[descOrder]
    date = date[descOrder]
    size = size[descOrder]

    data = dict(zip(href, zip(date, size)))

    return data


def download(info):
    url, output = info
    st = dt.now()
    print "start download {} at {}".format(url)
    urlretrieve(url, output)
    print "download success {} at {} duration: {}".format(url, ed, ed - st)

def dump_wiki(lang):
    infos = prepare_wiki_url(lang)
    pool = Pool(3)
    pool.map(download, [(href, lang + "/" + os.path.basename(href)) for href in infos.keys()])


if __name__ == '__main__':
    import sys
    name, lang = sys.argv
    dump_wiki(lang)

