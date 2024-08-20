import sys
import requests
import sqlite3
from PyQt5.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton, 
                             QListWidget, QLabel, QListWidgetItem, QComboBox)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QEvent
from PyQt5.QtGui import QFont, QColor
from fuzzywuzzy import process
from datetime import datetime, timedelta
import locale
from ge_tracker import GETracker  # Import GETracker from ge_tracker.py

class CustomComboBox(QComboBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setEditable(True)
        self.setInsertPolicy(QComboBox.NoInsert)
        self.lineEdit().setPlaceholderText("Search for an item...")
        self.setMaxVisibleItems(10)
        self.setStyleSheet("""
            QComboBox QAbstractItemView {
                border: 1px solid #555;
                selection-background-color: #4CAF50;
            }
        """)
        self.setCompleter(None)  # Disable the default completer
        self.view().installEventFilter(self)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Return or event.key() == Qt.Key_Enter:
            self.showPopup()
        else:
            super().keyPressEvent(event)

    def focusOutEvent(self, event):
        # Prevent the popup from closing when clicking on it
        if not self.view().isVisible():
            super().focusOutEvent(event)

class OSRSPriceTracker(QWidget):
    def __init__(self):
        super().__init__()
        self.ge_tracker = GETracker()
        self.initUI()
        self.initDB()
        self.loadItems()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refreshPrices)
        self.timer.start(5000)  # Refresh every 5 seconds
        self.price_changes = {}
        self.all_items = self.fetch_all_items()
        self.search_timer = QTimer()
        self.search_timer.setSingleShot(True)
        self.search_timer.timeout.connect(self.performSearch)

    def fetch_all_items(self):
        try:
            url = f"{self.ge_tracker.base_url}/mapping"
            response = requests.get(url, headers=self.ge_tracker.headers)
            if response.status_code == 200:
                return {item['name']: item['id'] for item in response.json()}
            else:
                print(f"Error fetching items: HTTP {response.status_code}")
        except Exception as e:
            print(f"Error fetching items: {e}")
        return {}

    def initUI(self):
        self.setWindowTitle('OSRS Price Tracker')
        self.setGeometry(100, 100, 600, 800)
        self.setStyleSheet("""
            QWidget {
                background-color: #2b2b2b;
                color: #e0e0e0;
                font-family: Arial, sans-serif;
            }
            QLineEdit, QListWidget {
                background-color: #3d3d3d;
                border: 1px solid #555;
                border-radius: 4px;
                padding: 5px;
                color: #e0e0e0;
            }
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QLabel {
                color: #e0e0e0;
                font-weight: bold;
            }
        """)

        layout = QVBoxLayout()

        # Title
        title_label = QLabel("OSRS Price Tracker")
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet("font-size: 24px; margin-bottom: 10px;")
        layout.addWidget(title_label)

        # Search bar
        self.search_input = CustomComboBox()
        self.search_input.lineEdit().textChanged.connect(self.onSearchTextChanged)
        self.search_input.activated[str].connect(self.onItemSelected)
        self.search_input.lineEdit().returnPressed.connect(self.onEnterPressed)
        layout.addWidget(self.search_input)

        # Tracked items
        self.tracked_items = QListWidget()
        self.tracked_items.setWordWrap(True)
        self.tracked_items.setTextElideMode(Qt.ElideNone)
        self.tracked_items.setSelectionMode(QListWidget.SingleSelection)  # Allow single selection
        self.tracked_items.itemClicked.connect(self.onItemClicked)  # Connect itemClicked signal
        layout.addWidget(self.tracked_items)

        # Buttons for operations
        button_layout = QHBoxLayout()
        self.refresh_button = QPushButton("Manual Refresh (Auto every 5s)")
        self.refresh_button.clicked.connect(self.refreshPrices)
        self.remove_button = QPushButton("Remove Selected")
        self.remove_button.clicked.connect(self.removeSelectedItem)
        button_layout.addWidget(self.refresh_button)
        button_layout.addWidget(self.remove_button)
        layout.addLayout(button_layout)

        self.setLayout(layout)

    def initDB(self):
        self.conn = sqlite3.connect('osrs_prices.db')
        self.cursor = self.conn.cursor()
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                high_price REAL NOT NULL,
                low_price REAL NOT NULL,
                last_high_price REAL,
                last_low_price REAL
            )
        """)
        self.conn.commit()

    def loadItems(self):
        self.cursor.execute("SELECT name, high_price, low_price, last_high_price, last_low_price FROM items")
        items = self.cursor.fetchall()
        for item in items:
            name, high_price, low_price, last_high_price, last_low_price = item
            last_high_price = last_high_price if last_high_price is not None else high_price
            last_low_price = last_low_price if last_low_price is not None else low_price
            self.addItemToList(name, high_price, low_price, last_high_price, last_low_price)
            item_id = self.ge_tracker.get_item_id(name)
            if item_id:
                self.ge_tracker.items[name] = item_id

    def onSearchTextChanged(self, text):
        self.search_timer.stop()
        self.search_timer.start(300)  # 300ms delay

    def performSearch(self):
        text = self.search_input.currentText()
        if text:
            try:
                results = process.extract(text, self.all_items.keys(), limit=10)
                self.search_input.clear()
                for result in results:
                    self.search_input.addItem(result[0])
                self.search_input.setCurrentText(text)
                self.search_input.lineEdit().setCursorPosition(len(text))
                # Don't show popup automatically
            except Exception as e:
                print(f"Error during search: {e}")
        else:
            self.search_input.clear()

    def onEnterPressed(self):
        text = self.search_input.currentText()
        if text:
            self.search_input.showPopup()
        else:
            self.addSelectedItem(text)

    def onItemSelected(self, item_name):
        self.addSelectedItem(item_name)
        self.search_input.setCurrentText("")
        self.search_input.clearFocus()

    def addSelectedItem(self, item_name):
        item_id = self.all_items.get(item_name)
        if item_id:
            self.ge_tracker.items[item_name] = item_id
            prices = self.ge_tracker.fetch_prices()
            if item_name in prices:
                high_price = prices[item_name]['high']
                low_price = prices[item_name]['low']
                self.cursor.execute("INSERT OR REPLACE INTO items (name, high_price, low_price, last_high_price, last_low_price) VALUES (?, ?, ?, ?, ?)", 
                                    (item_name, high_price, low_price, high_price, low_price))
                self.conn.commit()
                self.addItemToList(item_name, high_price, low_price, high_price, low_price)
            else:
                print(f"No price data available for {item_name}")
        else:
            print(f"Could not find item ID for {item_name}")

    def addItemToList(self, item_name, high_price, low_price, last_high_price, last_low_price):
        high_price_str = self.format_price(high_price)
        low_price_str = self.format_price(low_price)
        high_change = high_price - last_high_price
        low_change = low_price - last_low_price
        
        item_text = f"--{item_name}--\n"
        item_text += f"Buy: {high_price_str} ({self.format_change(high_change)})\n"
        item_text += f"Sell: {low_price_str} ({self.format_change(low_change)})"
        
        item = QListWidgetItem(item_text)
        item.setData(Qt.UserRole, item_name)
        
        self.tracked_items.addItem(item)
        self.updateItemColor(item, high_change, low_change)

    def updateItemInList(self, item_name, high_price, low_price, last_high_price, last_low_price):
        for i in range(self.tracked_items.count()):
            item = self.tracked_items.item(i)
            if item.data(Qt.UserRole) == item_name:
                high_price_str = self.format_price(high_price)
                low_price_str = self.format_price(low_price)
                high_change = high_price - last_high_price
                low_change = low_price - last_low_price
                
                item_text = f"--{item_name}--\n"
                item_text += f"Buy: {high_price_str} ({self.format_change(high_change)})\n"
                item_text += f"Sell: {low_price_str} ({self.format_change(low_change)})"
                
                item.setText(item_text)
                self.updateItemColor(item, high_change, low_change)
                break

    def updateItemColor(self, item, high_change, low_change):
        if high_change > 0 and low_change > 0:
            item.setForeground(QColor('#4CAF50'))  # Green
        elif high_change < 0 and low_change < 0:
            item.setForeground(QColor('#F44336'))  # Red
        else:
            item.setForeground(QColor('#FFC107'))  # Amber for mixed changes

    def refreshPrices(self):
        prices = self.ge_tracker.fetch_prices()
        self.cursor.execute("SELECT id, name, high_price, low_price FROM items")
        items = self.cursor.fetchall()
        for item_id, item_name, last_high_price, last_low_price in items:
            if item_name in prices:
                high_price = prices[item_name]['high']
                low_price = prices[item_name]['low']
                self.cursor.execute("UPDATE items SET high_price = ?, low_price = ?, last_high_price = ?, last_low_price = ? WHERE id = ?", 
                                    (high_price, low_price, last_high_price, last_low_price, item_id))
                self.updateItemInList(item_name, high_price, low_price, last_high_price, last_low_price)
        self.conn.commit()

    def removeSelectedItem(self):
        current_item = self.tracked_items.currentItem()
        if current_item:
            item_name = current_item.data(Qt.UserRole)
            self.cursor.execute("DELETE FROM items WHERE name = ?", (item_name,))
            self.conn.commit()
            self.tracked_items.takeItem(self.tracked_items.row(current_item))
            if item_name in self.ge_tracker.items:
                del self.ge_tracker.items[item_name]

    def onItemClicked(self, item):
        # Toggle selection when an item is clicked
        if item.isSelected():
            self.tracked_items.clearSelection()
        else:
            item.setSelected(True)

    def closeEvent(self, event):
        self.conn.close()
        event.accept()

    @staticmethod
    def format_price(price):
        return f"{price:,}"

    @staticmethod
    def format_change(change):
        if change > 0:
            return f"+{change:,}"
        elif change < 0:
            return f"{change:,}"
        else:
            return "0"

if __name__ == '__main__':
    app = QApplication(sys.argv)
    app.setStyle('Fusion')  # Use Fusion style for a more modern look
    ex = OSRSPriceTracker()
    ex.show()
    sys.exit(app.exec_())