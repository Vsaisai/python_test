import psycopg2
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QPushButton, QListWidget, QMessageBox, QInputDialog
import json

class PhoneBook:
    def __init__(self, conn):
        self.conn = conn
        self.create_database()
        self.contacts = self.load_contacts()

    def create_database(self):
        # Закрываем текущее соединение
        self.conn.close()

        # Создаем новое соединение к шаблонной базе данных (template1)
        new_conn = psycopg2.connect(
            host="localhost",
            database="template1",
            user="postgres",
            password="1234",
            port="5432"
        )

        # Отключаемся от шаблонной базы данных (template1)
        new_conn.close()

        # Повторно подключаемся к оригинальной базе данных
        self.conn = psycopg2.connect(
            host="localhost",
            database="phonebook",
            user="postgres",
            password="1234",
            port="5432"
        )

        # Теперь создаем таблицу
        with self.conn.cursor() as cur:
            cur.execute("CREATE TABLE IF NOT EXISTS contacts (name VARCHAR(255), number VARCHAR(255))")
        self.conn.commit()


    def load_contacts(self):
        with self.conn.cursor() as cur:
            try:
                cur.execute("SELECT * FROM contacts")
                rows = cur.fetchall()
                return {row[0]: row[1] for row in rows}
            except psycopg2.Error as e:
                print(f"Error loading contacts: {e}")

    def save_contacts(self):
        with self.conn.cursor() as cur:
            try:
                cur.execute("DELETE FROM contacts")
                for name, number in self.contacts.items():
                    cur.execute("INSERT INTO contacts (name, number) VALUES (%s, %s)", (name, number))
            except psycopg2.Error as e:
                print(f"Error saving contacts: {e}")
        self.conn.commit()

    def add_contact(self, name, number):
        if name not in self.contacts:
            self.contacts[name] = number
            self.save_contacts()
            return True
        return False

    def edit_contact(self, name, new_name, new_number):
        if name in self.contacts:
            del self.contacts[name]
            self.contacts[new_name] = new_number
            self.save_contacts()
            return True
        return False

    def delete_contact(self, name):
        if name in self.contacts:
            del self.contacts[name]
            self.save_contacts()
            return True
        return False

    def search_contact(self, name):
        result = [(contact_name, number) for contact_name, number in self.contacts.items() if name in contact_name or name in number]
        return result

class PhoneBookApp(QWidget):
    def __init__(self):
        super().__init__()
        self.buttons = [
            ("Вывести все контакты", self.show_all_contacts),
            ("Добавить контакт", self.add_contact),
            ("Редактировать контакт", self.edit_contact),
            ("Удалить контакт", self.delete_contact),
            ("Найти контакт", self.search_contact)
        ]
        try:
            self.conn = psycopg2.connect(
                host="localhost",
                database="phonebook",
                user="postgres",
                password="1234",
                port="5432"
            )
        except psycopg2.Error as e:
            print(f"Error connecting to the database: {e}")
            exit(1)

        self.phonebook = PhoneBook(self.conn)
        self.initUI()

    def initUI(self):
        layout = QVBoxLayout()
        for btn_text, btn_func in self.buttons:
            btn = QPushButton(btn_text, self)
            btn.clicked.connect(btn_func)
            layout.addWidget(btn)
        self.contactList = QListWidget(self)
        layout.addWidget(self.contactList)
        self.setLayout(layout)

    def show_all_contacts(self):
        self.contactList.clear()
        for name, number in sorted(self.phonebook.contacts.items()):
            self.contactList.addItem(f"Имя: {name}, Номер: {number}")
        self.contactList.addItem(f"Сохранено в PostgreSQL")

    def get_input(self, title, label):
        text, okPressed = QInputDialog.getText(self, title, label)
        return text.strip(), okPressed

    def add_contact(self):
        name, okPressed = self.get_input("Добавить контакт", "ФИО:")
        if okPressed:
            number, okPressed = self.get_input("Добавить контакт", "Номер:")
            if okPressed:
                if self.phonebook.add_contact(name, number):
                    QMessageBox.information(self, "Добавлено", "Контакт добавлен")
                else:
                    QMessageBox.warning(self, "Ошибка", "Контакт уже существует")
                self.show_all_contacts()

    def edit_contact(self):
        name, okPressed = self.get_input("Редактировать контакт", "ФИО:")
        if okPressed and name in self.phonebook.contacts:
            new_name, okPressed = self.get_input("Редактировать контакт", "Новое ФИО (оставьте пустым, чтобы пропустить):")
            if okPressed:
                new_number, okPressed = self.get_input("Редактировать контакт", "Новый номер (оставьте пустым, чтобы пропустить):")
                if okPressed:
                    if self.phonebook.edit_contact(name, new_name, new_number):
                        QMessageBox.information(self, "Отредактировано", "Контакт отредактирован")
                    else:
                        QMessageBox.warning(self, "Ошибка", "Контакт не может быть отредактирован")
                    self.show_all_contacts()

    def delete_contact(self):
        name, okPressed = self.get_input("Удалить контакт", "ФИО:")
        if okPressed and name in self.phonebook.contacts:
            if self.phonebook.delete_contact(name):
                QMessageBox.information(self, "Удалено", "Контакт удален")
            else:
                QMessageBox.warning(self, "Ошибка", "Контакт не может быть удален")
            self.show_all_contacts()

    def search_contact(self):
        search_text, okPressed = self.get_input("Найти контакт", "Введите ФИО для поиска:")
        if okPressed:
            result = self.phonebook.search_contact(search_text)
            if result:
                result_str = "\n".join([f"Имя: {name}, Номер: {number}" for name, number in result])
                QMessageBox.information(self, "Результат поиска", f"Найден контакт: \n{result_str}")
            else:
                QMessageBox.information(self, "Результат поиска", "Контакт не найден")

    def closeEvent(self, event):
        try:
            self.conn.close()
        except psycopg2.Error as e:
            print(f"Error closing the database connection: {e}")

if __name__ == "__main__":
    app = QApplication([])
    ex = PhoneBookApp()
    ex.show()
    app.exec_()