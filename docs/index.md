---
layout: default
---

## Getting Started

1. Install the latest version of Firefox.

1. Download [debbit](https://github.com/jakehilborn/debbit/releases) if you haven't done so yet, then unzip the download.

1. Run debbit to see a (fake) example purchase, refer to your operating system:  
    Mac: Double click on `debbit`. If using Catalina, to run for the first time right click on `debbit`, click Open, and then click the Open button.  
    Windows: Double click on `debbit_keep_window_open.bat`  
    Linux: [instructions here](https://github.com/jakehilborn/debbit/blob/master/src/HOW_TO_RUN_FROM_SOURCE.txt)

1. To make debbit work for real, edit the file config.txt. TODO instructions below?

1. Debbit was built to be a set it and forget solution. It will run month to month automatically scheduling and executing purchases to meet your spending requirements. After seeing how it works, you'll want to set 'hide_web_browser: yes' so Firefox stops popping up on your screen while you're using your computer.

## Config.txt Explanation

{% highlight yaml%}
card_1:
  amazon_gift_card_reload: reallylongline reallylongline reallylongline reallylongline reallylongline reallylongline reallylongline reallylongline reallylongline reallylongline reallylongline reallylongline reallylongline reallylongline 
    total_purchases: 40
    amount_min: 50
    amount_max: 59
    usr: you@domain.com
    psw: p@ssw0rd
    card: 1111222233334444
    burst_count: 2
  xfinity_bill_pay:
    total_purchases: 20
    amount_min: 10
    amount_max: 20
    usr: username
    psw: p@ssw0rd
    burst_count: 1
    card: 4444
{% endhighlight %}


# set to "burst" if running on a computer that is not always on (e.g. a laptop). Set to "spread" if running on a server or computer that never sleeps.
mode: burst

# set to "yes" to run web automation invisibly in the background, aka headless mode.
hide_web_browser: no

# Optional. If debbit is unable to complete a purchase after 5 tries you'll be notified via email.
notify_failure: your.email@website.com

# You can put any name for the card here.
card_1:

# The name of the merchant. This must match the file in
# the merchants folder, e.g. example_merchant.py
  example_merchant:

  # card_1 will make this many purchases from this merchant each month
  total_purchases: 10

  # Random price between amount_min and amount_max will be spent.
  # These numbers are in cents.
  amount_min: 10
  amount_max: 20

  # Your username and password to login to the merchant website.
  usr: you@domain.com
  psw: p@ssw0rd

  # Card description, please refer to the Merchant Info
  # section below for what to put here.
  card: 4444

  # Does not apply to "spread" mode, only applies to "burst" mode. The amount
  # of purchases to do back-to-back. For example, if doing 50 total_purchases a
  # month, you may want to set to 5 so debbit only needs to run 10 times a month.
  burst_count: 1

  # From here below are advanced settings. It's unlikely you'll want to change these.
  # Refer to sample below to include these settings in your config.txt.
  advanced:

    # Cookies tell websites that the web browser has been seen before and does not always need a new login.
    # "yes" will reduce likelihood of captcha challenges and repeating multi-factor auth.
    # "no" can help avoid unexpected web page changes.
    # Recommended to leave at "yes". Try setting to "no" if seeing purchase failures.
    use_cookies: yes

    # day of the month to start making purchases. Recommended to leave at 2 to avoid potential off by one errors in all systems.
    min_day: 2

    # day of the month to stop making purchases. Useful if your cable bill auto-pays on the 22nd of the month, for example. Leave blank to default to the end of the month minus one day.
    max_day: 22

    # Bursts a few purchases in a row. Use this mode when running on a laptop so debbit anticipates sleep/shutdown throughout the month.
    burst:

      # minimum gap in seconds between each burst. Each burst will be spaced out by at least this much.
      min_gap: 79200

      # random extra time up to this number added to burst min_gap between gaps to allow for some randomness in the timing
      time_variance: 14400

    # Spaces out purchases evenly with some randomness through the month. Use this mode if running on a server or computer that never sleeps.
    spread:

      # minimum gap in seconds between each purchase. This usually only applies if you start this program late in the month.
      min_gap: 43200

      # extra time before & after each scheduled purchase to allow for some randomness in the timing
      time_variance: 14400

##################
Config.txt Example
##################

mode: burst
hide_web_browser: yes
notify_failure: your.email@website.com

card_1:
  amazon_gift_card_reload:
    total_purchases: 40
    amount_min: 50
    amount_max: 59
    usr: you@domain.com
    psw: p@ssw0rd
    card: 1111222233334444
    burst_count: 2
  xfinity_bill_pay:
    total_purchases: 20
    amount_min: 10
    amount_max: 20
    usr: username
    psw: p@ssw0rd
    burst_count: 1
    card: 4444

card_2:
  amazon_gift_card_reload:
    total_purchases: 40
    amount_min: 50
    amount_max: 59
    usr: myotheraccount@domain.com
    psw: p@ssw0rd
    card: 5555666677778888
    burst_count: 2
  xfinity_bill_pay:
    total_purchases: 20
    amount_min: 10
    amount_max: 20
    usr: username
    psw: p@ssw0rd
    burst_count: 1
    card: 8888
    advanced:
      use_cookies: yes
      min_day: 2
      max_day:
      burst:
        min_gap: 79200
        time_variance: 14400
      spread:
        min_gap: 17280
        time_variance: 14400

########################
Config.txt Merchant Info
########################

amazon_gift_card_reload:
  amount_min: 50 # Amazon's gift card minimum is 50 cents
  card: 1111222233334444 # Amazon often requires the full 16 digit credit card number to verify you own the card before purchase.

xfinity_bill_pay:
  card: 4444 # Put last 4 digits of card

att_bill_pay:
  amount_min: 100 # AT&T minimum payment is $1
  card: Blue Debit Card # Card name as saved in AT&T account

optimum_bill_pay:
  amount_min: 100 # Optimum minimum payment is $1
  card: Blue Debit Card # Card name as saved in Optimum account

#################
OTHER INFORMATION
#################
Q. How do I see how many purchases debbit has made?
A. Open the folder 'state' and click the file for this month. It will show 'purchase_count' for each merchant.

Q. Debbit's web automation failed, how do I get it fixed?
A. In the failures folder there will be files with timestamps for names. Each timestamp will have 3 files ending in .txt, .png, and .html. Open the .png file and make sure it doesn't have your credit card number or password showing. Then, email these three files to jakehilborn@gmail.com or open an Issue on GitHub and attach them there.

Q. Can debbit automate purchases for other websites?
A. Yes, please open an issue on GitHub and I'll work with you to get it automated.

Q. What is debbit's homepage?
A. https://github.com/jakehilborn/debbit
