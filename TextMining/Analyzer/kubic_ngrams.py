import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname('TextMining/Tokenizer'))))

from numpy.core.records import array


from TextMining.Tokenizer.kubic_morph import *
from TextMining.Tokenizer.kubic_data import *
from TextMining.Tokenizer.kubic_mystorage import *
from TextMining.Analyzer.kubic_wordCount import *

import account.MongoAccount as monAcc

import numpy as np

from bson import json_util

from io import StringIO
import gridfs
import csv
from collections import defaultdict

from collections import Counter
import nltk
import networkx as nx
import operator

import logging

logger = logging.getLogger("flask.app.ngrams")

#logger = logging.getLogger()
#logging.basicConfig(level=logging.DEBUG, format=f'%(asctime)s %(levelname)s %(name)s %(threadName)s : %(message)s')

def filter_links(edges, matrix, linkStrength, minWeight, maxWeight):
    if linkStrength == 100 or minWeight == maxWeight:
        edgeList = list()
        for s,t in edges:
            edgeDict = dict()
            edgeDict["source"] = int(s)
            edgeDict["target"] = int(t) 
            edgeDict["weight"] = int(matrix[s][t])
            edgeList.append(edgeDict)
        logger.debug(str(len(edgeList)))
        return edgeList
    elif linkStrength == 0:
        return None
    else:
        strengthVal = ( maxWeight - minWeight ) * (int(linkStrength) / 100) 
        edgeList = list()
        for s,t in edges:
            edgeDict = dict()
            edgeDict["source"] = int(s)
            edgeDict["target"] = int(t) 
            if int(matrix[s][t]) > strengthVal + minWeight:
                edgeDict["weight"] = int(matrix[s][t])
                edgeList.append(edgeDict)

        logger.debug(str(minWeight)+" "+str(maxWeight)+" "+str(strengthVal)+" "+str(len(edgeList)))
        return edgeList

def ngrams(email, keyword, savedDate, optionList, analysisName, n, linkStrength):
    logger.info("ngram start")
    identification = str(email)+'_'+analysisName+'_'+str(savedDate)+"// "
    try:
        preprocessed = getPreprocessing(email, keyword, savedDate, optionList)[0]
        n = int(n)
        optionList = int(optionList)
        bglist = []
        for sentence in preprocessed:
            bglist += list(nltk.ngrams(sentence, n))

        bgCountDict = Counter(bglist)

        sortedBgCountDict = dict(sorted(bgCountDict.items(), key=operator.itemgetter(1), reverse=True))
        sortedBgCountList = list(sortedBgCountDict.items())
        #logger.debug(sortedBgCountList[0:optionList])
        
        top_words = dict(sortedBgCountList[0:optionList])
        #logger.debug(enumerate(top_words.keys()))
        
        wordList = list()

        for ngram in top_words.keys():
            for word in ngram:
                if word not in wordList:
                    wordList.append(word)


        wordToid = {w:i for i, w in enumerate(wordList)}
        idToWord = {i:w for i, w in enumerate(wordList)}


        adjacent_matrix = np.zeros((len(wordList), len(wordList)), int)

        for ngram,ngram_count in top_words.items():
            for i in range(len(ngram)-1):
                c = wordToid[ngram[i]]
                r = wordToid[ngram[i+1]]
                adjacent_matrix[c][r] += ngram_count
        logger.debug(adjacent_matrix)
        network = nx.from_numpy_matrix(adjacent_matrix)


        jsonDict = dict()
        nodeList = list()
        for n in network.nodes:
            nodeDict = dict()
            wrd = idToWord[n]
            nodeDict["id"] = int(n)
            nodeDict["name"] = wrd

            nodeList.append(nodeDict)
        
        jsonDict["nodes"] = nodeList

        edgeList = list()
        for s,t in network.edges:
            edgeDict = dict()
            edgeDict["source"] = int(s)
            edgeDict["target"] = int(t)
            edgeDict["weight"] = int(adjacent_matrix[s][t])
            edgeList.append(edgeDict)
        
        jsonDict["links"] = filter_links(network.edges, adjacent_matrix, linkStrength, np.min(adjacent_matrix[adjacent_matrix>0]), np.max(adjacent_matrix))

        logger.debug(jsonDict)
        #print(jsonDict)

        logger.info("MongoDB에 데이터를 저장합니다.")
        
        client = MongoClient(monAcc.host, monAcc.port)
        db=client.textMining

        doc={
            "userEmail" : email,
            "keyword" : keyword,
            "savedDate": savedDate,
            "analysisDate" : datetime.datetime.now(),
            #"duration" : ,
            "result" : jsonDict,
            #"resultCSV":
        }

        db.ngrams.insert_one(doc) 

        logger.info("MongoDB에 저장되었습니다.")


        return True, jsonDict
    except Exception as e :
        import traceback
        err = traceback.format_exc()
        logger.error(identification+str(err))
        return False, err
    

#ngrams('21800520@handong.edu', '북한', "2021-08-10T10:59:29.974Z", 10, 'tfidf', 3, 100)