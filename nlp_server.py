import json
import time

from flask import Flask
from flask import request
from flask import jsonify
from flask_cors import CORS, cross_origin

import nltk
from nltk.tokenize import sent_tokenize
from nltk import word_tokenize
from nltk.tokenize.treebank import TreebankWordTokenizer

#from quiz_generator import QuizGenerator
from quiz_generator_fast import QuizGeneratorFast
from quiz_generator_word2vec import QuizGeneratorW2V


app = Flask(__name__)
app.config['DEBUG'] = True
CORS(app)

nltk.data.path.append('./nltk_data')

sentence_segmenter = nltk.data.load('tokenizers/punkt/english.pickle')
word_tokenizer = TreebankWordTokenizer()
pos_tagger = nltk.data.load(nltk.tag._POS_TAGGER)

# generator = QuizGenerator()
generator = QuizGeneratorFast()
generator_w2v = QuizGeneratorW2V()


@app.route("/")
def index():
    print 'index'
    print request
    return "index!"
    
    
def segment_sentence(text):
    text = text.replace("\n", " ")
    sent_tokenize_list = sentence_segmenter.tokenize(text)
    return sent_tokenize_list


def tokenize_words(sentence):
    tokens = nltk.word_tokenize(sentence)                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                               
    return tokens
    

# Return format: [('word', 'tag'), ('word', 'tag'),...]
# NLTK uses Penn Treebank Tag Set
def pos_tag(text):
    tokenized_text = word_tokenizer.tokenize(text)
    word_tags = pos_tagger(tokenized_text)
    return word_tags


def process_pipeline(text):
    start = time.time()
    result = []
    
    sentences = sentence_segmenter.tokenize(text)
    for sentence in sentences:
        tokenized_text = word_tokenizer.tokenize(sentence)
        word_tag_list = pos_tagger.tag(tokenized_text)
        
        words = []
        tags = []
        for word, tag in word_tag_list:
            words.append(word)
            tags.append(tag)
            
        rst_sent = {}
        rst_sent['sent'] = sentence
        rst_sent['words'] = ' '.join(words)
        rst_sent['tags'] = ' '.join(tags)
        result.append(rst_sent)
    
    end = time.time()
    print (end-start)
    return result


def process_pipeline_batch(text):
    start = time.time()
    result = []
    
    sentences = sentence_segmenter.tokenize(text)
    tokenized_text = word_tokenizer.tokenize_sents(sentences)
    word_tag_lists = pos_tagger.tag_sents(tokenized_text)

    for index, word_tag_list in enumerate(word_tag_lists):
      words = []
      tags = []
      for word, tag in word_tag_list:
          words.append(word)
          tags.append(tag)

      rst_sent = {}
      rst_sent['sent'] = sentences[index]
      rst_sent['words'] = ' '.join(words)
      rst_sent['tags'] = ' '.join(tags)
      result.append(rst_sent)

    end = time.time()
    print (end-start)
    return result



@app.route("/generate_quiz", methods=['POST'])
def generate_quiz():
    if request.json is not None:
      content = request.json
    elif request.form is not None:
      content = request.form
    else:
      return 'Invalid Parameters'

    if 'word' not in content or 'word_pos' not in content or 'test_type' not in content or 'news_category' not in content:
       return 'Invalid Parameters'

    print('==' + content['word'] + '==')
    print(content['word_translation'].encode('utf-8'))

    print("--lin distance--")
    start = time.time()
    result = generator.get_distractors(content['word'], content['word_pos'], 
                                       content['test_type'], content['news_category'])
    end = time.time()
    print "time spent: " + str(end-start)
    print(", ".join(result))
    print("--w2v--")
    start = time.time()
    result_w2v = generator_w2v.get_distractors(content['word'], content['word_pos'], 
                                       content['test_type'], content['news_category'],
                                       content['word_translation'].encode('utf-8'))

    end = time.time()
    print "time spent: " + str(end-start)
    print(", ".join(result_w2v))
    print("   ")
    return jsonify(result)

 
    
@app.route("/text_process", methods=['POST'])
def text_process():
  # for get
  #text = request.args.get('text', '')
  #mode = request.args.get('mode', '')

  if request.json is not None:
    content = request.json
  elif request.form is not None:
    content = request.form
  else:
     return 'Invalid Parameters'

  if 'text' not in content:
     return 'Invalid Parameters'
    
  result = process_pipeline(content['text'])
  return jsonify(result)


@app.route("/text_process_batch", methods=['POST'])
def text_process_batch():
  # for get
  #text = request.args.get('text', '')
  #mode = request.args.get('mode', '')

  if request.json is not None:
    content = request.json
  elif request.form is not None:
    content = request.form
  else:
     return 'Invalid Parameters'

  if 'text' not in content:
     return 'Invalid Parameters'
    
  result = process_pipeline_batch(content['text'])
  return jsonify(result)



if __name__ == "__main__":
    app.run()