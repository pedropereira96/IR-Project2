import sys
from tokenizer import Tokenizer
from indexer import Indexer
from query import Query
from argparse import ArgumentParser
from os import path
from time import time

class Main:
    data_path: str
    stopwords_path: str
    minimum_word_size: int
    stemmer_enabled: bool
    use_positions: bool
    parser: ArgumentParser
    tokenizer: Tokenizer     
    indexer: Indexer

    def __init__(self):
        # default arguments
        self.data_path = ""
        self.stopwords_path = 'content/stopwords.txt'
        self.minimum_word_size = 3
        self.stemmer_enabled = True
        self.use_positions = False
        self.max_post = 1000000
        self.parser = ArgumentParser()
        self.tokenizer = Tokenizer(stopwords_path = self.stopwords_path, 
                                stemmer_enabled = self.stemmer_enabled, 
                                size_filter = self.minimum_word_size, 
                                use_positions = self.use_positions)
        self.indexer = Indexer(tokenizer = self.tokenizer, max_postings_per_temp_block = self.max_post)
 
    def parse_args(self):
        parser = ArgumentParser()
        # path to new data file
        parser.add_argument("--data_path", help="Set the path to the data", required=True, 
                            type=str, metavar="(path to data file (.gz))")
        # do not use stopwords list
        parser.add_argument("--nostopwords", help="Disable stop words",
                            action="store_false")
        # path to new stopwords
        parser.add_argument("--stopwords", help="Set the path to stop words List", 
                            type=str, metavar="(path to stopwords list)")
        # minimum word size
        parser.add_argument("--word_size", help="Set the maximum for the word size filter", 
                            type=int, metavar="(integer number)")
        # no minimum word size
        parser.add_argument("--no_word_size", help="Disable word size filter",
                            action="store_false")
        # do not use stemmer
        parser.add_argument("--no_stemmer", help="Disable stemmer",
                            action="store_false")
        # do not use positions
        parser.add_argument("--use_positions", help="Enable positions indexing",
                            action="store_true")
        # maximum postings per block for the SPIMI
        parser.add_argument("--max_post", help="Set the maximum postings per block",
                            type=int)
        return parser

    def check_arguments(self, parser, args):

        if args.data_path:
            self.data_path = args.data_path
            if not path.exists(self.data_path) or not self.data_path.endswith('.gz'):
                print("File does not exist or does not have the correct extension! ")
                print(parser.parse_args(['-h']))
                sys.exit()
        
        # if stopwords are disabled but a stopwords path is still defined by the user
        if (not args.nostopwords) and (args.stopwords != None):
            print(parser.parse_args(['-h']))
            sys.exit()

        if not args.nostopwords:
            self.stopwords_path = ''

        if args.stopwords:
            self.stopwords_path = args.stopwords

        # if word size is disabled but a size is still defined by the user
        if (not args.no_word_size) and (args.word_size != None):
            print(parser.parse_args(['-h']))
            sys.exit()
        
        if args.word_size:
            self.minimum_word_size = args.word_size
 
        if not args.no_word_size:
            self.minimum_word_size = 0
        
        if not args.no_stemmer:
            self.stemmer_enabled = False

        if not args.use_positions:
            self.use_positions = True 

        if args.max_post:
            self.max_post = args.max_post     

    def main(self):

        # create and check all arguments
        parser = self.parse_args()
        args = parser.parse_args()
        self.check_arguments(parser, args)

        self.indexer.index_data_source(data_source_path = self.data_path)

        statistics = self.indexer.get_statistics()

        for statistic in statistics:
            print(statistic + ": " + str(statistics[statistic]))

        query = Query(stopwords_path = self.stopwords_path, 
                        stemmer_enabled = self.stemmer_enabled, 
                        size_filter = self.minimum_word_size, 
                        use_positions = self.use_positions,
                        data_path = self.data_path)
        
        initial_time = time()
        
        query.read_master_index()
      
        print("Time to set up a query searcher (s): " + str(time() - initial_time) )
        print("Search term:")
        word_to_search = input()
        while word_to_search != '0':
            
            query.process_query(word_to_search)
            print("Search term ( 0 to exit ):")
            word_to_search = input()

if __name__ == "__main__":    
    
    Main().main()
