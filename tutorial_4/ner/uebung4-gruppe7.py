#! /usr/bin/python3
import sys
import string
import ssl
import math
from typing import List

import pickle
import numpy as np

import nltk
from nltk import SnowballStemmer
from nltk import edit_distance, pos_tag
from nltk.util import ngrams
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize


class Token:
    def __init__(self, value: str, tag: str, pos_tagging: str):
        self.value = value
        self.tag = tag
        self.pos_tagging = pos_tagging


class NERTagger:
    __tag_no_entity = "O"

    def __init__(self, *args):
        if len(args) == 4:
            self.dictionary = args[0]
            self.stopwords_list = args[1]
            self.punctuation = args[2]
            self.pos_tagging = args[3]
        else:
            self.__load_dictionaries()

    def save_dictionaries(self):
        pickle.dump(self.dictionary, open("dictionary.p", "wb"))
        pickle.dump(self.stopwords_list, open("stopwords_list.p", "wb"))
        pickle.dump(self.punctuation, open("punctuation.p", "wb"))
        pickle.dump(self.pos_tagging, open("pos_tagging.p", "wb"))

    def __load_dictionaries(self):
        self.dictionary = pickle.load(open("dictionary.p", "rb"))
        self.stopwords_list = pickle.load(open("stopwords_list.p", "rb"))
        self.punctuation = pickle.load(open("punctuation.p", "rb"))
        self.pos_tagging = pickle.load(open("pos_tagging.p", "rb"))

    def tag_tokens(self, words: List[Token]) -> List[Token]:
        tagged_words = []
        i = 0
        print("words to tag: {}".format(str(len(words))))
        for word in words:
            if self.__check_no_entity(word):
                tagged_words.append(Token(word.value, self.__tag_no_entity, word.pos_tagging))
            else:
                tag = self.__check_rules(word)
                tagged_words.append(Token(word.value, tag, word.pos_tagging))
            i += 1
            if i % 1000 == 0:
                print(i)
        return tagged_words

    def __check_no_entity(self, word: Token) -> bool:
        if word.value in self.stopwords_list:
            return True
        elif word.value in self.punctuation:
            return True
        else:
            return False

    def __check_rules(self, word: Token) -> str:
        keys = list(self.dictionary.keys())

        if word.pos_tagging in self.pos_tagging:
            if word.value in keys:
                return self.dictionary[word.value]
            else:
                tag = self.__tag_no_entity
            # found, tag = self.__check_distance(word, keys)
            # if found:
            #     return tag
            # else:
            #     found, tag = self.__check_word_stems(word, keys)

        else:
            tag = self.__tag_no_entity
        return tag

    def __check_distance(self, word: Token, keys) -> (bool, str):
        # calculate edit-distances
        relevant_keys = [k for k in keys if np.abs(len(k) - len(word.value)) < 4]

        if len(word.value) < 4:
            distance, index = self.__min_edit_distance(word, relevant_keys)

            if distance < round(math.floor(len(word.value)) * 0.9):
                return True, self.dictionary[relevant_keys[index]]
            else:
                return False, self.__tag_no_entity
        else:
            similarity, index = self.__max_jaccard_similarity(word, relevant_keys, 3)

            if similarity > 0.8:
                return True, self.dictionary[relevant_keys[index]]
            else:
                return False, self.__tag_no_entity

    @staticmethod
    def __min_edit_distance(word: Token, keys) -> (float, int):
        # calculate edit-distances
        distances = list(map(lambda x: edit_distance(word.value, x), keys))
        # get index where distance is minimal - conflict resolution happens here as we just pick first index_min
        index_min = min(range(len(distances)), key=distances.__getitem__)
        return distances[index_min], index_min

    @staticmethod
    def __max_jaccard_similarity(word: Token, keys, gram_number) -> (float, int):
        # calculate jaccard-distances
        distances = list(map(lambda x: jaccard_similarity(set(ngrams(word.value, gram_number)),
                                                          set(ngrams(x, gram_number))), keys))
        index_max = max(range(len(distances)), key=distances.__getitem__)
        return distances[index_max], index_max

    def __check_word_stems(self, word, keys) -> (bool, str):
        stemmer = SnowballStemmer("english")
        stemmed_word = stemmer.stem(word.value)
        stemmed_keys = list(map(lambda x: stemmer.stem(x), keys))

        if stemmed_word in stemmed_keys:
            idx = stemmed_keys.index(stemmed_word)
            return True, self.dictionary[keys[idx]]

        return False, self.__tag_no_entity


def jaccard_similarity(label1: set, label2: set) -> float:
    intersection_cardinality = (len(label1.union(label2)) - len(label1.intersection(label2)))
    union_cardinality = len(label1.union(label2))

    if intersection_cardinality > 0 and union_cardinality > 0:
        result = intersection_cardinality / float(union_cardinality)
    else:
        result = 0
    return result


def main():
    if len(sys.argv) < 2:
        input_file = "./../data/uebung4-training.iob"
        train_tagger(input_file)
        print('---- Training for NER-Tagger is finished ----')
    elif len(sys.argv) == 3:
        input_file = sys.argv[1]
        output_file = sys.argv[2]
        tag_tokens(input_file, output_file)
        print('---- NER-Tagger finished, see result in output file ----')
    else:
        print(sys.argv[1].lower())
        print('Oops, something went wrong, please check if you called the script correctly :)')


def train_tagger(input_file):
    gold_std, pos_taggings = build_dict_from_input_file(input_file)
    additional_dictionary = build_additional_dict("./../data/dictionary/human-genenames.txt")
    dictionary = concatenate_dicts(gold_std, additional_dictionary)
    stopwords_list = build_stopwords()
    punctuation = set(string.punctuation)
    tagger = NERTagger(dictionary, stopwords_list, punctuation, pos_taggings)
    tagger.save_dictionaries()


def tag_tokens(input_file, output_file):
    tokens = read_tokens_from_input_file(input_file)
    tagger = NERTagger()
    tagged_list = tagger.tag_tokens(tokens)
    write_annotations_to_file(tagged_list, output_file)


def build_dict_from_input_file(path) -> (dict, set):
    entities_from_file = {}
    pos_taggings_from_file = []
    with open(path, "r", encoding='latin-1') as f:
        for token in get_tokens_from_input_file(f.readlines()):
            if token.tag != "O":
                entities_from_file[token.value] = token.tag
                pos_taggings_from_file.append(token.pos_tagging)
    return entities_from_file, set(pos_taggings_from_file)


def build_additional_dict(path: str) -> dict:
    entities_from_file = {}
    with open(path, "r", encoding='latin-1') as f:
        for token in get_tokens_from_list(f.readlines()):
            entities_from_file[token] = "B-protein"
    return entities_from_file


def concatenate_dicts(gold_std, additional_dict) -> dict:
    set1 = set(list(gold_std.items()))
    set2 = set(list(additional_dict.items()))
    set_conc = set1.union(set2)
    return dict(set_conc)


def build_stopwords() -> set:
    nltk.download('stopwords')
    stopwords_list = []
    path = "./../data/dictionary/english_stop_words.txt"
    with open(path, "r", encoding='latin-1') as f:
        for token in get_tokens_from_list(f.readlines()):
            stopwords_list.append(token)
    return set(stopwords_list).union(set(stopwords.words('english')))


def read_tokens_from_input_file(path) -> List[Token]:
    with open(path, "r", encoding='latin-1') as f:
        tokens = get_tokens_from_input_file(f.readlines())
    return tokens


def write_annotations_to_file(annotations: List[Token], output_file):
    my_file = open(output_file, 'w')
    for token in annotations:
        my_file.write("{}\t{}\n".format(token.value, token.tag))
    my_file.close()


def get_tokens_from_list(lines) -> list:
    tokens = []
    for line in lines:
        if len(line) > 0:
            found_tokens = word_tokenize(line)
            if len(found_tokens) == 1:
                tokens.append(found_tokens[0])
    return tokens


def get_tokens_from_input_file(lines) -> List[Token]:
    words = []
    tags = []
    pos_taggings = []
    tokens = []
    # reading words / tags
    for line in lines:
        if len(line) > 0:
            found_tokens = word_tokenize(line)
            if len(found_tokens) == 2:
                words.append(found_tokens[0])
                tags.append(found_tokens[1])
    # reading pos-tags
    for pos_tagging in pos_tag(words):
        pos_taggings.append(pos_tagging[1])
    # concatenate all
    for i in range(len(words)):
        tokens.append(Token(words[i], tags[i], pos_taggings[i]))
    return tokens


if __name__ == '__main__':
    try:
        _create_unverified_https_context = ssl._create_unverified_context
    except AttributeError:
        pass
    else:
        ssl._create_default_https_context = _create_unverified_https_context
    main()
