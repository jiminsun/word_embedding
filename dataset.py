import sys, os
import numpy as np
import pickle as pkl
import torch
from torch.utils.data import Dataset, ConcatDataset
import re
import random
import operator
from functools import reduce
from nltk.corpus import stopwords
import bz2
import _pickle as cPickle
from multiprocessing import Process
import multiprocessing as mp
# from sklearn.externals import joblib

class TextDataset(Dataset):
    def __init__(self, data_dir, dataset, window_size, ns_size, is_character):
        self.dataset_dir = os.path.join(data_dir, dataset)
        data_config_list = [dataset, window_size, ns_size, is_character]
        self.data_file = '_'.join(map(str, data_config_list)) + '.pkl'
        self.file_dir = os.path.join(data_dir, self.data_file)
        self.window_size = window_size
        self.ns_size = ns_size
        self.is_character = is_character
        self.stopwords = set(stopwords.words('english'))
        # self.counter = counter
        if not self.is_data_exist():
            self.open_file()

        with open(self.file_dir, 'rb') as f:
            if is_character:
                # self.word_pairs, self.vocabs, self.char2idx, self.idx2char = joblib.load(f)
                self.word_pairs, self.vocabs, self.char2idx, self.idx2char = pkl.load(f)
            else:
                # self.word_pairs, self.vocabs, self.word2idx, self.idx2word = joblib.load(f)
                self.word_pairs, self.vocabs, self.word2idx, self.idx2word = pkl.load(f)
    
    def open_file(self):
        if self.dataset_dir.endswith(".bz2"):
            self.text = bz2.BZ2File(self.dataset_dir).read().decode("utf-8").lower().strip()
        else:
            self.text = open(self.dataset_dir, encoding="utf-8").read().lower().strip()
        self.make_dataset()

    def is_data_exist(self):
        if os.path.isfile(self.file_dir):
            print("Data {} exist".format(self.data_file))
            return True
        else:
            print("Data {} does not exist".format(self.data_file))
            return False

    def make_dataset(self):
        print("Start to make data")
        tokenized_text = self.tokenize()
        print("compelete tokenize")
        tokenized_text_flatten = reduce(operator.concat, tokenized_text)
        self.vocabs = list(set(tokenized_text_flatten))
        if self.is_character:
            self.char2idx, self.idx2char = self.map_char_idx()
        else:
            word2idx, idx2word = self.map_word_idx(self.vocabs)
        word_pairs = []
        for sentence in tokenized_text:
            for i, word in enumerate(sentence):
                sentence = np.asarray(sentence)
                for w in range(-self.window_size, self.window_size + 1):
                    context_word_idx = i + w
                    if context_word_idx < 0 or context_word_idx >= len(sentence)\
                        or context_word_idx == i:
                        continue
                    neg_samples = self.negative_sampling()
                    if self.is_character:
                        word_pairs.append(self.make_char((word, sentence[context_word_idx], neg_samples)))
                    else:
                        word_pairs.append((word2idx[word], word2idx[sentence[context_word_idx]], [word2idx[word] for word in neg_samples]))
        if self.is_character:
            saves = word_pairs, self.vocabs, self.char2idx, self.idx2char
        else:
            saves = word_pairs, self.vocabs, word2idx, idx2word
        with open(self.file_dir, 'wb') as f:
            # joblib.dump(saves, f)
            cPickle.dump(saves, f, protocol=2)
            print("Data saved in {}".format(self.data_file))

    def tokenize(self):
        text = re.sub("(january|febuary|march|april|may|june|july|august|september|october|november|december)", " ", self.text)
        text = re.sub('<.*>'," ", text)
        text = re.sub('[^A-Za-z.]+', " ", text)
        text = text.split(".")
        tokens_list=[]
        for sen in text:
            tokens=[]
            for word in sen.split():
                if word not in self.stopwords:
                    tokens.append(word)
            tokens_list.append(tokens) 
        return tokens_list

    def map_char_idx(self):
        alphabet = 'abcdefghijklmnopqrstuvwxyz'
        char2idx = {}
        idx2char = {}
        for i in range(len(alphabet)):
            char2idx[list(alphabet)[i]] = i+1
            idx2char[i+1] = list(alphabet)[i]
        return char2idx, idx2char

    def map_word_idx(self, vocabs):
        word2idx = {}
        idx2word = {}
        for n, word in enumerate(vocabs):
            word2idx[word] = n
            idx2word[n] = word
        return word2idx, idx2word

    def negative_sampling(self):
        # self.calculate_distribution()
        neg_sample = random.sample(self.vocabs, self.ns_size)
        return neg_sample

    # def calculate_distribution(self):
    #     power = 3/4
    #     for key, value in self.counter.items():
    #         value**power
    #     return

    def _unicodeToAscii(self, s):
        return ''.join(
            c for c in unicodedata.normalize('NFD', s)
            if unicodedata.category(c) != 'Mn')

    def make_char(self, pairs):
        center, context, neg_samples = pairs
        center_idx = [self.char2idx[char] for char in list(center)]
        context_idx = [self.char2idx[char] for char in list(context)]
        negs_idx = []
        for i in range(self.ns_size):
            negs_idx.append([self.char2idx[char] for char in list(neg_samples[i])])
        return center_idx, context_idx, negs_idx

    def __getitem__(self, idx):
        if self.is_character:
            center_idx, context_idx, negs_idx = self.word_pairs[idx]
            center_idx, context_idx = torch.tensor(center_idx), torch.tensor(context_idx)
            negs_tensor_idx = []
            for i in range(self.ns_size):
                negs_tensor_idx.append(torch.tensor(negs_idx[i]))
            return center_idx, context_idx, negs_tensor_idx
        else:
            center_idx, context_idx, negs_idx = self.word_pairs[idx]
            center_idx, context_idx, negs_idx = torch.tensor(center_idx), torch.tensor(context_idx), torch.tensor(negs_idx)
            return center_idx, context_idx, negs_idx

    def __len__(self):
        return len(self.word_pairs)

def trial(dataset):
    text_dataset = TextDataset('./data', dataset, 5, 5, True)

if __name__ == '__main__':
    # text_dataset = TextDataset('./data', 'toy/merge.txt', 5, 5, True)
    # index = 1
    # print(text_dataset.word_pairs[index])
    processes=[]
    dataset_list = ['toy/merge.txt', 'toy/merge2.txt']
    for data in dataset_list:
        p = mp.Process(target=trial, args=(data,))
        p.start()
        processes.append(p)
    for p in processes:
        p.join()
    # processes = [mp.Process(target=trial, args=()) for x in range(4)]
    # for p in processes:
    #     p.start()
    # for p in processes:
    #     p.join()

    
