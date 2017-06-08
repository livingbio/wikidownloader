from parser

workdir /opt 
run pip install sklearn gensim
run apt-get install libopenblas-base
run pip install git+https://github.com/banyh/PyStanfordNLP


run git clone https://github.com/ektormak/Lyssandra.git
add lyssa.conf /opt/Lyssandra/config.yml
workdir /opt/Lyssandra
run python setup.py install
