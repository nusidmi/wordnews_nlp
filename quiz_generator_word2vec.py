#!/usr/local/bin/python
# -*- coding: utf-8 -*-

import word2vec
import pinyin
import numpy as np
import json
from re import compile as _Re
import unicodedata
from math import floor
from mafan import simplify
import codecs
import time

# http://stackoverflow.com/questions/3797746/how-to-do-a-python-split-on-languages-like-chinese-that-dont-use-whitespace
_unicode_chr_splitter = _Re( '(?s)((?:[\ud800-\udbff][\udc00-\udfff])|.)' ).split

MAX_SOUND_DISTANCE = 1

W2V_DIMEN = 100
W2V_FREQUENCY_CUTOFF = 10

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
            self.pinyin_to_chinese_word, \
            self.pinyin_without_tone_to_chinese_word = self.load_word_tags('./quiz_data/english_chinese_translations.csv')
            # print(self.pinyin_to_chinese_word)
            
            # print('pre-compute pinyin distance')
            # self.pinyin_distance = {}
            # for candidate_pinyin in self.pinyin_without_tone_to_chinese_word.keys():
            #     for candidate_pinyin_2 in self.pinyin_without_tone_to_chinese_word.keys():
            #         self.pinyin_distance[candidate_pinyin + "_" + candidate_pinyin_2] = levenshtein(candidate_pinyin, candidate_pinyin_2)
            #     print('done' + candidate_pinyin)

            print('loading chinese dict')
            # data from https://github.com/skishore/makemeahanzi
            self.chinese_word_radical, \
            self.radical_chinese_word, \
            self.chinese_word_decomposition = self.load_chinese_dict('./quiz_data/makemeahanzi/dictionary.txt')
            # print(self.chinese_word_radical)
            # print(self.radical_chinese_word)

            print('loading stroke count')
            # data from http://www.mypolyuweb.hk/~sjpolit/cgi-bin/strokecounter.pl
            self.chinese_word_hex_stroke_count = self.load_chinese_stroke_count('./quiz_data/totalstrokes.txt')

            print('loading character frequency')
            # data from http://lingua.mtsu.edu/chinese-computing/statistics/index.html
            self.chinese_word_cumulative_frequency = self.load_chinese_cumulative_frequency('./quiz_data/CharFreq.txt')

            print('loading word2vec...')
            self.models = {}
            # dimension, frequency cutoff
            # test_params = [[10, 5], [100, 5], [100, 10], [500, 10]]
            test_params = [[W2V_DIMEN, W2V_FREQUENCY_CUTOFF]]
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

    def load_chinese_cumulative_frequency(self, cumulative_frequency_file):
        chinese_word_cumulative_frequency = {}
        with open(cumulative_frequency_file) as f:
            for line in f:
                if line.startswith("/*"):
                    continue
                tokens = line.split('\t')
                character = tokens[1]
                cumulative_frequency = float(tokens[3])
                chinese_word_cumulative_frequency[character] = cumulative_frequency
        # print(chinese_word_cumulative_frequency)
        return chinese_word_cumulative_frequency

    def load_chinese_stroke_count(self, stroke_count_file):
        chinese_word_hex_stroke_count = {}
        with open(stroke_count_file) as f:
            for line in f:
                hex_str, count_str = line.split('\t')
                count = int(count_str.replace('\n', ''))
                chinese_word_hex_stroke_count[hex_str.lower()] = count
        # print(chinese_word_hex_stroke_count)
        return chinese_word_hex_stroke_count

    def load_chinese_dict(self, dict_file):
        chinese_word_radical = {}
        radical_chinese_word = {}
        chinese_word_decomposition = {}
        with open(dict_file) as f:
            for line in f:
                obj = json.loads(line)
                character = obj['character']
                radical = obj['radical']
                decomposition = unicodedata.normalize('NFKC', obj['decomposition'])
                # skip characters that are radicals themselves and cannot be decomposed
                if character == radical:
                    if decomposition == '?':
                        # print(character)
                        continue
                chinese_word_decomposition[character] = split_unicode_chrs(decomposition)[0]
                chinese_word_radical[character] = radical
                if radical not in radical_chinese_word:
                    radical_chinese_word[radical] = set([character])
                else:
                    radical_chinese_word[radical].add(character)
        return chinese_word_radical, radical_chinese_word, chinese_word_decomposition

    # Load the list of english, chinese words and their pos tags from 
    # the dump file of english_chinese_translations tables
    def load_word_tags(self, translation_file):
        print('loading ' + translation_file)
        english_word_tags = dict()
        chinese_word_tags = dict()
        most_frequent_translation = dict()
        pinyin_to_chinese_word = dict()
        pinyin_without_tone_to_chinese_word = dict()

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

                chinese_pinyin_without_tone = remove_numbers(chinese_pinyin)
                if chinese_pinyin_without_tone in pinyin_without_tone_to_chinese_word:
                    pinyin_without_tone_to_chinese_word[chinese_pinyin_without_tone].add(chinese_word)
                else:
                    pinyin_without_tone_to_chinese_word[chinese_pinyin_without_tone] = set([chinese_word])

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
        return english_word_tags, chinese_word_tags, most_frequent_translation, pinyin_to_chinese_word, pinyin_without_tone_to_chinese_word

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
    def get_distractors(self, word, word_pos, test_type, news_category, word_translation, dimension=W2V_DIMEN, cutoff=W2V_FREQUENCY_CUTOFF):
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
        
        # word2vec distractor
        start = time.time()
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
                if distractor_lang == 'chinese':
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
        end = time.time()
        print("word2vec time spent: " + str(end-start))

        if len(distractors_list) < 3:
            print("> no enough valid distractors")
            return []
        print(word)
        print(" ".join([word_translation, pinyin.get(word_translation, format="numerical")]))
        # print("word2vec:")
        # print("> " + ", ".join(map(lambda x: x.split('-')[0], keys)))
        # print("> " + ", ".join(map(lambda x: " ".join([x, pinyin.get(x, format="numerical")]), distractors_list)))
        
        # word2vec non-semantic variant
        start = time.time()
        if len(distractors_list) > 0:
            word2vec_non_semantic = self.get_non_semantic_distractors(distractors_list[0], distractor_lang)
            end = time.time()
            print("word2vec non-semantic time spent: " + str(end-start))
            # print("word2vec non-semantic:")
            # print("> " + " ".join([word2vec_non_semantic[0], pinyin.get(word2vec_non_semantic[0], format="numerical")]))


        # correct translation non-semantic variant
        start = time.time()
        final_ranked_distractors = self.get_non_semantic_distractors(word_translation, distractor_lang)
        end = time.time()
        print("translation non-semantic time spent: " + str(end-start))

        # print("ranked non-semantic:")
        # print("> " + ", ".join(map(lambda x: " ".join([x, pinyin.get(x, format="numerical")]), final_ranked_distractors)))
        
        # use word2vec, word2vec non-semantic variant and orrect translation non-semantic variant as final distractors
        composite_distractors_list = [distractors_list[0], word2vec_non_semantic[0], final_ranked_distractors[0]]

        # return distractors_list
        return composite_distractors_list

    def get_non_semantic_distractors(self, word_translation, distractor_lang='chinese', verbose=True):
        final_ranked_distractors = []
        if distractor_lang == 'chinese':
            # sound
            start = time.time()
            sound_distractors = self.get_sound_distractors(word_translation)
            mixed_sound_distractors = self.mix_distractors(word_translation, sound_distractors)
            final_sound_distractors = self.format_distractors_for_display(mixed_sound_distractors)
            end = time.time()
            print("sound distractor generation time spent: " + str(end-start))
            # mixed_sound_distractors = []

            # radical
            start = time.time()
            radical_distractors = self.get_radical_distractors(word_translation)
            mixed_radical_distractors = self.mix_distractors(word_translation, radical_distractors)
            final_radical_distractors = self.format_distractors_for_display(mixed_radical_distractors)
            end = time.time()
            print("radical distractor generation time spent: " + str(end-start))


            # ranking
            start = time.time()
            all_raw_distractors = list(set(mixed_sound_distractors) | set(mixed_radical_distractors))
            ranked_distractors = self.rank_distractors(word_translation, all_raw_distractors, verbose)
            final_ranked_distractors = self.format_distractors_for_display(ranked_distractors)
            end = time.time()
            print("ranking distractor time spent: " + str(end-start))

        return final_ranked_distractors

    def rank_distractors(self, source_chinese_word, distractors, verbose):
        source_chinese_word_simplified = simplify(source_chinese_word)
        distractors_with_score = []
        for distractor in distractors:
            distractor_str = self.format_distractors_for_display(distractor)
            if simplify(distractor_str) == source_chinese_word_simplified:
                # print("tranditional simplified detected")
                # print(source_chinese_word_simplified)
                continue
            characters = split_unicode_chrs(source_chinese_word)
            if not len(characters) == len(distractor):
                continue
            score_obj = {}
            score_obj['distractor'] = distractor
            # score_obj['mix_score'] = self.get_distractor_mix_score(source_chinese_word, distractor)
            score_obj['sound_score'] = self.get_distractor_sound_score(source_chinese_word, distractor)
            score_obj['radical_score'] = self.get_distractor_radical_score(source_chinese_word, distractor)
            score_obj['decompo_score'] = self.get_distractor_decomposition_score(source_chinese_word, distractor)
            score_obj['stroke_count_score'] = self.get_distractor_stroke_count_score(source_chinese_word, distractor)
            score_obj['frequency_score'] = self.get_distractor_frequency_score(source_chinese_word, distractor)
            score_obj['total_score'] = sum([ \
                # score_obj['mix_score'], \
                score_obj['sound_score'], \
                score_obj['radical_score'], \
                score_obj['decompo_score'], \
                score_obj['stroke_count_score'], \
                score_obj['frequency_score'] \
                ])
            # print(score_obj)
            distractors_with_score.append(score_obj)

        sorted_distractors_with_score = sorted(distractors_with_score, key=lambda k: k['total_score'], reverse=True) 
        
        limit = 3
        if len(sorted_distractors_with_score) < limit:
            limit = len(sorted_distractors_with_score) - 1
        if verbose:
            for i in range(limit):
                print(sorted_distractors_with_score[i])
        return [distractor['distractor'] for distractor in sorted_distractors_with_score[:limit]]

    def get_distractor_frequency_score(self, source_chinese_word, distractors):
        HIGH_FREQUENCY_THRESHOLD = 97
        LOW_FREQUENCY_THRESHOLD = 99
        characters = split_unicode_chrs(source_chinese_word)
        score = 0
        for distractor_character in distractors:
            if distractor_character in self.chinese_word_cumulative_frequency:
                cumulative_frequency = self.chinese_word_cumulative_frequency[distractor_character]
                # print(cumulative_frequency)
                if cumulative_frequency < HIGH_FREQUENCY_THRESHOLD:
                    score += 1
                elif cumulative_frequency > LOW_FREQUENCY_THRESHOLD:
                    score -= 1
            else:
                # print('no frequency data for ' + distractor_character)
                # no frequency data suggests very low frequency, hence penalty
                score -= 1.0
        return score / len(characters)

    def get_distractor_stroke_count_score(self, source_chinese_word, distractors):
        GOOD_DIFFERENCE_THRESHOLD = 0.2
        BAD_DIFFERENCE_THRESHOLD = 0.5
        COMPLEX_CHARACTER_THRESHOLD = 10
        characters = split_unicode_chrs(source_chinese_word)
        score = 0
        for i, character in enumerate(characters):
            character_hex = format(ord(character), 'x')
            if not len(distractors[i]) == 1:
                continue
            distractor_hex = format(ord(distractors[i]), 'x')
            if character_hex in self.chinese_word_hex_stroke_count and distractor_hex in self.chinese_word_hex_stroke_count:
                difference = abs(self.chinese_word_hex_stroke_count[character_hex] - self.chinese_word_hex_stroke_count[distractor_hex])
                percentage_difference = difference / self.chinese_word_hex_stroke_count[character_hex]
                # print(percentage_difference)
                if percentage_difference < GOOD_DIFFERENCE_THRESHOLD:
                    score += 1
                elif percentage_difference > BAD_DIFFERENCE_THRESHOLD:
                    score -= 1
            else:
                print('no stroke count data')
            # print(codecs.encode(character.encode("utf-8"), "hex"))
            # print(character.encode("utf-8").encode("hex"))
        return score / len(characters)

    def get_distractor_decomposition_score(self, source_chinese_word, distractors):
        characters = split_unicode_chrs(source_chinese_word)
        score = 0
        for i, character in enumerate(characters):
            if character in self.chinese_word_decomposition and distractors[i] in self.chinese_word_decomposition:
                if self.chinese_word_decomposition[character] == self.chinese_word_decomposition[distractors[i]]:
                    score += 1
        return score / len(characters)
        

    # def get_distractor_mix_score(self, source_chinese_word, distractors):
    #     characters = split_unicode_chrs(source_chinese_word)
    #     score = 0
    #     for i, character in enumerate(characters):
    #         if character == distractors[i]:
    #             score += 1
    #     return score

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
        return list(map(lambda x: "".join(x), distractors))

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
            score = 3
        elif total_distance_ignore_tone == 0:
            score = 2
        elif total_distance == 1:
            score = 1
        else:
            score = 0
        return score

    def get_sound_distractors(self, source_chinese_word):
        characters = split_unicode_chrs(source_chinese_word)
        distractors = []
        for source_character in characters:
            source_pinyin = pinyin.get(source_character, format="numerical")
            source_pinyin_without_tone = remove_numbers(source_pinyin)
            distractors_for_character = []
            # use pinyin without tone to generate candidate instead of with tone
            # for performance gains, only use tones for ranking
            # for candidate_pinyin in self.pinyin_without_tone_to_chinese_word:
            #     # skip pinyin with very different length for performance gain
            #     if abs(len(candidate_pinyin) - len(source_pinyin_without_tone)) > (MAX_SOUND_DISTANCE + 1):
            #         continue
                
            #     dist_key = source_pinyin_without_tone + "_" + candidate_pinyin
            #     if dist_key in self.pinyin_distance:
            #         distance_ignore_tone = self.pinyin_distance[dist_key]
            #     else:
            #         print('pinyin distance not pre-computed')
            #         distance_ignore_tone = levenshtein(source_pinyin_without_tone, candidate_pinyin)
            #     # distance = levenshtein(source_pinyin, candidate_pinyin)
            #     if distance_ignore_tone <= MAX_SOUND_DISTANCE:
            #         for candidate_chinese_word in self.pinyin_without_tone_to_chinese_word[candidate_pinyin]:
            #             if candidate_chinese_word != source_character:
            #                 distractors_for_character.append(candidate_chinese_word)

            # only use same pinyin to avoid iterating through pinyin list
            if source_pinyin_without_tone in self.pinyin_without_tone_to_chinese_word:
                # print(self.pinyin_without_tone_to_chinese_word[source_pinyin_without_tone])
                for candidate_chinese_word in self.pinyin_without_tone_to_chinese_word[source_pinyin_without_tone]:
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
                    score += 2
        return score / len(characters)

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