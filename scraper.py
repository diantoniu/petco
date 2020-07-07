import requests
import re

import config
from bs4 import BeautifulSoup, Tag

# selenium
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options

import pymongo

client = pymongo.MongoClient("localhost", 27017)
products_links = client['petco']['products_links']
products = client['petco']['products']

import csv

path_to_chromedriver = '/Users/dianaantoniuk/PycharmProjects/petco/chromedriver'

# user_agent_string = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) ' + \
#                     'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/67.0.3396.99 Safari/537.36'
# language = 'en-GB'
options = Options()
options.add_argument('--headless')
# options.add_argument('--disable-gpu')  # used to be/is necessary on windows; working on linux
# options.add_argument('user-agent=' + user_agent_string)
# options.add_argument('--lang=' + language)
# options.add_argument("--window-size=1024,768")  # because driver.maximize_window() doesn't work in headless mode
# driver = webdriver.Chrome(path_to_chromedriver, options=options)


driver = webdriver.Remote(command_executor='http://127.0.0.1:49532', desired_capabilities={}, options=options)
driver.session_id = 'fab9333716b7e48e18f349a7ec8cc33b'


def variable(url, bs):
    description_dict = config.description_dict.copy()
    description_dict['explicit_url'] = url
    description_dict['type'] = 'variable'
    description_dict['in_stock'] = 1
    try:
        driver.find_element_by_class_name('out_of_stock')
        description_dict['in_stock'] = 0
    except:
        pass
    description_dict['backorders_allowed'] = 0
    description_dict['allow_customer_reviews'] = 1


    # sold individually
    min_qty = 1
    try:
        min_qty = int(bs.find('input', {'class': 'product_quantity_input'})['value'])
    except:
        _id = \
            driver.find_element_by_class_name('product-price-normal').get_attribute(
                'id').split('_')[1]
        min_qty = int(bs.find('input', {'id': 'quantity_' + _id})['value'])

    description_dict['sold_individually'] = (1 if min_qty == 1 else 0)

    try:
        driver.find_element_by_id('Count')
        description_dict['sold_individually'] = 0
    except:
        pass

    # parent
    description_dict['parent'] = ''

    # categories
    categories = ''
    for li in bs.find('div', {'data-pagetype': 'product-detail-page'}).find_all('li'):
        if categories:
            categories += ' > '
        categories += li.text.strip()
    description_dict['categories'] = categories

    # name
    name = bs.find('div', {'class': 'pdp-product-info'}).find('h1', {'itemprop': 'name'}).text.split(',', 1)[0].strip()
    description_dict['name'] = name

    # regular price
    description_dict['regular_price'] = ''

    # description
    description = ''
    description_tag = bs.find('div', {'class': 'product-description'})
    for description_element in description_tag.contents:
        if isinstance(description_element, Tag):
            if not description_element.get('class') or \
                    (description_element.get('class') and ('hide' not in description_element.get('class'))):
                description += ' ' + description_element.text
    description = re.sub('\\s+', ' ', description).strip()
    description_dict['description'] = description

    # images (bs is not working for some reason)
    images = ''
    images_set = set()
    for img_container in driver.find_element_by_id('thumbnail-slider').find_elements_by_class_name('imgContainer'):
        if 'display: none;' in img_container.find_element_by_tag_name('div').get_attribute('style'): continue
        for img in img_container.find_elements_by_tag_name('img'):
            href = str(img.get_attribute('src')).replace('t_Thumbnail', 't_ProductDetail-large').replace(
                'f_auto,q_auto,', '') + '.jpg'
            if href not in images_set:
                if images:
                    images += ','
                images += href
                images_set.add(href)
    description_dict['images'] = images

    # SKU
    SKU = bs.find('span', text='SKU').next_sibling.text
    description_dict['SKU'] = SKU

    # lifestage
    try:
        lifestage = bs.find('span', text='Lifestage').next_sibling.text
        description_dict['lifestage'] = lifestage
    except:
        pass

    for attribute_tag in driver.find_elements_by_xpath("//span[starts-with(@id, 'attributes_span')]"):
        parent = attribute_tag.find_element_by_xpath('..')
        if parent.text.strip():
            parent.click()

    driver.implicitly_wait(1)
    time.sleep(1)

    # normal attributes
    html = driver.page_source
    bs = BeautifulSoup(html, 'html.parser')

    attributes = {}

    for attribute_name in config.attributes_names:
        attribute_val = ''
        attribute_index = config.attributes_indexes.get(attribute_name)
        attribute_visible = 1
        attribute_global = 1

        try:
            attribute_val = bs.find('td', text=attribute_name).findNext('td').text.strip()
        except:
            pass

        attributes[attribute_index] = [attribute_index,
                                       attribute_name if attribute_val else '',
                                       attribute_val,
                                       attribute_visible if attribute_val else '',
                                       attribute_global if attribute_val else '']

    for attribute_name in config.individual_attributes_names:
        attribute_val = ''
        attribute_index = config.attributes_indexes.get(attribute_name)
        attribute_visible = 1
        attribute_global = 1

        attributes[attribute_index] = [attribute_index,
                                       attribute_name if attribute_val else '',
                                       attribute_val,
                                       attribute_visible if attribute_val else '',
                                       attribute_global if attribute_val else '']

    # weight
    attribute_weight_val = ''
    attribute_weight_name = 'Weight'
    attribute_weight_index = config.attributes_indexes.get('Weight')
    attribute_weight_visible = 1
    attribute_weight_global = 1
    for option in bs.find('select', {'aria-label': 'Weight'}).find_all('option'):
        weight_val = option['value']
        if weight_val:
            if attribute_weight_val:
                attribute_weight_val += ', '
            attribute_weight_val += weight_val

    attributes[attribute_weight_index] = [attribute_weight_index,
                                          attribute_weight_name if attribute_weight_val else '',
                                          attribute_weight_val,
                                          attribute_weight_visible if attribute_weight_val else '',
                                          attribute_weight_global if attribute_weight_val else '']

    description_dict['attributes'] = attributes

    return description_dict


def variations(variable_dict, bs):
    result = []
    current_table = -1

    for option in driver.find_element_by_id('Weight').find_elements_by_tag_name('option'):
        text = option.text.strip()
        if text != 'Select a weight':
            option.click()
            driver.implicitly_wait(2)
            time.sleep(1)

            description_dict = variable_dict.copy()
            description_dict['allow_customer_reviews'] = 0
            description_dict['parent'] = description_dict['SKU']
            description_dict['categories'] = ''
            description_dict['description'] = ''
            description_dict['images'] = ''
            description_dict['SKU'] = ''
            description_dict['lifestage'] = ''
            description_dict['attributes'] = []
            description_dict['type'] = 'variation'

            # change name
            description_dict['name'] = description_dict['name'] + ', ' + text

            # change price
            description_dict['regular_price'] = driver.find_element_by_class_name(
                'product-price-normal').find_element_by_tag_name('span').text

            _id = \
                driver.find_element_by_class_name('product-price-normal').find_element_by_tag_name(
                    'span').get_attribute(
                    'id').split('_')[1]

            attributes = {}
            # change weight

            attribute_weight_val = text
            attribute_weight_name = 'Weight'
            attribute_weight_index = config.attributes_indexes.get('Weight')
            attribute_weight_visible = 1
            attribute_weight_global = 1
            attributes[attribute_weight_index] = [attribute_weight_index,
                                                  attribute_weight_name if attribute_weight_val else '',
                                                  attribute_weight_val,
                                                  attribute_weight_visible if attribute_weight_val else '',
                                                  attribute_weight_global if attribute_weight_val else '']

            table = bs.find('div', {'id': 'attributes_' + _id})
            for attribute_name in config.individual_attributes_names:
                attribute_val = ''
                attribute_index = config.attributes_indexes.get(attribute_name)
                attribute_visible = 1
                attribute_global = 1

                try:
                    attribute_val = table.find('td', text=attribute_name).findNext('td').text.strip()
                except:
                    pass

                attributes[attribute_index] = [attribute_index,
                                               attribute_name if attribute_val else '',
                                               attribute_val,
                                               attribute_visible if attribute_val else '',
                                               attribute_global if attribute_val else '']

            for attribute_name in config.attributes_names:
                attribute_val = ''
                attribute_index = config.attributes_indexes.get(attribute_name)
                attribute_visible = 1
                attribute_global = 1

                attributes[attribute_index] = [attribute_index,
                                               attribute_name if attribute_val else '',
                                               attribute_val,
                                               attribute_visible if attribute_val else '',
                                               attribute_global if attribute_val else '']

            description_dict['attributes'] = attributes
            result.append(description_dict)
            current_table -= 1
    return result


def simple(url, bs):
    description_dict = config.description_dict.copy()
    description_dict['explicit_url'] = url
    description_dict['type'] = 'simple'
    description_dict['in_stock'] = 1
    try:
        driver.find_element_by_class_name('out_of_stock')
        description_dict['in_stock'] = 0
    except:
        pass
    description_dict['backorders_allowed'] = 0
    description_dict['allow_customer_reviews'] = 1

    # sold individually
    min_qty = 1

    try:
        min_qty = int(bs.find('input', {'class': 'product_quantity_input'})['value'])
    except:
        _id = \
            driver.find_element_by_class_name('product-price-normal').get_attribute(
                'id').split('_')[1]
        min_qty = int(bs.find('input', {'id': 'quantity_' + _id})['value'])

    description_dict['sold_individually'] = (1 if min_qty == 1 else 0)

    try:
        driver.find_element_by_id('Count')
        description_dict['sold_individually'] = 0
    except:
        pass

    # parent
    description_dict['parent'] = ''

    # categories
    categories = ''
    for li in bs.find('div', {'data-pagetype': 'product-detail-page'}).find_all('li'):
        if categories:
            categories += ' > '
        categories += li.text.strip()
    description_dict['categories'] = categories

    # name
    name = bs.find('div', {'class': 'pdp-product-info'}).find('h1', {'itemprop': 'name'}).text.split(',', 1)[0].strip()
    description_dict['name'] = name

    # regular price
    description_dict['regular_price'] = driver.find_element_by_class_name(
        'product-price-normal').find_element_by_tag_name('span').text

    # description
    description = ''
    description_tag = bs.find('div', {'class': 'product-description'})
    for description_element in description_tag.contents:
        if isinstance(description_element, Tag):
            if not description_element.get('class') or \
                    (description_element.get('class') and ('hide' not in description_element.get('class'))):
                description += ' ' + description_element.text
    description = re.sub('\\s+', ' ', description).strip()
    description_dict['description'] = description

    # images (bs is not working for some reason)
    images = ''
    images_set = set()
    for img_container in driver.find_element_by_id('thumbnail-slider').find_elements_by_class_name('imgContainer'):
        if 'display: none;' in img_container.find_element_by_tag_name('div').get_attribute('style'): continue
        for img in img_container.find_elements_by_tag_name('img'):
            href = str(img.get_attribute('src')).replace('t_Thumbnail', 't_ProductDetail-large').replace(
                'f_auto,q_auto,', '') + 'jpg'
            if href not in images_set:
                if images:
                    images += ','
                images += href
                images_set.add(href)
    description_dict['images'] = images

    # SKU
    SKU = bs.find('span', text='SKU').next_sibling.text
    description_dict['SKU'] = SKU

    # lifestage
    try:
        lifestage = bs.find('span', text='Lifestage').next_sibling.text
        description_dict['lifestage'] = lifestage
    except:
        pass

    # weight
    attribute_weight_name = 'Weight'
    attribute_weight_val = bs.find('span', text=attribute_weight_name).next_sibling.text.strip()
    attribute_weight_index = config.attributes_indexes.get('Weight')
    attribute_weight_visible = 1
    attribute_weight_global = 1

    attributes = {}
    attributes[attribute_weight_index] = [attribute_weight_index,
                                          attribute_weight_name if attribute_weight_val else '',
                                          attribute_weight_val,
                                          attribute_weight_visible if attribute_weight_val else '',
                                          attribute_weight_global if attribute_weight_val else '']

    for attribute_tag in driver.find_elements_by_xpath("//span[starts-with(@id, 'attributes_span')]"):
        parent = attribute_tag.find_element_by_xpath('..')
        if parent.text.strip():
            parent.click()

    driver.implicitly_wait(1)

    # normal attributes
    html = driver.page_source
    bs = BeautifulSoup(html, 'html.parser')

    for attribute_name in config.attributes_names:
        attribute_val = ''
        attribute_index = config.attributes_indexes.get(attribute_name)
        attribute_visible = 1
        attribute_global = 1

        try:
            attribute_val = bs.find('td', text=attribute_name).findNext('td').text.strip()
        except:
            pass

        attributes[attribute_index] = [attribute_index,
                                       attribute_name if attribute_val else '',
                                       attribute_val,
                                       attribute_visible if attribute_val else '',
                                       attribute_global if attribute_val else '']

    for attribute_name in config.individual_attributes_names:
        attribute_val = ''
        attribute_index = config.attributes_indexes.get(attribute_name)
        attribute_visible = 1
        attribute_global = 1

        try:
            attribute_val = bs.find('td', text=attribute_name).findNext('td').text.strip()
        except:
            pass

        attributes[attribute_index] = [attribute_index,
                                       attribute_name if attribute_val else '',
                                       attribute_val,
                                       attribute_visible if attribute_val else '',
                                       attribute_global if attribute_val else '']

    description_dict['attributes'] = attributes

    return description_dict


def product(product_url):
    driver.get(product_url)
    driver.implicitly_wait(2)
    time.sleep(1)

    try:
        driver.find_element_by_id('Size')
        return []
    except:
        pass

    html = driver.page_source
    bs = BeautifulSoup(html, 'html.parser')

    result = []
    # check if simple or variable with variation
    try:
        amount = len(bs.find('select', {'id': 'Weight'}).find_all('option'))
        if amount > 2:
            # scrape variable
            variable_dict = variable(product_url, bs)
            result.append(variable_dict)

            # scrape variations
            variations_dicts = variations(variable_dict, bs)
            result.extend(variations_dicts)
        else:
            # simple
            simple_dicts = simple(product_url, bs)
            result.extend(simple_dicts)
    except:
        # simple
        simple_dict = simple(product_url, bs)
        result.append(simple_dict)
    return result


def write_to_cvs():
    pass


def scrape_page():
    # iterate through items
    for item in driver.find_element_by_class_name('product_listing_container').find_elements_by_class_name('prod-tile'):
        try:
            item_link = str(item.find_element_by_tag_name('a').get_attribute('href'))
            if item_link and (products_links.count({'link': item_link}) == 0):
                products_links.insert_one({'link': item_link})
        except:
            pass


import time


def main():
    # index = 0
    # while index <= 348:
    #     product_url = f'https://www.petco.com/shop/en/petcostore/category/bird/bird-health-and-wellness#facet:&productBeginIndex:{index}&orderBy:&pageView:grid&minPrice:&maxPrice:&pageSize:48&'
    #     driver.get(product_url)
    #     time.sleep(15)
    #     counter_prev = 0
    #     for i in products_links.find():
    #         counter_prev += 1
    #     scrape_page()
    #
    #     counter = 0
    #     for i in products_links.find():
    #         counter += 1
    #     index += 48
    #     print(counter)

    counter = 0
    for item in products_links.find():
        counter += 1
        item_link = item.get('link')

        if products.count({'explicit_url': item_link}) > 0 or counter == 161:
            continue
        print(counter)
        print(item_link)

        current_result = product(item_link)
        for r in current_result:
            for key, val in r.items():
                r[key] = str(val)

        products.insert_many(current_result)

    # # create headers
    # headers = []
    # for naming in config.description_dict_namings:
    #     headers.append(naming[0])
    #
    # for attribute_naming in range(1, config.total_attributes_amount + 1):
    #     headers.append('Attribute ' + str(attribute_naming) + ' name')
    #     headers.append('Attribute ' + str(attribute_naming) + ' value(s)')
    #     headers.append('Attribute ' + str(attribute_naming) + ' visible')
    #     headers.append('Attribute ' + str(attribute_naming) + ' global')
    #
    # table = [headers]
    # # add rows
    # for result in results:
    #     current_row = []
    #     for naming in config.description_dict_namings:
    #         current_row.append(result.get(naming[1]))
    #     for i in range(1, config.total_attributes_amount + 1):
    #         attributes = result.get('attributes').get(i)
    #         name, val, visible, _global = attributes[1], attributes[2], attributes[3], attributes[4]
    #         current_row.extend([name, val, visible, _global])
    #     table.append(current_row)
    #
    # with open('petco_diana.csv', 'w', newline='') as file:
    #     writer = csv.writer(file)
    #     writer.writerows(table)


main()

# https://www.petco.com/shop/en/petcostore/product/gamma-frozen-food-mysis-shrimp-blister-pack-fish-food
