import argparse
import pickle  # save model

import matplotlib.pyplot as plt
import numpy as np
from sklearn.linear_model.logistic import LogisticRegression
from sklearn.metrics import roc_curve, auc
from sklearn.model_selection import KFold


class category_result:
    '''
    class for calculating and storing result of each category
    '''
    mean_fpr = np.linspace(0, 1, 100)

    def __init__(self):
        self.fprs = []
        self.tprs = []
        self.aucs = []

    def append(self, y_test, proba, label):
        fpr, tpr, thresholds = roc_curve(y_test, proba, label)
        self.fprs.append(fpr)
        self.tprs.append(tpr)
        self.aucs.append(auc(fpr, tpr))

    def print_result(self, label):
        for fold in range(len(self.fprs)):
            plt.plot(self.fprs[fold], self.tprs[fold], lw=1, alpha=0.3,
                     label='ROC fold %d AUC = %0.2f' % (fold, self.aucs[fold]))
        plt.plot([0, 1], [0, 1], linestyle='--', lw=2, color='r',
                 label='Random', alpha=.8)
        plt.xlim([-0.05, 1.05])
        plt.ylim([-0.05, 1.05])
        plt.xlabel('False Positive Rate')
        plt.ylabel('True Positive Rate')
        plt.title('ROCs of category %d Mean AUC = %0.2f $\pm$ %0.2f'
                  % (label, np.mean(self.aucs), np.std(self.aucs)))
        plt.legend(loc="lower right")
        plt.savefig('%d.png' % (label))
        plt.show()


class fold_result:
    '''
    class for calculating and storing result of each fold
    '''

    def __init__(self):
        self.train_scores = []
        self.test_scores = []

    def append(self, clf, X_train, y_train, X_test, y_test):
        self.train_scores.append(clf.score(X_train, y_train))
        self.test_scores.append(clf.score(X_test, y_test))

    def print_score(self):
        print("Train set accuracy: %0.3f (+/- %0.3f)"
              % (np.mean(self.train_scores), np.std(self.train_scores)))
        print("Test set accuracy: %0.3f (+/- %0.3f)"
              % (np.mean(self.test_scores), np.std(self.test_scores)))


def train_model(X, y, out, N):
    '''
    :param X: ndarray data points
    :param y: ndarray labels
    :param print_r: whether to print rocs
    :return:
    '''
    clf = LogisticRegression(solver='sag', n_jobs=N)
    clf.fit(X, y)
    with open(out, 'w') as f:
        pickle.dump(clf, f)
    print "Model saved in", out


def validate_model(X, y, N):
    '''
    :param X: ndarray data points
    :param y: ndarray labels
    :param print_r: whether to print rocs
    :return:
    '''
    # K-fold cross validation
    folds = KFold(n_splits=5, shuffle=True, random_state=1234567).split(X)
    fold_r = fold_result()
    labels = np.unique(y)
    category_rs = [None] * len(labels)
    for label in labels:
        category_rs[label] = category_result()
    for train, test in folds:
        X_train = X[train]
        X_test = X[test]
        y_train = y[train]
        y_test = y[test]
        clf = LogisticRegression(solver='sag', n_jobs=N)
        clf.fit(X_train, y_train)
        probas = clf.predict_proba(X_test)
        fold_r.append(clf, X_train, y_train, X_test, y_test)
        for label in labels:
            category_rs[label].append(y_test, probas[:, label], label)
    fold_r.print_score()
    # print and save ROCS
    for label in labels:
        category_rs[label].print_result(label)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='train a model do a validation analysis using logistic regression')
    parser.add_argument('--X', default="X.npy", help="an ndarray of the data points")
    parser.add_argument('--y', default="y.npy", help='an ndarray of the labels')
    parser.add_argument('--validate', default=True, type=bool, help="validate the model or not")
    parser.add_argument('--out', default="model.out", help='trained model')
    parser.add_argument('--N', default=-1, type=int, help="number of cores")
    args = parser.parse_args()

    # load processed data
    X = np.load(args.X)
    y = np.load(args.y)

    # train the model
    train_model(X, y, args.out, args.N)

    # validate the model
    if (args.validate):
        validate_model(X, y, args.N)