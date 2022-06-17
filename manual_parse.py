import pandas as pd

import parsers
from database_operations import db_ops
import os
from fpdf import FPDF


def parse_file(filename):

    # парсимо файл в датафрейм
    df = pd.read_table(filename, sep="|", encoding="Windows-1251", error_bad_lines=False)

    # перевірка чи є прізвище, ім'я, по-батькові хедерах
    #
    print(df.columns)
    #

    if "Прізвище" in list(df.columns):
        surname_loc = df.columns.get_loc('Прізвище')
        print(1)
        if "Імя" in list(df.columns):
            print(2)
            name_loc = df.columns.get_loc("Імя")
            if "По-батькові" in list(df.columns):
                patronymic_loc = df.columns.get_loc('По-батькові')
                print(3)
                df["ПІБ"] = df.iloc[:, surname_loc:patronymic_loc+1].apply(
    lambda x: ' '.join(x.dropna().astype(str)),
    axis=1)
                # df.drop(["По-батькові"])
            else:
                df["ПІБ"] = df.iloc[:, surname_loc:name_loc+1].apply(
                    lambda x: ' '.join(x.dropna().astype(str)),
                axis=1)
            # df.drop(["Імя"])
        # df.drop(["Прізвище"])
    print(df.head())
    return df

# path = "D://Python Projects/database_operations/"
# # df = pd.read_csv(path)
# # db_ops.upload_data(df, tablegroup="Інформація про фізичних осіб")
#
# for root, dirs, files in os.walk(path):
#     for file in files:
#         print(file)
#         if "csv" in file:
#             print("Іде занесення наступного файлу до БД: ", file)
#
#             df = pd.read_csv(path+"/"+file)
#             db_ops.upload_data(df, tablegroup="Інформація про фізичних осіб")

