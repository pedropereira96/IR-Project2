from tokenizer import Tokenizer
from collections import defaultdict
from typing import DefaultDict, List, Dict, Tuple
import gzip
from csv import reader, writer, field_size_limit, unix_dialect, QUOTE_NONE
from os import path, makedirs
from contextlib import ExitStack
from time import time
from glob import glob

class Indexer:
    tokenizer: Tokenizer
    max_postings_per_temp_block: int
    
    block_posting_count: int
    
    # the positional inverted index needs a different structure to store
    # positions
    inverted_index: DefaultDict[str, List[int]]
    inverted_index_positional: DefaultDict[str, DefaultDict[str, List[int]]]
    
    # contains for each term its document frequency and file number of the
    # final index blocks
    master_index: DefaultDict[str, List[int]]
    
    # contains the correspondence of surrogate keys to natural keys (the 
    # hexadecimal keys from the data source)
    doc_keys: Dict[int, str]
    
    # statistics
    nr_postings: int
    nr_indexed_docs: int
    indexing_time: int
    index_size: int
    vocabulary_size: int
    nr_temp_index_segments: int
    
    def __init__(self, tokenizer: Tokenizer,
                 max_postings_per_temp_block: int = 1000000) -> None:
        field_size_limit(10000000)
        self.tokenizer = tokenizer
        self.max_postings_per_temp_block = max_postings_per_temp_block
        self.block_posting_count = 0
        
        if self.tokenizer.use_positions:
            self.inverted_index_positional = defaultdict(lambda: 
                                                       defaultdict(lambda: []))
        else:
            self.inverted_index = defaultdict(list)
        self.master_index = defaultdict(lambda: [0, 0])
        self.doc_keys = {}
        
        self.initialize_statistics()
    
    def get_inverted_index(self):
        if self.tokenizer.use_positions:
            return self.inverted_index_positional
        else:
            return self.inverted_index
    
    def initialize_statistics(self) -> None:
        self.nr_postings = 0
        self.nr_indexed_docs = 0
        self.indexing_time = 0
        self.index_size = 0
        self.vocabulary_size = 0
        self.nr_temp_index_segments = 0
    
    def get_statistics(self) -> Dict[str, int]:
        statistics = {
            'Number of indexed documents': self.nr_indexed_docs,
            'Number of postings': self.nr_postings,
            'Vocabulary size': self.vocabulary_size,
            'Total indexing time (s)': self.indexing_time,
            'Total index size on disk (MB)': self.index_size,
            'Number of temporary index segments': self.nr_temp_index_segments,
        }

        return statistics

    # tokenize and index document
    def index_doc(self, doc_id, doc_body) -> None:
        tokens = self.tokenizer.tokenize(doc_body)
        
        nr_tokens = len(tokens)
        self.nr_postings += nr_tokens
        self.block_posting_count += nr_tokens
        
        for token in tokens:
            if self.tokenizer.use_positions:
                self.get_inverted_index()[token][doc_id] = tokens[token]
            else:
                self.get_inverted_index()[token].append(doc_id)

    # start indexing a data source, the index files will be placed in the 
    # index/data_source_filename subfolder
    def index_data_source(self, data_source_path: str) -> None:
        self.initialize_statistics()
        
        start_time = time()
        
        index_folder = 'index/' + path.basename(data_source_path).split('.')[0]
        if not path.exists(index_folder):
            makedirs(index_folder)
        
        # define the dialect used by csv.reader to correctly interpret amazon
        # review data files
        dialect = unix_dialect()
        dialect.delimiter = '\t'
        dialect.quoting = QUOTE_NONE
        dialect.escapechar = None
        
        with gzip.open(data_source_path, 
                  mode='rt', encoding='utf8', newline='') as data_file:
            data_reader = reader(data_file, dialect)
            
            # skip the first line (the header)
            data_file.readline()
            
            for doc in data_reader:
                
                # condition to dump index block to disk
                if self.block_posting_count > self.max_postings_per_temp_block:
                    
                    self.nr_temp_index_segments += 1
                    block_file_path = '{}/TempBlock{}.tsv'.format(
                        index_folder, 
                        self.nr_temp_index_segments)
                    self.dump_index_to_disk(block_file_path)

                doc_id, doc_body = self.parse_doc_from_data_source(doc)
                self.index_doc(doc_id, doc_body)
            
            # if the maximum wasn't exceeded and the index isn't empty, make a
            # final dump to disk
            if len(self.get_inverted_index().keys()) > 0:
                
                self.nr_temp_index_segments += 1
                block_file_path = '{}/TempBlock{}.tsv'.format(
                    index_folder, 
                    self.nr_temp_index_segments)
                self.dump_index_to_disk(block_file_path)
            
        self.merge_index_blocks(index_folder)
        
        self.dump_master_index(index_folder)
        
        self.dump_doc_keys(index_folder)
        
        end_time = time()
        
        self.indexing_time = end_time - start_time
        
        file_list = glob(index_folder + '/PostingIndexBlock*.tsv')
        file_list.append(index_folder + '/MasterIndex.tsv')
        file_list.append(index_folder + '/DocKeys.tsv')
        for file_path in file_list:
            self.index_size += path.getsize(file_path)
        self.index_size = self.index_size / 1000000.0
        
        self.vocabulary_size = len(self.doc_keys)

    # merge temporary index blocks and create the final index blocks
    def merge_index_blocks(self, index_blocks_folder: str) -> None:
        file_path_list = []
        last_term_list = []
        
        # temporary dictionary of terms that were read from each temporary
        # index block. The key is the block number while the value is its index
        # as a dictionary
        temp_merge_dict = defaultdict(dict)
        
        # prepare list of block file paths
        for block_number in range(1, self.nr_temp_index_segments + 1):
            
            file_path_list.append(
                '{}/TempBlock{}.tsv'.format(index_blocks_folder, block_number))
            
        with ExitStack() as stack:
            
            block_files = [stack.enter_context(open(file_path)) 
                           for file_path in file_path_list]
            file_readers = [reader(block_file, delimiter='\t') 
                            for block_file in block_files]
            
            # the maximum number of postings read per block is 70% of the total
            # divided by the number of temporary index blocks
            max_postings_read_per_block = int((self.max_postings_per_temp_block 
                                        / self.nr_temp_index_segments) * 0.7)
            
            nr_final_index_blocks = 1
            self.block_posting_count = 0
            nr_merged_postings = 0
            
            while(nr_merged_postings < self.nr_postings):
                
                last_term_list.clear()
                
                # read terms from each temporary index block until the maximum
                # number of postings is exceeded
                for block_nr in range(0, self.nr_temp_index_segments):
                    
                    nr_postings_read = 0
                    while nr_postings_read < max_postings_read_per_block:
                        try:
                            row = next(file_readers[block_nr])
                        except StopIteration:
                            break
                        term, value = self.parse_index_file_row(row)
                        temp_merge_dict[block_nr + 1][term] = value
                        nr_postings_read += len(value)
                    
                    last_term_list.append(term)
                
                # of the last terms read on each block, the lexicographically
                # lowest term will be the last to be merged, while the others
                # remain in memory for the next iteration
                last_term_list.sort()
                last_term_to_merge = last_term_list[0]
                
                # merge on memory all terms in the temporary dictionary of read 
                # terms from each block that are ready to be merged
                for block_nr in range(1, self.nr_temp_index_segments + 1):
                    
                    block_terms = list(temp_merge_dict[block_nr].keys())
                    
                    for term in block_terms:
                        
                        if term <= last_term_to_merge:
                            
                            nr_postings_for_term = len(temp_merge_dict[block_nr][term])
                            self.block_posting_count += nr_postings_for_term
                            if self.tokenizer.use_positions:
                                
                                posting_dict = temp_merge_dict[block_nr].pop(term)
                                for posting in posting_dict:
                                    self.get_inverted_index()[term][posting] = posting_dict[posting]
                            
                            else:
                                
                                self.get_inverted_index()[term] += temp_merge_dict[block_nr].pop(term)
                            
                            nr_merged_postings += nr_postings_for_term
                            self.master_index[term][0] += nr_postings_for_term
                            self.master_index[term][1] = nr_final_index_blocks
                
                # dump to disk if the number of postings on the final index on
                # memory exceeds the maximum per block
                if self.block_posting_count >= self.max_postings_per_temp_block:
                    block_file_path = '{}/PostingIndexBlock{}.tsv'.format(
                        index_blocks_folder, 
                        nr_final_index_blocks)
                    self.dump_index_to_disk(block_file_path)
                    nr_final_index_blocks += 1
            
            # if the maximum wasn't exceeded and the index isn't empty, make a
            # final dump to disk
            if len(self.get_inverted_index().keys()) > 0:
                block_file_path = '{}/PostingIndexBlock{}.tsv'.format(
                    index_blocks_folder, 
                    nr_final_index_blocks)
                self.dump_index_to_disk(block_file_path)

    # add index file to memory
    def read_index_from_disk(self, index_file_path: str):
        with open(index_file_path, 
                  mode='rt', encoding='utf8', newline='') as data_file:
            data_reader = reader(data_file, delimiter='\t')

            for row in data_reader:
                term, value = self.parse_index_file_row(row)
                self.get_inverted_index()[term] = value

    # process the contents of an index file for indexing in memory again
    def parse_index_file_row(self, row: List[str]):
        term = row[0]
        posting_str_list = row[1:]
        if self.tokenizer.use_positions:
            value = defaultdict(lambda: [])
            for posting_str in posting_str_list:
                doc_id, positions_str = posting_str.split(':')
                positions_list = list(map(int, 
                                          positions_str.split(',')))
                value[doc_id] = positions_list
        else:
            value = list(map(int, posting_str_list))
        return term, value

    # process the contents of an Amazon review data file for indexing. 
    # Fields other than reviewid are concatenated separated by spaces, as the
    # body of the document
    def parse_doc_from_data_source(self, doc: List[str]) -> Tuple[str, str]:
        doc_id = doc[2]
        doc_body = '{} {} {}'.format(doc[5], doc[12], doc[13])
        
        self.nr_indexed_docs += 1
        self.doc_keys[self.nr_indexed_docs] = doc_id

        return self.nr_indexed_docs, doc_body

    # process the contents of a term from the index on memory for storing on
    # disk
    def parse_index_term_for_dumping(self, term: str) -> List[str]:
        row = [term]
        
        for posting in self.get_inverted_index()[term]:
            if self.tokenizer.use_positions:
                positions_str = ','.join([str(i) for i in 
                                  self.get_inverted_index()[term][posting]])
                row.append(str(posting) + ':' + positions_str)
            else:
                row.append(str(posting))
        
        return row

    # the resulting TSV file on disk will have a term on the first column of
    # each row, and a posting on each subsequent column, as its document ID.
    # When positions are being considered for the index, each posting will be a
    # string containing the document ID followed by the character ':' and the
    # list of positions on the document separated by ','
    def dump_index_to_disk(self, file_path: str) -> None:
        with open(file_path, mode='wt', encoding='utf8', 
                  newline='') as block_file:
            block_writer = writer(block_file, delimiter='\t')
            
            ordered_terms = list(self.get_inverted_index().keys())
            list.sort(ordered_terms)
            for block_term in ordered_terms:
                block_writer.writerow(
                    self.parse_index_term_for_dumping(block_term))
        
        self.block_posting_count = 0
        
        self.get_inverted_index().clear()
    
    # the resulting TSV file on disk will have a term on the first column of
    # each row, followed on each column by its document frequency and the block 
    # number of the final index where it can be found
    def dump_master_index(self, index_folder_path):
        file_path = index_folder_path + '/MasterIndex.tsv'
        
        with open(file_path, mode='wt', encoding='utf8', 
                  newline='') as master_index_file:
            file_writer = writer(master_index_file, delimiter='\t')
            keys = list(self.master_index.keys())
            list.sort(keys)
            keys.sort()
            for key in keys:
                file_writer.writerow([key, 
                                      self.master_index[key][0],
                                      self.master_index[key][1]])

    # the resulting TSV file on disk will have the surrogate key on each row,
    # followed by the natural key (hexadecimal) on the next column
    def dump_doc_keys(self, index_folder_path: str) -> None:
        file_path = index_folder_path + '/DocKeys.tsv'
        
        with open(file_path, mode='wt', encoding='utf8', 
                  newline='') as doc_keys_file:
            file_writer = writer(doc_keys_file, delimiter='\t')
            # ordered_terms = list(self.get_inverted_index().keys())
            # list.sort(ordered_terms)
            for key in self.doc_keys:
                file_writer.writerow([key, self.doc_keys[key]])
