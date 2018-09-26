import re
from time import sleep
from bs4 import BeautifulSoup
from decouple import config
from praw import Reddit
from requests import get, codes
from selenium import webdriver
from telebot import TeleBot, util


def get_token(grant_type, client_id, client_secret):
    data = {
        'grant_type': grant_type,
        'client_id': client_id ,
        'client_secret': client_secret
        }
    url = 'https://api.coinmarketcal.com/oauth/v2/token'
    r = get(url, data)
    if r.status_code == codes.ok:
        return r.json().get('access_token')
    return None


def get_coinmarketcal_events(coin):
    token = get_token(config('GRANT_TYPE'), config('COINMARKETCAL_CLIENT_ID'),
                      config('COINMARKETCAL_CLIENT_SECRET'))
    if token:
        url = 'https://api.coinmarketcal.com/v1/events'
        data = {
            'access_token': token,
            'coins': coin
            }
        try:
            r = get(url, data)
            if r.status_code == codes.ok:
                content = r.json()
                if content:
                    coin_events = coin.title() + ' CoinMarketCal Events:\n\n'
                for event in content:
                    coin_events += f"{event.get('date_event')[:10]}\n{event.get('title')}\n"\
                                   f"{event.get('description')}\n{event.get('proof')}\n\n"
                return coin_events
        except Exception:
            return "Oops! Invalid coin name or event wasn't found."
    return None


def get_coincalendarinfo_events(event_type):
    types = {
        '': '3,1266,1267,564',
        'hot': '3',
        'conf': '1266',
        'meetup': '1267',
        'ann': '564'
        }
    try:
        type = types[event_type]
        url = f'http://www.coincalendar.info/wp-json/eventon/calendar?event_type={type}\
        &number_of_months=1&event_count=20'
    except Exception:
        return 'Opps! Invalid event type.'

    r = get(url)
    if codes.ok:
        content = r.json().get('html').strip()
        pattern = re.compile(r'(\'name\'>.*?</span>)')
        events = (pattern.findall(content))
        pattern = re.compile(r'(itemprop=\'image\' content=\'.*?jpg)')
        images = (pattern.findall(content))

        coin_events = 'CoinCalendarInfo Events:\n\n'
        for i in range(len(events)):
            coin_events += f'{events[i][7:events[i].index("<")]}\n{images[i][26:]}\n\n'
        return coin_events
    return None


def get_reddit_data(subreddit_name, limit):
    try:
        reddit = Reddit(
            client_id=config('REDDIT_ID'),
            client_secret=config('REDDIT_SECRET'),
            username=config('REDDIT_USERNAME'),
            password=config('REDDIT_PASSWORD'),
            user_agent=config('REDDIT_USER_AGENT')
            )
        subreddit = reddit.subreddit(subreddit_name).hot(limit=limit)
        subreddit_content = f'{subreddit_name.title()} Reddit posts: \n\n'
        for sub in subreddit:
            subreddit_content += f'{sub.title}\nhttps://reddit.com{sub.permalink}\n\n'
        return subreddit_content
    except Exception:
        return 'Oops! Invalid API credentials or subreddit name.'


def get_bitcointalk_data(coin):
    try:
        driver = webdriver.Chrome()
        driver.get('http://www.google.com/')
        driver.find_element_by_class_name('gsfi')\
              .send_keys(f'{coin} btctalk ann 2018')
        driver.find_element_by_name('btnK').click()
        result = driver.find_element_by_class_name('r')
        result.find_element_by_tag_name('a').click()
        driver.find_elements_by_class_name('navPages')[-2].click()
        posts = driver.find_elements_by_class_name('post')
        content = f'{coin.title()} Bitcointalk posts:\n\n'
        for post in posts:
            content += f'{post.text}\n\n'
    except Exception as e:
        return 'Oops! Invalid coin name.'
    finally:
        driver.quit()
    return content


def get_cointelegraph_news():
    r = get('https://cointelegraph.com/')
    bs = BeautifulSoup(r.content, 'html.parser')
    post_titles = [p.text for p in bs.select('span.postTitle')][:20]
    post_links = [p.attrs.get('href') for p in bs.select('div.image > a')][:20]
    content = 'Cointelegraph posts:\n\n'
    for title, link in zip(post_titles, post_links):
        content += f'{title}\n{link}\n\n'
    return content


def get_price_alert_notify(coin, alert_price, currency):
    while True:
        try:
            url = f'https://coinmarketcap.com/currencies/{coin}/'
            r = get(url)
            if r.status_code == codes.ok:
                bs = BeautifulSoup(r.content, 'html.parser')
                if currency == 'usd':
                    price_usd = bs.select('span#quote_price > span')[0].text
                    if float(price_usd) > float(alert_price):
                        return f'{coin.title()} hit your alert price ${alert_price} - ${price_usd}!'
                price_sats = bs.select('span.text-gray > span')[0].text
                if float(price_sats) > float(alert_price):
                    return f'{coin.title()} hit your alert price {alert_price} sats - {price_sats} sats!'
        except Exception as e:
            return 'Oops! Invalid coin name.'
        sleep(5)
    return None


def main():
    try:
        bot = TeleBot(token=config('TELEGRAM_BOT_TOKEN'))
        @bot.message_handler(commands=['start'])
        def welcome(msg):
            bot.reply_to(msg, 'Welcome to Crypto Bot!\nType /help to see available commands!')
        @bot.message_handler(commands=['help'])
        def help(msg):
            bot.reply_to(msg, 'Commands:\n/cmcal (coin name) - Get coin events from coinmarketcal.com\n' +
                         '/coincal (event_type) - Get coin events from coincalendar.info\n' +
                         '/reddit (subreddit name, limit) - Get subreddit posts\n' +
                         '/btctalk (coin name) - Get latest posts from bitcointalk.org\n' +
                         '/news - Get latest crypto news from cointelegraph.com\n' +
                         '/alert (coin name, price_alert, currency) - Get notify when coin hit specified price!')
        @bot.message_handler(func=lambda msg: True)
        def answer(msg):
            split_msg = msg.text.split()
            choice = split_msg[0]
            if choice == '/cmcal':
                try:
                    coin = split_msg[1]
                except IndexError:
                    bot.reply_to(msg, 'Opps! The parameter is missing.')
                finally:
                    bot.reply_to(msg, get_coinmarketcal_events(coin))
            elif choice == '/coincal':
                try:
                    event_type = split_msg[1]
                except IndexError:
                    event_type = ''
                finally:
                    bot.reply_to(msg, get_coincalendarinfo_events(event_type))
            elif choice == '/reddit':
                try:
                    subreddit = split_msg[1]
                    limit = int(split_msg[2])
                except IndexError:
                    limit = 5
                finally:
                    bot.reply_to(msg, get_reddit_data(subreddit, limit))
            elif choice == '/btctalk':
                coin = split_msg[1]
                content = get_bitcointalk_data(coin)
                splitted_text = util.split_string(content, 3000)
                for txt in splitted_text:
                    bot.reply_to(msg, txt)
            elif choice == '/cryptonews':
                bot.reply_to(msg, get_cointelegraph_news())
            elif choice == '/alert':
                try:
                    bot.reply_to(msg, get_price_alert_notify(split_msg[1],
                                                             split_msg[2],
                                                             split_msg[3]))
                except IndexError:
                    bot.reply_to(msg, 'Oops! The parameters are missing.')
            else:
                bot.reply_to(msg, 'Oops! Wrong choice.')
    except Exception as ex:
        print(str(ex))
        bot.reply_to(msg, 'Oops! An unexpected error has occurred.')
    finally:
        bot.polling()


if __name__ == '__main__':
    main()
