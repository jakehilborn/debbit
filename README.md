<a href="https://i.imgur.com/6TQjwsI.mp4"><img align="right" src="debbit_preview.png"></a>

# Debbit
**Click image for gif demo [👉](https://i.imgur.com/6TQjwsI.mp4)**

### Download

[macOS and Windows](https://github.com/jakehilborn/debbit/releases). Or, clone the source and run debbit.py.

### Description

Debbit is a set it and forget it solution to automate monthly transaction count requirements. Debbit does this by purchasing 50 cent Amazon gift cards and/or paying your cable bill in small increments multiple times throughout the month.

* [High interest checking accounts](https://www.doctorofcredit.com/high-interest-savings-to-get/#Mega_High-Interest_Nationwide) offer up to a 5% return on your account balance. To qualify for these high returns, you'll typically need to make 10 to 50 debit card transactions per month depending on each bank's requirements. Debbit can automate as many transactions per month as you need.

* [Prevent credit card closures from inactivity](https://www.doctorofcredit.com/which-banks-close-credit-cards-for-inactivity/) - Banks will close out credit cards due to inactivity. Use Debbit to automatically schedule 1 tiny transaction per month for all your sock drawer credit cards.

* [Get $.99 per card per month for free](https://www.doctorofcredit.com/small-balance-waiver-a-k-a-lots-of-free-99-cent-amazon-gcs/) - Many (most?) banks will waive your credit card bill if your balance is less than $1. Use Debbit to schedule one $0.99 Amazon gift card reload per month for all your sock drawer credit cards.

### Debbit currently supports
- Amazon gift card reloads (confirmed working as of Dec. 18th 2021)
- Xfinity bill pay (may not work, haven't used this in a while)
- AT&T bill pay (may not work, haven't used this in a while)
- Optimum bill bay (may not work, haven't used this in a while)
- Happy to accept pull requests for new merchant implementations. Refer to [example_merchant](https://github.com/jakehilborn/debbit/blob/master/src/program_files/merchants/example_merchant.py) for instructions.

### Features
- **Anti account lockout**: Debbit will spread purchases through the month with some randomness in timing and amount spent. These controls prevent Debbit from spamming your accounts with too many transactions too quickly or too similarly.
- **Fault tolerant**: Start up or shut down Debbit at any time. Debbit saves important state to your hard drive and will auto-adjust its spending to fit the time left in the month. It doesn't matter if you start Debbit on the 1st or the 15th of the month, it will adjust its scheduling accordingly.
- **Built in support**: If amazon/xfinity/etc changes their website and Debbit stops working, it will generate error logs to describe the issue. All passwords & cc details are automatically removed from the logs. There is no built-in error uploads so you'll have to email the files or create an Issue on GitHub to share.
- **Private**: There are no analytics or anything uploading data anywhere.

### FAQ
[https://jakehilborn.github.io/debbit/#faq](https://jakehilborn.github.io/debbit/#faq)

### Feedback
Please create a GitHub Issue for any feedback, feature requests, merchant requests bugs, etc. Happy to accept pull requests too!
