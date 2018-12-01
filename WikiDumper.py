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
from collections import namedtuple

from datetime import datetime as dt
from time import mktime, time
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

    filenames = np.array([urlsplit(url).path.split('/')[-1] for url in href])
    try:
        numbers = [re.findall('articles(\d+).xml', fn)[0] for fn in filenames]
    except IndexError:
        #如果檔案有articles.xml...的格式，沒有含任何數字
        print('No numbers found in filenames. Creating numbers.')
        numbers = list(range(len(filenames)))
    for i in range(len(numbers) - 1, -1, -1):
        if numbers[:i].count(numbers[i]):
            numbers[i] += '-' + str(numbers[:i].count(numbers[i]))
    numbers = np.array(numbers)
    paths = np.array([os.path.join(lang, fn) for fn in filenames])

    if not os.path.isdir(lang):  # 如果連目錄都沒有建，全部都需要下載
        os.mkdir(lang)
        return zip(href, [lang] * len(articles), date, size, paths, filenames, numbers)

    to_download = np.array([not os.path.isfile(fn) or  # the file doesn't exist
                            dt.fromtimestamp(os.stat(fn).st_mtime) != day or  # the date's wrong
                            os.stat(fn).st_size != sz  # the size's wrong
                            for day, sz, fn in zip(date, size, paths)])
    href = href[to_download]
    date = date[to_download]
    size = size[to_download]
    paths = paths[to_download]
    filenames = filenames[to_download]
    numbers = numbers[to_download]

    return list(zip(href, [lang] * len(articles), date, size, paths, filenames, numbers))


download_log = dict()
Log = namedtuple('Log', ['size_mb', 'last_mb', 'duration', 'speed', 'percent', 'st_time', 'last_time'])


def gen_download_hook(number):
    def download_hook(count, block_size, total_size):
        self_log = download_log[number]
        if time() - self_log.last_time < 0.1:
            return
        size_mb = count * block_size / 1024.0 / 1024.0
        speed = (size_mb - self_log.last_mb) / (time() - self_log.last_time)
        last_mb, last_time = size_mb, time()
        percent = min(int(count * block_size * 100 / total_size), 100)
        download_log[number] = Log(size_mb, size_mb, time() - self_log.st_time,
            speed, percent, self_log.st_time, time())
        info = '\r'
        for n, log in download_log.items():
            tmp = '[{}] {}%, {:.0f} MB, {:.2f} MB/s'.format(
                n, log.percent, log.size_mb, log.speed)
            info += tmp + ' ' * (35 - len(tmp))
        print(info, end='')
    return download_hook


def download(info):
    url, lang, date, size, output, filename, number = info
    if not os.path.isdir(lang):
        os.mkdir(lang)

    st = dt.now()
    download_log[number] = Log(0, 0, 0, 0, 0, time(), time())
    urlretrieve(url, output, reporthook=gen_download_hook(number))
    os.utime(output, (mktime(date.timetuple()),) * 2)
    assert os.stat(output).st_size == size, '{} downloaded failed'.format(filename)
    ed = dt.now()
    del download_log[number]
    duration = (ed - st).total_seconds()
    print("\n[{}] finished, average speed = {:.2f} MB/s".format(
        filename, size / 1024.0 / 1024.0 / duration))


def dump_wiki(lang):
    infos = prepare_wiki_url(lang)
    print(infos)
    print(len(infos))
    pool = Pool(3)
    pool.map(download, infos)


if __name__ == '__main__':
    import sys
    if len(sys.argv) == 1:
        for lang in ('en', 'zh', 'ja'):
            dump_wiki(lang)
    else:
        dump_wiki(sys.argv[1])
