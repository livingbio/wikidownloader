#! /usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright © 2017 lizongzhe
#
# Distributed under terms of the MIT license.
from __future__ import print_function
import gevent
from gevent import monkey
monkey.patch_all()
import requests
from bs4 import *
import os

from datetime import datetime as dt
from time import mktime
import re
import numpy as np
from gevent.pool import Pool
import requests
# Python 2/3 compatible
try:
    from urllib import urlretrieve
except ImportError:
    from urllib.request import urlretrieve
try:
    from urlparse import urljoin, urlsplit
except ImportError:
    from urllib.parse import urljoin, urlsplit


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
    articles = bhtml.find_all('a', {'href': re.compile(r'.*pages-articles\d.*bz2$')})
    if len(articles) == 0:
        articles = bhtml.find_all('a', {'href': re.compile(r'.*pages-articles\.xml\.bz2$')})
    date_time_size = [tag.next.next.split() for tag in articles]

    href = np.array([urljoin(base_url, tag['href']) for tag in articles], dtype=np.str)
    date = np.array([dt.strptime(date + ' ' + time, '%d-%b-%Y %H:%M')
                     for date, time, _ in date_time_size])
    size = np.array([int(size) for _, _, size in date_time_size], dtype=np.int64)

    # 同名檔案會包含一個 xml 檔及一個 bz2，我們只需要抓 bz2
    if sum(size <= 100000):
        href = href[size > 100000]
        date = date[size > 100000]
        size = size[size > 100000]
    # 用檔案大小排序，方便作 multi-processing
    descOrder = np.argsort(size)[::-1]
    href = href[descOrder]
    date = date[descOrder]
    size = size[descOrder]

    return zip(href, date, size)


def download(info):
    url, lang, date, size = info
    filename = urlsplit(url).path.split('/')[-1]
    output = lang + '/' + filename
    if not os.path.isdir(lang):
        os.mkdir(lang)

    st = dt.now()
    urlretrieve(url, output)
    os.utime(output, (mktime(date.timetuple()),) * 2)
    assert os.stat(output).st_size == size
    ed = dt.now()
    print("[{}] finished, duration={}".format(filename, ed - st))


def dump_wiki(lang):
    infos = prepare_wiki_url(lang)
    print('Start Time: {}'.format(dt.now()))
    for url, date, size in infos:
        print('    {}, {}, {}'.format(url, date, size))

    pool = Pool(3)
    pool.map(download, [(url, lang, date, size) for url, date, size in infos])


if __name__ == '__main__':
    import sys
    if len(sys.argv) == 1:
        for lang in ('en', 'zh', 'ja'):
            dump_wiki(lang)
    else:
        dump_wiki(sys.argv[1])
