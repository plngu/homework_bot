import os
import logging
import requests
import telegram
import time

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO)

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

HOMEWORK_STATUSES = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def send_message(bot, message):
    """Отправка сообщения"""
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
        logging.info(message)
    except Exception as error:
        logging.error(error, 'Сообщение не отправлено')


def get_api_answer(current_timestamp):
    """Получаем ответ от API"""
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    try:
        homework_statuses = requests.get(ENDPOINT,
                                         headers=HEADERS,
                                         params=params)
    except Exception as error:
        logging.error(error, 'Ошибка при обращении к эндпоинту')
        return None
    status_code = homework_statuses.status_code
    if status_code != 200:
        msg = f'Ошибка при обращении к эндпоинту: HTTP status - {status_code}'
        logging.error(msg)
        raise Exception(msg)
    return homework_statuses.json()


def check_response(response):
    """Проверка корректности API-ответа"""
    try:
        data = response['homeworks']
    except KeyError as error:
        logging.error(error, 'Ключа `homeworks` не существует в ответе')
        return None
    if type(data) is list:
        return data


def parse_status(homework):
    """Данные из конкретной домашней работы"""
    try:
        homework_name = homework['homework_name']
        homework_status = homework['status']
    except TypeError as error:
        logging.error(error,
                      f'Отсутствие ожидаемых ключей в ответе API')
        return None
    try:
        verdict = HOMEWORK_STATUSES[homework_status]
    except TypeError as error:
        logging.error(error,
                      f'Недокументированный статус домашней работы, '
                      f'обнаруженный в ответе API: {homework_status}')
        return None
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Проверка наличия токеноу"""
    tokens = {'TELEGRAM_CHAT_ID': TELEGRAM_CHAT_ID,
              'TELEGRAM_TOKEN': TELEGRAM_TOKEN,
              'PRACTICUM_TOKEN': PRACTICUM_TOKEN}
    for name, value in tokens.items():
        if not value:
            msg = f'Отсутствует обязательная переменная окружения: {name}'
            logging.critical(msg)
            return False
    return True


def main():
    """Основная логика работы бота."""
    check = check_tokens()
    if not check:
        exit('Программа принудительно остановлена.')

    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())

    get_api = get_api_answer(current_timestamp)
    response = check_response(get_api)
    init_verdict = parse_status(response[0])
    init_error = 'No errors'

    while True:
        try:
            get_api = get_api_answer(current_timestamp)
            response = check_response(get_api)
            verdict = parse_status(response[0])
            if verdict != init_verdict:
                send_message(bot, verdict)
                logging.info(verdict)
                init_verdict = verdict
            else:
                logging.debug('Обновления статуса нет')
            current_timestamp = int(time.time())
            time.sleep(RETRY_TIME)
        except Exception as error:
            if error != init_error:
                logging.error(f'Сбой в работе программы: {error}')
                send_message(bot, error)
                init_error = error
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
