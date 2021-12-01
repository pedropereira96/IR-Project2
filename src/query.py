from tokenizer import Tokenizer
import csv
from os import path
from collections import defaultdict

class Query:
    dock_keys = {}
    doc_keys_folder_path: str
    master_index_folder_path: str
    master_index: dict
    tokenize: Tokenizer      
    word_compressed: str  

    def __init__(self, data_path , stopwords_path = '', stemmer_enabled = True,
                 size_filter = 0, use_positions = False):
        # doc keys file
        self.dock_keys= {}
        self.doc_keys_folder_path = ('index/' 
                                     + path.basename(data_path).split('.')[0] 
                                     + '/DocKeys.tsv')

        # master index file
        self.master_index_folder_path = ('index/' 
                                         + path.basename(data_path).split('.')[0] 
                                         + '/MasterIndex.tsv')

        self.master_index = defaultdict(lambda: defaultdict(dict))

        self.tokenize = Tokenizer(stopwords_path = '', stemmer_enabled = True, 
                                  size_filter = 0)

        self.word_compressed = ''  

    def read_doc_keys(self):
        with open(self.doc_keys_folder_path, 'r') as file:
            filecontent = csv.reader(file)
            for row in filecontent:
                values = row[0].split(":")
                self.dock_keys[values[0]]=values[1]
        print(self.dock_keys)

    def read_master_index(self):
        with open(self.master_index_folder_path, 'r') as file:
            filecontent = csv.reader(file, delimiter='\t')
            for row in filecontent:
                term = row[0]
                number = row[1]
                file_path = row[2]
                self.master_index[term]['doc_freq'] = number
                self.master_index[term]['file_path'] = file_path

    def term_tokenizer(self, term):
        return self.tokenize.tokenize(input_string = term)

    def process_query(self, term:str):
        
        self.word_compressed = list(self.term_tokenizer(term))
        
        for word in self.word_compressed:
            print("Inserted term: " + term)
            print("Normalized term: " + word)
            print("Document frequency: " + str("Not found" if self.master_index[word]['doc_freq']=={} else self.master_index[word]['doc_freq']))
            print("Main index block number for term: "+ str("Not found" if self.master_index[word]['file_path']=={} else self.master_index[word]['file_path']))