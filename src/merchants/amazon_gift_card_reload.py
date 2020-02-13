import logging
import time

from selenium import common
from selenium.common.exceptions import TimeoutException, ElementClickInterceptedException
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions
from selenium.webdriver.support.wait import WebDriverWait

from utils import cents_to_str
from result import Result

LOGGER = logging.getLogger('debbit')


def web_automation(driver, merchant, amount):

    driver.get('https://www.amazon.com/asv/reload/order')
    WebDriverWait(driver, 30).until(expected_conditions.element_to_be_clickable((By.XPATH, "//button[contains(text(),'Sign In to Continue')]")))

    try:
        driver.find_element_by_xpath("//button[contains(text(),'Sign In to Continue')]").click()
    except ElementClickInterceptedException:  # spinner blocking button
        time.sleep(3)
        driver.find_element_by_xpath("//button[contains(text(),'Sign In to Continue')]").click()

    driver.find_element_by_id('ap_email').send_keys(merchant.usr)

    try:  # a/b tested new UI flow
        driver.find_element_by_id('continue').click()  # if not exists, exception is raised
    except common.exceptions.NoSuchElementException:  # a/b tested old UI flow
        pass

    WebDriverWait(driver, 30).until(expected_conditions.element_to_be_clickable((By.ID, 'ap_password')))
    driver.find_element_by_id('ap_password').send_keys(merchant.psw)
    driver.find_element_by_id('signInSubmit').click()

    try:  # OTP email validation
        WebDriverWait(driver, 3).until(expected_conditions.element_to_be_clickable((By.XPATH, "//*[contains(text(),'One Time Password')]")))
        otp_flow = True
    except TimeoutException:
        otp_flow = False

    try:
        driver.find_element_by_xpath("//*[contains(text(),'one-time pass')]").click()
        otp_flow = True
    except common.exceptions.NoSuchElementException:
        pass

    if otp_flow:
        driver.find_element_by_id('continue').click()

        WebDriverWait(driver, 5).until(expected_conditions.element_to_be_clickable((By.XPATH, "//input")))
        sent_to_text = driver.find_element_by_xpath("//*[contains(text(),'@')]").text
        LOGGER.info(sent_to_text)
        LOGGER.info('Enter OTP here:')
        otp = input()

        elem = driver.find_element_by_xpath("//input")
        elem.send_keys(otp)
        elem.send_keys(Keys.TAB)
        elem.send_keys(Keys.ENTER)

    WebDriverWait(driver, 30).until(expected_conditions.element_to_be_clickable((By.ID, 'asv-manual-reload-amount')))
    driver.find_element_by_id('asv-manual-reload-amount').send_keys(cents_to_str(amount))
    driver.find_element_by_xpath("//span[contains(text(),'ending in " + merchant.card[-4:] + "')]").click()
    driver.find_element_by_xpath("//button[contains(text(),'Reload $" + cents_to_str(amount) + "')]").click()

    time.sleep(10)  # give page a chance to load
    if 'thank-you' not in driver.current_url:
        WebDriverWait(driver, 30).until(expected_conditions.element_to_be_clickable((By.XPATH, "//input[@placeholder='ending in " + merchant.card[-4:] + "']")))
        elem = driver.find_element_by_xpath("//input[@placeholder='ending in " + merchant.card[-4:] + "']")
        elem.send_keys(merchant.card)
        elem.send_keys(Keys.TAB)
        elem.send_keys(Keys.ENTER)
        WebDriverWait(driver, 30).until(expected_conditions.element_to_be_clickable((By.XPATH, "//button[contains(text(),'Reload $" + cents_to_str(amount) + "')]")))
        time.sleep(1)
        driver.find_element_by_xpath("//button[contains(text(),'Reload $" + cents_to_str(amount) + "')]").click()
        time.sleep(10)  # give page a chance to load

    if 'thank-you' not in driver.current_url:
        return Result.unverified

    return Result.success
