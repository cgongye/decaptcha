#!/usr/bin/env python
import argparse
import os
import random
import sys
import time
from multiprocessing import Manager, Process
import string
import numpy as np
from captcha.image import ImageCaptcha


CLASSES = string.digits + string.lowercase

class PreProcessor(object):

    @staticmethod
    def L_split(length):
        @next
        def _(s, img):
            img = img.convert("L")
            # TODO: fallback to 40*60 for single char?
            # split image every 27x60 px
            return s, [np.array(img.crop((i * 27, 0, i * 27 + 27, 60))).flatten() for i in
                                       range(length)]

        return _

    @staticmethod
    def binary_split(length):
        from scipy import ndimage
        @next
        def _(s, img):
            img = img.convert("L")
            r = [np.array(img.crop((i * 27, 0, i * 27 + 27, 60))) for i in range(length)]
            # Binarization
            # if a pixel is darker than image mean, it's set to black, otherwise set to white
            r = map(lambda im: ndimage.binary_opening((im > im.mean()).astype(np.float)).flatten(), r)
            # TODO: fallback to 40*60 for single char?
            return s, r

        return _

    @staticmethod
    def binary_only(length):
        from scipy import ndimage
        @next
        def _(s, img):
            im = np.array(img.convert("L"))
            r = ndimage.binary_opening((im > im.mean()).astype(np.float)).flatten()
            return [s], [r]

        return _

    @staticmethod
    def binary_resize(length, size=0.5):
        from scipy import ndimage
        from scipy.misc import imresize
        @next
        def _(s, img):
            im = imresize(np.array(img.convert("L")), size)
            r = ndimage.binary_opening((im > im.mean()).astype(np.float)).flatten()
            return [s], [r]

        return _


def generate(length, img_captcha):
    @next
    def _(seq):
        # generate a captcha image, return each character's index and the image
        idx = [random.randrange(0, len(CLASSES)) for i in range(length)]
        s = "".join([CLASSES[i] for i in idx])
        return idx, img_captcha.generate_image(s)

    return _


def save_image(path):
    @next
    def _(s, img):
        # save a image
        _str = "".join([CLASSES[i] for i in s])
        fname = os.path.join(path, "%s-%s.png" % (_str, 10000000 * random.random()))
        img.save(fname)
        return s, img

    return _


def next(f):
    # a stub decorator to define a pipeline function
    def exe(*args):
        r = __exe.next(*f(*args))
        return r

    __exe = exe
    return exe


def process(count, chain, L, _id=None):
    '''
    Processing the pipeline
    :param count: iterations to run
    :param chain: the pipeline function chain
    :param L: the list to store resukt
    :param _id: set process id
    '''
    X = []
    y = []
    for i in range(count):
        _ = chain(i)
        for _X in _[1]:
            X.append(_X)
        for _y in _[0]:
            y.append(_y)
    L.append((X, y))
    # if _id is not None:
    #    print("child %s exits" % (_id))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='generate captcha and save to ndarray')
    parser.add_argument('CNT', default=1000, help="number of captcha to generate")
    parser.add_argument('-l', '--length', default=4, help="length of digits per captcha")
    parser.add_argument('-s', '--save', metavar="PATH", default=None,
                        help="path to save generated captcha, by default, images are not saved")
    parser.add_argument('--X', default="X.npy", help="path to save the ndarray of the data points")
    parser.add_argument('--y', default="y.npy", help="path to save the ndarray of the labels")
    parser.add_argument('--N', default="1", help="number of worker processes")

    parser.add_argument('-p', '--process', default="L_split",
                        choices=[f for f in PreProcessor.__dict__.keys() if not f.startswith("_")],
                        help="algorithms to process images")

    args = parser.parse_args()

    if args.save:
        if os.path.exists(args.save) and os.path.isdir(args.save) and os.listdir(args.save):
            print("ERROR: save path \"%s\" exists and is not empty" % args.save)
            sys.exit(0)
        elif not os.path.exists(args.save):
            os.makedirs(args.save)

    length = int(args.length)
    # the ImageCaptcha instance
    img_captcha = ImageCaptcha(width=27 * length, height=60, font_sizes=(45,))

    # setup call chains, join all functions to a pipeline
    chain = []
    chain.append(generate(length, img_captcha))
    if args.save:
        chain.append(save_image(args.save))
    chain.append(getattr(PreProcessor, args.process)(length))
    chain.append(lambda x, y: (x, y))

    for i in range(len(chain) - 1):
        chain[i].next = chain[i + 1]

    # start processing
    process_cnt = int(args.N)
    sample_cnt = int(args.CNT)
    s = time.time()
    manager = Manager()
    # shared list instance
    L = manager.list()
    childs = []
    for i in range(process_cnt):
        if i == process_cnt - 1:
            # assign all rest slices to the last process
            p = Process(target=process,
                        args=(sample_cnt - sample_cnt / process_cnt * (process_cnt - 1), chain[0], L, i,))
        else:
            p = Process(target=process, args=(sample_cnt / process_cnt, chain[0], L, i,))
        childs.append(p)
        p.start()
    for i in range(process_cnt):
        childs[i].join()
    print("generated %d samples in %.2fs" % (sample_cnt, time.time() - s))
    
    # it's time to save the generated samples
    s = time.time()
    X = []
    y = []
    # TODO: avoid pulling data from manager
    for _X, _y in L:
        X += _X
        y += _y
    with open(args.X, "wb") as f:
        np.save(f, np.array(X))
    with open(args.y, "wb") as f:
        np.save(f, np.array(y))
    print("saved %s samples in %.2fs" % (sample_cnt, time.time() - s))
