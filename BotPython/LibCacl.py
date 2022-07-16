# print("hello world!") # Checking...

# Making Calc


#from curses.ascii import isdigit


# res = 0 # result of operation
# err = False
def Sum(firstNamber, secondNamber): # Summation
  
    if(CheckNamber(firstNamber) != True):
        answer = "Ошибка ввода"
        return answer
    elif(CheckNamber(secondNamber) != True):
        answer = "Ошибка ввода"
        return answer 
    else:
         return firstNamber + secondNamber
def Sub(firstNamber, secondNamber): #Substraktion
    if CheckNamber(firstNamber) & CheckNamber(secondNamber):
       return firstNamber - secondNamber
    else:
        answer = "Ошибка ввода"
        return answer
def Div(firstNamber, secondNamber): #division
    if CheckNamber(firstNamber) & CheckNamber(secondNamber):
       return firstNamber / secondNamber 
    else:
        answer = "Ошибка ввода"
        return answer
def Mul(firstNamber, secondNamber): #multiplication
    if CheckNamber(firstNamber) & CheckNamber(secondNamber):
      return firstNamber * secondNamber 
    else:
        answer = "Ошибка ввода"
        return answer
def BinDiv(firstNamber, secondNamber):
    if CheckNamber(firstNamber) & CheckNamber(secondNamber):
       return firstNamber % secondNamber 
    else:
        answer = "Ошибка ввода"
        return answer
def CheckNamber(num): #In Function!
    try:
        float(num)
        return True
    except ValueError:
        return False
# def ProblemNamber(): # Need for fix bug with number
# firstNamber = 0
# secondNamber = 0
# op = ""
# try:
#     s = input("Input expression (Exemple: a + b): \n").split(" ") # exempl 1 + 4 
#     firstNamber = float(s[0])
#     secondNamber = float(s[2])
#     op = s[1] # operation
# except ValueError:
#     input("except input, try again please")
#     exit(0)

# if op == "+":
#     print(Sum(firstNamber,secondNamber))
# elif op == "-":
#     print(Sub(firstNamber,secondNamber))
# elif op == "/":
#     print(Div(firstNamber,secondNamber))
# elif op == "*":
#     print(Mul(firstNamber,secondNamber))
# elif op == "%":
#     print(BinDiv(firstNamber, secondNamber))
# else:
#     print("Не верная операция")

