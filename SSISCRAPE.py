

#IMPORTING LIBRARIES

import pandas as pd
import requests
from bs4 import BeautifulSoup
import numpy as np
import csv

#FUNCTIONS

def ExpMovingAverage(values, window):
    try:
        weights = np.exp(np.linspace(-1.,0.,window))
        weights /= weights.sum()

        a = np.convolve(values,weights)[:len(values)]
        a[:window]=a[window]
        return a
    except:
        return values

def CSVAggregate(SYMBOL, SYMBOLSTRING,RATIOLIST,NUM):
    with open(SYMBOLSTRING + '.csv','a') as csvDataFile:
        csvDataFile.write(RATIOLIST[NUM] + '\n')

    with open(SYMBOLSTRING + '.csv', newline='') as csvDataFile:
        for row in csv.reader(csvDataFile):
            SYMBOL.append(float(row[0]))

    EMA = (ExpMovingAverage(SYMBOL, 10,))
    indicatorDict = pd.DataFrame(
        {'LongPercent': SYMBOL, 'ExpMA': EMA,
        })
    indicatorDict.to_csv(SYMBOLSTRING + 'INDICATOR.csv')


#REQUESTING AND SCRAPING

page = requests.get('https://fxssi.com')
soup = BeautifulSoup(page.content, 'html.parser')
currencies = soup.find_all("div", {"class":"symbol"})

ratios = soup.find_all("div", class_="ratio-bar-left")


#DECLARING LIST VARIABLE

currencyList = []
ratioList = []

#EXTRACTING TEXT FOR CURRENCIES

for eachStep in currencies:
    eachStep = eachStep.text
    currencyList.append(eachStep)


#EXTRACTING TEXT AND TAKING FIRST TWO CHARACTERS

for eachStep2 in ratios:

    eachStep2 = eachStep2.text
    firstVals = eachStep2[0] + eachStep2[1]
    ratioList.append(firstVals)

#REMOVING LAST REPEATED VALUE

currencyList.pop()
ratioList.pop()

#DECLARING THESE LISTS

AUDUSD = []     #0
EURUSD = []     #1
GBPUSD = []     #2
NZDUSD = []     #3
USDCAD = []     #4
USDCHF = []     #5
USDJPY = []     #6
XAUUSD = []     #7

#RUNNING THE AGGREGATE FUNCTION

CSVAggregate(AUDUSD,'AUDUSD',ratioList,0)
CSVAggregate(EURUSD,'EURUSD',ratioList,1)
CSVAggregate(GBPUSD,'GBPUSD',ratioList,2)
CSVAggregate(NZDUSD,'NZDUSD',ratioList,3)
CSVAggregate(USDCAD,'USDCAD',ratioList,4)
CSVAggregate(USDCHF,'USDCHF',ratioList,5)
CSVAggregate(USDJPY,'USDJPY',ratioList,6)
CSVAggregate(XAUUSD,'XAUUSD',ratioList,7)



