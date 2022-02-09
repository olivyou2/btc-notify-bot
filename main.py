from datetime import datetime, timedelta
from imp import get_magic
from math import ceil, floor
from time import time
import pytz
import telegram
import json
import ccxt
import os

from telegram.ext import Updater, MessageHandler, CommandHandler, CallbackContext
from apscheduler.schedulers.background import BackgroundScheduler

class Exchanger:
    def __init__(self):
        self.binance = ccxt.binance()
    
    def FetchOhlcv(self, epoch, limit, symbol="BTCBUSD", timeframe="5m"):
        ohlcvs = []
        
        for i in range(epoch):
            retrive = self.binance.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
            ohlcvs = ohlcvs + retrive
        
        return ohlcvs

    def GetMA(self, length, index, symbol="BTCBUSD", timeframe="5m", ohlcv_data=None):
        total = 0

        ohlcvs = None
        if (ohlcv_data == None):
            ohlcvs = self.binance.fetch_ohlcv(symbol, timeframe=timeframe, limit=length+index+1)
        else:
            ohlcvs = ohlcv_data

        for ohlcv in ohlcvs[-1-length-index:-1-index]:
            total += ohlcv[4]

        total /= length

        return total

    def GetRegularArray(self, index, timeframe="5m", ohlcv_data=None):
        MA5 = self.GetMA(5, index, timeframe=timeframe, ohlcv_data=ohlcv_data)
        MA10 = self.GetMA(10, index, timeframe=timeframe, ohlcv_data=ohlcv_data)
        MA15 = self.GetMA(15, index, timeframe=timeframe, ohlcv_data=ohlcv_data)
        MA25 = self.GetMA(25, index, timeframe=timeframe, ohlcv_data=ohlcv_data)

        if ((MA5 > MA10) and (MA10 > MA15) and (MA15 > MA25)):
            return True
        else:
            return False

    def GetReverseArray(self, index, timeframe="5m", ohlcv_data=None):
        MA5 = self.GetMA(5, index, timeframe=timeframe, ohlcv_data=ohlcv_data)
        MA10 = self.GetMA(10, index, timeframe=timeframe, ohlcv_data=ohlcv_data)
        MA15 = self.GetMA(15, index, timeframe=timeframe, ohlcv_data=ohlcv_data)
        MA25 = self.GetMA(25, index, timeframe=timeframe, ohlcv_data=ohlcv_data)
        
        if ((MA5 < MA10) and (MA10 < MA15) and (MA15 < MA25)):
            return True
        else:
            return False

    def MAAnalyze(self, limit, fetchCallback=None):
        ohlcvs_5m = self.FetchOhlcv(ceil(limit/5000), 1000, timeframe="5m")
        if (fetchCallback != None):
            fetchCallback("5m")

        ohlcvs_1m = self.FetchOhlcv(ceil(limit/1000), 1000, timeframe="1m")
        if (fetchCallback != None):
            fetchCallback("1m")

        analyze = list()

        for index in range(limit):
            reg5m = self.GetRegularArray(floor(index/5), ohlcv_data=ohlcvs_5m)
            reg1m = self.GetRegularArray(index, ohlcv_data=ohlcvs_1m)

            rev5m = self.GetReverseArray(floor(index/5), ohlcv_data=ohlcvs_5m)
            rev1m = self.GetReverseArray(index, ohlcv_data=ohlcvs_1m)

            if (reg5m and reg1m):
                analyze.append([index, "REGULAR"])    
            elif (rev5m and rev1m):
                analyze.append([index, "REVERSE"])   

        return analyze

class Memory:
    def __init__(self):
        self.memory = dict()

    def getList(self, key)->list:
        if (key in self.memory):
            return self.memory[key]
        else:
            self.memory[key] = list()

            return self.memory[key]

    def getDict(self, key)->dict:
        if (key in self.memory):
            return self.memory[key]
        else:
            self.memory[key] = dict()

            return self.memory[key]

    def save(self):
        with open("memory/memory.json", "w") as f:
            json.dump(self.memory, f)

class Bot:
    def __init__(self):
        self.memory = Memory()

        self.token = os.environ.get("bot-token")

        self.bot = telegram.Bot(self.token)
        self.updater = Updater(self.token)

        self.updater.dispatcher.add_handler(CommandHandler("register", self.registerCommand))
        self.updater.dispatcher.add_handler(CommandHandler("deregister", self.deregisterCommand))

        self.updater.start_polling(timeout=10, clean=True)

        self.scheduler = BackgroundScheduler()
        self.scheduler.start()

    def handler(self, command:str, handle):
        self.updater.dispatcher.add_handler(CommandHandler(command, handle))

    def run(self):
        print('bot start')
        self.updater.idle()

    def getChatIds(self)->list:
        chatList = self.memory.getDict("ChatIds")

        return chatList.keys()

    def registerCommand(self, update:telegram.Update, context):
        chatId = str(update.message.chat_id)
        chatList = self.memory.getDict("ChatIds")

        if (chatId in chatList):
            update.message.reply_text(f"이미 구독되어있습니다! chatId: {chatId}")
        else:
            chatList[chatId] = 0
            update.message.reply_text(f"구독 성공! chatId: {chatId}")

        self.memory.save()

    def deregisterCommand(self, update:telegram.Update, context):
        chatId = str(update.message.chat_id)
        chatList = self.memory.getDict("ChatIds")

        if (chatId in chatList):
            del chatList[chatId]
            update.message.reply_text(f"구독취소 완료! chatId : {chatId}")
        else:
            update.message.reply_text(f"이미 구독자가 아닙니다. chatId : {chatId}")    

        self.memory.save()

    def broadcast(self, context):
        for chatId in self.getChatIds():
            self.bot.get_chat(chatId).send_message(context)

    def setTimer(self, interval, callback):
        self.scheduler.add_job(callback, "interval", seconds=interval)

class Business:
    def __init__(self):
        self.exchanger = Exchanger()
        self.bot = Bot()

        self.bot.handler("test", self.AnalyzeCommand)

    def run(self):
        self.bot.setTimer(30, self.RegularProcess)

        self.bot.run()

    def AnalyzeCommand(self, update:telegram.Update, context:CallbackContext):
        chat = self.bot.bot.get_chat(update.message.chat_id)

        if (len(context.args[0]) > 0):
            limit = int(context.args[0])

            chat.send_message(f"{limit}개의 봉에서 이평선 타점을 계산합니다")
            
            def FetchCallback(stamp):
                chat.send_message(f"{stamp}분봉 가져오기 성공")

            res = self.exchanger.MAAnalyze(limit, FetchCallback)
            src = ""

            for ind, point in enumerate(res):
                pointTime = point[0]
                pointType = "📈 매수" if point[1] == "REGULAR" else "📉매도"

                available = False

                if (ind == len(res)-1):
                    available = True
                else:
                    prevTime = res[ind+1][0]
                    if (prevTime != pointTime+1):
                        available = True

                if (available):
                    now = datetime.fromtimestamp(time(), tz=pytz.timezone("Asia/Seoul"))
                    now -= timedelta(minutes=pointTime)
                    datet = now.strftime("%m-%d %H:%M")

                    src += f"{datet}, {pointType} 신호\n"

            chat.send_message(src)
        else:
            chat.send_message("5분봉 개수를 설정해주세요!")

    def RegularProcess(self):
        now = datetime.fromtimestamp(time())

        if (now.minute % 5 == 0):
            regularNow = self.exchanger.GetRegularArray(0)
            regularPrev = self.exchanger.GetRegularArray(1)

            reverseNow = self.exchanger.GetReverseArray(0)
            reversePrev = self.exchanger.GetReverseArray(1)

            regular1m = self.exchanger.GetRegularArray(0, "1m")
            reverse1m = self.exchanger.GetReverseArray(0, "1m")

            if (not regularPrev):
                if (regularNow and not regular1m):
                    self.bot.broadcast(f"📈 ➚➚➚ 이평선 정배열 변화, 매수신호 ➚➚➚")
                elif (regularNow and regular1m):
                    self.bot.broadcast(f"📈 ➚➚➚ 5분봉 1분봉 정배열, 매수신호 ➚➚➚")

            if (not reversePrev):
                if (reverseNow and not reverse1m):
                    self.bot.broadcast(f"📉 ➘➘➘ 이평선 역배열 변화, 매도신호 ➘➘➘")
                elif (reverseNow and reverse1m):
                    self.bot.broadcast(f"📉 ➘➘➘ 5분봉 1분봉 역배열, 매도신호 ➘➘➘")

app = Business()
app.run()