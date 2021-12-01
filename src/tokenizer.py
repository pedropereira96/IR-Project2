from re import sub
from Stemmer import Stemmer
from collections import defaultdict
from typing import List, Dict, Set

class Tokenizer:
    stopwords: Set[str]
    stemmer_enabled: bool
    size_filter: int
    stemmer: Stemmer
    use_positions: bool
    
    # An empty string as a stopwords_path disables stopwords.
    # A size_filter of 0 disables size filter
    def __init__(self, stopwords_path: str = 'content/stopwords.txt', 
                 stemmer_enabled: bool = True, size_filter: int = 3,
                 use_positions: bool = False) -> None:
        
        if stopwords_path != '':
            with open(stopwords_path, 'r') as stopwords_file:
                self.stopwords = set(stopwords_file.read().split('\n'))
        else:
            self.stopwords = set()

        self.stemmer_enabled = stemmer_enabled
        if stemmer_enabled:
            self.stemmer = Stemmer('english')
        
        self.size_filter = size_filter
        
        self.use_positions = use_positions
        
    def tokenize(self, input_string: str):
        word_list = self.preprocess_input(input_string)
        
        if self.use_positions:
            tokens = self.stem_and_filter_words_with_positions(word_list)
        else:
            tokens = self.stem_and_filter_words(word_list)
        
        return tokens
    
    # The input string has all HTML line breaks and symbols replaced by spaces,
    # and words that start or end with numbers are then removed. It is then
    # made all lower case and split into substrings using the spaces to get the 
    # words
    def preprocess_input(self, input_string: str) -> List[str]:
        word_list = sub("<br />|[^0-9a-zA-Z]+", " ", input_string)
        word_list = sub("[^a-zA-Z ]+[a-zA-Z]+|[a-zA-Z]+[^a-zA-Z ]+", "", word_list).lower().split(" ")
        
        return word_list
    
    # Returns a set of tokens.
    # It makes a single iteration over all words to apply the stopword filter, 
    # the size filter and the stemmer, to avoid multiple passes
    def stem_and_filter_words(self, word_list: List[str]) -> Set[str]:
        tokens = set()

        for i in range(0, len(word_list)):
            if word_list[i] not in self.stopwords:
                if len(word_list[i]) > self.size_filter:
                    if self.stemmer_enabled:
                        token = self.stemmer.stemWord(word_list[i])
                    else:
                        token = word_list[i]
                    tokens.add(token)
        
        return tokens
    
    # Returns a dictionary of tokens associated with lists of respective 
    # positions in the document.
    # It makes a single iteration over all words to apply the stopword filter, 
    # the size filter and the stemmer, to avoid multiple passes
    def stem_and_filter_words_with_positions(self, 
                                 word_list: List[str]) -> Dict[str, List[int]]:
        tokens = defaultdict(lambda: [])

        for i in range(0, len(word_list)):
            if word_list[i] not in self.stopwords:
                if len(word_list[i]) > self.size_filter:
                    if self.stemmer_enabled:
                        token = self.stemmer.stemWord(word_list[i])
                    else:
                        token = word_list[i]
                    tokens[token].append(i)
        
        return tokens
