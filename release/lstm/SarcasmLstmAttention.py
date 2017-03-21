# using the following for reference:
# https://github.com/umass-semeval/semeval16/blob/master/semeval/lstm_words.py 
import cPickle
import numpy as np
from collections import defaultdict, OrderedDict
import theano
import theano.tensor as T
import re
import warnings
import sys
import pandas as pd
import logging
import math
import pickle
import os
import timeit
import time
import lasagne
from lasagne.layers import get_output_shape
from lasagne.regularization import apply_penalty, l2

from release.lstm.hidey_layers import AttentionWordLayer, AttentionSentenceLayer, WeightedAverageWordLayer, WeightedAverageSentenceLayer, HighwayLayer



class SarcasmLstmAttention:
    def __init__(self, 
                W=None, 
                W_path=None, 
                K=300, 
                num_hidden=256,
                batch_size=None,
                grad_clip=100., 
                max_sent_len=200, 
                num_classes=2, 
                **kwargs):

        W = W
        V = len(W)
        K = int(K)
        num_hidden = int(num_hidden)
        batch_size = int(batch_size)
        grad_clip = int(grad_clip)
        max_seq_len = int(max_sent_len)
        max_post_len = int(kwargs["max_post_len"])
        num_classes = int(num_classes)    

        #S x N matrix of sentences (aka list of word indices)
        #B x S x N tensor of batches of posts
        idxs_rr = T.itensor3('idxs_rr') #imatrix
        #B x S matrix of discourse tags
        #idxs_disc_rr = T.imatrix('idxs_disc_rr')
        #B x S x N matrix
        mask_rr_w = T.itensor3('mask_rr_w')
        #B x S matrix
        mask_rr_s = T.imatrix('mask_rr_s')
        #B-long vector
        y = T.ivector('y')
        #gold = T.ivector('gold')
        #lambda_w = T.scalar('lambda_w')
        #p_dropout = T.scalar('p_dropout')

        #idxs_frames_rr = T.itensor3('idxs_frames_rr')
        ##idxs_intra_rr = T.itensor3('idxs_intra_rr')
        #idxs_intra_rr = T.imatrix('idxs_intra_rr')
        #idxs_sentiment_rr = T.imatrix('idxs_sentiment_rr')

        #biases = T.matrix('biases')
        #weights = T.ivector('weights')
        
        inputs = [idxs_rr, mask_rr_w, mask_rr_s]
                
        #now use this as an input to an LSTM
        l_idxs_rr = lasagne.layers.InputLayer(shape=(None, max_post_len, max_sent_len),
                                            input_var=idxs_rr)
        l_mask_rr_w = lasagne.layers.InputLayer(shape=(None, max_post_len, max_sent_len),input_var=mask_rr_w)
        l_mask_rr_s = lasagne.layers.InputLayer(shape=(None, max_post_len),
                                                input_var=mask_rr_s)
        #l_idxs_frames_rr = lasagne.layers.InputLayer(shape=(None, max_post_length, max_sentence_length),
        #                                    input_var=idxs_frames_rr)
        #l_disc_idxs_rr = lasagne.layers.InputLayer(shape=(None, max_post_length),
        #                                            input_var=idxs_disc_rr)
        #l_idxs_intra_rr = lasagne.layers.InputLayer(shape=(None, max_post_length),
        #                                            input_var=idxs_intra_rr)
        #l_idxs_sentiment_rr = lasagne.layers.InputLayer(shape=(None, max_post_length),
        #                                            input_var=idxs_sentiment_rr)

        #if add_biases:
        #    l_biases = lasagne.layers.InputLayer(shape=(None,1),
                                                 # input_var=biases)
        #now B x S x N x D
        #l_emb = lasagne.layers.EmbeddingLayer(l_in, input_size=V, output_size=K, W=W)
        l_emb_rr_w = lasagne.layers.EmbeddingLayer(l_idxs_rr, input_size=V, output_size=K,
                                                   W=W)
#        l_hid = l_emb_rr_w
        #CBOW w/attn
        #now B x S x D
        # TODO change
        l_attn_rr_w = AttentionWordLayer([l_emb_rr_w, l_mask_rr_w], K)
        l_avg_rr_s_words = WeightedAverageWordLayer([l_emb_rr_w, l_attn_rr_w])
        ##concats = l_avg_rr_s_words
        ##concats = [l_avg_rr_s_words]
        l_avg_rr_s = l_avg_rr_s_words

            
            
        #l_avg_rr_s = lasagne.layers.ConcatLayer(concats, axis=-1)

        #add MLP
        #if highway:
        #    l_avg_rr_s = HighwayLayer(l_avg_rr_s, num_units=l_avg_rr_s.output_shape[-1],
        #                              nonlinearity=lasagne.nonlinearities.rectify,
        #                              num_leading_axes=2)
        #    
        # TODO
        l_lstm_rr_s = lasagne.layers.LSTMLayer(l_avg_rr_s, num_hidden,
                                               nonlinearity=lasagne.nonlinearities.tanh,
                                               grad_clipping=grad_clip,
                                               mask_input=l_mask_rr_s)
        
        l_hid = l_lstm_rr_s
        #LSTM w/ attn
        #now B x D
        l_attn_rr_s = AttentionSentenceLayer([l_lstm_rr_s, l_mask_rr_s], num_hidden)        
        l_lstm_rr_avg = WeightedAverageSentenceLayer([l_lstm_rr_s, l_attn_rr_s])
        l_hid = l_lstm_rr_avg
            
        #for num_layer in range(num_layers):
        #    l_hid = lasagne.layers.DenseLayer(l_hid, num_units=rd,
        #                                  nonlinearity=lasagne.nonlinearities.rectify)

        #    #now B x 1
        #    l_hid = lasagne.layers.DropoutLayer(l_hid, p_dropout)
        #    
        #if add_biases:
        #    l_hid = lasagne.layers.ConcatLayer([l_hid, l_biases], axis=-1)
        #    inputs.append(biases)
        #    
        #self.network = lasagne.layers.DenseLayer(l_hid, num_units=2,
        #                                         nonlinearity=T.nnet.sigmoid)
        #
        #predictions = lasagne.layers.get_output(self.network).ravel()
        #
        #xent = lasagne.objectives.binary_crossentropy(predictions, gold)
        #loss = lasagne.objectives.aggregate(xent, weights, mode='normalized_sum')
        #
        #params = lasagne.layers.get_all_params(self.network, trainable=True)
        #
        ##add regularization
        #loss += lambda_w*apply_penalty(params, l2)

        #updates = lasagne.updates.nesterov_momentum(loss, params,
        #                                            learning_rate=learning_rate, momentum=0.9)

        #print('compiling...')
        #train_outputs = loss
        #self.train = theano.function(inputs + [gold, lambda_w, p_dropout, weights],
        #                             train_outputs,
        #                              updates=updates,
        #                              allow_input_downcast=True,
        #                              on_unused_input='warn')
        #print('...')
        #test_predictions = lasagne.layers.get_output(self.network, deterministic=True).ravel()
        #
        #self.predict = theano.function(inputs,
        #                               test_predictions,
        #                               allow_input_downcast=True,
        #                              on_unused_input='warn')

        #test_acc = T.mean(T.eq(test_predictions > .5, gold),
        #                                    dtype=theano.config.floatX)
        #print('...')
        #test_loss = lasagne.objectives.binary_crossentropy(test_predictions,
        #                                                    gold).mean()        
        #self.validate = theano.function(inputs + [gold, lambda_w, p_dropout, weights],
        #                                [loss, test_acc],
        #                              on_unused_input='warn')

        print('...')
        #attention for words, B x S x N        
         # TODO
        word_attention = lasagne.layers.get_output(AttentionWordLayer([l_emb_rr_w, l_mask_rr_w], K,
                                                                      W_w = l_attn_rr_w.W_w,
                                                                      u_w = l_attn_rr_w.u_w,
                                                                      b_w = l_attn_rr_w.b_w,
                                                                      normalized=False))
        self.word_attention = theano.function([idxs_rr,
                                               mask_rr_w],
                                               word_attention,
                                               allow_input_downcast=True,
                                               on_unused_input='warn')

        #if d_frames:        
        #    frames_attention = lasagne.layers.get_output(AttentionWordLayer([l_emb_frames_rr_w, l_mask_rr_w], d,
        #                                                                  W_w = l_attn_rr_frames.W_w,
        #                                                                  u_w = l_attn_rr_frames.u_w,
        #                                                                  b_w = l_attn_rr_frames.b_w,
        #                                                                  normalized=False))
        #    self.frames_attention = theano.function([idxs_frames_rr,
        #                                           mask_rr_w],
        #                                           frames_attention,
        #                                           allow_input_downcast=True,
        #                                           on_unused_input='warn')
        #    
        #attention for sentences, B x S
        # TODO
        sentence_attention = lasagne.layers.get_output(l_attn_rr_s)
        #if add_biases:
        #    inputs = inputs[:-1]
        self.sentence_attention = theano.function(inputs,
                                                  sentence_attention,
                                                  allow_input_downcast=True,
                                                  on_unused_input='warn')
        print('finished compiling...')
    
    
        network = lasagne.layers.DenseLayer(
            l_hid,
            num_units=num_classes,
            nonlinearity=lasagne.nonlinearities.softmax
        )
        #theano.printing.debugprint(network, print_type=True)
        #print(" network shape: {}\n".format(get_output_shape(network)))

        self.network = network
        output = lasagne.layers.get_output(network)

        # Define objective function (cost) to minimize, mean crossentropy error
        cost = lasagne.objectives.categorical_crossentropy(output, y).mean()

        # Compute gradient updates
        params = lasagne.layers.get_all_params(network)
        # grad_updates = lasagne.updates.nesterov_momentum(cost, params,learn_rate)
        grad_updates = lasagne.updates.adam(cost, params)
        #learn_rate = .01
        #grad_updates = lasagne.updates.adadelta(cost, params, learn_rate)
        test_output = lasagne.layers.get_output(network, deterministic=True)
        val_cost_fn = lasagne.objectives.categorical_crossentropy(
            test_output, y).mean()
        preds = T.argmax(test_output, axis=1)

        val_acc_fn = T.mean(T.eq(preds, y),
                            dtype=theano.config.floatX)

        self.val_fn = theano.function([idxs_rr, mask_rr_w, mask_rr_s, y], [val_cost_fn, val_acc_fn, preds],
                                 allow_input_downcast=True,on_unused_input='warn')
        # Compile train objective
        print "Compiling training functions"
        self.train = theano.function(inputs = [idxs_rr, mask_rr_w, mask_rr_s, y], outputs = cost, updates = grad_updates, allow_input_downcast=True,on_unused_input='warn')
        self.test = theano.function(inputs = [idxs_rr, mask_rr_w, mask_rr_s, y], outputs = val_acc_fn,allow_input_downcast=True,on_unused_input='warn')
        self.pred = theano.function(inputs = [idxs_rr, mask_rr_w, mask_rr_s, y],outputs = preds,allow_input_downcast=True,on_unused_input='warn')

    def get_params(self):
        return lasagne.layers.get_all_param_values(self.network)

    def set_params(self, params):
        lasagne.layers.set_all_param_values(self.network, params)

    def save(self, filename):
        params = self.get_params()
        np.savez_compressed(filename, *params)

def load(model, filename):
    params = np.load(filename)
    param_keys = map(lambda x: 'arr_' + str(x), sorted([int(i[4:]) for i in params.keys()]))
    param_values = [params[i] for i in param_keys]
    lasagne.layers.set_all_param_values(model.network, param_values)
        