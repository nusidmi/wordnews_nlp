#!/usr/local/bin/python
# -*- coding: utf-8 -*-

import pickle
import random

class QuizGeneratorFast(object):
    MIN_SIM = 0.5

    def __init__(self):
        print 'init...'
        self.tag_index = {1:'NN', 2:'VB', 4:'RB', 5:'JJ'}
    
        try:
            print 'loading word category...'
            with open('./quiz_data/news_data4.txt', 'r') as file1, open('./quiz_data/strongwords.txt', 'r') as file2:
                raw_super_dict = pickle.load(file1) # {category: {pos_tag: {word, freq}}}
                raw_strong_dict = pickle.load(file2)

            self.super_dict = raw_super_dict
            self.strong_dict = raw_strong_dict
            self.all_english_distractors = self.convert_dict_without_category(self.super_dict)


            self.english_word_tags, self.chinese_word_tags, self.most_frequent_translation = self.load_word_tags('./quiz_data/english_chinese_translations.csv')
            self.similar_words = self.load_similar_word('./quiz_data/word_lin_distance.txt')
            
        except IOError as e:
            print "[Error in MCQGenerator: while opening files]"


    # similar to convert_dict but remove category information
    def convert_dict_without_category(self, raw_dict):
        new_dict = dict()
        for category, pos_tag_dict in raw_dict.iteritems():
            for pos_tag, word_dict in pos_tag_dict.iteritems():
                if pos_tag not in new_dict:
                    new_dict[pos_tag] = []
                for word, freq in word_dict.iteritems():
                    new_dict[pos_tag].append(word)
        for pos_tag, words in new_dict.iteritems():
            new_dict[pos_tag] = list(set(words))
        return new_dict



    # Load the list of english, chinese words and their pos tags from 
    # the dump file of english_chinese_translations tables
    def load_word_tags(self, translation_file):
        print 'loading ' + translation_file
        english_word_tags = dict()
        chinese_word_tags = dict()
        most_frequent_translation = dict()

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
                pos_tag_idx = int(items[3].strip())
                rank = int(items[4].strip())

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
        return english_word_tags, chinese_word_tags, most_frequent_translation


    def load_similar_word(self, sim_file):
        similar_words = dict()
        with open(sim_file) as f:
            for line in f:
                line = line.strip()
                if line!='':
                    w1, w2, sim = line.split(',')
                    if sim>=QuizGeneratorFast.MIN_SIM:
                        if w1 not in similar_words:
                            similar_words[w1] = []
                        if w2 not in similar_words:
                            similar_words[w2] = []
                        similar_words[w1].append(w2)
                        similar_words[w2].append(w1)
        return similar_words





    # distractor can be either chinese or english
    # news_category denotes the topic of the news, e.g., technology, finance, etc
    # knowledge level decides the difficulty of distractors
    def get_distractors(self, word, word_pos, knowledge_level, news_category):
        knowledge_level = int(knowledge_level)
        print 'generating distractors...'

        if word not in self.similar_words:
            return []
        if knowledge_level<=2:
            return self.get_hard_distractors(word, word_pos, 'english')
        elif knowledge_level>=3:
            return self.get_hard_distractors(word, word_pos, 'chinese')
        else:
            return []


    def get_hard_distractors(self, word, word_pos, distractor_lang):
        distractors_list = []

        nums = set()
        candidate_count = len(self.similar_words[word])
        candidates = self.similar_words[word]

        while len(distractors_list)<3 or len(nums)>=candidate_count:
            n = random.randint(0, candidate_count-1)
            if n not in nums:
                nums.add(n)
                candidate = candidates[n]
                if self.is_same_form(word, word_pos, candidate):
                    print candidate 
                    if distractor_lang=='chinese':
                        key = candidate +'-'+word_pos
                        if key in self.most_frequent_translation:
                            distractors_list.append(self.most_frequent_translation[key])
                    else:
                        distractors_list.append(candidate)
        return distractors_list


    # If the candidate has the same pos tag as the word
    def is_same_form(self, word, word_pos, candidate):
        return word!=candidate and (candidate in self.english_word_tags) and (word_pos in self.english_word_tags[candidate])



if __name__ == "__main__":
    print 'start...'
    #try: 
    generator = QuizGeneratorFast()
    result = generator.get_distractors(word='test', word_pos='NN', knowledge_level=3, news_category=any)
    #except Exception as e:
    #    print "Error in QuizGenerator!"
    #    print e
    
    print ", ".join(result)