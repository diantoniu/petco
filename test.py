# from selenium import webdriver
# from selenium.webdriver.chrome.options import Options
#
#
# path_to_chromedriver = '/Users/dianaantoniuk/PycharmProjects/petco/chromedriver'
#
# user_agent_string = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) ' + \
#                     'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/67.0.3396.99 Safari/537.36'
# language = 'en-GB'
# options = Options()
#
# options.add_argument('--disable-gpu')  # used to be/is necessary on windows; working on linux
# options.add_argument('user-agent=' + user_agent_string)
# options.add_argument('--lang=' + language)
# options.add_argument("--window-size=1024,768")  # because driver.maximize_window() doesn't work in headless mode
# driver = webdriver.Chrome(path_to_chromedriver, options=options)
#
# print(driver.session_id)
# print(driver.command_executor._url)
#
import json

_dict = {1: {1: 2}, 2:[1, 2]}

_dict = json.dumps(_dict)
print(_dict)