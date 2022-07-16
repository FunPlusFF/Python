# print("hello world!") # Checking...

# Making Calc


#from curses.ascii import isdigit


res = 0 # result of operation
err = False
def Sum(firstNamber, secondNamber): # Summation
  
    if(CheckNamber(firstNamber) != True):
        print("It's not number! try again, please")
        input("except input, try again please")
        exit(0)
    elif(CheckNamber(secondNamber) != True):
        print("It's not number! try again, please")
        input("except input, try again please")
        exit(0)   
    else:
         return firstNamber + secondNamber
def Sub(firsNamber, secondNumber): #Substraktion
    if CheckNamber(firstNamber) & CheckNamber(secondNamber):
       return firstNamber - secondNamber
    else:
        print("It's not number! try again, please")
        input("except input, try again please")
        exit(0)
def Div(FirstNamber, secondNamber): #division
    if CheckNamber(firstNamber) & CheckNamber(secondNamber):
       return firstNamber / secondNamber 
    else:
        print("It's not number! try again, please")
        input("except input, try again please")
        exit(0) 
def Mul(firstNamber, secondNamber): #multiplication
    if CheckNamber(firstNamber) & CheckNamber(secondNamber):
      return firstNamber * secondNamber 
    else:
        print("It's not number! try again, please")
        input("except input, try again please")
        exit(0)
def BinDiv(firstNamber, secondNamber):
    if CheckNamber(firstNamber) & CheckNamber(secondNamber):
       return firstNamber % secondNamber 
    else:
        print("It's not number! try again, please")
        input("except input, try again please")
        exit(0)
def CheckNamber(num): #In Function!
    try:
        float(num)
        return True
    except ValueError:
        return False
# def ProblemNamber(): # Need for fix bug with number
firstNamber = 0
secondNamber = 0
op = ""
try:
    s = input("Input expression (Exemple: a + b): \n").split(" ") # exempl 1 + 4 
    firstNamber = float(s[0])
    secondNamber = float(s[2])
    op = s[1] # operation
except ValueError:
    input("except input, try again please")
    exit(0)

if op == "+":
    print(Sum(firstNamber,secondNamber))
elif op == "-":
    print(Sub(firstNamber,secondNamber))
elif op == "/":
    print(Div(firstNamber,secondNamber))
elif op == "*":
    print(Mul(firstNamber,secondNamber))
elif op == "%":
    print(BinDiv(firstNamber, secondNamber))
else:
    print("Не верная операция")

