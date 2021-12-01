from tokenizer import Tokenizer
from indexer import Indexer

tokenizer = Tokenizer(stopwords_path='', stemmer_enabled=True, size_filter=0,
                      use_positions=True)

indexer = Indexer(tokenizer, 30)
indexer.index_data_source('content/data.tsv.gz')
