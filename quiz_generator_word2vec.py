#!/usr/local/bin/python
# -*- coding: utf-8 -*-

import word2vec

class QuizGeneratorW2V(object):
    def __init__(self):
        print 'init...'
        self.tag_index = {1:'NN', 2:'VB', 4:'RB', 5:'JJ'}
    
        try:
            print 'loading translation...'
            self.english_word_tags, self.chinese_word_tags, self.most_frequent_translation = self.load_word_tags('./quiz_data/english_chinese_translations.csv')
            
            print 'loading word2vec...'
            # self.model = self.load_word2vec('./quiz_data/text8.bin')
            self.model = self.load_word2vec('./quiz_data/text8_10.bin')
            
        except IOError as e:
            print "[Error in MCQGenerator: while opening files]"

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


    def load_word2vec(self, word2vec_binary):
        model = word2vec.load(word2vec_binary)
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
    def get_distractors(self, word, word_pos, test_type, news_category, word_translation):
        test_type = int(test_type)
        print 'generating distractors...'

        if word not in self.model:
            print 'word ' + word + ' is out of dictionary'
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
                        print(self.most_frequent_translation[key])
                        print(type(self.most_frequent_translation[key]))
                        print(word_translation)
                        print(type(word_translation))
                        if type(self.most_frequent_translation[key]) != type(word_translation):
                            print("different types")
                        if self.most_frequent_translation[key] != word_translation:
                            distractors_list.append(self.most_frequent_translation[key])
                    else:
                        # print "no translation for " + key
                        pass
                else:
                    distractors_list.append(candidate_word)
            n += 1

        if len(distractors_list) < 3:
            print("no enough valid distractors")
            return []

        return distractors_list

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

if __name__ == "__main__":
    print 'start...'
    #try: 
    word = 'key'
    word_pos = 'JJ'
    key = word +'-'+word_pos
    
    generator = QuizGeneratorW2V()
    result = generator.get_distractors(word=word, word_pos=word_pos, test_type=2, news_category=any, word_translation=generator.most_frequent_translation[key])
    #except Exception as e:
    #    print "Error in QuizGenerator!"
    #    print e
    
    print ", ".join(result)