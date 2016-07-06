# -*- coding: utf-8 -*-

import os
import string

import nltk

import tinysegmenter

nltk.download('punkt')

class CWSegmenter(object):
    DICT_PATH = os.path.join(os.path.dirname(__file__), 'data/cw_dict.txt')

    def __init__(self, dictionary=None):
        """The dictioanry can be customized."""
        if dictionary:
            self.dictionary = dictionary
        else:
            self.dictionary = set()
            with open(self.DICT_PATH) as fin:
                for c in fin:
                    self.dictionary.add(c.strip())
        self.longest = max((len(c) for c in self.dictionary))
        self.punctuation_marks = set(string.punctuation)

    def _is_punctuation(self, c):
        # CJK punctuation marks
        if (0x3000 <= ord(c) <= 0x303F) or (
            0xFF00 <= ord(c) <= 0xFFEF):
            return True
        # ASCII punctuation marks
        if c not in ["-", "/"] and c in self.punctuation_marks:
            return True
        return False

    def longest_match(self, text, pos):
        #   Always split punctuations.
        if self._is_punctuation(text[pos:pos+1]):
           return 1
        for l in range(self.longest, 0, -1):
            if text[pos:pos+l] in self.dictionary:
                return l
        return 0

    def segment(self, text):
        results = []
        oov = ""
        i = 0
        while i < len(text):
            l = self.longest_match(text, i)
            if l == 0:
                oov += text[i:i+1]
                i += 1
            else:
                if oov:
                    results.append(oov.strip())
                    oov = ""
                results.append(text[i:i+l])
                i += l 
        if oov:
            results.append(oov.strip())
        return results
    

ChineseWordSegmenter = CWSegmenter()
JapaneseWordSegmenter = tinysegmenter.TinySegmenter()

def sentence_segment(text, lang):
    if lang in ['zh', 'ja']:
        sents = text.replace("!", "。").replace("?", "。").replace("！", "。").replace("？", "。").replace("；", "。").split("。")
    elif lang == 'en':
        sents = nltk.tokenize.sent_tokenize(text)
    else:
        raise ValueError('Unknown langauge %r' % lang)

    results = []
    for sent in sents:
        if len(sent) >= 8:
            results.append(sent)
    return results


def word_segment(text, lang):
    if lang == 'zh':
        global ChineseWordSegmenter
        return ChineseWordSegmenter.segment(text)
    elif lang == 'ja':
        global JapaneseWordSegmenter
        return JapaneseWordSegmenter.tokenize(text)
    elif lang == 'en':
        return nltk.tokenize.word_tokenize(text)
    else:
        raise ValueError('Unknown language %r' % lang)


if __name__ == "__main__":
    print(" ".join(word_segment(u"今天天氣好好", 'zh')))
    print(" ".join(word_segment(u"台灣遊戲絕無僅有，結合當紅電視劇龍飛鳳舞的全新創意休閒遊戲！在龍飛鳳舞傳遊戲中，您將可以收納劇中知名角色為您得力的助手，利用老少咸宜的益智連線 ...", 'zh')))
    
    print(" ".join(word_segment(u"""國民黨主席暨總統參選人朱立倫結束7天訪美行程，於16日凌晨返台，上午馬不停蹄接受《聯合晚報》專訪。談到17日將討論的不分區立委名單，朱立倫指出，將藉此培育黨內選舉人才，這些人必須切結在2年後辭職投入2018年縣市長選舉；接棒的不分區立委經過2年國會歷練後，也將投入下一屆、2020。年區域立委選戰。
朱立倫分析，這次民進黨的不分區立委名單中，專業功能考量占很高的比重，國民黨在上一屆也是如此，但過去4年受到一些批評，這次會檢討。不過，安全名單中至少應有5席專業立委。""", 'zh')))
    print(" ".join(word_segment(u"""今年冬天音響展來到圓山飯店舉行。展場不多，這次音響展展房很少，好聽的更少，三個小時就看完了。國內小廠笙偉展出自製管機，鬆爽輕快的個性管機少見，非常有潛力。老闆兼設計師說機箱是用竹材打造，他喜歡這種輕盈、有彈性的材料，不知道是否因此聽感接近碳纖維墊材。竹製板材最近很流行，常用於家具與地板，取得比以前容易許多。三樓美德聲的無音箱喇叭，來自法國品牌 LEEDH。喇叭的確幾乎完全消失於舞台，營造出非常寫真的音場，音象的輪廓尺寸與深度都很自然。中低音部每聲道都是由兩顆單體反向發聲，藉此抵消震動。振錩應該是老代理商德錩的關係企業，風格也有雷同之處，都是昂貴而有趣，聲音有特色的品牌。F1 排氣管喇叭非常吸睛，但不知道聲音如何？除了訊源是 Accuphase 之外，全套的 Daniel Hertz。其實一樓還有另一間台笙的展房，用 Accuphase 系統推動更大的 Daniel Hertz 落地喇叭，但我比較喜歡樓上這間。樓上這套 Daniel Hertz，承襲了當年的 Mark Levinson 與 Cello 的路線，活潑奔放、透明直率的聲音非常動人。米迪安科技展出 VDP Audio 全音域喇叭，聲音清新自然。音盆尺寸雖大，但高頻仍然很豐盈。惠樺這次似乎比從前都好聽，可惜 Mircomega 的訊源等級似乎差了全系統一截。離開前回到惠樺再聽一下，當時展房沒客人，老闆陶先生人在現場播放馬勒第三號最末樂章。我對這首曲子有很多回憶，不知不覺就一直聽下去。陶先生忽然說，這是 Kegel 的版本，鐵幕末期的錄音，充滿了悲悽之情，是他最愛聽版本，每次沒人就會放來自己聽。接著又跟我說最後的定音鼓如何悽美，又說某一段 Kegel 的詮釋充滿反諷的意味。多年前便曾聽聞惠樺的陶先生不只對音響執著，對音樂更是熱情無比，有獨到的見解，這次見面終於體會到了。""", 'zh')))


