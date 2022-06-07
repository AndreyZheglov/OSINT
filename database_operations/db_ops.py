from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    Sequence,
    String,
)
import pandas as pd
import parsers
import json


# variables
database = 'sqlite:///database_operations/osint_database_v2.db'
# database = 'sqlite:///osint_database_v2.db'
path = 'database_operations/tablegroups.json'

# database connection
engine = create_engine(database, echo=False)
Session = sessionmaker(bind=engine)
session = Session()


def read_tablegroups(filepath='database_operations/tablegroups.json'):

    with open(filepath, "r", encoding="utf-8") as file:
        return json.load(file)


def write_tablegroups(info: dict, filepath='database_operations/tablegroups.json'):
    with open(filepath, "w", encoding="utf-8") as file:
        json.dump(info, file, indent=4)


def return_pragma(tablename: str):

    try:
        with engine.begin() as conn:
            pragma = conn.execute(f"PRAGMA table_info('{tablename}');")
            table_structure = [line[1] for line in pragma]
        return table_structure
    except Exception as e:
        return e


def return_tablenames():
    with engine.begin() as conn:
        pragma = conn.execute("SELECT name FROM sqlite_master WHERE type = 'table';")

        tablenames = [line[0] for line in pragma]
        return tablenames


def count_records(tablename, parameter='', value=''):
    sql = f"SELECT COUNT() FROM '{tablename}'"
    if parameter and value:
        sql += f" WHERE {parameter} LIKE '%{value}%'"
    sql += ";"
    with engine.begin() as conn:
        result = conn.execute(sql).fetchall()
    return result[0][0]

# ! Головне нагадати, аби при внесенні даних до існуючої таблиці перевіряли аби перше поле(перший стовпчик)\
# ! власне був тіпа ключовим


# Паше нехуйово
def upload_data(df, tablegroup: str, table_name="",  append_choise=True):

    # тут можна перевіряти чи є target_table_info. Якщо немає - створювати нову таблицю.
    if tablegroup:
        # print(f"<{df}, {tablegroup}>")
        # Прописати механізм визначення ключових полів та полів, що є у вибраній таблиці

        field_names_list = []
        field_dict = get_fieldnames_for_tables(tablegroup, path)
        for element in field_dict.keys():
            field_names_list.extend(field_dict[element])
        field_names = set(field_names_list)
        print(df.columns)
        df_columns = set(df.columns)
        num_rows = df.shape[0]

        # header equalization
        # Занесення даних до існуючої таблиці (Ця хуйня працює!!!!)
        equal_headers = df_columns & field_names
        if not append_choise and table_name:
            if 'id' not in df.columns:
                appending_df = pd.DataFrame({'id': list(range(1, df.shape[0]))})
                df = pd.concat([df, appending_df])
                appending_df = {}
            df.to_sql(table_name, con=engine, if_exists='append', chunksize=10000, index=True, index_label='id')

        # erasing the columns that are absent in the group of tables
        print(f"Field names: {field_names}")
        dropout_columns = list(df_columns - field_names)
        print(f"Dropout cols: {dropout_columns}")
        df = df.drop(columns=dropout_columns)

        # appending empty fields and data equalization
        new_tables_dict = {}
        print(f"Dataframe columns: {df.columns}")
        temp_header_list = set(df.columns)
        tables_dict = get_fieldnames_for_tables(tablegroup, path)
        for table in tables_dict:
            print(f"<{set(tables_dict[table])}><{temp_header_list}>")
            print(len(set(tables_dict[table]) & temp_header_list))
            if 'id' in tables_dict[table]:
                tables_dict[table].pop(tables_dict[table].index('id'))
            if len(set(tables_dict[table]) & temp_header_list) >= 2:
                print("True!")
                new_tables_dict.update({table: tables_dict[table]})

        print(f"Новий список таблиць: {new_tables_dict}")

        # ця хуйня не оптимізована чутка, але похуй
        absent_columns = list(field_names - df_columns)
        num_rows = df.shape[0]
        append_cols = {}
        for element in absent_columns:
            append_cols.update({element: [None] * num_rows})

        df_2 = pd.DataFrame(append_cols)
        df = pd.concat([df, df_2], axis=1)

        # slicing dataframe and sending_data to sql tables
        for table in new_tables_dict.keys():
            temp_header_list = list(set(new_tables_dict[table]) & set(df.columns))
            print(temp_header_list)
            temp_df = df.loc[:, temp_header_list]
            table_row_num = 0

            print(append_cols)
            # temp_df = pd.concat([temp_df, df_2])

            temp_df.to_sql(table, con=engine, if_exists='append', chunksize=10000, index=False)
            # чистимо дуплікати
            with engine.begin() as conn:
                conn.execute(f"""DELETE from "{table}" where rowid in (select rowid
  from (
    select
      rowid,
      row_number() over (
        partition by {temp_df.columns[0]}, {temp_df.columns[1]}
        ) as n
    from "Інформація про особу"
  )
  where n > 1); """)

    # except Exception as e:
    #     # тут прологувати
    #     return(f"Дані не було занесено до бази({e})")


def return_tables_with_common_fields(tables: dict, field: str, target_table_name=""):
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
    table_names = [key for key in tables_dict.keys() if count_records(key)]
    target_tablename = ""

    # 1. Шукаємо в якій із таблиць є хедер
    target_tablenames = return_tables_with_common_fields(tables_dict, parameter)
    print(target_tablenames)

    if len(target_tablenames) > 1:
        max_val = 0
        index = -1
        # опрацювати: поміряти кількість запитів
        for element in target_tablenames:
            with engine.begin() as conn:
                result = conn.execute(f"SELECT COUNT() from '{element}' WHERE {parameter} LIKE '%{value}%';").fetchall()
                if result[0][0] > max_val:
                    max_val = result[0][0]
                    index = target_tablenames.index(element)

        if max_val == 0:
            return -1, -1

        target_tablename = target_tablenames[index]

    else:
        target_tablename = target_tablenames[0]

    # 2. Починаємо будувати запит
    sql += f"SELECT * from '{target_tablename}'"  # Початкова стрічка
    headers_list = []
    headers_list.extend(tables_dict[target_tablename])
    primary_table = target_tablename
    print(f"<<{tables_dict}>>")

    # Додаємо INNER JOIN'и
    index = 0
    primary_parameter = parameter
    primary_value = value
    table_names.remove(primary_table)

    # перевірка доки масив імен таблиць не порожній
    while table_names:
        presence_flag = False

        if len([key for key in tables_dict]) <= 1:
            break
        print(f"Target table name: {target_tablename}")

        # ітерація полів у вибраній таблиці
        for field in tables_dict[target_tablename]:

            # пропуск айдішніків
            if field == 'id':
                continue

            # пошук таблиць зі схожими полями
            tables_with_common_fields = return_tables_with_common_fields(tables_dict, field)

            # Якщо знайдено таблиці із однаковими полями
            if tables_with_common_fields:

                new_val = ""
                with engine.begin() as conn:
                    new_sql = f"""SELECT {field} 
FROM '{target_tablename}' 
WHERE '{target_tablename}'.{parameter} LIKE '%{value}%';"""
                    new_val = conn.execute(new_sql).fetchall()[0][0]
                print("New sql:", new_sql)
                print("Field and new value:", field, new_val)

                # Ітеруємо по списку таблиць із однаковими полями
                for table in tables_with_common_fields:  # Перевіряємо поле, що рівне параметру
                    print(f"Result of counting values({field},{new_val}) in {table}: {count_records(table, field, new_val)}")

                    # Якщо таблиця "світилась" у запиті чи це уже початкова таблиця чи 0 результатів
                    if f"INNER JOIN '{table}'" in sql or table == primary_table or not count_records(table, field, new_val):
                        # target_tablename = table
                        if table in table_names:
                            table_names.remove(table)
                        if table in tables_dict.keys():
                            tables_dict.pop(table)
                        continue

                    else:
                        headers_list.extend(tables_dict[table])
                        sql += f" INNER JOIN '{table}' ON '{table}'.{field} = '{target_tablename}'.{field}"
                        print(sql)
                        parameter = field
                        target_table = table
                        value = new_val
                        print(tables_with_common_fields)
                        print(f"Query:{sql}\nTable Dict keys: [{tables_dict.keys()}]\nTarget tablename={target_tablename}")

    sql += f" WHERE '{primary_table}'.{primary_parameter} LIKE '%{primary_value}%';"

    with engine.begin() as conn:
        result = conn.execute(sql).fetchall()

    return_rows = []
    for row in result:
        return_rows.append(row)
    return return_rows, headers_list


# Поля для кожної таблиці у вигляді словника: назва таблиці: поля
def get_fieldnames_for_tables(table_group: str, path=""):
    table_groups = read_tablegroups(path)

    if table_group not in table_groups.keys():
        return "Немає такої групи"

    tablenames = return_tablenames()
    output_dict = {}
    for tablename in table_groups[table_group]:
        if count_records(tablename):
            output_dict.update({tablename: return_pragma(tablename)})
    return output_dict


# Метод для всіх полів усіх таблиць
def get_all_fieldnames():
    fieldnames = []
    for table_name in return_tablenames():
        pragma = return_pragma(table_name)
        fieldnames.extend(pragma)
    fieldnames = set(fieldnames)
    if 'id' in fieldnames:
        fieldnames = fieldnames - {'id'}
    return fieldnames
