import nltk

from WordDistanceCalculator import WordDistance
nltk.data.path.append('./nltk_data')

MIN_SIM = 0.1
MAX_SIM = 0


# Load the list of english, chinese words and their pos tags from 
# the dump file of english_chinese_translations tables
def load_word(translation_file):
    print 'loading ' + translation_file
    english_words = set()

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

            english_words.add(english_word)
	return list(english_words)


def compute(translate_file, sim_file):
	print 'start'
 	words = load_word(translate_file)
 	print 'words ' + str(len(words))

	calculator = WordDistance()

 	fw = open(sim_file, 'w')

	i = 0
	size = len(words)
	while i<size:
		if i%50==0:
	 		print i
	 		fw.flush()
	 	w1 = words[i]
	 	j = i+1
	 	while j<size:
	 		w2 = words[j]
	 		sim = calculator.get_lin_distance(w1, w2)
	 		if sim>=0.1 and sim<1:
	 			fw.write(w1 + ',' + w2 + ',' + str(sim) +'\n')
	 		j += 1
	 	i += 1
	fw.close()



if __name__ == "__main__":
	print 'init'
	compute('./quiz_data/english_chinese_translations.csv', './quiz_data/word_similarity.txt')

