import telebot
from LibCacl import *
bot = telebot.TeleBot("5452757963:AAHVtePR0QcNdNdc0I9yw5dQxScS1gcdDC8", parse_mode=None) # You can set parse_mode by default. HTML or MARKDOWN
def calc(firstNamber, op, secondNamber):
    answer = ""
    if op == "+":
        answer = str(Sum(firstNamber,secondNamber))
    elif op == "-":
        answer = str(Sub(firstNamber,secondNamber))
    elif op == "/":
        answer = str(Div(firstNamber,secondNamber))
    elif op == "*":
        answer = str(Mul(firstNamber,secondNamber))
    elif op == "%":
        answer = str(BinDiv(firstNamber, secondNamber))
    else:
        answer = "Не верная операция"
    return answer
def main():
    firstNamber = 0
    secondNamber = 0
	    
    @bot.message_handler(content_types =['text'])
    def send_echo(message):
        # if message.text == "Посчитай мне":
        try:
            s = message.text.split(" ")   
            firstNamber = float(s[0])
            secondNamber = float(s[2])
            op = s[1] # operation
            bot.send_message(message.chat.id, calc(firstNamber, op, secondNamber)) 
        except ValueError:
            bot.send_message(message.chat.id, "Вы ввели не верно вырожение, попробуйсте ввести по шаблону а + б")
        # else:
        #     bot.send_message(message.chat.id, "Не верная команда")  
    bot.polling( none_stop= True)
if __name__ == "__main__":
    main()
