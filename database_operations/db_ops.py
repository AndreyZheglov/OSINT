import sqlalchemy
from sqlalchemy.orm import sessionmaker
from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    Sequence,
    String,
)
import pandas as pd
import logging
import json
from datetime import datetime



# variables
# database = 'sqlite:///osint_database_v3.db'
dbName = "osint_database_v4"
database = f'postgresql://postgres:postgres@192.168.88.17:5433/{dbName}'

path = 'database_operations/tablegroups.json'
# path = "tablegroups.json"

# database connection
engine = create_engine(database, echo=False)
Session = sessionmaker(bind=engine)
session = Session()


def remove_duplicates():
    pass


def read_tablegroups(filepath='database_operations/tablegroups.json'):

    with open(filepath, "r", encoding="utf-8") as file:
        return json.load(file)


def write_tablegroups(info: dict, filepath='database_operations/tablegroups.json'):
    with open(filepath, "w", encoding="utf-8") as file:
        json.dump(info, file, indent=4)


def return_pragma(tablename: str, tablegroup: str):

    try:
        # print(tablename)
        tablegroups = read_tablegroups(path)
        # print("Tablegroups: ", tablegroups)
        tablegroup_dict = tablegroups[tablegroup]
        # print(f"Tablegoup dictionary: {tablegroup_dict}")
        table_structure = tablegroup_dict[tablename]
        return table_structure
    except Exception as e:
        return e


def return_tablenames(dbName: str):
    with engine.begin() as conn:
        pragma = conn.execute(f"SELECT table_name from information_schema.tables where table_type = 'BASE TABLE' and table_schema = '{dbName}';")

        tablenames = [line[0] for line in pragma if len(line[0]) > 1]
        return tablenames


def count_records(tablename, parameter='', value=''):
    try:
        sql = f"""SELECT COUNT(*) FROM "{tablename}" """
        if parameter and value:
            sql += f" WHERE {parameter} LIKE '{value}%%'"

        elif parameter:
            sql += f" WHERE {parameter} IS NOT NULL"

        sql += ";"
        # print(sql)
        with engine.begin() as conn:
            result = conn.execute(sql).fetchall()
        # print(result[0])
        return result[0][0]
    except Exception as e:
        return 0


# Паше нехуйово
def upload_data(df, tablegroup: str, table_name="",  append_choise=False):

    # тут можна перевіряти чи є target_table_info. Якщо немає - створювати нову таблицю.
    if tablegroup:

        # Прописати механізм визначення ключових полів та полів, що є у вибраній таблиці

        field_names_list = []
        table_groups = read_tablegroups(path)

        if "Прізвище" in list(df.columns):
            surname_loc = df.columns.get_loc('Прізвище')
            print(1)
            if "Імя" in list(df.columns):
                print(2)
                name_loc = df.columns.get_loc("Імя")
                if "По-батькові" in list(df.columns):
                    patronymic_loc = df.columns.get_loc('По-батькові')
                    print(3)
                    df["ПІБ"] = df.iloc[:, surname_loc:patronymic_loc + 1].apply(
                        lambda x: ' '.join(x.dropna().astype(str)),
                        axis=1)
                    df.drop(columns=["По-батькові"])
                else:
                    df["ПІБ"] = df.iloc[:, surname_loc:name_loc + 1].apply(
                        lambda x: ' '.join(x.dropna().astype(str)),
                        axis=1)
                df.drop(columns=['Імя'])
            df.drop(columns=['Прізвище'])



        field_dict = get_fieldnames_for_tables(tablegroup, path, mode="write")


        # print(f"<field_dict: {field_dict}>")
        # print(field_dict)
        for element in field_dict.keys():
            print(element)
            field_names_list.extend(field_dict[element])
        field_names = set(field_names_list)
        # print(f"<field_names: {field_names}>")
        # print(df.columns)
        df_columns = set(df.columns)
        num_rows = df.shape[0]




        # Занесення даних до існуючої таблиці (Ця хуйня працює!!!!)
        equal_headers = df_columns & field_names
        if append_choise and table_name:

            headers = [element for element in list(df.columns)]
            # підготовка підгрунтя: занесення хедерів та імені таблиці
            if tablegroup in table_groups.keys():

                table_groups[tablegroup].update({table_name: headers})

            else:
                table_group_dict = {tablegroup: {table_name}}
                table_groups.update({tablegroup: {table_name: headers}})
            write_tablegroups(table_groups)

            # header equalization
            # Index are go fuck around
            # if 'id' not in df.columns:
            #     appending_df = pd.DataFrame({'id': list(range(1, df.shape[0]))})
            #     df = pd.concat([df, appending_df])

            df.to_sql(table_name, con=engine, if_exists='append', chunksize=10000, index=False)

        # erasing the columns that are absent in the group of tables
        # print(f"Field names: {field_names}")
        dropout_columns = list(df_columns - field_names)
        # print(f"Dropout cols: {dropout_columns}")
        df = df.drop(columns=dropout_columns)


        # appending empty fields and data equalization
        new_tables_dict = {}
        # print(f"Dataframe columns: {df.columns}")
        temp_header_list = set(df.columns)
        tables_dict = get_fieldnames_for_tables(tablegroup, path, mode="write")
        for table in tables_dict:
            # print(f"<{set(tables_dict[table])}><{temp_header_list}>")
            # print(len(set(tables_dict[table]) & temp_header_list))
            if 'id' in tables_dict[table]:
                tables_dict[table].pop(tables_dict[table].index('id'))
            if len(set(tables_dict[table]) & temp_header_list) >= 2:
                print("True!")
                new_tables_dict.update({table: tables_dict[table]})

        # print(f"Новий список таблиць: {new_tables_dict}")

        # ця хуйня не оптимізована чутка, але похуй
        absent_columns = list(field_names - df_columns)
        num_rows = df.shape[0]
        append_cols = {}
        for element in absent_columns:
            append_cols.update({element: [None] * num_rows})

        df_2 = pd.DataFrame(append_cols)
        df = pd.concat([df, df_2], axis=1)

        # if tablegroup == "Інформація про фізичних осіб":
        #     # Sorting dataframe and slicing
        #
        #     # 1. Sort dataframe
        #     df = df.sort_values(by=["ПІБ"])
        #     temp_header_list = list(set(new_tables_dict["Інше"]) & set(df.columns))
        #     temp_df = df.loc[:, temp_header_list]
        #     # 2. Slicing dataframe and sending info into database
        #     for letter in alphabet_list:
        #
        #         print(temp_header_list)
        #
        #         # чесно скацапизжене з гіта
        #         temp_df_1 = temp_df[temp_df['ПІБ'].str.startswith(letter)]
        #
        #         if not temp_df_1.empty:
        #             # inserting data into DB tables
        #             temp_df_1.to_sql(letter, con=engine, if_exists='append', chunksize=10000, index=False)
        #             # чистимо дуплікати
        #             # with engine.begin() as conn:
        #             #     conn.execute(f"""DELETE from "{letter}" where rowid in (select rowid
        #             #   from (
        #             #     select
        #             #       rowid,
        #             #       row_number() over (
        #             #         partition by {temp_df.columns[0]}, {temp_df.columns[1]}
        #             #         ) as n
        #             #     from "{letter}"
        #             #   )
        #             #   where n > 1); """)
        #
        #             # тоже не сам придумав
        #             # temp_df = temp_df[not(df['ПІБ'].str.startswith(letter))]
        #             df = df[~df['ПІБ'].str.startswith(letter)]
        #             # index = df.index
        #             # condition = df['ПІБ'].str.startswith(letter)
        #             # letter_indices = list(index[condition])
        #             # df.drop(index=letter_indices, inplace=True)
        #
        #
        # slicing dataframe and sending_data to sql tables
        for table in new_tables_dict.keys():
            temp_header_list = list(set(new_tables_dict[table]) & set(df.columns))
            # print(temp_header_list)
            temp_df = df.loc[:, temp_header_list]
            table_row_num = 0

            # print(append_cols)
            # temp_df = pd.concat([temp_df, df_2])

            temp_df.to_sql(table, con=engine, if_exists='append', chunksize=10000, index=False)
            # чистимо дуплікати
            # pragma = return_pragma(table, tablegroup)
  # Прописати хуйню на постгресі для видалення дуплікатів
  #           with engine.begin() as conn:
  #               conn.execute(f"""DELETE from "{table}" where rowid in (select rowid
  # from (
  #   select
  #     rowid,
  #     row_number() over (
  #       partition by {pragma[0]}, {pragma[1]}
  #       ) as n
  #   from "{table}"
  # )
  # where n > 1); """)

    # except Exception as e:
    #     # тут прологувати
    #     return(f"Дані не було занесено до бази({e})")


def return_tables_with_common_fields(tables: dict, field: str, target_table_name=""):
    # print(f"RTWCF params: \n\t{tables}, \n\t{field}, \n\t{target_table_name}")
    output_arr = []
    for table in tables.keys():
        if field in tables[table] and table != target_table_name:
            output_arr.append(table)

    return output_arr


def get_data_from_db(parameter: str, value: str, table_group: str, path=""):

    # 0. Визначаємо робочі таблиці. При роботі із ботом це поправити.
    index = 0
    sql = ""
    tables_dict = get_fieldnames_for_tables(table_group, path)  # словник: ключі - імена таблиць
    # print(f"Tables_dict: {tables_dict}")
    temp_tablegroup = read_tablegroups(path)
    table_names = [key for key in temp_tablegroup[table_group] if count_records(key)]
    target_tablename = ""
    return_rows = []

    search_tables = []

    # 1. Шукаємо в яких із таблиць є хедер

    # target_tablenames - змінна, в якій є всі таблиці зі схожим параметром
    table_names = []
    # print("<<2>>")
    target_tablenames = return_tables_with_common_fields(tables_dict, parameter)
    # print(target_tablenames)
    if len(target_tablenames) <= 0:
        return -1, -1
    else:
        print(f"Target_tablenames: {target_tablenames}")
        table_names = list(set(target_tablenames)-set(table_names))
        print(f"Tablenames: {table_names}")

    if len(target_tablenames) > 1:
        max_val = 0
        index = -1
            # опрацювати: поміряти кількість запитів
        for element in target_tablenames:
            with engine.begin() as conn:
                result = conn.execute(f"""SELECT COUNT(*) from "{element}" WHERE {parameter} LIKE '{value}%%';""").fetchall()
                    # if result
                if result[0][0] > max_val:
                    max_val = result[0][0]
                    index = target_tablenames.index(element)

        if max_val == 0 or index == -1:
            return -1, -1
        else:
            target_tablename = table_names[index]
            table_names.remove(target_tablename)

    else:
        target_tablename = table_names[0]

    print(tables_dict, table_names)
    headers_list = []

    # 2. Починаємо будувати запит
    print(f"<{target_tablename}>")
    sql = f'SELECT * FROM "{target_tablename}" '
    # print(f"<<{tables_dict}>>")
    # Додаємо INNER JOIN'и
    print(f"New sql query: {sql}")
    table_names_cp = table_names
    print("Tables_dict: ", tables_dict)
    print("Target tablename: ", target_tablename)
    headers_list.extend(tables_dict[target_tablename])
    primary_table = target_tablename

    primary_parameter = parameter
    primary_value = value
    if table_names and primary_table in table_names:
        table_names.remove(primary_table)
    # Початкова стрічка
    # перевірка доки масив імен таблиць не порожній

    while table_names:
        presence_flag = False
        new_val = value
        if len([key for key in tables_dict]) <= 1:
            break
        print(f"Target table name: {target_tablename}")

        # ітерація полів у вибраній таблиці
        for field in tables_dict[target_tablename]:

            # пропуск айдішніків
            if field == 'id':
                continue

            # Якщо поле рівне прізвищу, шукаємо в алфавітних таблицях
            # if field == 'ПІБ':
            #     table = value.strip()[0].upper()
            #     if (table in alphabet_list or table == "Інше") and (not f"INNER JOIN '{table}'" in sql and table != primary_table and count_records(table, 'ПІБ', new_val)):
            #         sql += f" INNER JOIN '{table}' ON '{table}'.{'ПІБ'} = '{target_tablename}'.{'ПІБ'}"
            #         table_names = [item for item in table_names if len(table_names) > 1 or item != "Інше"]

            # пошук таблиць зі схожими полями
            tables_with_common_fields = return_tables_with_common_fields(tables_dict, field)

            # Якщо знайдено таблиці із однаковими полями
            if tables_with_common_fields:

                # рахуємо взагалі кількість значень в таблиці
                count = count_records(target_tablename, field, value)
                if count and value:
                    with engine.begin() as conn:
                        # поправляємо лайк велью аби ріл по частині пріззвища шукало
                        new_sql = f"""SELECT {field} 
                FROM "{target_tablename}" 
                WHERE "{target_tablename}".{parameter} LIKE '{value}%%' AND "{target_tablename}".{parameter} IS NOT 
                NULL AND {field} IS NOT NULL;"""
                        # print("New sql:", new_sql)
                        new_val = conn.execute(new_sql).fetchall()[0][0]
                        # print(new_val)
                        value = new_val

                    # print("Field and new value:", field, new_val)
                else:
                    # print("Перехід на нове значення")
                    new_val = value

                # Ітеруємо по списку таблиць із однаковими полями
                for table in tables_with_common_fields:  # Перевіряємо поле, що рівне параметру

                    # print(f"Result of counting values({field},{new_val}) in {table}: {count_records(table, field, new_val)}")

                    # Якщо таблиця "світилась" у запиті чи це уже початкова таблиця чи 0 результатів
                    if f"""LEFT OUTER JOIN "{table}" """ in sql or table == primary_table:
                        # target_tablename = table
                        if table in table_names:
                            table_names.remove(table)
                        if table in tables_dict.keys():
                            tables_dict.pop(table)
                        continue

                    else:
                        headers_list.extend(tables_dict[table])
                        # print(f"Table and field: {table} {field} {value} count_flag={count_records(table, field, value)}")
                        sql += f""" LEFT OUTER JOIN "{table}" ON "{table}".{field} = "{target_tablename}".{field}"""
                        print(sql)
                        parameter = field
                        target_table = table
                        # value = new_val
                        # print(tables_with_common_fields)
                        # print(f"Query:{sql}\nTable Dict keys: [{tables_dict.keys()}]\nTarget tablename={target_tablename}")

    sql += f''' WHERE "{primary_table}".{primary_parameter} LIKE '{primary_value}%%'; ''' # %%
    print(f"Resulting query: {sql}")
    engine.execute(sqlalchemy.text(sql))
    with engine.begin() as conn:
        result = conn.execute(sql).fetchall()


    return_rows.extend([row for row in result])
    table_names = table_names_cp
    sql = ""

    return return_rows, headers_list


# Поля для кожної таблиці у вигляді словника: назва таблиці: поля
def get_fieldnames_for_tables(table_group: str, path="", mode="read"):
    global dbName
    table_groups = read_tablegroups(path)
    print(f"<<tablegroups: {table_groups}>>")
    table_group_dict = table_groups[table_group]
    if table_group not in table_groups.keys():
        return "Немає такої групи"

    tablenames = return_tablenames(dbName)
    output_dict = {}
    for tablename in table_group_dict.keys():
            output_dict.update({tablename: return_pragma(tablename, table_group)})

    return output_dict


# Метод для всіх полів усіх таблиць
def get_all_fieldnames():
    fieldnames = []
    for table_name in return_tablenames(dbName):
        pragma = return_pragma(table_name)
        fieldnames.extend(pragma)
    fieldnames = set(fieldnames)
    if 'id' in fieldnames:
        fieldnames = fieldnames - {'id'}
    return fieldnames


def return_allowed_fields(tablename: str):

    try:
        with open("database_operations/searchable_params.json", "r", encoding="utf-8") as file:
            data = json.load(file)
            print(data)
            return data[tablename]
    except Exception as e:
        pass


def create_indices(tablename: str, col_list: list):
    try:

        for element in col_list:
            sql = f"CREATE index {element}_idx on '{tablename}'({element});"
            engine.execute(sql)

        return "Індекси створено"

    except Exception as e:
        return "Індекси не створено"



# time_0 = datetime.now()
# filename = "Rostelecom-drain (1).xlsx"
# df = pd.read_excel(filename, header=0)
# print('ПІБ' in df.columns)
# upload_data(df, tablegroup="Інформація про фізичних осіб")
# print(f"Elapsed time: {datetime.now() - time_0}")

# get data from database
#
# time_0 = datetime.now()
#
# data, header = get_data_from_db("ПІБ", "Дубиняк Руслан", "Інформація про фізичних осіб", "tablegroups.json")
# print(header)
# print("Результат пошуків:")
# for row in data:
#      print(row)
# print(f"Elapsed time: {datetime.now() - time_0}")
# print(header)
# print(data)