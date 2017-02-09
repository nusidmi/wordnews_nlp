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

MAX_SOUND_DISTANCE = 1

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
        
        sound_distractors = self.get_sound_distractors(word_translation)
        mixed_sound_distractors = self.mix_distractors(word_translation, sound_distractors)
        final_sound_distractors = self.format_distractors_for_display(mixed_sound_distractors)

        radical_distractors = self.get_radical_distractors(word_translation)
        mixed_radical_distractors = self.mix_distractors(word_translation, radical_distractors)
        final_radical_distractors = self.format_distractors_for_display(mixed_radical_distractors)
        # print(sound_distractors)
        # print(mixed_sound_distractors)
        all_raw_distractors = list(set(mixed_sound_distractors) | set(mixed_radical_distractors))
        ranked_distractors = self.rank_distractors(word_translation, all_raw_distractors)
        final_ranked_distractors = self.format_distractors_for_display(ranked_distractors)

        if len(distractors_list) < 3:
            print("> no enough valid distractors")
            return []
        print(word)
        print(" ".join([word_translation, pinyin.get(word_translation, format="numerical")]))
        print("word2vec:")
        print("> " + ", ".join(map(lambda x: x.split('-')[0], keys)))
        print("> " + ", ".join(map(lambda x: " ".join([x, pinyin.get(x, format="numerical")]), distractors_list)))
        
        # print("")
        # print("sound:")
        # print("> " + ", ".join(map(lambda x: " ".join([x, pinyin.get(x, format="numerical")]), final_sound_distractors)))
        
        # print("radical:")
        # print("> " + ", ".join(map(lambda x: " ".join([x, pinyin.get(x, format="numerical")]), final_radical_distractors)))

        print("ranked non-sementic:")
        print("> " + ", ".join(map(lambda x: " ".join([x, pinyin.get(x, format="numerical")]), final_ranked_distractors)))

        return distractors_list

    def rank_distractors(self, source_chinese_word, distractors):
        distractors_with_score = []
        for distractor in distractors:
            score_obj = {}
            score_obj['distractor'] = distractor
            score_obj['mix_score'] = self.get_distractor_mix_score(source_chinese_word, distractor)
            score_obj['sound_score'] = self.get_distractor_sound_score(source_chinese_word, distractor)
            score_obj['radical_score'] = self.get_distractor_radical_score(source_chinese_word, distractor)
            score_obj['total_score'] = sum([score_obj['mix_score'], score_obj['sound_score'], score_obj['radical_score']])
            # print(score_obj)
            distractors_with_score.append(score_obj)

        sorted_distractors_with_score = sorted(distractors_with_score, key=lambda k: k['total_score'], reverse=True) 
        
        limit = 10
        if len(sorted_distractors_with_score) < 10:
            limit = len(sorted_distractors_with_score) - 1
        for i in range(limit):
            print(sorted_distractors_with_score[i])
        return [distractor['distractor'] for distractor in sorted_distractors_with_score[:limit]]

    def get_distractor_mix_score(self, source_chinese_word, distractor):
        characters = split_unicode_chrs(source_chinese_word)
        score = 0
        for i, character in enumerate(characters):
            if character == distractor[i]:
                score += 5
        return score

    def mix_distractors(self, source_chinese_word, distractors):
        # mix with original characters if possible
        characters = split_unicode_chrs(source_chinese_word)
        mixed_distractors = []

        if len(distractors) < 2:
            # only work for distractors with more than 2 characters
            return distractors

        for distractor in distractors:
            mixed_distractors.append(distractor)
            for i, character_distractor in enumerate(distractor):
                distractor_copy = list(distractor)
                distractor_copy[i] = characters[i]
                mixed_distractors.append(tuple(distractor_copy))

        return mixed_distractors

    def format_distractors_for_display(self, distractors):
        return map(lambda x: "".join(x), distractors)

    def get_distractor_sound_score(self, source_chinese_word, distractor):
        characters = split_unicode_chrs(source_chinese_word)
        total_distance = 0
        total_distance_ignore_tone = 0
        score = 0
        for i, character in enumerate(characters):
            source_pinyin = pinyin.get(character, format="numerical")
            candidate_pinyin = pinyin.get(distractor[i], format="numerical")
            distance = levenshtein(source_pinyin, candidate_pinyin)
            distance_ignore_tone = levenshtein(remove_numbers(source_pinyin), remove_numbers(candidate_pinyin))
            total_distance += distance
            total_distance_ignore_tone += distance_ignore_tone
        if total_distance == 0:
            score = 5
        elif total_distance_ignore_tone == 0:
            score = 4
        elif total_distance == 1:
            score = 3
        else:
            score = 0
        return score

    def get_sound_distractors(self, source_chinese_word):
        characters = split_unicode_chrs(source_chinese_word)
        distractors = []
        for source_character in characters:
            source_pinyin = pinyin.get(source_character, format="numerical")
            distractors_for_character = []
            for candidate_pinyin in self.pinyin_to_chinese_word:
                distance_ignore_tone = levenshtein(remove_numbers(source_pinyin), remove_numbers(candidate_pinyin))
                distance = levenshtein(source_pinyin, candidate_pinyin)
                if distance_ignore_tone == 0:
                    for candidate_chinese_word in self.pinyin_to_chinese_word[candidate_pinyin]:
                        if candidate_chinese_word != source_character:
                            distractors_for_character.append(candidate_chinese_word)
                elif distance <= MAX_SOUND_DISTANCE:
                    for candidate_chinese_word in self.pinyin_to_chinese_word[candidate_pinyin]:
                        if candidate_chinese_word != source_character:
                            distractors_for_character.append(candidate_chinese_word)
            distractors.append(distractors_for_character)

        zipped = list(zip(*distractors))
        return zipped

    def get_distractor_radical_score(self, source_chinese_word, distractor):
        characters = split_unicode_chrs(source_chinese_word)
        score = 0
        for i, character in enumerate(characters):
            distractor_character = distractor[i]
            if character in self.chinese_word_radical and distractor_character in self.chinese_word_radical:
                if self.chinese_word_radical[distractor_character] == self.chinese_word_radical[character]:
                    score += 5
        return int(score / len(characters))

    def get_radical_distractors(self, source_chinese_word):
        characters = split_unicode_chrs(source_chinese_word)
        distractors = []
        for source_character in characters:
            if source_character in self.chinese_word_radical:
                radical = self.chinese_word_radical[source_character]
                raw_radical_distractors = list(self.radical_chinese_word[radical])
                raw_radical_distractors.remove(source_character)
                if len(raw_radical_distractors) == 0:
                    print("No radical distractors for Chinese character")
                    return []
                distractors.append(raw_radical_distractors)
        zipped = list(zip(*distractors))
        return zipped

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