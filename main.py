import telebot
from telebot import types
import numpy as np
import re
import requests
from bs4 import BeautifulSoup as bs
import pandas as pd
from settings import API_TOKEN

#Коннектимся к боту
bot = telebot.TeleBot(API_TOKEN)
bot.set_webhook()
#Подключаем таблицу размеров дисков
disks = pd.read_csv('disk_size.csv', delimiter=";",
                        names=['Размер шины', 'Минимальная', 'Рекомендуемая', 'Максимальная'])


#Ошибка для европейских размеров
error_mes = "Ошибка! Возможно, вы ввели данные в неправильном формате или они не являются европейским размером шин. \n\nВновь выберите функцию и попробуйте еще раз."
#Ошибка для дюймовых размеров
error_inch = "Ошибка! Возможно, вы ввели данные в неправильном формате или они не являются дюймовым размером шин. \n\nВновь выберите функцию и попробуйте еще раз."


def info_check(tyre):
    """
    Проверка данных на то, что это размер.
    Возвращает True, если указан европейский размер шины в правильном формате.
    """
    tyre = re.split("/|R|r| ", tyre) #Создаем список с размерами шины
    return len(tyre) == 3 and len(tyre[0]) == 3 and len(tyre[1]) == 2 and len(tyre[2]) == 2 \
           and np.all([(tyre[i]).isdigit() for i in range(3)]) and (int(tyre[0]) % 10 == 5 or int(tyre[0]) % 10 == 0) \
           and (int(tyre[1]) % 10 == 0 or int(tyre[1]) % 10 == 5)


def info_check_inch(tyre):
    """
    Проверка данных на то, что это размер.
    Возвращает True, если указан американский размер шины в правильном формате.
    """
    def is_number(str):
        try:
            float(str)
            return True
        except ValueError:
            return False

    tyre = re.split("/|R|r| ", tyre)
    return len(tyre[0]) == 2 and len(tyre[1]) <= 4 and len(tyre[2]) == 2 \
           and np.all([is_number(tyre[i]) for i in range(3)])


def height_calc(tyre):
    """
    Калькулятор высоты колеса.
    Возвращает внешний диаметр в мм.
    """
    if info_check(tyre) == True: #Проверяем данные
        tyre = re.split("/|R|r| ", tyre) #Создаем список с размерами шины
        width = int(tyre[0])
        height = int(tyre[1])
        raduis = int(tyre[2])
        return int(width * (height / 100) * 2 + raduis * 25.4)
    else:
        return False


def height_calc_inch(tyre):
    """
    Поиск дюймового значения диаметра колеса.
    Возвращаем диаметр в дюймах.
    """
    tyre = height_calc(tyre) #Ищем диаметр шины
    return round(tyre/25.4)


def compare(old_tyre, new_tyre):
    """
    Сравнение размеров новой и старой резины.
    Возвращаем разницу в размере.
    """
    if info_check(old_tyre) and info_check(new_tyre) == True: #Проверяем данные
        return int(height_calc(new_tyre) - height_calc(old_tyre)) #
    else:
        return "error"


def speed(old_tyre, new_tyre):
    """
    Поиск погрешности спидометра.
    Возвращаем погрешность с округлением до сотых.
    """
    if info_check(old_tyre) and info_check(new_tyre) == True: #Проверяем данные
        speed = float(height_calc(new_tyre) * 3.14 - height_calc(old_tyre) * 3.14) / float(height_calc(old_tyre) \
                                                                                           * 3.14) * 100
        return round(speed, 2)
    else:
        return "error"


def amer_calc(tyre):
    """
    Перевод дюймового размера в метрический.
    Возвращает размер шины уже в евро формате.
    """
    def euro_select(height):
        """Округляем размер до кратного 5 или 0"""
        return str(round(height / 5.0) * 5)

    if info_check_inch(tyre) == True: #Проверяем данные
        tyre = re.split("/|R|r| ", tyre) #Создаем список с размерами шины
        height = int(tyre[0])
        width = float(tyre[1])
        raduis = int(tyre[2])
        new_height = width * 25.4
        new_width = (height * 25.4 - raduis * 25.4) / 2 / (width * 25.4) * 100
        return "".join([euro_select(new_height),"/", str(round(new_width/5.0)*5), "R", str(raduis)])
    else:
        return "error"


def disk_size(tyre):
    """
    Подбор диска.
    Возвращает готовый размер диска.
    """
    if info_check(tyre) == True:
        tyre = re.split("/|R|r| ", tyre) #Создаем список с размерами шины
        rad = tyre[2] #Вытаскиваем радиус
        tyre = "/".join(tyre[0:3]) #Приводим запрос к формату данных в таблице размеров
        try: #На случай, если такого значения в таблице размеров нет
            idx = list(disks.loc[(disks[['Размер шины']] == [tyre]).all(axis=1)].index) #Ищем индекс строки
            return rad + "X" + disks.iloc[idx[0]]['Рекомендуемая']
        except IndexError:
            return "error"
    else:
        bot.reply_to(message, error_mes, reply_markup=markup)
        bot.register_next_step_handler(message, start2)


def tyre_search(tyre, i, seas):
    """
    Поиск шин.
    Создает карточку товара и возвращает ее.
    """
    if info_check(tyre) == True:
        tyre = re.split("/|R|r| ", tyre) #Проверяем данные
        #Парсим страницу Мосавтошины, создаем URL нужного раздела, подставляя нужный размер и индекс сезона
        URL_TEMPLATE = "https://mosautoshina.ru/catalog/tyre/search/by-size/-"+"-".join(tyre)+"-" + str(seas)+"---/"
        r = requests.get(URL_TEMPLATE)
        soup = bs(r.text, "html.parser")

        #Сырые списки товара из парсера
        tyres_names = soup.find_all("div", class_="product-name")
        tyres_prices = soup.find_all("div", class_="product-price")
        tyres_links = soup.find_all("a", class_="product-container")

        # Создаем списки с готовыми данными
        if len(tyres_names) > 0:
            tyre_name = [name.text for name in tyres_names]
            tyre_price = [("".join((price.text).split()).rstrip("₽")) for price in tyres_prices]
            tyre_link = [("https://mosautoshina.ru" + link.get('href')) for link in tyres_links]
            #Создаем готовую карточку товара
            item_card = "🛞" + tyre_name[i] + "\n" + "💰Цена за колесо: " + tyre_price[i] + "₽" + "\n"\
                        + "🛒" + tyre_link[i]
            return item_card
        else:
            return False
    else:
        return False


@bot.message_handler(commands=["start"])
def start(m, res=False):
    """Начало, создаем кнопки, делаем разметку клавиатуры"""
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    item1 = types.KeyboardButton("Внешний диаметр")
    item2 = types.KeyboardButton("Сравнение размеров шин")
    item3 = types.KeyboardButton("Перевод из дюймового размера")
    item4 = types.KeyboardButton("Подбор дисков")
    item5 = types.KeyboardButton("Поиск шин в магазине")
    markup.add(item1)
    markup.add(item2)
    markup.add(item3)
    markup.add(item4)
    markup.add(item5)
    bot.send_message(m.chat.id,
                     'Привет! Это шинный калькулятор! \nЧто вы хотите узнать?', reply_markup=markup)


@bot.message_handler(content_types='text')
def menu(message):
    """
    Основное меню.
    Читаем ответ с кнопок, просим ввести данные.
    """
    if message.text.strip() == 'Внешний диаметр':
        bot.reply_to(message, 'Напишите мне размер вашего колеса в формате XXX/XX/XX (например: 255/55/17)', reply_markup=types.ReplyKeyboardRemove())
        bot.register_next_step_handler(message, message_input_external_diameter)
    elif message.text.strip() == 'Сравнение размеров шин':
        bot.reply_to(message,'Напишите мне размер колес, которые у вас сейчас в формате XXX/XX/XX (например: 255/55/17)', reply_markup=types.ReplyKeyboardRemove())
        bot.register_next_step_handler(message, message_input_compare_step1)
    elif message.text.strip() == 'Перевод из дюймового размера':
        bot.reply_to(message,'Напишите мне размер дюймового колеса в формате XX/XX/XX (например: 33/12.5/15)', reply_markup=types.ReplyKeyboardRemove())
        bot.register_next_step_handler(message, message_input_inch)
    elif message.text.strip() == 'Поиск шин в магазине':
        #Создаем новую одноразовую клавиатуру для выбора сезона шин
        bot.register_next_step_handler(message, message_input_season)
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        summer = types.KeyboardButton("Лето")
        winter = types.KeyboardButton("Зима")
        ms = types.KeyboardButton("Всесезонка")
        back = types.KeyboardButton("<< Назад")
        markup.add(summer)
        markup.add(winter)
        markup.add(ms)
        markup.add(back)
        #Ответ
        bot.reply_to(message, 'Сейчас я попытаюсь найти необходимые шины в магазине Мосавтошина. \n\nВыберите сезон', reply_markup=markup)
    elif message.text.strip() == 'Подбор дисков':
        bot.register_next_step_handler(message, message_input_disk)
        bot.reply_to(message,
                     'Напишите мне размер шины в формате XXX/XX/XX (например: 255/55/17), и я подберу для вас размер диска',
                     reply_markup=types.ReplyKeyboardRemove())
    else:
        bot.reply_to(message,'Сначала выберите функцию c помощью кнопки ниже')


@bot.message_handler(content_types=['text'])
def message_input_external_diameter(message):
    """Поиск внешнего диаметра"""
    global text
    text = message.text
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    back = types.KeyboardButton("<< Назад")
    markup.add(back)
    if (height_calc(message.text)) != False:
        bot.reply_to(message, f"Внешний диаметр вашего колеса: " + str(height_calc(message.text)) + "мм" + "\nВ дюймах: " + str(height_calc_inch(message.text)) + '"', reply_markup = markup)
        bot.register_next_step_handler(message, start2)
    else:
        bot.reply_to(message, error_mes, reply_markup = markup)
        bot.register_next_step_handler(message, start2)


@bot.message_handler(content_types=['text'])
def message_input_inch(message):
    """Конвертация из дюймов"""
    global inch
    inch = message.text
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    back = types.KeyboardButton("<< Назад")
    markup.add(back)
    if (info_check_inch(inch)) != False:
        bot.reply_to(message, f"Ваше колесо примерно соответствует европейскому размеру " + str(amer_calc(inch)), reply_markup = markup)
        bot.register_next_step_handler(message, start2)
    else:
        bot.reply_to(message, error_inch, reply_markup = markup)
        bot.register_next_step_handler(message, start2)


@bot.message_handler(content_types=['text'])
def message_input_season(message):
    """Выбор сезона"""
    global season
    global seas
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    back = types.KeyboardButton("<< Назад")
    markup.add(back)
    season = message.text
    #Получаем ответ с названием сезона, создаем переменную seas, куда запишем индекс сезона для подстановки в URL
    if message.text.strip() == 'Лето':
        seas = 1
        bot.reply_to(message,
                     'Напишите мне нужный размер в формате XXX/XX/XX (например: 255/55/17)\n\nПока я могу выводить только 10 позиций.', reply_markup=types.ReplyKeyboardRemove())
        bot.register_next_step_handler(message, message_input_search)
    elif message.text.strip() == 'Зима':
        seas = 2
        bot.reply_to(message,'Напишите мне нужный размер в формате XXX/XX/XX (например: 255/55/17)\n\nПока я могу выводить только 10 позиций.', reply_markup=types.ReplyKeyboardRemove())
        bot.register_next_step_handler(message, message_input_search)
    elif message.text.strip() == 'Всесезонка':
        seas = 3
        bot.reply_to(message,
                     'Напишите мне нужный размер в формате XXX/XX/XX (например: 255/55/17)\n\nПока я могу выводить только 10 позиций.', reply_markup=types.ReplyKeyboardRemove())
        bot.register_next_step_handler(message, message_input_search)
    elif message.text.strip() == '<< Назад':
        start2(message)
    else:
        bot.reply_to(message, "Ошибка!", reply_markup = markup)
        bot.register_next_step_handler(message, start2)


@bot.message_handler(content_types=['text'])
def message_input_search(message):
    """Поиск по Мосавтошине"""
    global size
    size = message.text
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    back = types.KeyboardButton("<< Назад")
    markup.add(back)

    if (info_check(size)) != False:
        try:
            for i in range(10):
                if tyre_search(size, i, seas) != False:
                    bot.send_message(message.chat.id, tyre_search(size, i, seas))
                else:
                    bot.send_message(message.chat.id, "Такой размер не найден :(", reply_markup = markup)
                    break
            bot.send_message(message.chat.id, 'Нажмите на кнопку, чтобы вернуться в главное меню', reply_markup=markup)
            bot.register_next_step_handler(message, start2)
        except IndexError:
            bot.send_message(message.chat.id, 'Нажмите на кнопку, чтобы вернуться в главное меню', reply_markup=markup)
            bot.register_next_step_handler(message, start2)
    else:
        bot.reply_to(message, error_mes, reply_markup = markup)
        bot.register_next_step_handler(message, start2)


def start2(message):
    """Главное меню, чтобы снова не выводить приветствие"""
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    item1 = types.KeyboardButton("Внешний диаметр")
    item2 = types.KeyboardButton("Сравнение размеров шин")
    item3 = types.KeyboardButton("Перевод из дюймового размера")
    item4 = types.KeyboardButton("Подбор дисков")
    item5 = types.KeyboardButton("Поиск шин в магазине")
    markup.add(item1)
    markup.add(item2)
    markup.add(item3)
    markup.add(item4)
    markup.add(item5)
    #Ответ
    bot.send_message(message.chat.id,
                     'Что вы хотите узнать?', reply_markup=markup)


@bot.message_handler(content_types=['text'])
def message_input_disk(message):
    """Подбор диска"""
    global tyre
    tyre = message.text
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    back = types.KeyboardButton("<< Назад")
    markup.add(back)
    if info_check(tyre) == True:
        if disk_size(tyre) != "error":
            bot.reply_to(message, 'Рекомендуемый размер диска:' + ' ' + disk_size(tyre), reply_markup=markup)
            bot.register_next_step_handler(message, start2)
        else:
            bot.reply_to(message, error_mes, reply_markup=markup)
            bot.register_next_step_handler(message, start2)
    else:
        bot.reply_to(message, error_mes, reply_markup=markup)
        bot.register_next_step_handler(message, start2)


@bot.message_handler(content_types=['text'])
def message_input_compare_step1(message):
    """Первый шаг сравнения шин"""
    global old_item
    old_item = message.text
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    back = types.KeyboardButton("<< Назад")
    markup.add(back)
    if info_check(old_item) == True:
        bot.reply_to(message,'Напишите мне размер колес, с которыми вы хотите сравнить в формате XXX/XX/XX (например: 255/55/17)')  # Bot reply 'Введите текст'
        bot.register_next_step_handler(message, message_input_compare_step2)
    else:
        bot.reply_to(message, error_mes, reply_markup=markup)
        bot.register_next_step_handler(message, start2)


@bot.message_handler(content_types=['text'])
def message_input_compare_step2(message):
    """Второй шаг сравнения шин"""
    global new_item
    new_item = message.text
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    back = types.KeyboardButton("<< Назад")
    markup.add(back)
    if compare(old_item, new_item) != "error":
        if compare(old_item, new_item) > 0: #Если новый размер оказался больше старого
            answer = "Разница во внешнем диаметре составит " + str(compare(old_item, new_item)) + "мм \nКлиренс машины станет выше на "\
                     + str(compare(old_item, new_item)/2) + "мм" + "\nПоказания спидометра будут меньше реальных на " \
                     + str(speed(old_item, new_item)) + "%"
        elif compare(old_item, new_item) < 0: #Если старый размер оказался больше нового
            answer = "Разница во внешнем диаметре составит " + str(compare(old_item, new_item)) + "мм \nКлиренс машины станет ниже на " \
                     + str(abs(compare(old_item, new_item) / 2)) + "мм" + "\nПоказания спидометра будут больше реальных на " \
                     + str(abs(speed(old_item, new_item))) + "%"
        else: #Если пользователь ввел два одинаковых размера
            answer = "Размер не изменится"
        bot.reply_to(message, answer, reply_markup = markup)
        bot.register_next_step_handler(message, start2)
    else:
        bot.reply_to(message, error_mes, reply_markup = markup)
        bot.register_next_step_handler(message, start2)

bot.polling(none_stop=True) #Постоянно принимаем сообщения