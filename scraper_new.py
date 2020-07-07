import csv
import re
import config
from bs4 import BeautifulSoup, Tag
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
import pymongo

client = pymongo.MongoClient("localhost", 27017)
products_links = client['petco']['products_links']
products = client['petco']['products_new']

path_to_chromedriver = '/Users/dianaantoniuk/PycharmProjects/petco/chromedriver'
options = Options()
options.add_argument('--headless')

driver = webdriver.Remote(command_executor='http://127.0.0.1:49753', desired_capabilities={}, options=options)
driver.session_id = '00380579e35aea23f20afa3664b9fb5a'


def variable(url, bs, is_size, is_weight):
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
    description_dict['sold_individually'] = 1
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

    # fill attributes
    html = driver.page_source
    bs = BeautifulSoup(html, 'html.parser')
    attributes = {}

    # normal attributes
    attributes = {}

    for attribute_name in config.attributes_names:
        attribute_val = ''
        attribute_index = config.attributes_indexes.get(attribute_name)
        attribute_visible, attribute_global = 1, 1
        try:
            attribute_val = bs.find('td', text=attribute_name).findNext('td').text.strip()
        except:
            pass
        attributes[attribute_index] = [attribute_index,
                                       attribute_name if attribute_val else '',
                                       attribute_val,
                                       attribute_visible if attribute_val else '',
                                       attribute_global if attribute_val else '']

    # individual attributes
    for attribute_name in config.individual_attributes_names:
        attribute_val = ''
        attribute_index = config.attributes_indexes.get(attribute_name)
        attribute_visible, attribute_global = 1, 1
        attributes[attribute_index] = [attribute_index,
                                       attribute_name if attribute_val else '',
                                       attribute_val,
                                       attribute_visible if attribute_val else '',
                                       attribute_global if attribute_val else '']

    # weight
    attribute_weight_val = ''
    attribute_weight_name = 'Weight'
    attribute_weight_index = config.attributes_indexes.get(attribute_weight_name)
    attribute_weight_visible, attribute_weight_global = 1, 1

    try:
        for option in bs.find('select', {'aria-label': attribute_weight_name}).find_all('option'):
            weight_val = option['value']
            if weight_val:
                if attribute_weight_val:
                    attribute_weight_val += ', '
                attribute_weight_val += weight_val
    except:
        pass

    attributes[attribute_weight_index] = [attribute_weight_index,
                                          attribute_weight_name if attribute_weight_val else '',
                                          attribute_weight_val,
                                          attribute_weight_visible if attribute_weight_val else '',
                                          attribute_weight_global if attribute_weight_val else '']

    # size
    attribute_size_val = ''
    attribute_size_name = 'Size'
    attribute_size_index = config.attributes_indexes.get(attribute_size_name)
    attribute_size_visible, attribute_size_global = 1, 1

    try:
        for option in bs.find('select', {'aria-label': attribute_size_name}).find_all('option'):
            size_val = option['value']
            if size_val:
                if attribute_size_val:
                    attribute_size_val += ', '
                attribute_size_val += size_val
    except:
        pass

    attributes[attribute_size_index] = [attribute_size_index,
                                        attribute_size_name if attribute_size_val else '',
                                        attribute_size_val,
                                        attribute_size_visible if attribute_size_val else '',
                                        attribute_size_global if attribute_size_val else '']

    description_dict['attributes'] = attributes
    return description_dict


def variations(variable_dict, bs, is_size, is_weight):
    result = []
    variations_options = []
    if is_weight:
        variations_options = [option for option in
                              driver.find_element_by_id('Weight').find_elements_by_tag_name('option')]
    elif is_size:
        variations_options = [option for option in
                              driver.find_element_by_id('Size').find_elements_by_tag_name('option')]

    for option in variations_options:
        text = option.text.strip()
        if 'Select' not in text:
            option.click()
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

            _id = driver.find_element_by_class_name('product-price-normal'). \
                find_element_by_tag_name('span').get_attribute('id').split('_')[1]

            attributes = {}
            table = bs.find('div', {'id': 'attributes_' + _id})

            # change weight
            attribute_weight_val = text if is_weight else ''
            attribute_weight_name = 'Weight'
            if not is_weight:
                try:
                    attribute_weight_val = table.find('td', text=attribute_weight_name).findNext('td').text.strip()
                except:
                    pass
            attribute_weight_index = config.attributes_indexes.get(attribute_weight_name)
            attribute_weight_visible, attribute_weight_global = 1, 1
            attributes[attribute_weight_index] = [attribute_weight_index,
                                                  attribute_weight_name if attribute_weight_val else '',
                                                  attribute_weight_val,
                                                  attribute_weight_visible if attribute_weight_val else '',
                                                  attribute_weight_global if attribute_weight_val else '']

            # fill size
            attribute_size_val = text if is_size else ''
            attribute_size_name = 'Size'
            if not is_size:
                try:
                    attribute_size_val = table.find('td', text=attribute_size_name).findNext('td').text.strip()
                except:
                    pass
            attribute_size_index = config.attributes_indexes.get(attribute_size_name)
            attribute_size_visible, attribute_size_global = 1, 1
            attributes[attribute_size_index] = [attribute_size_index,
                                                attribute_size_name if attribute_size_val else '',
                                                attribute_size_val,
                                                attribute_size_visible if attribute_size_val else '',
                                                attribute_size_global if attribute_size_val else '']

            # fill other attributes
            for attribute_name in config.individual_attributes_names:
                attribute_val = ''
                attribute_index = config.attributes_indexes.get(attribute_name)
                attribute_visible, attribute_global = 1, 1

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
                attribute_visible, attribute_global = 1, 1
                attributes[attribute_index] = [attribute_index,
                                               attribute_name if attribute_val else '',
                                               attribute_val,
                                               attribute_visible if attribute_val else '',
                                               attribute_global if attribute_val else '']

            description_dict['attributes'] = attributes
            result.append(description_dict)

    return result


def simple(url, bs):
    description_dict = config.description_dict.copy()
    description_dict['explicit_url'] = url
    description_dict['type'] = 'simple'

    # in stock
    description_dict['in_stock'] = 1
    try:
        driver.find_element_by_class_name('out_of_stock')
        description_dict['in_stock'] = 0
    except:
        pass
    description_dict['backorders_allowed'] = 0
    description_dict['allow_customer_reviews'] = 1

    # sold individually
    description_dict['sold_individually'] = 1
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

    # fill attributes
    attributes = {}

    # weight
    attribute_weight_name = 'Weight'
    attribute_weight_val = ''
    try:
        attribute_weight_val = bs.find('span', text=attribute_weight_name).next_sibling.text.strip()
    except:
        pass

    if not attribute_weight_val:
        try:
            attribute_weight_val = bs.find('td', text=attribute_weight_name).findNext('td').text.strip()
        except:
            pass

    attribute_weight_index = config.attributes_indexes.get(attribute_weight_name)
    attribute_weight_visible, attribute_weight_global = 1, 1
    attributes[attribute_weight_index] = [attribute_weight_index,
                                          attribute_weight_name if attribute_weight_val else '',
                                          attribute_weight_val,
                                          attribute_weight_visible if attribute_weight_val else '',
                                          attribute_weight_global if attribute_weight_val else '']

    # size
    attribute_size_name = 'Size'
    attribute_size_val = ''
    try:
        attribute_size_val = bs.find('span', text=attribute_size_name).next_sibling.text.strip()
    except:
        pass

    if not attribute_size_val:
        try:
            attribute_size_val = bs.find('td', text=attribute_size_name).findNext('td').text.strip()
        except:
            pass

    attribute_size_index = config.attributes_indexes.get(attribute_size_name)
    attribute_size_visible, attribute_size_global = 1, 1
    attributes[attribute_size_index] = [attribute_size_index,
                                        attribute_size_name if attribute_size_val else '',
                                        attribute_size_val,
                                        attribute_size_visible if attribute_size_val else '',
                                        attribute_size_global if attribute_size_val else '']

    # general attributes
    html = driver.page_source
    bs = BeautifulSoup(html, 'html.parser')

    for attribute_name in config.attributes_names:
        attribute_val = ''
        attribute_index = config.attributes_indexes.get(attribute_name)
        attribute_visible, attribute_global = 1, 1

        try:
            attribute_val = bs.find('td', text=attribute_name).findNext('td').text.strip()
        except:
            pass
        attributes[attribute_index] = [attribute_index,
                                       attribute_name if attribute_val else '',
                                       attribute_val,
                                       attribute_visible if attribute_val else '',
                                       attribute_global if attribute_val else '']

    # individual attributes
    for attribute_name in config.individual_attributes_names:
        attribute_val = ''
        attribute_index = config.attributes_indexes.get(attribute_name)
        attribute_visible, attribute_global = 1, 1
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
    time.sleep(1)

    html = driver.page_source
    bs = BeautifulSoup(html, 'html.parser')

    result = []
    size_amount, weight_amount = 0, 0
    is_size, is_weight = False, False

    try:
        size_amount = len(bs.find('select', {'id': 'Size'}).find_all('option'))
        is_size = True
    except:
        pass

    try:
        weight_amount = len(bs.find('select', {'id': 'Weight'}).find_all('option'))
        is_weight = True
    except:
        pass

    if is_size or is_weight:
        if (is_size and size_amount >= 2) or (is_weight and weight_amount >= 2):
            # scrape variable
            variable_dict = variable(product_url, bs, is_size, is_weight)
            result.append(variable_dict)

            # scrape variations
            variations_dicts = variations(variable_dict, bs, is_size, is_weight)
            result.extend(variations_dicts)
            return result

    simple_dict = simple(product_url, bs)
    result.append(simple_dict)
    return result


def write_to_cvs(results):
    # create headers
    headers = []
    for naming in config.description_dict_namings:
        headers.append(naming[0])

    for attribute_naming in range(1, config.total_attributes_amount + 1):
        headers.append('Attribute ' + str(attribute_naming) + ' name')
        headers.append('Attribute ' + str(attribute_naming) + ' value(s)')
        headers.append('Attribute ' + str(attribute_naming) + ' visible')
        headers.append('Attribute ' + str(attribute_naming) + ' global')

    table = [headers]
    # add rows
    for result in results:
        current_row = []
        for naming in config.description_dict_namings:
            current_row.append(result.get(naming[1]))
        for i in range(1, config.total_attributes_amount + 1):
            attributes = result.get('attributes').get(i)
            name, val, visible, _global = attributes[1], attributes[2], attributes[3], attributes[4]
            current_row.extend([name, val, visible, _global])
        table.append(current_row)

    with open('petco_diana.csv', 'w', newline='') as file:
        writer = csv.writer(file)
        writer.writerows(table)


def dict_to_str_dict(_dict):
    for _d in _dict:
        for key, val in _d.items():
            if isinstance(_d.get(key), int):
                _d[key] = str(val)
    return _dict


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
import json


def main():
    # items = ['https://www.petco.com/shop/en/petcostore/product/blue-buffalo-wilderness-chicken-adult-dry-dog-food']
    counter = 0
    for item in products_links.find():
        item_link = item.get('link')
        counter += 1
        if products.count({'explicit_url': item_link}) > 0:
            continue

        print(counter, item_link)
        current_results = product(item_link)
        new_results = []
        for current_result in current_results:
            new_results.append({'explicit_url' : current_result.get('explicit_url'), 'data': json.dumps(current_result)})
        products.insert_many(new_results)


main()
