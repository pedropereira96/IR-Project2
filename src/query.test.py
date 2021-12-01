from tokenizer import Tokenizer
from indexer import Indexer
from query import Query

term_to_search = input()
query = Query()
query.process_query(term_to_search)