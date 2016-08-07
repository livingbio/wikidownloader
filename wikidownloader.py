# -*- coding: utf-8 -*-
from socket import setdefaulttimeout
from bs4 import BeautifulSoup
from urllib.request import urlretrieve
from urllib.request import urlopen
from argparse import ArgumentParser
from pymongo import MongoClient
import os
from sys import exit
from re import compile, findall, sub
from datetime import datetime as dt
from time import mktime, sleep
import numpy as np
from bz2 import BZ2File
from xml import sax
from multiprocessing import Pool
from bany_logger import setLogger
import logging as log
from janome.tokenizer import Tokenizer as ja_Tokenizer
from zhconvert import *
zh = ZHConvert('http://localhost:9998/pos?wsdl', 'http://localhost:9999/seg?wsdl')

# 為了讓 word segmentation function 可替換，需要有共同的interface
# 所有的 word segmentation，統一以空白字元作為斷詞符號
# 輸入是 "今天天氣不錯" --> 輸出是 "今天 天氣 不 錯"
# 所以 zh_segment(u'今天天氣不錯').split() --> [u'今天', u'天氣', u'不', u'錯']
# 如果未來要替換 segmenter，只需要修改這三個函式，讓輸出符合規格即可
# def zh_segment(text):
#     return u' '.join((u' '.join(jieba_cut(text))).split())
# def zh_segment(text):
#     return u' '.join(word_segment(text, 'zh'))
def zh_segment(text):
    try:
        seg = zh.tw_segment(text)
    except:
        try:  # try again
            seg = zh.tw_segment(text)
        except:
            return None
    if seg is None:
        return None
    return ' '.join(seg)


def ja_segment(text):
    return u' '.join(token.surface for token in ja_Tokenizer().tokenize(u' '.join(text.split())))


# default timeout 是設定網路相關的timeout，例如 MongoDB 及 Slack
setdefaulttimeout(30)
# 預設情況下，logging會同時輸出到 stdout 及檔案(檔名為日期)
setLogger()
MongoURL = 'mongodb://localhost/NLP'

######################################################################
# Start of main program                                              #
######################################################################

def prepare_wiki_url(base_url):
    """分析 WikiMedia 網站，傳回要下載的檔案清單，包含日期及大小。
    日期及大小會用來核對檔案是否需要重新下載，只要日期或大小不同，就會重新下載。

    'href': 要下載的檔案名稱 (副檔名應為 bz2)
    'date': 檔案在server上的日期
    'size': 檔案大小
    """

    try:
        html = urlopen(base_url).read()
    except:
        exit(1)  # 如果連網路都連不上，就不用作下去了

    bhtml = BeautifulSoup(html, 'lxml')
    # 我們只要抓檔名中包含 pages-articles 的檔案
    tag_a = bhtml.find_all('a', {'href': compile('.*pages-articles\d.*bz2$')})
    if len(tag_a) == 0:
        tag_a = bhtml.find_all('a', {'href': compile('.*pages-articles\.xml\.bz2$')})
    s = [tag.next.next.split() for tag in tag_a]

    href = np.array([tag['href'] for tag in tag_a], dtype=np.str)
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

    return({'href': href, 'date': date, 'size': size})


def reporthook(count, block_size, total_size):
    """用來顯示下載進度的 callback function。

    每當下載進度前進1%，這個function就會顯示一次。
    """

    global start_time, percent
    if count == 0:
        start_time = dt.now()
        percent = 0
        return
    size = int(count * block_size / 1048576.0)
    new_percent = min(int(count * block_size * 100 / total_size), 100)
    # 只有下載進度前進1%時才會印訊息
    if new_percent != percent:
        percent = new_percent
        log.info('{}%, {} MB, {}'.format(percent, size, dt.now() - start_time))


def download_wiki(base_url, urlData):
    """嘗試下載每個檔案，直到所有檔案下載完畢為止。

    每個檔案都會比對檔案大小及檔案日期，只要有一個不對，就會重新下載。
    下載完畢後，也會設定檔案日期，讓日期與server上的相同。

    urlData: 是 prepare_wiki_url() 的傳回值，應該是一個 dict
    """

    href = urlData['href']
    date = urlData['date']
    size = urlData['size']

    while True:
        downlist = []
        for i in range(href.shape[0]):
            is_exist = os.access(href[i], os.R_OK)
            if is_exist:
                is_samesize = os.stat(href[i]).st_size == size[i]
                is_samedate = dt.fromtimestamp(os.stat(href[i]).st_mtime) == date[i]
            else:
                is_samedate = False
                is_samesize = False
            log.info('{} {} {} {}'.format(i, is_exist, is_samesize, is_samedate))
            if is_exist and is_samesize and is_samedate:
                # 如果檔案日期及大小都相同，就不需下載
                log.info('because same date and size, {} is skipped'.format(href[i]))
            else:
                # 如果檔案不存在、或日期不同、或大小不同，就加到 downlist
                downlist.append((href[i], date[i]))

        # 結束條件是所有檔案都不需下載
        if len(downlist) == 0:
            break

        # 呼叫 urlretrieve() 下載，並提供 reporthook 作為callback function
        # 下載後會設定檔案日期，與server上相同
        # 如果下載中斷或發生timeout，不會產生任何錯誤訊息，而會繼續下一個檔案
        # 等這批檔案都下載後，再重新產生一份 downlist
        for fn, d in downlist:
            log.info('start downloading {}'.format(fn))
            try:
                urlretrieve(base_url + fn, fn, reporthook)
                os.utime(fn, (mktime(d.timetuple()),) * 2)
            except:
                None  # just skip this file

    log.warn('Downloading {} finished'.format(base_url))


def tidify_wiki_en(t):
    """整理英文wiki的文章內容

    t: 必須是 unicode string。
       如果不是，可以用 unicode(text, errors='ignore') 來轉換成 unicode string。
    """

    text = t.replace('\n', ' ')
    t = ''
    level = 0
    start = 0
    # delete {{....}}
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

    t = sub('<!--.*?-->', '', t)                    # delete <!--...-->
    t = sub('<ref[^/]*?/(ref|)>', '', t)            # delete <ref .../>
    t = sub('<ref.*?ref>', '', t)                   # delete <ref>...</ref>
    t = sub('\[\[[^\]]*?:.*?\]\]', '', t)           # delete [[AA:BB]]
    t = sub('\[\[([^\|\]]*?)\|.*?\]\]', '\\1', t)   # [[AA|BB]] --> [[AA]]
    t = sub('</?[^>]+?>', '', t)                    # delete <tag>
    t = sub('\w+://(\w+\.){1,}\w+/[^ ]*', '', t)    # delete http://....
    t = sub('==see also==.*', '', t)
    t = sub('==references==.*', '', t)
    t = sub('==further reading==.*', '', t)
    t = sub('==external links==.*', '', t)
    t = sub('=+[ \w]+?=+', '', t)                   # delete == tt ==
    t = t.replace('#', ' ').replace('===', ' ').replace('==', ' ')
    t = t.replace(', ', ' , ').replace('. ', ' . ').replace('(', ' ( ').replace(')', ' ) ') \
         .replace('!', ' ! ').replace('?', ' ? ').replace(';', ' ; ').replace(':', ' : ') \
         .replace("'''", ' ').replace("''", ' ').replace('"', ' ').replace(" '", " ").replace("' ", " ") \
         .replace('*', ' ').replace('$', '').replace('/', ' ').replace(u'\u2013', '-')
    t = ' '.join(t.split())         # tokenize and delete redundant spaces
    return(t)


def tidify_wiki_zh(t):
    """整理中文wiki的文章內容

    t: 必須是 unicode string。
       如果不是，可以用 unicode(text, errors='ignore') 來轉換成 unicode string。
    """

    if not t or len(t) < 10:
        return u''
    text = t.replace('\n', ' ')
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

    t = sub('<!--.*?-->', '', t)                    # delete <!--...-->
    t = sub('<ref[^/]*?/(ref|)>', '', t)            # delete <ref .../>
    t = sub('<ref.*?ref>', '', t)                   # delete <ref>...</ref>
    t = sub('\[\[[^\]]*?:.*?\]\]', '', t)           # delete [[AA:BB]]
    t = sub('\[\[([^\|\]]*?)\|.*?\]\]', '\\1', t)   # [[AA|BB]] --> [[AA]]
    t = sub('</?[^>]+?>', '', t)                    # delete <tag>
    t = sub('\w+://(\w+\.){1,}\w+/[^ ]*', '', t)    # delete http://....
    t = sub(u'==參考資料==.*', '', t)
    t = sub(u'==參考==.*', '', t)
    t = sub(u'==延伸閱讀==.*', '', t)
    t = sub(u'==外部鏈接==.*', '', t)
    t = sub(u'=+[ \w]+?=+', '', t)                   # delete == tt ==
    t = t.replace('#', ' ').replace('===', ' ').replace('==', ' ').replace('&nbsp;', ' ')
    t = t.replace(', ', ' ').replace('. ', ' ').replace('(', ' ').replace(')', ' ') \
         .replace('!', ' ').replace('?', ' ').replace(';', ' ').replace(': ', ' ') \
         .replace("'''", ' ').replace("''", ' ').replace('"', ' ').replace(" '", " ") \
         .replace("' ", " ") \
         .replace('*', ' ').replace('$', '').replace('/', ' ').replace(u'\u2013', '-')
    t = t.replace(u'，', u' ').replace(u'。', u' ').replace(u'；', u' ') \
         .replace(u'：', u' ') \
         .replace(u'、', u' ').replace(u'“', ' ').replace(u'”', ' ').replace(u'「', ' ') \
         .replace(u'」', ' ').replace(u'[[', '[ [').replace(u']]', '] ]') \
         .replace(u'『', u' ').replace(u'』', ' ').replace(u'（', ' ').replace(u'）', ' ') \
         .replace(u'！', u' ').replace(u'？', ' ').replace(u'《', ' ').replace(u'》', ' ') \
         .replace(u'·', ' ')
    t = zh_segment(t)
    if t is None:
        return ''
    t = t.split()
    if len(t) == 0:
        return ''
    text = []
    tmp = []
    inside_bracket = False
    for i in range(len(t) - 1):
        if t[i] == '[' and t[i+1] == '[':
            inside_bracket = True
        if inside_bracket and t[i] == ']' and t[i+1] == ']':
            inside_bracket = False
            text.append(''.join(tmp))
            tmp = []
        if t[i] == '[' or t[i] == ']':
            continue
        if inside_bracket:
            tmp.append(t[i])
        else:
            text.append(t[i])
    text.append(t[-1])
    return ' '.join(text)


def tidify_wiki_ja(t):
    """整理日文wiki的文章內容

    t: 必須是 unicode string。
       如果不是，可以用 unicode(text, errors='ignore') 來轉換成 unicode string。
    """

    if not t or len(t) < 10:
        return u''
    text = t.replace('\n', ' ')
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

    t = sub('<!--.*?-->', '', t)                    # delete <!--...-->
    t = sub('<ref[^/]*?/(ref|)>', '', t)            # delete <ref .../>
    t = sub('<ref.*?ref>', '', t)                   # delete <ref>...</ref>
    t = sub('\[\[[^\]]*?:.*?\]\]', '', t)           # delete [[AA:BB]]
    t = sub('\[\[([^\|\]]*?)\|.*?\]\]', '\\1', t)   # [[AA|BB]] --> [[AA]]
    t = sub('</?[^>]+?>', '', t)                    # delete <tag>
    t = sub('\w+://(\w+\.){1,}\w+/[^ ]*', '', t)    # delete http://....
    t = sub(u'==注==.*', '', t)
    t = sub(u'==参照==.*', '', t)
    t = sub(u'=+[ \w]+?=+', '', t)                   # delete == tt ==
    t = t.replace('#', ' ').replace('===', ' ').replace('==', ' ')
    t = t.replace(', ', ' , ').replace('. ', ' . ').replace('(', ' ( ').replace(')', ' ) ') \
         .replace('!', ' ! ').replace('?', ' ? ').replace(';', ' ; ').replace(':', ' : ') \
         .replace("'''", ' ').replace("''", ' ').replace('"', ' ').replace(" '", " ").replace("' ", " ") \
         .replace('*', ' ').replace('$', '').replace('/', ' ').replace(u'\u2013', '-')
    t = t.replace(u'，', u' , ').replace(u'。', u' . ').replace(u'；', u' ; ').replace(u'：', u' : ') \
         .replace(u'、', u' , ').replace(u'“', ' ').replace(u'”', ' ').replace(u'「', ' ').replace(u'」', ' ') \
         .replace(u'『', u' ').replace(u'』', ' ').replace(u'（', ' ( ').replace(u'）', ' ) ') \
         .replace(u'！', u' ! ').replace(u'？', ' ? ').replace(u'《', ' ').replace(u'》', ' ').replace(u'·', ' ')
    return ja_segment(t)


def tidify_wiki_ko(t):
    """整理韓文wiki的文章內容

    t: 必須是 unicode string。
       如果不是，可以用 unicode(text, errors='ignore') 來轉換成 unicode string。
    """

    if not t or len(t) < 10:
        return u''
    text = t.replace('\n', ' ')
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

    t = sub('<!--.*?-->', '', t)                    # delete <!--...-->
    t = sub('<ref[^/]*?/(ref|)>', '', t)            # delete <ref .../>
    t = sub('<ref.*?ref>', '', t)                   # delete <ref>...</ref>
    t = sub('\[\[[^\]]*?:.*?\]\]', '', t)           # delete [[AA:BB]]
    t = sub('\[\[([^\|\]]*?)\|.*?\]\]', '\\1', t)   # [[AA|BB]] --> [[AA]]
    t = sub('</?[^>]+?>', '', t)                    # delete <tag>
    t = sub('\w+://(\w+\.){1,}\w+/[^ ]*', '', t)    # delete http://....
    t = sub(u'==각주==.*', '', t)
    t = sub(u'==바깥 고리==.*', '', t)
    t = sub(u'=+[ \w]+?=+', '', t)                   # delete == tt ==
    t = t.replace('#', ' ').replace('===', ' ').replace('==', ' ')
    t = t.replace(', ', ' , ').replace('. ', ' . ').replace('(', ' ( ').replace(')', ' ) ') \
         .replace('!', ' ! ').replace('?', ' ? ').replace(';', ' ; ').replace(':', ' : ') \
         .replace("'''", ' ').replace("''", ' ').replace('"', ' ').replace(" '", " ").replace("' ", " ") \
         .replace('*', ' ').replace('$', '').replace('/', ' ').replace(u'\u2013', '-')
    t = t.replace(u'，', u' , ').replace(u'。', u' . ').replace(u'；', u' ; ').replace(u'：', u' : ') \
         .replace(u'、', u' , ').replace(u'“', ' ').replace(u'”', ' ').replace(u'「', ' ').replace(u'」', ' ') \
         .replace(u'『', u' ').replace(u'』', ' ').replace(u'（', ' ( ').replace(u'）', ' ) ') \
         .replace(u'！', u' ! ').replace(u'？', ' ? ').replace(u'《', ' ').replace(u'》', ' ').replace(u'·', ' ')
    # 韓文的segmenter遇到Unicode中的high surrogate codes會當掉
    t = u''.join([ch for ch in t if ord(ch) < 0xD800 and ord(ch) > 0xDB7F])
    return t


parse_article = {}


# 這個decorator的用途是整合不同語言到 parse_article
# 在 function 前面加 @register_article_parser('en')
# 就會使 parse_article['en'] = function
def register_article_parser(lang):
    def decorator(func):
        parse_article[lang] = func
        return func
    return decorator


@register_article_parser('en')
def parse_article_en(title, identical, the_id, text, buffer, temp_collect):
    """在wiki XML檔案遇到</text>時，會將收集到的資訊傳入此function。

    title: article/category 的標題
    identical: 重新導向的主題
    the_id: wikipedia內部的id
    text: 文章內容
    buffer: 收集處理好的文章，每100筆會寫入到MongoDB一次
    temp_collect: MongoDB的collection物件
    """

    text = text.lower()
    links = set(findall('\[\[([^#]+?)[\]\|#]', text))
    # 所有的 [[...]] 會分為三類
    # 'category:' 開頭的放在 cat 中
    # 'xxx:' 開頭的會丟掉
    # 其他的會放在 related 中
    cat = [x[9:].lower() for x in links if x[:9] == u'category:']
    related = [x.lower() for x in links if x.find(':') < 0]

    # 準備要放進 MongoDB 的資料
    data = {}
    # title 中的 (...) 要刪除
    title = (title[:title.find('(')] if title.find('(') > -1 else title).lower().strip()
    data[u'title'] = title
    if identical:
        data[u'identical'] = identical.lower()
    if the_id:
        data[u'id'] = int(the_id)
    if len(cat):
        data[u'categories'] = cat     # cat是所屬的category
    if len(related):
        data[u'related'] = related    # related是文章中出現的相關連結
    if title[:9] == u'category:':
        data[u'title'] = title[9:]    # 如果是category，只保留名稱，不保留開頭的'category:'
        data[u'isCategory'] = True
        i = text.find('{{cat main|')  # 如果有對應的main article，記錄在這裡
        if i > -1:
            j = text.find('}}', i)
            data[u'mainArticle'] = text[(i + 11):j].lower()
    else:
        data[u'isArticle'] = True
        if text[:9] != u'#redirect' and text.find('{{disambig') == -1:
            data[u'text'] = tidify_wiki_en(text)

    buffer.append(data)
    if len(buffer) >= 100:
        # 每100筆就存到 MongoDB，如果程式結束還沒有存完，就留給上層作
        temp_collect.insert_many(buffer)
        del buffer[:]


@register_article_parser('zh')
def parse_article_zh(title, identical, the_id, text, buffer, temp_collect):
    """在wiki XML檔案遇到</text>時，會將收集到的資訊傳入此function。

    title: article/category 的標題
    identical: 重新導向的主題
    the_id: wikipedia內部的id
    text: 文章內容
    buffer: 收集處理好的文章，每100筆會寫入到MongoDB一次
    temp_collect: MongoDB的collection物件
    """

    text = conv2tw(text).lower()  # 中文仍然會夾雜英文，所以 lower() 是必須的
    links = set(findall('\[\[([^#]+?)[\]\|#]', text))
    cat = [x[9:].lower() for x in links if x[:9] == u'category:']
    related = [x.lower() for x in links if x.find(':') < 0]

    data = {}
    title = (title[:title.find('(')] if title.find('(') > -1 else title).lower().strip()
    title = conv2tw(title)
    data[u'title'] = title
    if identical:
        data[u'identical'] = identical.lower()
    if the_id:
        data[u'id'] = int(the_id)
    if len(cat):
        data[u'categories'] = cat
    if len(related):
        data[u'related'] = related
    if title[:9] == u'category:':
        data[u'title'] = title[9:]
        data[u'isCategory'] = True
        i = text.find('{{cat main|')
        if i > -1:
            j = text.find('}}', i)
            data[u'mainArticle'] = text[(i + 11):j].lower()
    else:
        data[u'isArticle'] = True
        if text[:9] != u'#redirect' and text[:4] != u'#重定向' and text.find('{{disambig') == -1:
            data[u'text'] = tidify_wiki_zh(text)

    buffer.append(data)
    if len(buffer) >= 100:
        temp_collect.insert_many(buffer)
        del buffer[:]


@register_article_parser('ja')
def parse_article_ja(title, identical, the_id, text, buffer, temp_collect):
    """在wiki XML檔案遇到</text>時，會將收集到的資訊傳入此function。

    title: article/category 的標題
    identical: 重新導向的主題
    the_id: wikipedia內部的id
    text: 文章內容
    buffer: 收集處理好的文章，每100筆會寫入到MongoDB一次
    temp_collect: MongoDB的collection物件
    """

    text = text.lower()
    links = set(findall('\[\[([^#]+?)[\]\|#]', text))
    cat = [x[9:].lower() for x in links if x[:9] == u'category:']
    related = [x.lower() for x in links if x.find(':') < 0]

    data = {}
    title = (title[:title.find('(')] if title.find('(') > -1 else title).lower().strip()
    data[u'title'] = title
    if identical:
        data[u'identical'] = identical.lower()
    if the_id:
        data[u'id'] = int(the_id)
    if len(cat):
        data[u'categories'] = cat
    if len(related):
        data[u'related'] = related
    if title[:9] == u'category:':
        data[u'title'] = title[9:]
        data[u'isCategory'] = True
        i = text.find('{{cat main|')
        if i > -1:
            j = text.find('}}', i)
            data[u'mainArticle'] = text[(i + 11):j].lower()
    else:
        data[u'isArticle'] = True
        if text[:9] != u'#redirect':
            data[u'text'] = tidify_wiki_ja(text)

    buffer.append(data)
    if len(buffer) >= 100:
        temp_collect.insert_many(buffer)
        del buffer[:]


@register_article_parser('ko')
def parse_article_ko(title, identical, the_id, text, buffer, temp_collect):
    """在wiki XML檔案遇到</text>時，會將收集到的資訊傳入此function。

    title: article/category 的標題
    identical: 重新導向的主題
    the_id: wikipedia內部的id
    text: 文章內容
    buffer: 收集處理好的文章，每100筆會寫入到MongoDB一次
    temp_collect: MongoDB的collection物件
    """

    text = text.lower()
    links = set(findall('\[\[([^#]+?)[\]\|#]', text))
    cat = [x[9:].lower() for x in links if x[:9] == u'category:']
    related = [x.lower() for x in links if x.find(':') < 0]

    data = {}
    title = (title[:title.find('(')] if title.find('(') > -1 else title).lower().strip()
    data[u'title'] = title
    if identical:
        data[u'identical'] = identical.lower()
    if the_id:
        data[u'id'] = int(the_id)
    if len(cat):
        data[u'categories'] = cat
    if len(related):
        data[u'related'] = related
    if title[:9] == u'category:':
        data[u'title'] = title[9:]
        data[u'isCategory'] = True
        i = text.find('{{cat main|')
        if i > -1:
            j = text.find('}}', i)
            data[u'mainArticle'] = text[(i + 11):j].lower()
    else:
        data[u'isArticle'] = True
        if text[:9] != u'#redirect':
            data[u'text'] = tidify_wiki_ko(text)

    buffer.append(data)
    if len(buffer) >= 100:
        temp_collect.insert_many(buffer)
        del buffer[:]


@register_article_parser('de')
def parse_article_de(title, identical, the_id, text, buffer, temp_collect):
    """在wiki XML檔案遇到</text>時，會將收集到的資訊傳入此function。

    title: article/category 的標題
    identical: 重新導向的主題
    the_id: wikipedia內部的id
    text: 文章內容
    buffer: 收集處理好的文章，每100筆會寫入到MongoDB一次
    temp_collect: MongoDB的collection物件
    """

    text = text.lower()
    links = set(findall('\[\[([^#]+?)[\]\|#]', text))
    cat = [x[9:].lower() for x in links if x[:9] == u'category:']
    related = [x.lower() for x in links if x.find(':') < 0]

    data = {}
    title = (title[:title.find('(')] if title.find('(') > -1 else title).lower().strip()
    data[u'title'] = title.lower()
    if identical:
        data[u'identical'] = identical.lower()
    if the_id:
        data[u'id'] = int(the_id)
    if len(cat):
        data[u'categories'] = cat
    if len(related):
        data[u'related'] = related
    if title[:9] == u'category:':
        data[u'title'] = title[9:]
        data[u'isCategory'] = True
        i = text.find('{{cat main|')
        if i > -1:
            j = text.find('}}', i)
            data[u'mainArticle'] = text[(i + 11):j].lower()
    else:
        data[u'isArticle'] = True

    buffer.append(data)
    if len(buffer) >= 100:
        temp_collect.insert_many(buffer)
        del buffer[:]


class xmlHandler(sax.ContentHandler):
    """A Sax handler to parse WikiMedia xml files.
    """

    def __init__(self, language, worker_id, temp_collect):
        sax.ContentHandler.__init__(self)
        self.buffer = []
        self.parse = parse_article[language]  # 不同語言有不同的parser
        self.temp_collect = temp_collect      # 要存入的MongoDB collection物件
        self.worker_id = worker_id            # 這是multiprocessing的worker編號，目前沒用到

    def startElement(self, name, attrs):
        self.content = ''
        if name == 'page':  # 每一個page代表一個article或category
            self.title = None
            self.identical = None
            self.id = None
            self.text = None
        if name == 'redirect' and attrs.getValue('title'):
            self.identical = attrs.getValue('title')

    def endElement(self, name):
        if name == 'title':
            self.title = self.content
        elif name == 'id' and not self.id:
            self.id = self.content
        elif name == 'text':
            if self.title.find(':') < 0 or self.title[:9] == u'Category:':
                self.text = self.content
                self.parse(self.title, self.identical, self.id, self.text, self.buffer,
                           self.temp_collect)

    def characters(self, content):
        self.content += content


def wiki_xml_parser(args):
    """給bz2的檔案名稱，將裡面的文章處理後存到MongoDB。

    這個function是multiprocessing時的worker。
    """

    xmlBz2File, worker_id, tmp_collect_name = args
    log.info('[{}] {} parsing started, stored to {}'.format(worker_id, xmlBz2File, tmp_collect_name))
    start = dt.now()
    temp_collect = MongoClient(MongoURL)['NLP'][tmp_collect_name]

    bzfile = BZ2File(xmlBz2File, 'r')
    parser = sax.make_parser()
    # xmlBz2File[:2] 應該是 en, zh, ja, ko, de 等等
    handler = xmlHandler(xmlBz2File[:2], worker_id, temp_collect)
    parser.setContentHandler(handler)
    parser.parse(bzfile)

    # 每個 xmlHandler 都有一個buffer，會存放處理的資料
    # 在 parse_article_xx 中，每100筆會寫入一次，但如果沒有滿100筆，則沒寫入的資料會留在buffer中
    if len(handler.buffer) > 0:
        temp_collect.insert_many(handler.buffer)
        del handler.buffer[:]
    log.info('[{}] {} parsing finished, time={}'.format(worker_id, xmlBz2File, str(dt.now() - start)))
    return None


def parse_wiki(urlData, worker):
    """For all xml files we downloaded, parse them and store data on Mongodb.
    """

    new_collect_name = urlData['href'][0][:2] + 'wiki'
    tmp_collect_name = urlData['href'][0][:2] + 'wiki-' + str(dt.now().date())
    back_collect_name = tmp_collect_name + '-backup'

    # 無條件刪除 temp_collect
    temp_collect = MongoClient(MongoURL)['NLP'][tmp_collect_name]
    try:
        temp_collect.drop()
    except:
        None

    if worker <= 1:
        # 單個process時，就依序作
        for xmlBz2File in urlData['href']:
            wiki_xml_parser((xmlBz2File, 0, tmp_collect_name))
    else:
        # 多個process時，每個worker負責一個檔案
        pool = Pool(worker)
        href = urlData['href'].tolist()
        pool.map(wiki_xml_parser, zip(href, range(len(href)), [tmp_collect_name] * len(href)))
        pool.close()
        pool.join()

    current_collect = MongoClient(MongoURL)['NLP'][new_collect_name]
    # 將 'enwiki' 改名成 'enwiki-2016-04-16-backup'
    try:
        current_collect.rename(back_collect_name)
    except:
        None
    # 將 'enwiki-2016-04-16' 改名成 'enwiki'
    try:
        temp_collect.rename(new_collect_name)
    except:
        None

    # 自動建立index，包含 title/id/isCategory/identical
    new_collect = MongoClient(MongoURL)['NLP'][new_collect_name]
    sleep(10)
    new_collect.create_index('title', background=True)
    sleep(10)
    new_collect.create_index('id', background=True)
    sleep(10)
    new_collect.create_index('isCategory', background=True)
    sleep(10)
    new_collect.create_index('identical', background=True)
    log.warn('{} parsing finished'.format(new_collect_name))


def clear_duplicated_url(urlData):
    """有時候WikiMedia上，同樣編號的bz2有兩個，這裡用來刪除重複的bz2。
    """

    seq = np.argsort(urlData['href'])
    href = {}
    size = {}
    date = {}
    for i in seq:
        fn = urlData['href'][i]
        num = fn[(fn.find('articles') + 8):(fn.find('.xml'))]
        href[num] = fn
        size[num] = urlData['size'][i]
        date[num] = urlData['date'][i]
    return {'href': np.array(list(href.values())), 'size': np.array(list(size.values())),
            'date': np.array(list(date.values()))}


def wiki_downloader_preview(language, use_local_file):
    """這個function用來檢查可能有那些檔案會被處理或下載。
    """

    if use_local_file:
        bz2files = np.array([fn for fn in os.listdir('.')
                             if fn.startswith(language) and fn.endswith('bz2')], dtype=np.str)
        bz2sizes = np.array([os.stat(fn).st_size for fn in bz2files], dtype=np.int64)
        bz2dates = np.array([np.datetime64(dt.fromtimestamp(os.stat(fn).st_mtime)) for fn in bz2files], dtype=np.datetime64)
        descOrder = np.argsort(bz2sizes)[::-1]
        urlData = {'href': bz2files[descOrder], 'size': bz2sizes[descOrder], 'date': bz2dates[descOrder]}
    else:
        base_url = 'https://dumps.wikimedia.org/{}wiki/latest/'.format(language)
        urlData = prepare_wiki_url(base_url)
        urlData = clear_duplicated_url(urlData)
    for i in np.argsort(urlData['href']):
        print('{:60}{:12}'.format(urlData['href'][i], urlData['size'][i]))


def wiki_downloader(language, use_local_file, worker):
    """全自動下載 WikiMedia 上的檔案，處理後放到 MongoDB。

    language: 可以是 'en','zh','ja','ko','de'
    use_local_file: True表示不要嘗試下載，直接用現有目錄下的檔案
    worker: 要用幾個process同時執行
    """

    if use_local_file:
        # 不作任何檢查，直接用目錄下的bz2作為檔案清單
        bz2files = np.array([fn for fn in os.listdir('.')
                             if fn.startswith(language) and fn.endswith('bz2')], dtype=np.str)
        bz2sizes = np.array([os.stat(fn).st_size for fn in bz2files], dtype=np.int64)
        descOrder = np.argsort(bz2sizes)[::-1]
        urlData = {'href': bz2files[descOrder], 'size': bz2sizes[descOrder]}
    else:
        base_url = 'https://dumps.wikimedia.org/{}wiki/latest/'.format(language)
        urlData = prepare_wiki_url(base_url)
        urlData = clear_duplicated_url(urlData)
        download_wiki(base_url, urlData)
    parse_wiki(urlData, worker)


if __name__ == '__main__':
    supported_lang = ('en', 'zh', 'de', 'ja', 'ko')
    parser = ArgumentParser(description='Download wiki articles and store to MongoDb')
    parser.add_argument('language', metavar='LANG', type=str, nargs='+',
                        help='Which language of wikipedia to be downloaded: {}.'
                        .format(', '.join(supported_lang)))
    parser.add_argument('--local', dest='use_local_file', action='store_const',
                        const=True, default=False, help='Use local bz2 files, skip downloading.')
    parser.add_argument('--worker', dest='worker', action='store', metavar='NUM',
                        default=4, help='The number of processes to run parser.')
    parser.add_argument('--preview', dest='preview', action='store_const',
                        const=True, default=False, help='Preview what files will be downloaded or parsed.')
    args = vars(parser.parse_args())
    for lang in args['language']:
        if lang not in supported_lang:
            raise ValueError('Language "{}" is not acceptable.'.format(lang))
        if args['preview']:
            wiki_downloader_preview(lang, use_local_file=args['use_local_file'])
        else:
            wiki_downloader(lang, use_local_file=args['use_local_file'], worker=int(args['worker']))
