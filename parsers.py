import csv
import xlsxwriter
import json
import re
from database_operations import db_ops
import pandas as pd
from datetime import datetime, date
from sqlalchemy.orm import declarative_base
from sqlalchemy import (
    create_engine,
)
from fpdf import FPDF
import os
import unicodedata
#


"""
    "CREATE TABLE IF NOT EXISTS {db_name}.{table_name} ( \
                    #   id int(11) NOT NULL AUTO_INCREMENT, \
                    #   full_name varchar(50) NOT NULL, \
                    age varchar(50) NULL, \
                    #   mob_tel varchar(50) NULL, \
                    home_tel varchar(50) NULL, \
                    contact_tel varchar(50) NULL, \
                    #   address varchar(50) NULL, \
                    birth_date varchar(50) NULL, \
                    birth_address varchar(50) NULL, \
                    #   gender varchar(50) NULL, \
                    #   email varchar(50) NOT NULL,\
                    passport_id varchar(50) NOT NULL,\
                    passport_issued_by varchar(50) NOT NULL,\
                    passport_issue_date varchar(50) NOT NULL,\
                    tax_id  varchar(50) NOT NULL,\
                    source varchar(480) NOT NULL,\
                    PRIMARY KEY(id) \
                   )
    """
# спизжено із гіта
class FPDF_multicell(FPDF):


    def write_multicell_with_styles(self, max_width, cell_height, text_list):
        startx = self.get_x()
        # self.set_font('DejaVuSans', '', 12)

        #loop through differenct sections in different styles
        for text_part in text_list:
            #check and set style
            try:
                current_style = text_part['style']
                self.set_font('DejaVuSans', current_style, 10)
            except KeyError:
                print("А от хуй!")
                self.set_font('DejaVuSans', '', 10)

            #loop through words and write them down
            space_width = self.get_string_width(' ')
            for word in text_part['text'].split(' '):
                current_pos = self.get_x()
                word_width = self.get_string_width(word)
                #check for newline
                if (current_pos + word_width) > (startx + max_width):
                    #return
                    self.set_y(self.get_y() + cell_height)
                    self.set_x(startx)
                self.cell(word_width, 5, word) #
                #add a space
                self.set_x(self.get_x() + space_width)


def log_event(event, filename="userlog.txt"):
    with open(filename, "a", encoding="utf-8") as log:
        log.write(f"{datetime.now()} --> {event}")


def refresh_logs():

    # retrieving data from log
    with open("userlog.txt", "r", encoding="utf-8") as file:
        log_data = file.readlines()
    for record in log_data:
        print(record, type(record))
        record_date = try_parsing_date(record[:10])
        delta = datetime.today()-record_date
        if delta.days > 5:
            log_data.pop(log_data.index(record))

    # rewriting bot.log
    with open("userlog.txt", "w", encoding="utf-8") as file:
        file.writelines(log_data)


def unicode_normalize(s):
    return unicodedata.normalize('NFKD', s).encode('ascii', 'ignore')

# necessary variables for futher operations
csv_header = [
    "ПІБ",                  # 1
    "ДН",                   # 2
    "АДРЕСА",               # 3
    "МІСЦЕ РОБОТИ/СЛУЖБИ",  # 4
    "ПОСАДА/ЗВАННЯ",        # 5
    "ТЕЛ",                  # 6
    "ЕЛ.ПОШТА",             # 7
    "СОЦМЕРЕЖІ",            # 8
    "ПАСПОРТ",              # 9
    "СЕРІЯ",                # 10
    "ІД"                    # 11
]
header_orm = {
    "ПІБ": "fullname",                  # 1
    "ДН": "birth",                   # 2
    "АДРЕСА": "address",               # 3
    "МІСЦЕ РОБОТИ/СЛУЖБИ": "workplace",  # 4
    "ПОСАДА/ЗВАННЯ": "position",        # 5
    "ТЕЛ": "phone_number",                  # 6
    "ЕЛ.ПОШТА": "email",             # 7
    "СОЦМЕРЕЖІ": "social",            # 8
    "ПАСПОРТ": "passport",              # 9
    "СЕРІЯ": "series",                # 10
    "ІД": "id_number"                    # 11
}


AVAILABLE_FORMATS = ['.csv', '.xls/.xlsx', '.txt']
PHOTO_FORMATS = ['jpeg', 'jpg', 'png', 'bmp']
csv_path = __file__.replace('parsers.py', 'person_info.csv')
Base = declarative_base()


# для гарного виведення словника
def beautify_dict_output(data: dict) -> str:
    return_str = ""
    for key in data.keys():
        return_str += f"{key}: {data[key]}\n"
    return return_str


def return_pragma(fields: dict) -> dict:
    pragma = {}
    additional_list = []
    for element in fields.values():
        additional_list.extend(element)
    additional_list = list(dict.fromkeys(additional_list))
    if 'id' in additional_list:
        additional_list.remove('id')

    for key in additional_list:
        pragma.update({additional_list.index(key) + 1: key})

    return pragma


class User:

    def __init__(self, username: str, PIN: int, telegram_id: int, admin: bool):

        # stuff for authentication
        self.username = username
        self.PIN = PIN
        self.telegram_id = telegram_id
        self.admin = admin

        # stuff for bot functioning

        # dictionary of parameters, that is used in input/output operations
        self.param_dict = {}

        # string, that contains type of input
        self.input_choice = ""

        # pragma for DB
        self.pragma = {}

        self.append_choice = ""
        self.param = ""

        # boolean, that is used to determine whether OCR (False) or S4F functionality (True) will be used
        self.photo_search_flag = False

        # string, that contains table group, in/to which information will be searched/added
        self.table_group_name = ""

        #
        self.pragma = {}


    def __str__(self):
        return f'''Ім'я користувача:{self.username}
ПІН:{self.PIN}
Телеграм ІД:{self.telegram_id}                
Адмін:{self.admin}                                
'''

    def to_json(self):
        return {"username": self.username, "PIN": self.PIN, "telegram_id": self.telegram_id, "admin": self.admin}


def user_init(data: dict):
    return User(data['username'], data['PIN'], data['telegram_id'], data['admin'])


def parse_users():
    filename = __file__.replace('parsers.py', 'allowed_users.json')
    with open(filename, "r", encoding="utf-8") as file:
        data = json.load(file)
        users = [user_init(fragment) for fragment in data]
    return users


def config_write(userslist: list, filename: str):
    json_list = [user.to_json() for user in userslist]
    with open(filename, "w", encoding="utf-8") as file:
        json.dump(json_list, file, indent=4)


def write_csv(data: list, header=csv_header, path=csv_path):

    with open(path, 'w', encoding="utf-8", newline='') as file:
        writer = csv.writer(file)
        writer.writerow(header)
        writer.writerows(data)


def available_formats():
    out_string = ""
    for i in range(len(AVAILABLE_FORMATS)):
        out_string  += f"{i+1}. {AVAILABLE_FORMATS[i]}" + '\n'
    return out_string


def available_headers():
    out_string = ""
    for header in csv_header:
        out_string += f"{csv_header.index(header)+1}. {header}\n"
    out_string += "\nПримітка:\nДН: дата народження\nІД: ідентифікаційний номер"
    return out_string


def update_element(updatable_list: list, input_list: list):

    for index in range(len(updatable_list)):
        updatable_list[index] = input_list[index] if input_list[index] not in {"-", " ", "None"} \
            else updatable_list[index]


def find_element(data, header: list, key: str, value: str):

    output_arr = []
    if len(data) == 0:
        return None
    for sublist in data:
        if sublist[header.index(key)] in value:
            output_arr.append(sublist)

    return (output_arr, data.index(output_arr[0])) if len(output_arr) > 0 else (None, None)


def write_xlsx(filename: str, data: list, header=csv_header):
    workbook = xlsxwriter.Workbook(filename)
    worksheet = workbook.add_worksheet('Список осіб')
    worksheet.write_row(0, 0, header)
    for element in data:
        worksheet.write_row(data.index(element)+1, 0, element)
    workbook.close()


def try_parsing_date(text):
    for fmt in ('%Y-%m-%d', '%Y/%m/%d', '%Y.%m.%d', '%d.%m.%Y', '%d/%m/%Y', '%d.%m.%Y'):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            pass
    raise ValueError('no valid date format found')


def date_parse(data: str):
    """
    Formats of date can be found by the function:
        -    1900/12/01
        -    2019.01.25
        -    2099-10-30
        -    vice versa
    """
    result = re.search(r"(0[1-9]|[12][0-9]|3[01])[-/.](?:0[1-9]|1[012])[-/.](?:19\d{2}|20[01][0-9]|20[0-9]{2})",
                       data)
    return result.group() if result is not None else None


def phone_parse(data: str):

    """
    Phone numbers can be found:
        -   +919367788755
        -   8989829304
        -   +16308520397
        -   786-307-3615
    """

    result = re.findall(r"[\+]?[(]?[0-9]{3}[)]?[-\s\.]?[0-9]{3}[-\s\.]?[0-9]{4,6}", data)
    return ",".join(result) if result != None else None


def email_parse(data: str):

    result = re.findall(r"(?:^|\s)[\w!#$%&'*+/=?^`{|}~-](\.?[\w!#$%&'*+/=?^`{|}~-]+)*@\w+[.-]?\w*\.[a-zA-Z]{2,3}\b",
                        data)
    return ",".join(result) if result != [] else None


def sites_parse(data: str):
    result = re.findall(r"http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+", data)
    return ",".join(result) if result != [] else None



def parse_file(file: str, table_group_name: str, tablename:str, append_choise=True):
    msg = ""
    columns = []
    filetype = file[len(file) - 5:len(file)]
    print(filetype)
    # checking if filetype can be processed
    filetype_flag = True
    photo_flag = False
    for form in AVAILABLE_FORMATS:
        if form in filetype or filetype  in form:
            filetype_flag = False
            break

    for photo in PHOTO_FORMATS:
        if photo in filetype:
            photo_flag = True
            break

    if photo_flag:
        return "Для обробки фотографії спробуйте іншу опцію та надішліть фотографію \
у нестисненому виглді"


    elif filetype_flag:
        return "На жаль, даний тип файлів ще не реалізовано"

    else:
        flag = False
        if file:
            columns = parser(file, table_group_name, tablename, append_choice=append_choise)
            flag = True
    if file:
        os.system(f"DEL {file}")
    if flag:
        return "Дані занесено до БД.", None
    if not flag:
        return "Дані не було занесено до БД", None


# general parsing choice
def parser(filename: str, table_group_name: str, tablename:str, append_choice: bool, delimiter="\t"):

    filetype = filename[len(filename)-5:len(filename)]
    df = None
    if ".csv" in filetype:
        df = pd.read_csv(filename)

    elif ".xlsx" in filetype:
        df = None
        excelFile = pd.ExcelFile(filename)
        for sheet in excelFile.sheet_names:
            if df is None:
                df = pd.read_excel(filename, header=0, sheet_name=sheet)
            else:
                new_df = pd.read_excel(filename, header=0, sheet_name=sheet)
                df.append(new_df, ignore_index=False, verify_integrity=False)

    elif ".txt" in filetype:
        df = pd.read_table(filename)

    else:
        print(f"Parser for {filetype} has not been impemented yet.")
        return False

    columns = list(df.columns)

    flag = db_ops.upload_data(df, table_group_name, table_name=tablename,
                              append_choise=append_choice)
    return columns

# db parser
def db_parse(database_name: str, table_name):
    try:
        engine = create_engine(f"sqlite:///")
        dataframe = pd.read_csv()
    except Exception:
        return -1
    pass


# csv parser
def csv_parse(filename: str):

    with open(filename, 'r', encoding="utf-8") as file:
        reader = csv.reader(file)
        header = next(reader)
        data = [row for row in reader]

    return header, data


# text parser
def txt_parse(filename: str, delimiter='\t'):

    with open(filename, 'r') as file:
        reader = file.read().splitlines()
        header = reader[0].split(delimiter)
        data = [element.split(delimiter) for element in reader[1:]]
    return header, data


# writing to csv
def to_csv(data: list, out_file=csv_path, header=csv_header):

    # loading data from csv
    path = __file__.replace('parsers.py', 'person_info.csv')
    with open(path, 'r', encoding='utf-8') as file:
        reader = csv.reader(file)
        header_1 = next(reader)
        info_from_csv = [element for element in reader]

    # set for further check
    checker_set = {"None", "-"}

    # standardizing header
    upper_header = [element.upper().strip() for element in header]

    # data standardization
    csv_data = []
    for element in data:
        csv_element = []
        for header_element in csv_header:
            header_element_upper = header_element.upper()
            if header_element_upper in upper_header:
                if header_element_upper == "ДН":
                    csv_element.append(try_parsing_date(element[upper_header.index(header_element_upper)]))
                else:
                    data_element = str(element[upper_header.index(header_element_upper)]).strip()
                    csv_element.append(data_element)
            else:
                csv_element.append(None)
        print(csv_element)

    # check for empty data
        if len(set(csv_element) - checker_set) > 1:
            if len(info_from_csv) > 0:
                updatable_list, index = find_element(info_from_csv, csv_header, "ПІБ", csv_element[0])
                if updatable_list != None:
                    update_element(updatable_list[0], csv_element)
                    info_from_csv[index] = updatable_list[0]
                    print(f"Record for {csv_element[0]} has been modified")
                    continue
            csv_data.append(csv_element)

    # forming a resulting data list
    info_from_csv.extend(csv_data)
    print(info_from_csv)

    # appending to csv
    write_csv(csv_data, csv_header)

    return True


def get_data(path: str, user: User):

    # print("Пошук здійснено")
    # print(user.param_dict)
    if not user.param_dict:
        return "Список параметрів порожній"

    # getting the first parameter
    parameter = list(user.param_dict.keys())[0]
    value = user.param_dict[parameter]

    user.param_dict.pop(parameter)

    # getting data from database
    data, header = db_ops.get_data_from_db(parameter, value, user.table_group_name, path)
    return_data = data

    if data is int:
        return data

    elif data is list:

        for key in user.param_dict:
            for row in data:
                print(header.index(key), key)
                if user.param_dict[key] not in row[header.index(key)]:
                    return_data.remove(row)
                    # print(f"Row to be removed: {row}")

        for key in list(header):
            if header.count(key):
                indexes = [n for n, x in enumerate(header) if x == key]
                for index in range(1, len(indexes), -1):
                    header.pop(index)
                    for row in return_data:
                        row.pop(index)

    data = return_data

    if len(data) > 30:
        return -5

    elif len(data) == 1:
        # print(f"Data to be printed: {data}")
        msg = ""
        for row in data:
            # print(row)
            for key in header:

                if row[header.index(key)] and msg.find(row[header.index(key)]) == -1:
                    msg += f"{key}: {row[header.index(key)]}\n"
                # print("Message to be sent:", msg)
        return msg

    # data rectification


    # print(f"Data after rectification: {data}")
    if data:
        write_pdf(data, header)
        return "Результати пошуку.pdf"

    else:
        return "За даним запитом нічого не було знайдено"

def write_pdf(data: list, header: list):
    # creating pdf file and
    pdf = FPDF_multicell()
    pdf.add_font('DejaVuSans', '', 'Fonts/DejaVuSans.ttf', uni=True)
    pdf.add_font('DejaVuSans', 'B', 'Fonts/DejaVuSans-Bold.ttf', uni=True)
    # pdf.set_font("DejaVu", size=12)

    pdf.add_page()

    # Adding header
    pdf.set_font('DejaVuSans', 'B', 20)
    # Move to the right
    pdf.cell(80)

    page = 0
    if pdf.page_no() != page:
        pdf.image('Fonts/bugs bunny.png', x=0, y=0, w=210, h=297)
        page = pdf.page_no()

    pdf.cell(30, 10, txt='Результати пошуку', border=0, align='C')
    # Line break
    pdf.ln(20)
    pdf.set_margins(10, 10, 10)

    pdf.set_font('DejaVuSans', '', 10)
    msg = ""

    for row in data:

        for key in header:
            if row[header.index(key)] and msg.find(row[header.index(key)]) == -1:

                # костиль
                msg += f"{key}: {row[header.index(key)]}\n"

                pdf_val = row[header.index(key)]
                pdf_key = f"{key}:"
                row_list = [
                    {'style': 'B', 'text': pdf_key},
                    {'style': '', 'text': pdf_val},
                ]
                print(row_list)
                if pdf.page_no() != page:
                    pdf.image('Fonts/bugs bunny.png', x=0, y=0, w=210, h=297)
                    page = pdf.page_no()
                # pdf.multi_cell(180, 6, f"{pdf_key}: {pdf_val}")
                pdf.write_multicell_with_styles(180, 6, row_list)
                pdf.cell(180, 6, "", ln=1)
        pdf.cell(180, 6, "", ln=1)

    pdf.output("Результати пошуку.pdf")
# def write_pdf(data: list, header: list):
#     # creating pdf file and
#     pdf = FPDF_multicell()
#     pdf.add_font('DejaVuSans', '', 'Fonts/DejaVuSans.ttf', uni=True)
#     pdf.add_font('DejaVuSans', 'B', 'Fonts/DejaVuSans-Bold.ttf', uni=True)
#     # pdf.set_font("DejaVu", size=12)
#
#     pdf.add_page()
#
#     # Adding header
#     pdf.set_font('DejaVuSans', 'B', 20)
#     # Move to the right
#     pdf.cell(80)
#
#     pdf.cell(30, 10, txt='Результати пошуку', border=0, align='C')
#     # Line break
#     pdf.ln(20)
#     pdf.set_margins(10, 10, 10)
#
#     pdf.set_font('DejaVuSans', '', 10)
#
#     for row in data:
#
#         for key in header:
#             if row[header.index(key)] and key != 'id':
#                 pdf_val = row[header.index(key)]
#                 pdf_key = f"{key}:"
#                 row_list = [
#                     {'style': 'B', 'text': pdf_key},
#                     {'style': '', 'text': pdf_val},
#                 ]
#                 print(row_list)
#                 # pdf.multi_cell(180, 6, f"{pdf_key}: {pdf_val}")
#                 pdf.write_multicell_with_styles(180, 6, row_list)
#                 pdf.cell(180, 6, "", ln=1)
#         pdf.cell(180, 6, "", ln=1)
#
#     pdf.output("Результати пошуку.pdf")

