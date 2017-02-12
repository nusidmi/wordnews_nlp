from nlp_server import process_pipeline, generator_w2v
import time
from quiz_generator_fast import QuizGeneratorFast
from quiz_generator import QuizGenerator
generator_fast = QuizGeneratorFast()
generator_baseline = QuizGenerator()

ALLOWED_POS_TAGS = ['NN', 'VB', 'RB', 'JJ']

def generate(words, tags):
    for word, tag in list(zip(words, tags)):
        key = word + '-' + tag
        if tag in ALLOWED_POS_TAGS and key in generator_w2v.most_frequent_translation:
            # print(word)
            # print(tag)
            key = word + '-' + tag
            word_translation = generator_w2v.most_frequent_translation[key]
            # hard-code most accurate translations
            if key == 'director-NN':
                word_translation = '主任'
            # print(word)
            # print(word_translation)
            # dimension, frequency cutoff
            # test_params = [[10, 5], [100, 5], [100, 10], [500, 10]]
            test_params = [[500, 10]]
            for test_param in test_params:
                # print('dimension: {0}, cutoff: {1}'.format(test_param[0], test_param[1]))
                start = time.time()
                result = generator_w2v.get_distractors(word=word, 
                    word_pos=tag, 
                    test_type=2, 
                    news_category=any, 
                    word_translation=word_translation,
                    dimension=test_param[0],
                    cutoff=test_param[1])
                end = time.time()
                print("time spent: " + str(end-start))

            # baseline fast
            baseline_fast_result = generator_fast.get_distractors(word=word, 
                    word_pos=tag, 
                    test_type=2, 
                    news_category=any)
            print("baseline_fast_result")
            print(baseline_fast_result)

            # baseline
            baseline_result = generator_baseline.get_distractors(word=word, 
                    word_pos=tag, 
                    knowledge_level=3,
                    news_category=any)
            print("baseline_result")
            print(baseline_result)
            print('------\n')

if __name__ == "__main__":
    print('\n')
    # print('\n')
    #try: 
    results = process_pipeline("""
        The director of the US Office of Government Ethics has criticised Donald Trump's plan to hand control of his business empire to his sons before his inauguration on 20 January.
        "Every president in modern times has taken the strong medicine of divestiture," he said, referring to a process whereby Mr Trump would sell off his corporate assets and put the profits into a blind trust run by an independent trustee.
        """)
    for result in results:
        print(result['words'])
        print('------')
        tags = result['tags'].split()
        words = result['words'].split()
        generate(words, tags)



