import re
import argparse
import csv
from functools import lru_cache

TURNS = 6
FILE1 = "wordle_successes.csv"
FILE2 = "wordle_guess.csv"
FILE3 = "wordle_missed.csv"
FILE4 = "wordle_maxturns.csv"

# basic score validating, not fool proof
def validScore(score, guess, knownWord, knownLetters, failedLetters):
    if not re.match("^[012]{5}$", score):
        return False
    for i, c in enumerate(guess):
        if c in knownLetters and score[i] == '0':
            return False
        if c in failedLetters and score[i] != '0':
            return False
        if knownWord[i] != '.' and score[i] != '2':
            return False
    return True

def updateWordList(wordList, knownWord, knownWrongPos, knownLetters, failedLetters, expandingLetters):
    positiveMask = re.compile("".join(knownWord))
    negativeMask = "#" # matches nothing
    for i, v in enumerate(knownWrongPos):
        if len(v) > 0:
            negativeMask += "|" + ('.' * i) + "[" + "".join(v) + "]" + ((4-i) * '.')
    negativeMask = re.compile(negativeMask)
    return [w for w in wordList if
     (expandingLetters or positiveMask.match(w)) and
     not negativeMask.match(w) and
     (expandingLetters or set(knownLetters).issubset(set(w))) and
     not set(w) & set(failedLetters)]

def getScoreFromCMDLine(guess, knownWord, knownLetters, failedLetters):
    score = input("Please score: " + guess.upper() + "\n            : ")
    while not validScore(score, guess, knownWord, knownLetters, failedLetters):
        print("Invalid Score enter again or enter q to quit")
        help()
        score = input("Please score: " + guess.upper() + "\n            : ")
        if score == "q":
            return None
    return score

def getScoreFromKnownWord(knownWord):
    correctLetters = set(knownWord)
    def getScore(guess, a, b, c):
        result = ""
        for i, c in enumerate(guess):
            if c == knownWord[i]:
                result += '2'
            elif c in correctLetters:
                result += '1'
            else:
                result += '0'
        return result
    return getScore

def updateWordFacts(score, guess, knownWord, knownWrongPos, knownLetters, failedLetters):
    for i, c in enumerate(score):
        if c == '0' and guess[i] not in failedLetters:
            failedLetters.append(guess[i])
        elif c == '1':
            if guess[i] not in knownLetters:
                knownLetters.append(guess[i])
            if guess[i] not in knownWrongPos[i]:
                knownWrongPos[i].append(guess[i])
        elif c == '2' and knownWord[i] == '.':
            knownWord[i] = guess[i]

# runs a wordle with the given params. Returns guesses made and the word if one is found
def startWordle(wordList, cutoff, search, scoringMethod):
    knownWord = ['.' for i in range(5)]
    knownWrongPos = [[], [], [], [], []]
    knownLetters = []
    failedLetters = []
    for t in range(TURNS):
        guess = None
        expandingLetters = t < cutoff and len(knownLetters) < search
        if expandingLetters:
            guess = wordleIgnore(wordList, knownLetters + knownWord + failedLetters)
        else:
            guess = wordle(tuple(wordList)) # so wordList is hashable for lru_cache
        score = scoringMethod(guess, knownWord, knownLetters, failedLetters)
        if score == None:
            return -1, None
        elif score == "22222":
            return t + 1, guess
        updateWordFacts(score, guess, knownWord, knownWrongPos, knownLetters, failedLetters)
        wordList = updateWordList(wordList, knownWord, knownWrongPos, knownLetters, failedLetters, expandingLetters)
        if len(wordList) == 1:
            return t + 2, wordList[0] # plus 2 as it would be guessed in the next iteration
        elif len(wordList) == 0:
            return -1, None
    return -1, None

# tests the wordle implementation on the entire word list for all possible params
# this will take a while for larger wordLists
def startWordleTest(wordList):
    global TURNS
    with open(FILE1,"w") as s, open(FILE2,"w") as g, open(FILE3, "w") as m, open(FILE4, "w") as t:
        sWriter = csv.writer(s, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
        gWriter = csv.writer(g, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
        mWriter = csv.writer(m, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
        tWriter = csv.writer(t, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
        allMissedWords = {}
        for cutoff in range(TURNS+1):
            for search in range(6):
                print((cutoff, search))
                successes = 0
                turns = [0 for i in range(TURNS+2)]
                turns[0] = cutoff
                turns[1] = search
                missedWords = [cutoff, search]
                for word in wordList:
                    result, _ = startWordle(wordList, cutoff, search, getScoreFromKnownWord(word))
                    if result <= TURNS and result != -1:
                        successes += 1
                        turns[result+1] += 1
                    else:
                        missedWords.append(word)
                mWriter.writerow(missedWords)
                allMissedWords[(cutoff, search)] = missedWords[2:]
                sWriter.writerow([cutoff, search, successes])
                gWriter.writerow(turns)
        oturns = TURNS
        for cutoff in range(TURNS+1):
            for search in range(6):
                TURNS = oturns
                testWords = allMissedWords[(cutoff, search)]
                while len(testWords) > 0:
                    TURNS += 1
                    passingWords = []
                    for word in testWords:
                        result, _ = startWordle(wordList, cutoff, search, getScoreFromKnownWord(word))
                        if result <= TURNS and result != -1:
                            passingWords.append(word)
                        else:
                            break
                    testWords = [w for w in testWords if w not in passingWords]
                tWriter.writerow([cutoff, search, TURNS])


# counts the frequency of each letter in each position
# and returns the word corresponding to the highest score
@lru_cache(maxsize=None)
def wordle(wordList):
    counts = [{}, {}, {}, {}, {}]
    for word in wordList:
        for i, c in enumerate(word): # character c in position i
            counts[i][c] = counts[i].get(c, 0) + 1 # increased the count by 1
    return max(wordList, key=lambda word: scoreWord(word, counts))

# scores a word given the frequency of each letter in each position
def scoreWord(word, counts):
    score = 0
    for i, c in enumerate(word):
        score += counts[i][c]
    return score

# counts the frequency of each letter in each position ignoring the set of letters
# information is already known about and returns the highest scoring word
def wordleIgnore(wordList, ignore):
    counts = [{}, {}, {}, {}, {}]
    for word in wordList:
        for i, c in enumerate(word):
            counts[i][c] = counts[i].get(c, 0) + 1
    for c in ignore:
        for count in counts:
            count[c] = 0
    return max(wordList, key=lambda word: scoreWordIgnore(word, counts))

# scores a word given the frequency of each letter in each position.
# decreases score on repeated letters to get larger coverage of letters
def scoreWordIgnore(word, counts):
    score = 0
    for i, c in enumerate(word):
        score += counts[i][c] // (word.count(c))
    return score

def help():
        print("Each turn the program will guess a word, you must then give it the feedback so it can make a best next guess\n")
        print("When scoring a word use the following:")
        print(" - If a letter is incorrect mark it 0")
        print(" - If a letter is in the wrong place, mark it 1")
        print(" - If a letter in in the correct place, make it 2\n")
        print("If the correct word is:    WORDS")
        print("and the program suggested: WRONG")
        print("then the scoring would be: 21100\n")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Wordle Puzzle Solver')
    parser.add_argument("-t", "--test", action='store_true', help="When flagged a table of scores for different cutoff and search values on the given wordlist will be generated")
    parser.add_argument("-f", "--file", default="words.txt", type=open, help="File to read words from. Defaults to 'words.txt'")
    parser.add_argument("-c", "--cutoff", default=3, type=int, help="After cutoff turns the program will start guessing words")
    parser.add_argument("-s", "--search", default=3, type=int, help="Once search characters and known the program will start guessing words")
    args = parser.parse_args()
    words = []
    for line in args.file:
        line = line.strip()
        if len(line) != 5:
            print("Skipping word: " + line)
        else:
            words.append(line)
    args.file.close()
    if args.test:
        startWordleTest(words)
    else:
        help()
        result, word = startWordle(words, args.cutoff, args.search, getScoreFromCMDLine)
        if result != -1:
            print("The word is: " + word + "! It was guessed in " + str(result) + " turns")
        else:
            print("Couldn't solve the word")
