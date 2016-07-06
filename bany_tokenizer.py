import codecs


def naive_tokenize(string):
    """Tokenize given string
    string: a list of lowered strings: ['i', 'like', 'music', 'manuscript']
    return: a list of tokenized strings: ['i', 'like', 'music_manuscript']
    """
    global dict2, dict3, dict4
    try:
        dict2
    except NameError:
        with codecs.open('DictForSemanticSearch_V3', 'r', 'utf-8') as f:
            newdict = [word for word in f.read().splitlines()]
            assert len(newdict) == 4071352
            dict2 = set([tuple(word.split()) for word in newdict if word.count(' ') == 1])
            dict3 = set([tuple(word.split()) for word in newdict if word.count(' ') == 2])
            dict4 = set([tuple(word.split()) for word in newdict if word.count(' ') == 3])
            assert len(dict2) == 1758743
            assert len(dict3) == 1592605
            assert len(dict4) == 388329
            del newdict

    out = string
    if len(string) >= 4:
        out = []
        i = 0
        while True:
            if (string[i], string[i+1], string[i+2], string[i+3]) in dict4:
                out.append('_'.join(string[i:(i+4)]))
                i += 4
            else:
                out.append(string[i])
                i += 1
            if i > len(string) - 4:
                break
        if i < len(string):
            out.extend(string[i:])

    if len(out) >= 3:
        string, out = out, []
        i = 0
        while True:
            if (string[i], string[i+1], string[i+2]) in dict3:
                out.append('_'.join(string[i:(i+3)]))
                i += 3
            else:
                out.append(string[i])
                i += 1
            if i > len(string) - 3:
                break
        if i < len(string):
            out.extend(string[i:])

    if len(out) >= 2:
        string, out = out, []
        i = 0
        while True:
            if (string[i], string[i+1]) in dict2:
                out.append('_'.join(string[i:(i+2)]))
                i += 2
            else:
                out.append(string[i])
                i += 1
            if i > len(string) - 2:
                break
        if i < len(string):
            out.extend(string[i:])
    return out
