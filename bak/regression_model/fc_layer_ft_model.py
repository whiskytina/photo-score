# coding: utf-8
import os, sys, glob
import logging
import numpy as np
import bcolz
from keras.models import Sequential
from keras.layers import Conv2D, MaxPooling2D, ZeroPadding2D, Dense, Dropout, Flatten, Lambda
from keras.layers.normalization import BatchNormalization
from keras import optimizers
from keras.preprocessing.image import *
from keras import backend as K
K.set_image_data_format("channels_first")

from vgg16 import Vgg16

logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s %(levelname)s %(message)s',
                    datefmt='%m-%d %H:%M')

path = "./data/"
batch_size = 64

def FC_Model(model_h5, do=0.5):
    fc_model = Sequential([
        Dense(4096, activation="relu", input_shape=(25088,)),
        Dropout(do),
        Dense(4096, activation="relu"),
        Dropout(do),
        Dense(1, activation="linear")
        ])
    fc_model.load_weights(model_h5)
    for layer in fc_model.layers[:]:
        if type(layer) == Dense:
            old_weights = layer.get_weights()
            new_weights = [w*0.5/(1-do) for w in old_weights]
            layer.set_weights(new_weights)
    return fc_model

def save_array(fname, arr): 
    c=bcolz.carray(arr, rootdir=fname, mode='w')
    c.flush()

def load_array(fname): 
    return bcolz.open(fname)[:]

def load_all_array(rootdir):
    all_features = []
    for feature_file in sorted(glob.glob(rootdir+"feature*.bc")):
        all_features.append(load_array(feature_file))
    all_features = np.concatenate(all_features, axis=0)

    all_labels = []
    for label_file in sorted(glob.glob(rootdir+"label*.bc")):
        all_labels.append(load_array(label_file))
    all_labels = np.concatenate(all_labels, axis=0)

    return (all_features, all_labels)

def gen_batch_array(rootdir):
    feature_files = sorted(glob.glob(rootdir+"feature*.bc"))
    label_files = sorted(glob.glob(rootdir+"label*.bc"))
    for feature_file, label_file in zip(feature_files, label_files):
        logging.info("loading array of %s and %s"%(feature_file, label_file))
        yield load_array(feature_file), load_array(label_file)

if __name__=="__main__":
    fc_model = FC_Model("./data/results/last_layer_ft_model_epoch19.h5", do=0.5)
    if sys.argv[1] == "sgd":
        optimizer = optimizers.SGD(lr=1e-5, decay=1e-4, momentum=0., nesterov=False)
    elif sys.argv[1] == "adagrad":
        optimizer = optimizers.Adagrad(lr=1e-5, epsilon=1e-08, decay=0.0)
    elif sys.argv[1] == "rmsprop":
        optimizer = optimizers.RMSprop(lr=1e-5, rho=0.9, epsilon=1e-08, decay=0.0)
    fc_model.compile(optimizer=optimizer, loss="mse", metrics=["mae"])

    valid_features, valid_labels = load_all_array(path+"results/valid/")
    for epoch in range(10):
        logging.info("train epoch=%d"%epoch)
        train_generator = gen_batch_array(path+"results/train/")
        for train_features, train_labels in train_generator:
            fc_model.fit(x=train_features, y=train_labels, batch_size=batch_size, epochs=1,
                    validation_data=(valid_features, valid_labels), shuffle=True)
        # save weights
        if (epoch+1)%10 == 0:
            fc_model.save_weights(path+"results/fc_layer_ft_model_epoch%d.h5"%epoch)

