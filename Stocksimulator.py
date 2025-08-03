import json
import yfinance as yf 
import webbrowser
from datetime import datetime
import csv
import os
import numpy as np
import getpass
import bcrypt
import base64

class StockHolding:
    def __init__(self, symbol, quantity):
        self.symbol = symbol
        self.quantity = quantity

    def update_quantity(self, change):
        self.quantity += change
        if self.quantity < 0:
            raise ValueError(f"Cannot sell more than {self.quantity} shares of {self.symbol}")

    def get_current_value(self, price):
        return self.quantity * price


class Portfolio:
    def __init__(self):
        self.holdings = {}

    def add_stock(self, symbol, quantity):
        self.holdings[symbol] = StockHolding(symbol, quantity)

    def buy(self, symbol, quantity, price):
        if symbol in self.holdings:
            self.holdings[symbol].update_quantity(quantity)
        else:
            self.add_stock(symbol, quantity)

    def sell(self, symbol, quantity, price):
        if symbol in self.holdings:
            if self.holdings[symbol].quantity >= quantity:
                self.holdings[symbol].update_quantity(-quantity)
                if self.holdings[symbol].quantity == 0:
                    del self.holdings[symbol]
                return True
            else:
                print(f"You don't own enough shares of {symbol} to sell")
        else:
            print(f"You don't own any shares of {symbol} to sell")
        return False
    
    def reset_portfolio(self):
        self.holdings = {}
    
    def get_total_value(self):
        total_value = 0
        for holding in self.holdings.values():
            current_price = yf.Ticker(holding.symbol).history(period="1d").iloc[-1]["Close"]
            total_value += holding.get_current_value(current_price)
        return total_value

    def to_dict(self):
        return {symbol: {"quantity": holding.quantity} for symbol, holding in self.holdings.items()}

    @classmethod
    def from_dict(cls, data):
        portfolio = cls()
        for symbol, holding_data in data.items():
            portfolio.add_stock(symbol, holding_data["quantity"])
        return portfolio


    def calculate_returns_volatility(self):
        metrics = {}
        for symbol in self.holdings.keys():
            ticker = yf.Ticker(symbol)
            history_data = ticker.history(period="1y")
            if not history_data.empty:
                history_data['Daily Return'] = history_data['Close'].pct_change()
                avg_return = history_data['Daily Return'].mean() * 252
                volatility = history_data['Daily Return'].std() * np.sqrt(252)
                metrics[symbol] = {
                    "avg_return": avg_return,
                    "volatility": volatility
                }
        return metrics


class User:
    def __init__(self, username, password):
        self.username = username
        self.password = hash_password(password)  # Store hashed password
        self.portfolio = Portfolio()

    def to_dict(self):
        return {
            "password": self.password,  # Store as string
            "portfolio": self.portfolio.to_dict()
        }

    @classmethod
    def from_dict(cls, username, data):
        user = cls(username, "")  # Initialize with empty password
        user.password = data.get("password", "")  # Store hashed password as string
        user.portfolio = Portfolio.from_dict(data.get("portfolio", {}))  # Handle empty portfolio
        return user





def load_users():
    try:
        with open("users.json", "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.decoder.JSONDecodeError):
        return {}
 


def save_users(users):
    with open("users.json", "w") as f:
        json.dump(users, f, indent=4)




def hash_password(password):
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode(), salt)
    return hashed.decode('utf-8')  # Convert byte string to normal string for storage


def check_password(hashed, password):
    # Ensure hashed is a byte string
    return bcrypt.checkpw(password.encode(), hashed.encode())






def sign_up(users):
    username = input("Enter a username: ").strip()
    if username in users:
        print("Username already exists.")
        return None
    password = getpass.getpass("Enter a password: ").strip()
    hashed_password = hash_password(password)
    users[username] = {"password": hashed_password, "portfolio": {}}
    save_users(users)
    print("Sign-up successful.")
    return {"username": username, **users[username]}  # Include the username in the returned dictionary




def login(users):
    username = input("Enter your username: ")
    password = getpass.getpass("Enter your password: ")  # Use getpass to avoid password echoing
    if username in users and check_password(users[username]["password"], password):
        return username
    else:
        print("Invalid username or password")
        return None




def save_portfolio(user):
    users = load_users()
    users[user.username] = user.to_dict()
    save_users(users)


def save_trade_to_csv(user, trade_details):
    filename = f"{user.username}_trades.csv"
    with open(filename, "a", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(trade_details)


def load_portfolio(user):
    users = load_users()
    if user.username in users:
        return Portfolio.from_dict(users[user.username]["portfolio"])
    else:
        return Portfolio()


def display_portfolio(portfolio, user):
    print("-" * 30)
    print("Current Portfolio:")
    print("-" * 30)
    for holding in portfolio.holdings.values():
        current_price = yf.Ticker(holding.symbol).history(period="1d").iloc[-1]["Close"]
        total_value = holding.get_current_value(current_price)
        print(f"{holding.symbol}: {holding.quantity} shares (Current Price: ₹{current_price:.2f}, Total Value: ₹{total_value:.2f})")
    
    metrics = portfolio.calculate_returns_volatility()
    print("-" * 30)
    print("Portfolio Metrics:")
    for symbol, metric in metrics.items():
        print(f"{symbol}: Annualized Return: {metric['avg_return']*100:.2f}%, Volatility: {metric['volatility']*100:.2f}%")
    print("-" * 30)
    print(f"Total Portfolio Value: ₹{portfolio.get_total_value():.2f}")
    print("-" * 30)
    net_value = calculate_net_value(user)
    print(f"Net Portfolio Value: ₹{net_value:.2f}")
    print("-" * 30)


def calculate_net_value(user):
    filename = f"{user.username}_trades.csv"
    if os.path.exists(filename):
        total_buy = 0
        total_sell = 0
        with open(filename, "r") as f:
            reader = csv.reader(f)
            for row in reader:
                if row[1] == "Buy":
                    total_buy += float(row[2]) * int(row[3])
                elif row[1] == "Sell":
                    total_sell += float(row[2]) * int(row[3])
        return total_sell - total_buy
    else:
        return 0


def get_user_choice_trade():
    while True:
        choice = input("Enter your choice (b - buy, s - sell, v - view portfolio, t - view trades, r - reset, q - quit): ").lower()
        if choice in ("b", "s", "v", "t", "r", "q"):
            return choice
        else:
            print("Invalid choice. Please try again.")


def get_user_choice_view():
    while True:
        choice = input("Do you want to see a chart of a certain stock? (yes/no): ").lower()
        if choice in ("yes", "no"):
            return choice
        else:
            print("Invalid choice. Please enter 'yes' or 'no'.")


def reset_portfolio(user):
    user.portfolio.reset_portfolio()


def is_nse_stock(symbol):
    return symbol.upper().endswith(".NS")


def is_market_open():
    now = datetime.now()
    return now.weekday() < 5 and (now.hour > 9 or (now.hour == 9 and now.minute >= 15)) and (now.hour < 15 or (now.hour == 15 and now.minute <= 30))


def view_trade_csv(user):
    filename = f"{user.username}_trades.csv"
    if os.path.exists(filename):
        with open(filename, "r") as f:
            reader = csv.reader(f)
            for row in reader:
                print(row)
    else:
        print("No trade data available.")


def main():
    users = load_users()
    # Debugging line

    current_user = None

    while current_user is None:
        action = input("Do you want to sign up or login? (signup/login): ").lower()
        if action == "signup":
            user_data = sign_up(users)
            if user_data:
                # Debugging line
                current_user = User.from_dict(user_data["username"], user_data)
        elif action == "login":
            user_data = login(users)
            if user_data:
                
                current_user = User.from_dict(user_data, users[user_data])
        else:
            print("Invalid option. Please choose 'signup' or 'login'.")


    while True:
        option = input("Choose an option (Trade/View/Quit): ").lower()
        if option == "trade":
            if is_market_open():
                current_user.portfolio = load_portfolio(current_user)

                while True:
                    choice = get_user_choice_trade()
                    if choice == "b":
                        symbol = input("Enter stock symbol to buy: ").upper()
                        try:
                            quantity = int(input("Enter quantity to buy: "))
                            if is_nse_stock(symbol):
                                history_data = yf.Ticker(symbol).history(period="1d")
                                if not history_data.empty:
                                    price = history_data.iloc[-1]["Close"]
                                    current_user.portfolio.buy(symbol, quantity, price)
                                    print(f"Bought {quantity} shares of {symbol} at ₹{price:.2f} per share.")
                                    trade_details = [symbol, "Buy", price, quantity, datetime.now()]
                                    save_trade_to_csv(current_user, trade_details)
                                    save_portfolio(current_user)
                                else:
                                    print(f"No data found for {symbol}. It may not be a valid stock symbol.")
                            else:
                                print(f"{symbol} is not listed on NSE.")
                        except (KeyError, ValueError):
                            print(f"Invalid input or no data found for {symbol}.")
                    elif choice == "s":
                        symbol = input("Enter stock symbol to sell: ").upper()
                        try:
                            quantity = int(input("Enter quantity to sell: "))
                            if is_nse_stock(symbol):
                                history_data = yf.Ticker(symbol).history(period="1d")
                                if not history_data.empty:
                                    price = history_data.iloc[-1]["Close"]
                                    if current_user.portfolio.sell(symbol, quantity, price):
                                        print(f"Sold {quantity} shares of {symbol} at ₹{price:.2f}")
                                        trade_details = [symbol, "Sell", price, quantity, datetime.now()]
                                        save_trade_to_csv(current_user, trade_details)
                                        save_portfolio(current_user)
                                    else:
                                        print(f"Failed to sell {quantity} shares of {symbol}.")
                                else:
                                    print(f"No data found for {symbol}. It may not be a valid stock symbol.")
                            else:
                                print(f"{symbol} is not listed on NSE.")
                        except (KeyError, ValueError):
                            print(f"Invalid input or no data found for {symbol}.")
                    elif choice == "v":
                        display_portfolio(current_user.portfolio, current_user)
                    elif choice == "t":
                        view_trade_csv(current_user)
                    elif choice == "r":
                        reset_portfolio(current_user)
                        print("Portfolio has been reset.")
                        save_portfolio(current_user)
                    elif choice == "q":
                        print("Exiting the program.")
                        save_portfolio(current_user)
                        break
            else:
                print("Market is closed. Trading is only allowed from Monday to Friday, 9:15 AM to 3:30 PM.")
        elif option == "view":
            if is_market_open():
                view_choice = get_user_choice_view()
                if view_choice == "yes":
                    symbol = input("Enter the stock symbol to view its chart: ").upper()
                    webbrowser.open(f"https://finance.yahoo.com/chart/{symbol}")
                elif view_choice == "no":
                    continue
            else:
                print("Market is closed. You can still view your portfolio.")
                current_user.portfolio = load_portfolio(current_user)
                display_portfolio(current_user.portfolio, current_user)
        elif option == "quit":
            print("Exiting the program.")
            save_portfolio(current_user)
            break
        else:
            print("Invalid option. Please choose 'Trade' or 'View'.")





if __name__ == "__main__":
    main()