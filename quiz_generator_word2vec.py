#!/usr/local/bin/python
# -*- coding: utf-8 -*-

import word2vec
import pinyin
import numpy as np
import json
from re import compile as _Re
import unicodedata

# http://stackoverflow.com/questions/3797746/how-to-do-a-python-split-on-languages-like-chinese-that-dont-use-whitespace
_unicode_chr_splitter = _Re( '(?s)((?:[\ud800-\udbff][\udc00-\udfff])|.)' ).split
def split_unicode_chrs(text):
  return [ chr for chr in _unicode_chr_splitter( text ) if chr ]

class QuizGeneratorW2V(object):
    def __init__(self):
        print('init...')
        self.tag_index = {1:'NN', 2:'VB', 4:'RB', 5:'JJ'}
    
        try:
            print('loading translation...')
            self.english_word_tags, \
            self.chinese_word_tags, \
            self.most_frequent_translation, \
            self.pinyin_to_chinese_word = self.load_word_tags('./quiz_data/english_chinese_translations.csv')
            # print(self.pinyin_to_chinese_word)
            
            print('loading chinese dict')
            self.chinese_word_radical, \
            self.radical_chinese_word = self.load_chinese_dict('./quiz_data/makemeahanzi/dictionary.txt')
            # print(self.chinese_word_radical)
            # print(self.radical_chinese_word)

            print('loading word2vec...')
            self.models = {}
            # dimension, frequency cutoff
            # test_params = [[10, 5], [100, 5], [100, 10], [500, 10]]
            test_params = [[500, 10]]
            for test_param in test_params:
                model_key = self.get_model_key(test_param[0], test_param[1])
                self.models[model_key] = self.load_word2vec('./quiz_data/text8_{0}.bin'.format(model_key))
            # self.model = self.load_word2vec('./quiz_data/text8.bin')
            # self.model = self.load_word2vec('./quiz_data/text8_10.bin')
            # self.model = self.load_word2vec('./quiz_data/text8_500_min_10.bin')
            
        except IOError as e:
            print("[Error in MCQGenerator: while opening files]")

    def get_model_key(self, dimension, cutoff):
        return str(dimension) + '_' + str(cutoff)

    def load_chinese_dict(self, dict_file):
        chinese_word_radical = {}
        radical_chinese_word = {}
        with open(dict_file) as f:
            for line in f:
                obj = json.loads(line)
                character = obj['character']
                radical = obj['radical']
                # skip characters that are radicals themselves and cannot be decomposed
                if character == radical:
                    if unicodedata.normalize('NFKC', obj['decomposition']) == '?':
                        # print(character)
                        continue
                chinese_word_radical[character] = radical
                if radical not in radical_chinese_word:
                    radical_chinese_word[radical] = set([character])
                else:
                    radical_chinese_word[radical].add(character)
        
        return chinese_word_radical, radical_chinese_word

    # Load the list of english, chinese words and their pos tags from 
    # the dump file of english_chinese_translations tables
    def load_word_tags(self, translation_file):
        print('loading ' + translation_file)
        english_word_tags = dict()
        chinese_word_tags = dict()
        most_frequent_translation = dict()
        pinyin_to_chinese_word = dict()

        with open(translation_file) as f:
            for line in f:
                line = line.strip()
                if line=='':
                    continue
                items = line.split(',')
                #if len(items)>3:
                #    print line
                english_word = items[len(items)-3]
                chinese_word = items[len(items)-2]
                chinese_pinyin = items[len(items)-1].replace(" ", "")
                pos_tag_idx = int(items[3].strip())
                rank = int(items[4].strip())

                if chinese_pinyin in pinyin_to_chinese_word:
                    pinyin_to_chinese_word[chinese_pinyin].add(chinese_word)
                else:
                    pinyin_to_chinese_word[chinese_pinyin] = set([chinese_word])

                if pos_tag_idx not in self.tag_index:
                    #print english_word + ' ' + chinese_word + ' ' + str(pos_tag_idx) + ' ' + str(rank)
                    continue
                else:
                    pos_tag = self.tag_index[pos_tag_idx]

                if english_word in english_word_tags:
                    english_word_tags[english_word].add(pos_tag)
                else:
                    english_word_tags[english_word] = set([pos_tag])

                if chinese_word in chinese_word_tags:
                    chinese_word_tags[chinese_word].add(pos_tag)
                else:
                    chinese_word_tags[chinese_word] = set([pos_tag]) 

                if rank==0:
                    #print english_word+'-'+pos_tag + ': ' + chinese_word
                    most_frequent_translation[english_word+"-"+pos_tag] = chinese_word
        return english_word_tags, chinese_word_tags, most_frequent_translation, pinyin_to_chinese_word


    def load_word2vec(self, word2vec_binary):
        model = word2vec.load(word2vec_binary)
        print("vocab: {0} dimension: {1}".format(model.vectors.shape[0], model.vectors.shape[1]))
        return model

    def generate_similar_words(self, word):
        word = word.lower()
        similar_words = []
        # print(word)
        if word in self.model:
            indexes, metrics = self.model.cosine(word, n=50) # n is number of similar words to retrieve
            similar_words = self.model.generate_response(indexes, metrics).tolist()
        else:
            print('out of dict')
        # for similar_word in similar_words:
        #     print('word: ' + str(similar_word[0]) + ' score: ' + str(similar_word[1]))
        return similar_words

    # distractor can be either chinese or english
    # news_category denotes the topic of the news, e.g., technology, finance, etc
    # test_type decides the langauge of distractors
    def get_distractors(self, word, word_pos, test_type, news_category, word_translation, dimension=10, cutoff=5):
        test_type = int(test_type)
        model_key = self.get_model_key(dimension, cutoff)
        self.model = self.models[model_key]
        # print 'generating distractors...'
        if word not in self.model:
            print('word ' + word + ' is out of dictionary')
            return []
        if test_type<=1:
            return self.get_hard_distractors(word, word_pos, 'english', word_translation)
        elif test_type>=2:
            return self.get_hard_distractors(word, word_pos, 'chinese', word_translation)
        else:
            return []


    def get_hard_distractors(self, word, word_pos, distractor_lang, word_translation):
        distractors_list = []
        # print(word)
        # print(word_translation)
        candidates = self.generate_similar_words(word)
        # print(candidates)
        no_of_candidates = len(candidates)
        keys = []
        n = 0
        while len(distractors_list) < 3 and n < no_of_candidates:

            # candidates is a list of tuples of word and similar score, ordered by similar score
            # candidate[0] is word, candidate[1] is similarity score
            candidate = candidates[n]
            candidate_word = candidates[n][0]
            if self.is_same_form(word, word_pos, candidate_word):
                if distractor_lang=='chinese':
                    key = candidate_word +'-'+word_pos
                    if key in self.most_frequent_translation:
                        # print "found translation for " + key
                        if type(self.most_frequent_translation[key]) != type(word_translation):
                            print("different types")
                        if self.most_frequent_translation[key] != word_translation:
                            keys.append(key)
                            distractors_list.append(self.most_frequent_translation[key])
                    else:
                        # print "no translation for " + key
                        pass
                else:
                    distractors_list.append(candidate_word)
            n += 1

        # similar sound distractors
        
        sound_distractors_list, distractors_ignore_tone = self.get_sound_distractors(word_translation)
        sound_distractors_list_0 = sound_distractors_list[0]
        sound_distractors_list_1 = sound_distractors_list[1]
        sound_distractors_list_2 = sound_distractors_list[2]
        radical_distractors = self.get_radical_distractors(word_translation)
        radical_sound_distractors = self.get_radical_sound_distractors(word_translation)

        if len(distractors_list) < 3:
            print("> no enough valid distractors")
            return []
        print(word)
        print(" ".join([word_translation, pinyin.get(word_translation, format="numerical")]))
        print("word2vec:")
        print("> " + ", ".join(map(lambda x: x.split('-')[0], keys)))
        print("> " + ", ".join(map(lambda x: " ".join([x, pinyin.get(x, format="numerical")]), distractors_list)))
        
        print("")
        print("sound similarity 0:")
        print("> " + ", ".join(map(lambda x: " ".join([x, pinyin.get(x, format="numerical")]), sound_distractors_list_0)))
        
        print("sound similarity 0 ignore tone:")
        print("> " + ", ".join(map(lambda x: " ".join([x, pinyin.get(x, format="numerical")]), distractors_ignore_tone)))
        
        print("sound similarity 1:")
        print("> " + ", ".join(map(lambda x: " ".join([x, pinyin.get(x, format="numerical")]), sound_distractors_list_1)))
        
        print("sound similarity 2:")
        print("> " + ", ".join(map(lambda x: " ".join([x, pinyin.get(x, format="numerical")]), sound_distractors_list_2)))
        
        print("radical:")
        print("> " + ", ".join(map(lambda x: " ".join([x, pinyin.get(x, format="numerical")]), radical_distractors)))

        print("radical and sound similarity 2 ignore tone:")
        print("> " + ", ".join(map(lambda x: " ".join([x, pinyin.get(x, format="numerical")]), radical_sound_distractors)))
        radical_sound_distractors

        return distractors_list

    def get_radical_distractors(self, source_chinese_word):
        characters = split_unicode_chrs(source_chinese_word)
        distractors = []
        for character in characters:
            if character in self.chinese_word_radical:
                radical = self.chinese_word_radical[character]
                raw_radical_distractors = list(self.radical_chinese_word[radical])
                raw_radical_distractors.remove(character)
                if len(raw_radical_distractors) == 0:
                    print("No radical distractors for Chinese character")
                    return []
                distractors.append(raw_radical_distractors)
        zipped = list(zip(*distractors))[:5]
        return map(lambda x: "".join(x), zipped)

    def get_radical_sound_distractors(self, source_chinese_word):
        characters = split_unicode_chrs(source_chinese_word)
        distractors = []
        for character in characters:
            if character not in self.chinese_word_radical:
                distractors = []
                print("Chinese character out of dictionary")
                break
            if character in self.chinese_word_radical:
                radical = self.chinese_word_radical[character]
                raw_radical_distractors = list(self.radical_chinese_word[radical])
                raw_radical_distractors.remove(character)
                filtered_distractors = self.filter_distractors_by_sound_similarity(character, raw_radical_distractors, 0.4)
                if len(filtered_distractors) == 0:
                    distractors = []
                    print("No radical distractors for Chinese character")
                    break
                distractors.append(filtered_distractors)

        # mix with original characters if possible
        if len(distractors) >= 2:
            for i, character in enumerate(characters):
                for j in range(len(distractors)):
                    if i == j:
                        # insert orginal character
                        distractors[j].insert(0, character)
                    else:
                        # insert duplicated first distractor
                        distractors[j].insert(0, distractors[j][i])
        zipped = list(zip(*distractors))[:5]
        return map(lambda x: "".join(x), zipped)

    def filter_distractors_by_sound_similarity(self, source_chinese_character, raw_chinese_distractors, max_diff):
        filtered = []
        for candidate in raw_chinese_distractors:
            source_pinyin = pinyin.get(source_chinese_character, format="numerical")
            candidate_pinyin = pinyin.get(candidate, format="numerical")
            distance_ignore_tone = levenshtein(remove_numbers(source_pinyin), remove_numbers(candidate_pinyin))
            # print(source_pinyin)
            # print(candidate)
            # print(candidate_pinyin)
            # print(distance_ignore_tone)
            # print(distance_ignore_tone / len(source_pinyin))
            if distance_ignore_tone / len(source_pinyin) <= max_diff:
                filtered.append(candidate)
        return filtered

    def get_sound_distractors(self, source_chinese_word):
        source_pinyin = pinyin.get(source_chinese_word, format="numerical")
        # distractors with distance 0, 1, 2
        distractors_by_distance = [[], [], []]
        distractors_ignore_tone = []

        for candidate_pinyin in self.pinyin_to_chinese_word:
            distance_ignore_tone = levenshtein(remove_numbers(source_pinyin), remove_numbers(candidate_pinyin))
            if distance_ignore_tone == 0:
                for candidate_chinese_word in self.pinyin_to_chinese_word[candidate_pinyin]:
                    if candidate_chinese_word != source_chinese_word and len(distractors_ignore_tone) < 3:
                        distractors_ignore_tone.append(candidate_chinese_word)
            distance = levenshtein(source_pinyin, candidate_pinyin)
            if distance <= 2:
                for candidate_chinese_word in self.pinyin_to_chinese_word[candidate_pinyin]:
                    if candidate_chinese_word != source_chinese_word and len(distractors_by_distance[distance]) < 3:
                        distractors_by_distance[distance].append(candidate_chinese_word)

        return distractors_by_distance, distractors_ignore_tone

    # If the candidate has the same pos tag as the word
    def is_same_form(self, word, word_pos, candidate):
        # if candidate not in self.english_word_tags:
        #     print candidate + " - no tag info"
        # elif word_pos not in self.english_word_tags[candidate]:
        #     print candidate + " - no corresponding tag " + word_pos
        # else:
        #     print candidate + " - successful match"
        # print "___\n"
        return word!=candidate and (candidate in self.english_word_tags) and (word_pos in self.english_word_tags[candidate])

def remove_numbers(s):
    return ''.join(i for i in s if not i.isdigit())

# https://en.wikibooks.org/wiki/Algorithm_Implementation/Strings/Levenshtein_distance#Python
def levenshtein(source, target):
    if len(source) < len(target):
        return levenshtein(target, source)

    # So now we have len(source) >= len(target).
    if len(target) == 0:
        return len(source)

    # We call tuple() to force strings to be used as sequences
    # ('c', 'a', 't', 's') - numpy uses them as values by default.
    source = np.array(tuple(source))
    target = np.array(tuple(target))

    # We use a dynamic programming algorithm, but with the
    # added optimization that we only need the last two rows
    # of the matrix.
    previous_row = np.arange(target.size + 1)
    for s in source:
        # Insertion (target grows longer than source):
        current_row = previous_row + 1

        # Substitution or matching:
        # Target and source items are aligned, and either
        # are different (cost of 1), or are the same (cost of 0).
        current_row[1:] = np.minimum(
                current_row[1:],
                np.add(previous_row[:-1], target != s))

        # Deletion (target grows shorter than source):
        current_row[1:] = np.minimum(
                current_row[1:],
                current_row[0:-1] + 1)

        previous_row = current_row

    return previous_row[-1]

if __name__ == "__main__":
    print('start...')
    #try: 
    word = 'key'
    word_pos = 'JJ'
    key = word +'-'+word_pos
    
    generator = QuizGeneratorW2V()
    result = generator.get_distractors(word=word, word_pos=word_pos, test_type=2, news_category=any, word_translation=generator.most_frequent_translation[key])
    #except Exception as e:
    #    print "Error in QuizGenerator!"
    #    print e
    
    print(", ".join(result))