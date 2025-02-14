import pandas as pd
import numpy as np
from sklearn.exceptions import NotFittedError
import pymongo
from pymongo import MongoClient
import json
from common.cmm import showTime, SAMP_DATA_DIR
from common import prs
import os
import h5py
import csv
from elasticsearch import Elasticsearch
import time
import os.path
import traceback
import sys
import esFunc
import re
import pickle
import logging
from topic_analysis.Pre_date import *
from topic_analysis.Post_date import *
from topic_analysis.__get_logger import __get_logger
import topic_analysis.MongoAccount as MongoAccount

if os.name == "nt":# 윈도우 운영체제
    from eunjeon import Mecab
else:# 현재 리눅스 서버 및 맥은 konlpy으로 미캡 모듈 import
    from konlpy.tag import Mecab

def make_dir():
    log_path='./log'
    model_path='./model'
    svm_log='./log/cnn.log'
    svm_train='./log/cnn_train.log'
    log_error='./log/cnn_error.log'
    train_data='./train_data'


    if not os.path.exists(log_path):
        os.mkdir(log_path)
        logger.info("cnn의 log를 저장할./log 디렉토리를 생성하였습니다.")
        if not os.path.exists(log_error):
            os.touch(log_error)
            logger.info("cnn의 error를 저장할./log/cnn.log파일을 생성하였습니다.")
        if not os.path.exists(svm_log):
            os.touch(svm_log)
            logger.info("cnn을 사용한 주제예측을 시행일자가 저장될 ./log/cnn.log파일이 생성하었습니다.")
        if not os.path.exists(svm_train):
            os.touch(svm_train)
            logger.info("cnn 모델훈련 시행일자가 저장될 ./log/cnn_train.log파일을 생성하였습니다")
    if not os.path.exists(model_path):
        os.mkdir(model_path)
        logger.info("cnn model을 저장할 ./model 디렉토리를 생성하였습니다.")
    if not os.path.exists(train_data):
        os.mkdir(train_data)
        logger.info("cnn 모델 train data가 저장될 ./train_data 디렉토리를 생성하였습니다.")

### Word2Vec해주는 함수 ###
def W2V():
    from gensim.models import word2vec
    from tqdm import tqdm
    import nltk
    import string
    data=pd.read_csv("./train_data/single_20110224-20210224.csv")
    
    data.columns.to_list()
    data = data.drop_duplicates()
    print(data.shape)

    start=time.time()
    result=[]
    W2v_list=[]
    word_size=0

    for i in tqdm(range(len(data["키워드"]))):
        st=data["키워드"][i]
        lst=st.split(',')
        word_size+=len(lst)
        W2v_list.append(lst)
        
    print(word_size)
    print(len(W2v_list))

    print("Word2Vec 단어 임베딩 모델학습을 시작합니다. ")
    
    model = word2vec.Word2Vec(W2v_list,         # 리스트 형태의 데이터
                    sg=1,         # 0: CBOW, 1: Skip-gram
                    vector_size=100,     # 벡터 크기
                    window=5,     # 고려할 앞뒤 폭(앞뒤 3단어) #window 
                    min_count=10,  # 사용할 단어의 최소 빈도)
                    workers=4)    # 동시에 처리할 작업 수(코어 수와 비슷하게 설정)
    model.save('./model/word2vec_100.model') 
    #model.wv.save_word2vec_format('./model/word2vec_100.model',binary=False)
    print("time:",time.time()-start)
    #Word2Vec.save('./model/word2vec_100.model')
    print("Word2Vec 모델저장을 완료하였습니다. ")
    return model

### CNN모델을 훈련해주는 함수 ###
def cnn_train():
    from gensim.models.word2vec import Word2Vec
    import numpy as np
    import pandas as pd
    import os
    from sklearn.feature_extraction.text import CountVectorizer
    from sklearn.metrics import confusion_matrix, accuracy_score
    from sklearn.model_selection import train_test_split

    from keras.preprocessing.text import Tokenizer
    from keras.preprocessing.sequence import pad_sequences
    from keras.initializers import Constant
    from keras.models import Model
    from keras.layers import Input,Reshape,concatenate
    from keras.utils.np_utils import to_categorical
    import re
    from tensorflow.keras.models import Sequential
    from tensorflow.keras.layers import Embedding,Concatenate, Dropout, Conv2D, MaxPool2D, Dense, Dropout, Flatten
    from tensorflow.keras.callbacks import EarlyStopping, ModelCheckpoint
    from tensorflow.keras.models import load_model
    import numpy as np
    import pickle 
    import matplotlib.pyplot as plt
    
    make_dir()
    print('train data를 불러옵니다.')
    #f.write("train data를 불러옵니다")

    ##### 모델링 ######
    #train data load
    data=pd.read_csv('./train_data/single_20110224-20210224.csv')
    
    if os.path.isfile('./model/word2vec_100.model'):
        #Word2Vec_model=Worid2Vec.load_word2vec_format('./model/word2vec/model_100',binary=False, encoding='utf-8')
        Word2Vec_model=Word2Vec.load('./model/word2vec_100.model')
    else:
        Word2Vec_model=W2V()

    data.columns.to_list()
    data = data.drop_duplicates()
    del data['Unnamed: 0']
    print('train data를 불러오는데 성공하였습니다.')
    #f.write("train data를 불러오는데 성공하였습니다.")

    #tokenizer
    from keras.preprocessing.text import Tokenizer
    
    print("tokenizer를 생성합니다.")
    tokenizer = Tokenizer(num_words=1000, filters=',')
    print("tokenizer에게 1000개의 단어에 대한 dictionary를 만들도록 fit합니다")
    tokenizer.fit_on_texts(data['키워드'])
    print("tokenizer fit에 성공하였습니다.")

    # 532171

    print("만들어진 dictionary를 기준으로 텍스트를 숫자형으로 변환합니다.")
    text_sequence = tokenizer.texts_to_sequences(data['키워드'])
    max_length=max(len(l) for l in text_sequence)
    from keras.preprocessing.sequence import pad_sequences
    
    print(max_length,"를 최대길이로 pad_sequence를 시작합니다.")
    pad_text = pad_sequences(text_sequence, maxlen=max_length)
    y = pd.get_dummies(data['주제']).values
    
    from sklearn.model_selection import train_test_split 
    x_train, x_test, y_train, y_test = train_test_split(pad_text, 
                                                        y,
                                                        test_size=0.1
                                                        )

    
    vocab_size = len(tokenizer.word_index)+1 # 1을 더해주는 것은 padding으로 채운 0 때문입니다
    print("pad_sequence를 마치고, 임베딩을 진행합니다.")
    embedding_dim = 100
    input_length = max_length # 현재 1410
    print(input_length)
    max_features=2000

    num_words = min(max_features, len(tokenizer.word_index)) + 1
    print(num_words)

    # first create a matrix of zeros, this is our embedding matrix
    embedding_matrix = np.zeros((num_words, embedding_dim))

    def get_vector(word):
        if word in Word2Vec_model.wv.index_to_key:
            return Word2Vec_model.wv[word]
        else:
            return None

    # for each word in out tokenizer lets try to find that work in our w2v model
    for word, i in tokenizer.word_index.items():
        if i > max_features:
            continue
        embedding_vector =  get_vector(word)
        if embedding_vector is not None:
            # we found the word - add that words vector to the matrix
            embedding_matrix[i] = embedding_vector
        else:
            # doesn't exist, assign a random vector
            embedding_matrix[i] = np.random.randn(embedding_dim)
        
    sequence_length=max_length
    num_filters=100
    
    inputs_2 = Input(shape=(sequence_length,), dtype='int32')

    # note the `trainable=False`, later we will make this layer trainable
    embedding_layer_2 = Embedding(num_words,
                                embedding_dim,
                                embeddings_initializer=Constant(embedding_matrix),
                                input_length=sequence_length,
                                trainable=False)(inputs_2)

    reshape_2 = Reshape((sequence_length, embedding_dim, 1))(embedding_layer_2)

    conv_0_2 = Conv2D(num_filters, kernel_size=(3, embedding_dim), activation='relu', kernel_regularizer='l2')(reshape_2)
    conv_1_2 = Conv2D(num_filters, kernel_size=(4, embedding_dim), activation='relu', kernel_regularizer='l2')(reshape_2)
    conv_2_2 = Conv2D(num_filters, kernel_size=(5, embedding_dim), activation='relu', kernel_regularizer='l2')(reshape_2)

    maxpool_0_2 = MaxPool2D(pool_size=(sequence_length - 3 + 1, 1), strides=(1,1), padding='valid')(conv_0_2)
    maxpool_1_2 = MaxPool2D(pool_size=(sequence_length - 4 + 1, 1), strides=(1,1), padding='valid')(conv_1_2)
    maxpool_2_2 = MaxPool2D(pool_size=(sequence_length - 5 + 1, 1), strides=(1,1), padding='valid')(conv_2_2)

    concatenated_tensor_2 = Concatenate(axis=1)([maxpool_0_2, maxpool_1_2, maxpool_2_2])
    flatten_2 = Flatten()(concatenated_tensor_2)

    dropout_2 = Dropout(0.5)(flatten_2)
    output_2 = Dense(units=7, activation='softmax')(dropout_2)

    model_2 = Model(inputs=inputs_2, outputs=output_2)
    model_2.compile(loss='categorical_crossentropy', optimizer='adam', metrics=['accuracy'])

    start= time.time()
    batch_size = 32
    early_stopping=EarlyStopping(monitor='val_loss',mode='auto', verbose=1, patience=10)
    history = model_2.fit(
            x_train,y_train,
        epochs=30, batch_size=batch_size, 
        verbose=1, validation_split=0.2,
        callbacks=[early_stopping])
    
    filename='./model/cnn.h5'
    
    #with open(filename, 'wb') as filehandle:
    #    pickle.dump(model_2,filehandle, protocol=pickle.HIGHEST_PROTOCOL)
    model_2.save(filename)
    model=load_model(filename)
    print("\n\n#### 모델 학습 완료 ####")
    
    from keras.models import model_from_json

    model_json = model_2.to_json()
    with open("./model/cnn_model.json", "w") as json_file : 
        json_file.write(model_json)

    model_2.save_weights("./model/cnn_model.h5")
    
    print("time : ", time.time()-start)
    print("cnn 모델 학습을 성공적으로 마무리하였습니다.")
    return "cnn 모델 학습을 성공적으로 마무리하였습니다."
"""
    filename = './model_evaluation/cnn_evaluation.log'
    with open(filename,"w") as f:
        f.write("학습시간: ")
        f.write(str(time.time()-start))
        f.close()
   with open(filename,"a") as f:
        f.write("accuracy: ")
        f.write('{:.4f}'.format(model_2.evaluate(x_test, y_test)[1]))
        f.close()
    print('\nAccuracy: {:.4f}'.format(model_2.evaluate(x_test, y_test)[1]))
   
    plt.plot(history.history['loss'])
    plt.plot(history.history['val_loss'])
    plt.title('model loss')
    plt.ylabel('loss')
    plt.xlabel('epoch')
    plt.legend(['train', 'validation'], loc='upper left')
    fig_0 = plt.gcf()
    fig_0.savefig('./fig_loss.png')

    start_2= time.time()
    y_hat = model_2.predict(x_test)
    accuracy_score(list(map(lambda x: np.argmax(x), y_test)), list(map(lambda x: np.argmax(x), y_hat)))
    print("predict_time : ", time.time()-start_2)
    with open(filename,"a") as f:
        f.write("예측시간: ")
        f.write(str(time.time()-start_2))
        f.close()
    return accuracy_score
"""
     
### 모델 예측 ###
def CNNTest(tokenized_doc):
    from tensorflow.compat.v2.keras.models import model_from_json 
    from keras.models import load_model
    from keras.preprocessing.sequence import pad_sequences
    from tqdm import tqdm

    # model.json 파일 열기 
    with open('./model/cnn_model.json', 'r') as file :
        model_json = file.read()
        model = model_from_json(model_json)
    print("모델의 가중치 불러옵니다.")
    model.load_weights('./model/cnn_model.h5')

    model.compile(
        loss='categorical_crossentropy', 
        optimizer='adam', 
        metrics=['accuracy'])

    print("저장된 모델을 불러오는 데 성공했습니다. ")
    #f.write("저장된 모델을 불러오는 데 성공했습니다.")

    print("주제예측을 시작합니다.")
    #f.write("주제예측을 시작합니다.")
    result=list()
    
    #text_sequence=tokenized_doc
    print("만들어진 dictionary를 기준으로 텍스트를 숫자형으로 변환합니다.")
    from keras.preprocessing.text import Tokenizer
    tokenizer = Tokenizer(num_words=1000, filters=',')
    print("tokenizer에게 1000개의 단어에 대한 dictionary를 만들도록 fit합니다")
    
    text_sequence = tokenizer.texts_to_sequences(tokenized_doc)
    print("texts_to_sequence 과정을 무사히 마쳤습니다.")
    max_len=max(len(l) for l in text_sequence)
    print(max_len)
    max_length = 1452
    print("padding과정을 시작합니다.")
    pad_text = pad_sequences(text_sequence, maxlen=max_length)
    print("padding과정을 무사히 마쳤습니다.")
    #북한데이터 tokenizer & predict
    for i in tqdm(range(len(tokenized_doc))):
        if(len(tokenized_doc[i])>0):
            result.append(list(model.predict(pad_text))[0])#predict
        else:
            result.append("")#predict
    
    print(len(result),"개의 데이터의 주제예측을 성공적으로 완료하였습니다.")
    #f.write("주제예측을 성공적으로 완료하였습니다.")
    return result

def MoEs(date):
    import pandas as pd
    import numpy as np
    from sklearn.exceptions import NotFittedError
    import pymongo
    from pymongo import MongoClient

    #Mongo
    client=MongoClient(
        host=MongoAccount.host, 
        port=MongoAccount.port)
    logger.info('MongoDB에 연결을 성공했습니다.')
    #f.write("MongoDB에 연결을 성공했습니다..")
    db=client.topic_analysis

    collection_num=db.cnn.count()
    date=date
    print("\n")
    print(collection_num)
    if collection_num==0:#최초 시작
        print('svmDB에 ',collection_num,'개의 데이터가 있습니다. ')
        (hash_key, doc_title, tokenized_doc, contents, times)=Pre_date( date)
        print('MongoDB의 ', date, '이전의 데이터의 주제를 분석합니다.')
        #f.write("MongoDB의 모든 데이터의 주제를 분석합니다.")
        result=CNNTest(tokenized_doc)
        
    else: 
        print('svmDB에 ',collection_num,'개의 데이터가 있습니다. ')
        (hash_key, doc_title, tokenized_doc, contents, times)=Post_date(date)
        print('MongoDB에 새로유입된 ',len(tokenized_doc),'개의 데이터의 주제를 분석합니다.')
        #f.write("MongoDB에 새로유입된 데이터의 주제를 분석합니다.")
        result=CNNTest(tokenized_doc)#갱신  
    
    print('MongoDB의 svm collection에 분석한', len(result),'개의 주제를 저장합니다.')
    #f.write("MongoDB의 svm collection에 분석한 주제를 저장합니다")
    
    for i in range(len(hash_key)):
        doc={
            "hash_key" : hash_key[i],
            "doc_title" : doc_title[i],
            "contents": contents[i],
            "topic" : result[i],
            "timestamp": times[i]
        }
        db.cnn.insert_one(doc)
    showTime()
    print('MongoDB의 svm collection에 분석한', len(result),'개의 주제를 저장을 완료했습니다.')
    #f.write("MongoDB의 svm collection에 분석한 주제를 저장을 완료했습니다")
    return result

