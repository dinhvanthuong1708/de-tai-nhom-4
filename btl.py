import random
import numpy as np
import pandas as pd
import yfinance as yf
import pandas_ta as ta
from tkinter import *
from tkinter import ttk, messagebox
from datetime import datetime, timedelta

# Cấu hình thuật toán di truyền
POPULATION_SIZE = 50
GENERATIONS = 100
MUTATION_RATE = 0.1

# Chỉ số kỹ thuật và quy tắc giao dịch
TECHNICAL_INDICATORS = {
    'RSI': {'period': 14, 'buy_threshold': 30, 'sell_threshold': 70},
    'MACD': {'fast': 12, 'slow': 26, 'signal': 9},
    'SMA': {'period': 20},
    'BBANDS': {'period': 20, 'std': 2}
}

TIME_FRAMES = {
    'Ngắn hạn': 5,
    'Trung hạn': 20,
    'Dài hạn': 60
}

class TradingRule:
    def __init__(self, condition, action):
        self.condition = condition
        self.action = action  # 'BUY' hoặc 'SELL'

    def evaluate(self, data):
        try:
            return eval(self.condition, {}, {'data': data})
        except:
            return False

def get_historical_data(ticker, start_date, end_date):
    try:
        # Tải dữ liệu từ Yahoo Finance
        data = yf.download(ticker, start=start_date, end=end_date, auto_adjust=True)
        
        if data.empty:
            messagebox.showerror("Lỗi", f"Không thể tải dữ liệu cho {ticker}.")
            return None
        
        # Nếu dữ liệu có MultiIndex, loại bỏ cấp độ thứ 2
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.droplevel(1)

        # Tính toán các chỉ số kỹ thuật
        data['RSI'] = ta.rsi(data['Close'], length=TECHNICAL_INDICATORS['RSI']['period'])
        macd = ta.macd(data['Close'], fast=TECHNICAL_INDICATORS['MACD']['fast'], 
                      slow=TECHNICAL_INDICATORS['MACD']['slow'], 
                      signal=TECHNICAL_INDICATORS['MACD']['signal'])
        data = pd.concat([data, macd], axis=1)
        data['SMA'] = ta.sma(data['Close'], length=TECHNICAL_INDICATORS['SMA']['period'])
        bbands = ta.bbands(data['Close'], length=TECHNICAL_INDICATORS['BBANDS']['period'], 
                           std=TECHNICAL_INDICATORS['BBANDS']['std'])
        data = pd.concat([data, bbands], axis=1)

        # Xóa dữ liệu bị thiếu
        data = data.dropna()

        if data.empty:
            messagebox.showerror("Lỗi", f"Dữ liệu không đủ để tính toán chỉ số kỹ thuật cho {ticker}.")
            return None

        return data
    except Exception as e:
        messagebox.showerror("Lỗi", f"Lỗi khi tải dữ liệu: {e}")
        return None

def generate_initial_rules():
    base_rules = [
        ("data['RSI'] < TECHNICAL_INDICATORS['RSI']['buy_threshold']", 'BUY'),
        ("data['RSI'] > TECHNICAL_INDICATORS['RSI']['sell_threshold']", 'SELL'),
        ("data['MACD_12_26_9'] > data['MACDs_12_26_9']", 'BUY'),
        ("data['MACD_12_26_9'] < data['MACDs_12_26_9']", 'SELL'),
        ("data['Close'] > data['SMA']", 'BUY'),
        ("data['Close'] < data['SMA']", 'SELL'),
        ("data['Close'] < data['BBL_20_2.0']", 'BUY'),
        ("data['Close'] > data['BBU_20_2.0']", 'SELL')
    ]
    return [TradingRule(*rule) for rule in base_rules]

def calculate_profit(data, actions):
    capital = 10000
    position = 0
    for idx, row in data.iterrows():
        if actions[idx] == 'BUY' and capital > 0:
            position = capital / row['Close']
            capital = 0
        elif actions[idx] == 'SELL' and position > 0:
            capital = position * row['Close']
            position = 0
    return capital + (position * data.iloc[-1]['Close'])

def fitness(individual, data):
    actions = pd.Series(index=data.index, dtype=str)
    for rule in individual:
        for idx in data.index:
            if rule.evaluate(data.loc[idx]):
                actions[idx] = rule.action
    return calculate_profit(data, actions.fillna('HOLD'))

def genetic_algorithm(data):
    population = [random.sample(generate_initial_rules(), k=random.randint(2,4)) 
                for _ in range(POPULATION_SIZE)]
    
    for _ in range(GENERATIONS):
        population.sort(key=lambda x: fitness(x, data), reverse=True)
        next_generation = population[:int(POPULATION_SIZE*0.2)]
        
        while len(next_generation) < POPULATION_SIZE:
            parents = random.choices(population[:int(POPULATION_SIZE*0.4)], k=2)
            child = parents[0][:len(parents[0])//2] + parents[1][len(parents[1])//2:]
            
            if random.random() < MUTATION_RATE:
                if random.random() > 0.5:
                    child.append(random.choice(generate_initial_rules()))
                else:
                    child.pop(random.randint(0, len(child)-1))
            
            next_generation.append(child)
        
        population = next_generation
    
    return max(population, key=lambda x: fitness(x, data))

class Application(Frame):
    def __init__(self, master=None):
        super().__init__(master)
        self.master = master
        self.pack()
        self.create_widgets()
        
    def create_widgets(self):
        Label(self, text="Mã cổ phiếu (VD: AAPL):").grid(row=0, column=0)
        self.ticker_entry = Entry(self)
        self.ticker_entry.grid(row=0, column=1)

        Label(self, text="Khung thời gian:").grid(row=1, column=0)
        self.timeframe = ttk.Combobox(self, values=list(TIME_FRAMES.keys()))
        self.timeframe.grid(row=1, column=1)
        self.timeframe.current(0)

        self.run_btn = Button(self, text="Tối ưu chiến lược", command=self.run)
        self.run_btn.grid(row=2, columnspan=2)

        self.result_text = Text(self, height=10, width=50)
        self.result_text.grid(row=3, columnspan=2)

    def run(self):
        ticker = self.ticker_entry.get()
        timeframe = self.timeframe.get()
        end_date = datetime.now()
        days_required = max(50, TIME_FRAMES[timeframe] * 3)  
        start_date = end_date - timedelta(days=days_required)


        data = get_historical_data(ticker, start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d'))
        if data is None:
            return

        best_strategy = genetic_algorithm(data)
        profit = fitness(best_strategy, data)

        result = f"Chiến lược tối ưu ({timeframe}):\n"
        for rule in best_strategy:
            result += f"- {rule.condition} => {rule.action}\n"
        result += f"\nLợi nhuận ước tính: ${profit:,.2f}"

        self.result_text.delete(1.0, END)
        self.result_text.insert(END, result)

root = Tk()
root.title("Tối ưu hóa chiến lược giao dịch")
app = Application(master=root)
app.mainloop()
