import sys
import pyodbc
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QPushButton, QListWidget, QMessageBox, QInputDialog


def handle_exceptions(func):
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except pyodbc.Error as e:
            QMessageBox.warning(args[0], "Error", f"Error: {e}")
            return None

    return wrapper


class PhoneBook:
    def __init__(self, conn):
        self.conn = conn
        self.create_database()

    @handle_exceptions
    def create_database(self):
        with self.conn.cursor() as cur:
            # Создание таблицы people, если её нет
            cur.execute("""
                IF NOT EXISTS (SELECT * FROM sys.tables WHERE name='people')
                CREATE TABLE people (
                    id INT PRIMARY KEY IDENTITY(1,1),
                    name VARCHAR(255) UNIQUE
                )
            """)
            # Создание таблицы phone_numbers, если её нет
            cur.execute("""
                IF NOT EXISTS (SELECT * FROM sys.tables WHERE name='phone_numbers')
                CREATE TABLE phone_numbers (
                    id INT PRIMARY KEY IDENTITY(1,1),
                    person_id INT,
                    number VARCHAR(255),
                    FOREIGN KEY(person_id) REFERENCES people(id)
                )
            """)
        self.conn.commit()

    @handle_exceptions
    def get_person_id_by_name(self, name):
        with self.conn.cursor() as cur:
            # Получение id человека по его имени
            cur.execute("SELECT id FROM people WHERE name = ?", (name,))
            result = cur.fetchone()
            if result:
                return result[0]
        return None

    @handle_exceptions
    def add_person(self, name):
        existing_person_id = self.get_person_id_by_name(name)
        if existing_person_id is not None:
            QMessageBox.warning(None, "Предупреждение", f"Контакт с именем '{name}' уже существует.")
            return existing_person_id

        with self.conn.cursor() as cur:
            # Вставка нового человека в таблицу people
            cur.execute("INSERT INTO people (name) OUTPUT inserted.id VALUES (?)", (name,))
            person_id = cur.fetchone()[0]
            self.conn.commit()

        return person_id

    @handle_exceptions
    def edit_contact(self, person_id, new_name, new_number):
        with self.conn.cursor() as cur:
            # Обновление имени в таблице people и номера в таблице phone_numbers
            cur.execute("UPDATE people SET name = ? WHERE id = ?", (new_name, person_id))
            cur.execute("UPDATE phone_numbers SET number = ? WHERE person_id = ?", (new_number, person_id))
            self.conn.commit()
            return True

    @handle_exceptions
    def search_contact(self, search_text):
        with self.conn.cursor() as cur:
            # Поиск контактов по имени или номеру
            cur.execute("""
                SELECT people.name, phone_numbers.number FROM people
                JOIN phone_numbers ON people.id = phone_numbers.person_id
                WHERE LOWER(people.name) LIKE LOWER(?) OR phone_numbers.number LIKE ?
            """, (f"%{search_text}%", f"%{search_text}%"))
            return cur.fetchall()

    @handle_exceptions
    def add_phone_number(self, person_id, number):
        with self.conn.cursor() as cur:
            # Добавление нового номера телефона для человека
            cur.execute("INSERT INTO phone_numbers (person_id, number) VALUES (?, ?)", (person_id, number))
            self.conn.commit()

    @handle_exceptions
    def get_people(self):
        with self.conn.cursor() as cur:
            # Получение всех записей из таблицы people
            cur.execute("SELECT * FROM people")
            return cur.fetchall()

    @handle_exceptions
    def get_phone_numbers(self, person_id):
        with self.conn.cursor() as cur:
            # Получение всех номеров телефона для конкретного человека
            cur.execute("SELECT * FROM phone_numbers WHERE person_id = ?", (person_id,))
            return cur.fetchall()


class PhoneBookApp(QWidget):
    def __init__(self):
        global conn_str
        super().__init__()

        self.buttons = [
            ("Показать все контакты", self.show_all_contacts),
            ("Добавить контакт", self.add_contact),
            ("Редактировать контакт", self.edit_contact),
            ("Удалить контакт", self.delete_contact),
            ("Поиск контакта", self.search_contact)
        ]

        # Получаем настройки из файла config.txt
        try:
            with open("conf.txt", "r") as file:
                config_lines = file.readlines()

            # Извлекаем параметры из файла, игнорируя строки, начинающиеся с #
            server = next(
                (line.split(":")[1].split("#")[0].strip() for line in config_lines if "server" in line.lower()), "")
            database = next(
                (line.split(":")[1].split("#")[0].strip() for line in config_lines if "database" in line.lower()), "")
            trusted_connection = next((line.split(":")[1].split("#")[0].strip().lower() for line in config_lines if
                                       "trusted_connection" in line.lower()), "yes")

            if not server or not database:
                raise ValueError("Сервер или база данных не указаны в конфигурационном файле.")

            if trusted_connection.lower() == 'yes':
                # Используем аутентификацию Windows
                conn_str = f'DRIVER={{SQL Server}};SERVER={server};DATABASE={database};Trusted_Connection=yes'
            elif trusted_connection.lower() == 'no':
                # Используем аутентификацию SQL Server
                username = next((line.split(":")[1].strip() for line in config_lines if "username" in line.lower()), "")
                password = next((line.split(":")[1].strip() for line in config_lines if "password" in line.lower()), "")

                if not username or not password:
                    raise ValueError("Имя пользователя или пароль не указаны в конфигурационном файле.")

                conn_str = f'DRIVER={{SQL Server}};SERVER={server};DATABASE={database};UID={username};PWD={password}'

            try:
                self.conn = pyodbc.connect(conn_str)
            except pyodbc.Error as e:
                QMessageBox.warning(self, "Ошибка", f"Ошибка подключения к базе данных: {e}")
                exit(1)

            self.phonebook = PhoneBook(self.conn)
            self.initUI()

        except FileNotFoundError:
            QMessageBox.warning(self, "Ошибка", "Файл конфигурации не найден.")
            exit(1)
        except ValueError as ve:
            QMessageBox.warning(self, "Ошибка", f"Ошибка чтения файла конфигурации: {ve}")
            exit(1)

    '''
class PhoneBookApp(QWidget):
    def __init__(self):
        super().__init__()

        # Получаем настройки из файла config.txt
        try:
            with open("config.txt", "r") as file:
                config_lines = file.readlines()

            # Извлекаем параметры из файла
            server = next((line.split(":")[1].strip() for line in config_lines if "server" in line.lower()), "")
            database = next((line.split(":")[1].strip() for line in config_lines if "database" in line.lower()), "")

            if not server or not database:
                raise ValueError("Server or database not specified in the config file.")

        except FileNotFoundError:
            QMessageBox.warning(self, "Error", "Config file not found.")
            exit(1)
        except ValueError as ve:
            QMessageBox.warning(self, "Error", f"Error reading config file: {ve}")
            exit(1)
        trusted_connection = 'yes'
        conn_str = f'DRIVER={{SQL Server}};SERVER={server};DATABASE={database};Trusted_Connection={trusted_connection}'

        try:
            self.conn = pyodbc.connect(conn_str)
        except pyodbc.Error as e:
            QMessageBox.warning(self, "Error", f"Error connecting to the database: {e}")
            exit(1)

        self.phonebook = PhoneBook(self.conn)
        self.initUI()
    '''

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
            numbers = self.phonebook.get_phone_numbers(person_id)
            numbers_count = len(numbers)
            word_for_number = self.get_word_for_number(numbers_count)
            numbers_str = ", ".join([f"{number}" for _, _, number in numbers])

            item_text = f"ФИО: {name}, {numbers_count} {word_for_number}: {numbers_str}"
            self.contactList.addItem(item_text)

        self.contactList.addItem("Сохранено в SQL Server")

    # Функция для получения слова для формирования строки количества номеров
    def get_word_for_number(self, count):
        if 11 <= count <= 14 or count % 10 in {0, 5, 6, 7, 8, 9}:
            return "номеров"
        elif count % 10 == 1:
            return "номер"
        else:
            return "номера"

    # Функция для получения ввода от пользователя
    def get_input(self, title, label):
        text, okPressed = QInputDialog.getText(self, title, label)
        return text.strip(), okPressed

    def add_contact(self):
        name, okPressed = self.get_input("Добавить контакт", "Имя:")
        if okPressed:
            try:
                # Добавление нового человека
                person_id = self.phonebook.add_person(name)
                # Добавление новых номеров телефона для человека
                while True:
                    number, okPressed = self.get_input("Добавить контакт",
                                                       "Номер (оставьте поле пустым, чтобы закончить):")
                    if not okPressed or not number.strip():
                        break
                    self.phonebook.add_phone_number(person_id, number)
                QMessageBox.information(self, "Добавлено", "Контакт добавлен")
                # Обновление отображения всех контактов
                self.show_all_contacts()
            except pyodbc.Error as e:
                # Вывод предупреждения в случае ошибки добавления контакта
                QMessageBox.warning(self, "Ошибка", f"Ошибка при добавлении контакта: {e}")

    def edit_contact(self):
        # Запрос имени для поиска соответствующего человека
        name, okPressed = self.get_input("Редактировать контакт", "Имя:")
        if okPressed:
            # Получение id человека по имени
            person_id = self.phonebook.get_person_id_by_name(name)
            if person_id is not None:
                try:
                    # Получение существующих номеров телефона для данного человека
                    existing_numbers = self.phonebook.get_phone_numbers(person_id)
                    existing_numbers_str = "\n".join([number for _, _, number in existing_numbers])
                    # Вывод информации об существующих номерах
                    QMessageBox.information(self, "Существующие номера",
                                            f"Существующие номера:\n{existing_numbers_str}")

                    # Опции для обработки существующих номеров
                    options = ["Удалить все", "Удалить один", "Оставить все"]
                    option, okPressed = QInputDialog.getItem(self, "Редактировать контакт",
                                                             "Выберите вариант для существующих номеров:", options, 0,
                                                             False)

                    if okPressed:
                        if option == "Удалить все":
                            # Удаление всех существующих номеров
                            with self.conn.cursor() as cur:
                                cur.execute("DELETE FROM phone_numbers WHERE person_id = ?", (person_id,))
                                self.conn.commit()
                        elif option == "Удалить один":
                            # Опции для выбора номера для удаления
                            number_options = [f"{number}" for _, _, number in existing_numbers]
                            selected_number, okPressed = QInputDialog.getItem(self, "Редактировать контакт",
                                                                              "Выберите номер для удаления:",
                                                                              number_options, 0, False)

                            if okPressed:
                                # Получение id выбранного номера
                                selected_number_id = next((number_id for number_id, _, number in existing_numbers if
                                                           number == selected_number), None)
                                if selected_number_id is not None:
                                    # Удаление выбранного номера
                                    with self.conn.cursor() as cur:
                                        cur.execute("DELETE FROM phone_numbers WHERE person_id = ? AND id = ?",
                                                    (person_id, selected_number_id))
                                        self.conn.commit()

                    # Добавление новых номеров телефона
                    while True:
                        new_number, okPressed = self.get_input("Редактировать контакт",
                                                               "Новый номер (оставьте поле пустым, чтобы пропустить, или введите 'exit', чтобы закончить):")
                        if not okPressed or not new_number.strip() or new_number.strip().lower() == 'exit':
                            break
                        self.phonebook.add_phone_number(person_id, new_number)

                    # Получение обновленных номеров телефона после редактирования
                    updated_numbers = self.phonebook.get_phone_numbers(person_id)
                    updated_numbers_str = "\n".join(
                        [f"Обновленный номер: {number}" for _, _, number in updated_numbers])

                    # Получение нового имени для человека
                    new_name, okPressed = self.get_input("Редактировать контакт",
                                                         "Новое имя (оставьте поле пустым, чтобы пропустить):")
                    if new_name:
                        try:
                            # Редактирование контакта (имени и последнего номера телефона)
                            self.phonebook.edit_contact(person_id, new_name, updated_numbers[-1][2])
                            # Вывод информации о редактированном контакте
                            QMessageBox.information(self, "Отредактировано",
                                                    f"Контакт отредактирован:\n{updated_numbers_str}")
                            # Обновление отображения всех контактов
                            self.show_all_contacts()
                        except pyodbc.Error as e:
                            # Обработка исключения при смене имени на уже существующее
                            QMessageBox.warning(self, "Ошибка", f"Ошибка при редактировании контакта: {e}")
                    else:
                        # Если новое имя не введено, просто выводим информацию о редактированных номерах
                        QMessageBox.information(self, "Отредактировано",
                                                f"Контакт отредактирован:\n{updated_numbers_str}")
                        # Обновление отображения всех контактов
                        self.show_all_contacts()

                except pyodbc.Error as e:
                    # Вывод предупреждения в случае ошибки редактирования контакта
                    QMessageBox.warning(self, "Ошибка", f"Ошибка при редактировании контакта: {e}")

                # Обновление отображения всех контактов после завершения операций
                self.show_all_contacts()
            else:
                # Пользователь не найден, выводим предупреждение
                QMessageBox.warning(self, "Предупреждение", "Контакт не найден")

    def delete_contact(self):
        name, okPressed = self.get_input("Удалить контакт", "Имя:")
        if okPressed:
            person_id = self.phonebook.get_person_id_by_name(name)
            if person_id is not None:
                try:
                    with self.conn.cursor() as cur:
                        cur.execute("DELETE FROM phone_numbers WHERE person_id = ?", (person_id,))
                        cur.execute("DELETE FROM people WHERE id = ?", (person_id,))
                        self.conn.commit()
                        QMessageBox.information(self, "Удалено", "Контакт удален")
                        self.show_all_contacts()
                except pyodbc.Error as e:
                    QMessageBox.warning(self, "Ошибка", f"Ошибка при удалении контакта: {e}")
            else:
                QMessageBox.warning(self, "Предупреждение", "Контакт не найден")

    def search_contact(self):
        search_text, okPressed = self.get_input("Поиск контакта", "Введите имя для поиска:")
        if okPressed:
            result = self.phonebook.search_contact(search_text)
            if result:
                result_str = "\n".join([f"Имя: {name}, Номер: {number}" for name, number in result])
                QMessageBox.information(self, "Результат поиска", f"Контакт найден: \n{result_str}")
            else:
                QMessageBox.information(self, "Результат поиска", "Контакт не найден")

    def closeEvent(self, event):
        try:
            if self.conn and not self.conn.closed:
                self.conn.close()
        except pyodbc.Error as e:
            print(f"Ошибка при закрытии соединения с базой данных: {e}")


if __name__ == "__main__":
    app = QApplication([])
    ex = PhoneBookApp()
    ex.show()
    sys.exit(app.exec_())
