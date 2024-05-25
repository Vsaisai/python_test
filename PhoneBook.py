import sys
import yaml
import os
import psycopg2
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QPushButton, QListWidget, QMessageBox, QInputDialog


class PhoneBook:
    def __init__(self, conn):
        self.conn = conn
        self.create_database()

    def create_database(self):
        with self.conn.cursor() as cur:
            cur.execute("CREATE TABLE IF NOT EXISTS people (id SERIAL PRIMARY KEY, name VARCHAR(255))")
            cur.execute("CREATE TABLE IF NOT EXISTS phone_numbers (id SERIAL PRIMARY KEY, person_id INTEGER, phone_number VARCHAR(255), FOREIGN KEY(person_id) REFERENCES people(id))")

    def add_person(self, name):
        with self.conn.cursor() as cur:
            cur.execute("INSERT INTO people (name) VALUES (%s) RETURNING id", (name,))
            person_id = cur.fetchone()[0]
            self.conn.commit()
        return person_id

    def add_phone_number(self, person_id, phone_number):
        with self.conn.cursor() as cur:
            cur.execute("INSERT INTO phone_numbers (person_id, number) VALUES (%s, %s)", (person_id, phone_number))
            self.conn.commit()

    def get_people(self):
        with self.conn.cursor() as cur:
            cur.execute("SELECT * FROM people")
            return cur.fetchall()

    def get_phone_numbers(self, person_id):
        with self.conn.cursor() as cur:
            cur.execute("SELECT phone_numbers FROM phone_numbers WHERE person_id = %s", (person_id,))
            return [row[0] for row in cur.fetchall()]

    def find_person_by_name(self, name):
        with self.conn.cursor() as cur:
            cur.execute("SELECT * FROM people WHERE name ILIKE %s", ('%' + name + '%',))
            return cur.fetchall()

    def delete_person(self, person_id):
        with self.conn.cursor() as cur:
            cur.execute("DELETE FROM phone_numbers WHERE person_id = %s", (person_id,))
            cur.execute("DELETE FROM people WHERE id = %s", (person_id,))
            self.conn.commit()


class PhoneBookApp(QWidget):
    def __init__(self):
        super().__init__()
        self.contactList = None
        self.buttons = [
            ("Вывести все контакты", self.show_all_contacts),
            ("Добавить контакт", self.add_contact),
            ("Редактировать контакт", self.edit_contact),
            ("Удалить контакт", self.delete_contact),
            ("Найти контакт", self.search_contact)
        ]
        config = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.yaml")
        with open(config, "r") as f:
            config = yaml.safe_load(f)
        try:
            self.conn = psycopg2.connect(**config)
        except psycopg2.Error as e:
            QMessageBox.warning(self, "Ошибка", f"Ошибка подключения к базе данных: {e}")
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
        people = self.phonebook.get_people()
        for person in people:
            person_id, name = person
            phone_numbers = self.phonebook.get_phone_numbers(person_id)
            numbers_str = ", ".join(phone_numbers)
            self.contactList.addItem(f"Имя: {name}, Номер(а): {numbers_str}")
        self.contactList.addItem(f"Сохранено в PostgreSQL")

    def get_input(self, title, label):
        text, okPressed = QInputDialog.getText(self, title, label)
        return text.strip(), okPressed

    def add_contact(self):
        name, okPressed = self.get_input("Добавить контакт", "ФИО:")
        if okPressed:
            person_id = self.phonebook.add_person(name)
            numbers = []
            while True:
                number, okPressed = QInputDialog.getText(self, "Добавить контакт", "Номер (Enter для завершения):")
                if not okPressed or not number.strip():
                    break
                numbers.append(number.strip())
            for number in numbers:
                self.phonebook.add_phone_number(person_id, number)
            QMessageBox.information(self, "Добавлено", "Контакт добавлен")
            self.show_all_contacts()

    def edit_contact(self):
        name, okPressed = self.get_input("Редактировать контакт", "ФИО для редактирования:")
        if okPressed:
            people = self.phonebook.find_person_by_name(name)
            if not people:
                QMessageBox.warning(self, "Не найдено", "Контакт не найден")
                return

            if len(people) > 1:
                QMessageBox.warning(self, "Ошибка", "Найдено несколько контактов с таким именем. Уточните имя.")
                return

            person_id, old_name = people[0]

            new_name, okPressed = self.get_input("Редактировать контакт", f"Новое ФИО (старое: {old_name}):")
            if okPressed and new_name:
                with self.conn.cursor() as cur:
                    cur.execute