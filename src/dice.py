import re
import random
import sys

expression = re.compile('(((?P<dieCount>\d*)([dD])(?P<dieSides>\d+)(((?P<dropLowest>dl)(?P<dropLowestCount>\d*))?((?P<dropHighest>dh)(?P<dropHighestCount>\d*))?)?|(?P<staticValue>\d+))((?P<nextJoiner>[+*-])|(,\s*))?)+?')


def addition(x, y): return x+y

def subtract(x, y): return x-y

def multiply(x, y): return x*y

joiner = {
    '+': addition,
    '-': subtract,
    '*': multiply
}


class DiceNode:
    def __init__(self, capture):
        self.nextRoll = None
        self.nextJoiner = None
        self.sum = None
        self.string = ""

        self.parse(capture)

    def joinNext(self):
        if self.nextRoll:
            if self.nextJoiner:
                self.sum = joiner[self.nextJoiner](self.sum, self.nextRoll.sum)
                self.string = f"({self.string}) {self.nextJoiner} ({self.nextRoll.string}) = {self.sum}"
            else:
                self.string = f"{self.string}, {self.nextRoll.string}"
                self.sum = self.nextRoll.sum
            self.nextJoiner = self.nextRoll.nextJoiner
            self.nextRoll = self.nextRoll.nextRoll

    def parse(self, capture):
        if capture['staticValue']:
            self.sum = int(capture['staticValue'])
            self.string = str(self.sum)
        else: 
            sides = int(capture['dieSides'])
            count = int(capture.get('dieCount')) or 1
            # Roll the dice, recording their in-order indices, but sorting them in-place according to value
            results = {i:random.randint(1, sides) for i in range(count)}
            keys = [k for k, v in sorted(results.items(), key=lambda item: item[1])]

            dropped = [] #indexes (keys)
            dropMessage = ""
            if capture['dropLowest']:
                drop = int(capture.get('dropLowestCount') or 1)            
                for i in range(drop):
                    dropped.append(keys[i])
                dropMessage+=f"dl{drop}"
                

            if capture['dropHighest']:
                drop = int(capture.get('dropHighestCount') or 1)
                for i in range(drop):
                    dropped.append(keys[-(i+1)])
                dropMessage+=f"dh{drop}"
            
            resultString = ", ".join([str(results[i]) if i not in dropped else f"~~{results[i]}~~" for i in range(len(results))])
            
            self.sum = sum([result[1] for result in results.items() if result[0] not in dropped])
            self.string = f"{count}d{sides}{dropMessage} ({resultString}) = {self.sum}"
            self.nextJoiner = capture['nextJoiner']


class DiceSet:
    def __init__(self):
        self.firstRoll = None
        self.message = ""

    def addRoll(self, capture):
        newRoll = DiceNode(capture)
        if (self.firstRoll):
            current = self.firstRoll
            while (current.nextRoll):
                current = current.nextRoll
            current.nextRoll = newRoll
        else:
            self.firstRoll = newRoll
    
    def result(self):
        for operation in ['*','+','-',None]:
            current = self.firstRoll
            while(current):
                if current.nextJoiner == operation:
                    current.joinNext()
                current = current.nextRoll
            self.firstRoll.joinNext()
        return f"{self.message}{self.firstRoll.string}"
    
    def parseString(self, string):
        match = expression.match(string)

        while (match):
            self.addRoll(match.groupdict())
            string = string[match.end():]
            match = expression.match(string)

        if string.strip():
            self.message = string.strip()+": "


if __name__ == "__main__":
    dice = DiceSet()
    dice.parseString(" ".join(sys.argv[1:]))
    print(dice.result())