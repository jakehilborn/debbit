---
layout: default
title: Instructions
---

## Getting Started

1. Install the latest version of Firefox.

1. Download [debbit](https://github.com/jakehilborn/debbit/releases) if you haven't done so yet, then unzip the download.

1. Run debbit to see a (fake) example purchase, refer to your operating system:  
- Mac: Double click on `debbit`. If using Catalina, to run for the first time right click on `debbit`, click Open, and then click the Open button.  
- Windows: Double click on `debbit_keep_window_open.bat`  
- Linux: [Instructions here](https://github.com/jakehilborn/debbit/blob/master/src/HOW_TO_RUN_FROM_SOURCE.txt)

1. To make debbit work for real, edit the file config.txt. Refer to [config.txt Explanation](#configtxt-explanation) for info. **Important**: config.txt must have the correct structure (spaces, `:`'s, etc.), [config.txt Example](#configtxt-example) is a good resource to copy/paste and then edit the bits you need.

1. Debbit was built to be a set it and forget solution. It will run month to month automatically scheduling and executing purchases to meet your spending requirements. After seeing how it works, you'll want to set `hide_web_browser: yes` so Firefox stops popping up on your screen while you're using your computer. You may also want to make debbit automatically run when your computer starts up:
- [Mac instructions](https://jakehilborn.github.io/debbit/macOS-auto-run)
- [Windows instructions](https://jakehilborn.github.io/debbit/windows-auto-run)

## F.A.Q.

#### Where do I sign up for a high interest checking account?
Visit this [Doctor of Credit](https://www.doctorofcredit.com/high-interest-savings-to-get/#Mega_High-Interest_Nationwide) page. Regional banks will typically offer the best returns. If you can't find a regional bank you qualify for, select a nationwide bank.

#### How do I upgrade from debbit 1.0 / 1.0.1 to debbit 2.0?
If you have not made any purchases with debbit 2.0 yet (example_merchant purchases are okay), follow [this guide](https://jakehilborn.github.io/debbit/v1-to-v2).

#### How do I see how many purchases debbit has made?
Open the folder `state` and click the file for this month. It will show `purchase_count` for each merchant.

#### Can debbit run in headless mode?
Yes. Edit `config.txt` and set `hide_web_browser: yes`

#### Does my computer have to stay on?
No, you do not need to leave your computer on all the time. Debbit works in two different ways based on what's in config.txt.

`mode: burst`
Best if using a laptop or a computer that is not always on. Debbit will check every 5 minutes if enough time has elapsed such that it should execute purchases. This allows you to sleep your computer without concern for debbit. Whenever your computer is back on, debbit will check if it is time to execute purchases and do so accordingly.

`mode: spread`
Best if running on a server/computer that never sleeps. Debbit will spread out purchases through the month as evenly as possible (with some randomness).

#### What if I reboot my computer?
Rebooting will cause no issues, other than you'll need to run debbit again after starting up. Follow these instructions for [macOS](https://jakehilborn.github.io/debbit/macOS-auto-run) or [Windows](https://jakehilborn.github.io/debbit/windows-auto-run) to automatically run on start up.

#### Will rebooting lose monthly progress?
No. Debbit stores its progress through the month in files inside the `state` folder. You can stop/start debbit whenever and reboot whenever without concern for debbit. It is built to handle all these scenarios.

#### How do I check if debbit is running?
Debbit runs as a foreground application. On Windows it will show as a Command Prompt window in the taskbar. On macOS it will show as a Terminal window in the dock. If debbit fails to execute a purchase after 5 retries, an email will be sent to the email address in `config.txt` as a notification. 

#### Can debbit use multiple cards?
Yes, refer to the section [config.txt Example](#configtxt-example) for an example of two debit cards being used. One named blue_debbit_card, the other named red_debbit_card.

#### Will debbit accidentally spend money?
No. Debbit ensures that the correct amount is input and the correct payment method is selected before clicking purchase. If the webpage is not exactly as debbit expects, debbit will error-out preemptively and notify you so that debbit avoids spending money. If debbit clicks "purchase" but cannot verify the purchase was successful, it will error out and notify you and not schedule any future purchases until you re-run debbit. 

#### Does my debit card need to be the default card on my account?
No. Debbit automation will always click the payment method specified in config.txt before making a purchase. Whatever payment method is default in your account is irrelevant.

#### Merchant automation failed, how do I get it fixed?
In the `failures` folder there will be files with timestamps for names. Each timestamp will have 4 pieces ending in `.txt`, `.png`, `.html`, and a folder ending in `coverage`. Open the .png file and make sure it doesn't have your credit card number or password showing. Then, email these three files to jakehilborn@gmail.com or open an Issue on GitHub and attach them there. You can attach one error or all of them, the more errors to inspect the more helpful.

#### Can debbit automate purchases for other websites?
Yes, please open an issue on GitHub and I'll work with you to get it automated. Alternatively, download the source code and refer to [example_merchant.py](https://github.com/jakehilborn/debbit/blob/master/src/program_files/merchants/example_merchant.py) as a reference to code your own.

#### What is debbit's homepage?
[https://github.com/jakehilborn/debbit](https://github.com/jakehilborn/debbit)

## config.txt Explanation

{% highlight yaml%}
# Set to "burst" if running on a computer that is not always on (e.g. a laptop).
# Set to "spread" if running on a server or computer that never sleeps.
mode: burst

# Set to "yes" to run web automation invisibly in the background, aka headless mode.
hide_web_browser: no

# Optional. If debbit is unable to complete a purchase after 5 tries
# you'll be notified via an email from debbit.failure@debbit.com
notify_failure: your.email@website.com

# You can put any name for the debit card here.
example_card_description:

# The name of the merchant. This must match the file in the
# program_files/merchants folder, e.g. example_merchant.py
  example_merchant:

    # example_card_description will make this many
    # purchases from this merchant each month
    total_purchases: 10

    # Random price between amount_min and amount_max will be spent.
    # These numbers are in cents.
    amount_min: 10
    amount_max: 20

    # Your username and password to login to the merchant website.
    usr: you@domain.com
    psw: p@ssw0rd

    # Card description, refer to the "config.txt Merchant Info"
    # section below for what to put here.
    card: 4444

    # Does not apply to "spread" mode, only applies to "burst" mode. The amount
    # of purchases to do back-to-back. For example, if doing 50 total_purchases a
    # month, you may want to set to 5 so debbit only needs to run 10 times a month.
    burst_count: 1

    # From here below are advanced settings. It's unlikely you'll
    # want to change these. Refer to the "config.txt Example" section
    # below to include these settings in your config.txt.
    advanced:

      # Cookies tell websites that the web browser has been seen before
      # and does not always need a new login. "yes" will reduce likelihood
      # of captcha challenges and repeating multi-factor auth. "no" can help
      # avoid unexpected web page changes. Recommended to leave at "yes".
      # Try setting to "no" if seeing purchase failures.
      use_cookies: yes

      # Day of the month to start making purchases. Recommended to
      # leave at 2 to avoid potential off by one errors in all systems.
      min_day: 2

      # Day of the month to stop making purchases. Useful if your cable
      # bill auto-pays on the 22nd of the month, for example. Leave blank
      # to default to the end of the month minus one day.
      max_day: 22

      # Bursts a few purchases in a row. Use this mode when running on a
      # laptop so debbit anticipates sleep/shutdown throughout the month.
      burst:

        # Minimum gap in seconds between each burst.
        # Each burst will be spaced out by at least this much.
        min_gap: 79200

        # Random extra time up to this number added to burst min_gap
        # between gaps to allow for some randomness in the timing
        time_variance: 14400

      # Spaces out purchases evenly with some randomness through the month.
      # Use this mode if running on a server or computer that never sleeps.
      spread:

        # Minimum gap in seconds between each purchase.
        # This usually only applies if you start this program late in the month.
        min_gap: 43200

        # Extra time before & after each scheduled purchase
        # to allow for some randomness in the timing
        time_variance: 14400

{% endhighlight %}

## config.txt Example

{% highlight yaml%}
mode: burst
hide_web_browser: yes
notify_failure: your.email@website.com

blue_debbit_card:
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

red_debbit_card:
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

{% endhighlight %}

## config.txt Merchant Info

{% highlight yaml%}
amazon_gift_card_reload:
  amount_min: 50 # Amazon's gift card minimum is 50 cents
  card: 1111222233334444 # Amazon often requires the full 16 digit credit card number to verify you own the card before purchase.

att_bill_pay:
  amount_min: 100 # AT&T minimum payment is $1
  card: Blue Debit Card # Card name as saved in AT&T account

optimum_bill_pay:
  amount_min: 100 # Optimum minimum payment is $1
  card: Blue Debit Card # Card name as saved in Optimum account

xfinity_bill_pay:
  card: 4444 # Put last 4 digits of card
{% endhighlight %}
