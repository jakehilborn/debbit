import logging
import random
import time

from selenium import common
from selenium.common.exceptions import TimeoutException, ElementClickInterceptedException, WebDriverException
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions
from selenium.webdriver.support.wait import WebDriverWait

import utils
from result import Result

LOGGER = logging.getLogger('debbit')


def web_automation(driver, merchant, amount):
    driver.get('https://www.amazon.com/asv/reload/order')

    logged_in = utils.is_logged_in(driver, timeout=30,
        logged_out_element=(By.XPATH, "//button[contains(text(),'Sign In to Continue')]"),
        logged_in_element=(By.XPATH, "//button[starts-with(text(),'Reload')]")
    )

    time.sleep(1 + random.random() * 2)  # slow down automation randomly to help avoid bot detection
    if not logged_in:
        try:
            driver.find_element_by_xpath("//button[contains(text(),'Sign In to Continue')]").click()
            time.sleep(1 + random.random() * 2)
        except ElementClickInterceptedException:  # spinner blocking button
            time.sleep(3)
            driver.find_element_by_xpath("//button[contains(text(),'Sign In to Continue')]").click()
            time.sleep(1 + random.random() * 2)

        WebDriverWait(driver, 30).until(utils.AnyExpectedCondition(
            expected_conditions.element_to_be_clickable((By.ID, 'ap_email')),  # first time login
            expected_conditions.element_to_be_clickable((By.XPATH, "//*[contains(text(),'" + merchant.usr + "')]"))  # username found on page
        ))

        if driver.find_elements_by_xpath("//*[contains(text(),'" + merchant.usr + "')]"):
            driver.find_element_by_xpath("//*[contains(text(),'" + merchant.usr + "')]").click()  # click username in case we're on the Switch Accounts page
            WebDriverWait(driver, 30).until(expected_conditions.element_to_be_clickable((By.ID, 'signInSubmit')))
            time.sleep(1 + random.random() * 2)

        if driver.find_elements_by_id('ap_email'):  # if first run, fill in email. If subsequent run, nothing to fill in
            driver.find_element_by_id('ap_email').send_keys(merchant.usr)
            time.sleep(1 + random.random() * 2)

        if driver.find_elements_by_id('continue'):  # a/b tested new UI flow
            driver.find_element_by_id('continue').click()
            WebDriverWait(driver, 5).until(expected_conditions.element_to_be_clickable((By.ID, 'ap_password')))
            time.sleep(1 + random.random() * 2)

        driver.find_element_by_id('ap_password').send_keys(merchant.psw)
        time.sleep(1 + random.random() * 2)
        driver.find_element_by_id('signInSubmit').click()
        time.sleep(1 + random.random() * 2)

        handle_anti_automation_challenge(driver, merchant)

        try:  # OTP text message
            WebDriverWait(driver, 5).until(expected_conditions.element_to_be_clickable((By.XPATH, "//*[contains(text(),'phone number ending in')]")))
            if driver.find_elements_by_id('auth-mfa-remember-device'):
                driver.find_element_by_id('auth-mfa-remember-device').click()

            sent_to_text = driver.find_element_by_xpath("//*[contains(text(),'phone number ending in')]").text
            LOGGER.info(sent_to_text)
            LOGGER.info('Enter OTP here:')
            otp = input()

            driver.find_element_by_id('auth-mfa-otpcode').send_keys(otp)
            time.sleep(1 + random.random() * 2)
            driver.find_element_by_id('auth-signin-button').click()
            time.sleep(1 + random.random() * 2)
        except TimeoutException:
            pass

        try:  # OTP email validation
            WebDriverWait(driver, 5).until(expected_conditions.element_to_be_clickable((By.XPATH, "//*[contains(text(),'One Time Pass')]")))
            otp_email = True
        except TimeoutException:
            otp_email = False

        try:
            driver.find_element_by_xpath("//*[contains(text(),'one-time pass')]").click()
            time.sleep(1 + random.random() * 2)
            otp_email = True
        except common.exceptions.NoSuchElementException:
            pass

        if otp_email:
            if driver.find_elements_by_id('continue'):
                driver.find_element_by_id('continue').click()
                time.sleep(1 + random.random() * 2)

            handle_anti_automation_challenge(driver, merchant)

            try:  # User may have manually advanced to gift card screen or stopped at OTP input. Handle OTP input if on OTP screen.
                WebDriverWait(driver, 5).until(expected_conditions.element_to_be_clickable((By.XPATH, "//*[contains(text(),'Enter OTP')]")))
                sent_to_text = driver.find_element_by_xpath("//*[contains(text(),'@')]").text
                LOGGER.info(sent_to_text)
                LOGGER.info('Enter OTP here:')
                otp = input()

                elem = driver.find_element_by_xpath("//input")
                elem.send_keys(otp)
                time.sleep(1 + random.random() * 2)
                elem.send_keys(Keys.TAB)
                time.sleep(1 + random.random() * 2)
                elem.send_keys(Keys.ENTER)
                time.sleep(1 + random.random() * 2)
            except TimeoutException:
                pass

        try:
            WebDriverWait(driver, 5).until(expected_conditions.element_to_be_clickable((By.XPATH, "//*[contains(text(),'Not now')]")))
            driver.find_element_by_xpath("//*[contains(text(),'Not now')]").click()
            time.sleep(1 + random.random() * 2)
        except TimeoutException:  # add mobile number page
            pass

    WebDriverWait(driver, 30).until(expected_conditions.element_to_be_clickable((By.ID, 'asv-manual-reload-amount')))
    driver.find_element_by_id('asv-manual-reload-amount').send_keys(utils.cents_to_str(amount))
    time.sleep(1 + random.random() * 2)

    for element in driver.find_elements_by_xpath("//span[contains(text(),'ending in " + merchant.card[-4:] + "')]"):
        try:  # Amazon has redundant non-clickable elements. This will try each one until one works.
            element.click()
            time.sleep(1 + random.random() * 2)
            break
        except WebDriverException:
            pass

    driver.find_element_by_xpath("//button[starts-with(text(),'Reload') and contains(text(),'" + utils.cents_to_str(amount) + "')]").click()
    time.sleep(1 + random.random() * 2)

    time.sleep(10)  # give page a chance to load
    if 'thank-you' not in driver.current_url:
        WebDriverWait(driver, 30).until(expected_conditions.element_to_be_clickable((By.XPATH, "//input[@placeholder='ending in " + merchant.card[-4:] + "']")))
        elem = driver.find_element_by_xpath("//input[@placeholder='ending in " + merchant.card[-4:] + "']")
        time.sleep(1 + random.random() * 2)
        elem.send_keys(merchant.card)
        time.sleep(1 + random.random() * 2)
        elem.send_keys(Keys.TAB)
        time.sleep(1 + random.random() * 2)
        elem.send_keys(Keys.ENTER)
        WebDriverWait(driver, 30).until(expected_conditions.element_to_be_clickable((By.XPATH, "//button[contains(text(),'Reload $" + utils.cents_to_str(amount) + "')]")))
        time.sleep(1 + random.random() * 2)
        driver.find_element_by_xpath("//button[starts-with(text(),'Reload') and contains(text(),'" + utils.cents_to_str(amount) + "')]").click()
        time.sleep(10)  # give page a chance to load

    if 'thank-you' not in driver.current_url:
        return Result.unverified

    return Result.success


def handle_anti_automation_challenge(driver, merchant):
    try:
        WebDriverWait(driver, 5).until(expected_conditions.element_to_be_clickable((By.XPATH, "//*[contains(text(),'nter the characters')]")))

        time.sleep(1 + random.random() * 2)
        if driver.find_elements_by_id('ap_password'):
            driver.find_element_by_id('ap_password').send_keys(merchant.psw)

        LOGGER.info('amazon captcha detected')
        input('''
Anti-automation captcha detected. Please follow these steps, future runs shouldn't need captcha input unless you set "use_cookies: no" in config.txt.

1. Open the Firefox window that debbit created.
2. Input the captcha / other anti-automation challenges.
3. You should now be on the gift card reload page
4. Click on this terminal window and hit "Enter" to continue running debbit.
''')
    except TimeoutException:
        pass
