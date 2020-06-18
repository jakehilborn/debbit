---
layout: default
title: v1 to v2
---

## How to upgrade to debbit 2.0

If you're upgrading from debbit v1.0 or v1.0.1 and would like to keep this current month's progress, follow the instructions below. If you are using debbit 2.0 for the first time or do not have any transactions yet this month, skip this.

1. Open `config.txt` in the debbit 2.0 folder and input your merchant details. Here is an example showcasing amazon and xfinity. If you're using both, copy both. If you're just using one, copy just that one. Set all of the values that you were previously using in debbit 1.0. You can change `example_card_description` to any description of the debbit card you were using with debbit 1.0.

{% highlight yaml%}
# Confused? Read instructions at https://jakehilborn.github.io/debbit/

mode: burst
hide_web_browser: no
notify_failure: your.email@website.com

example_card_description:
  amazon_gift_card_reload:
    total_purchases: 20
    amount_min: 10
    amount_max: 25
    usr: user
    psw: pass
    card: 2222
    burst_count: 2
  xfinity_bill_pay:
    total_purchases: 20
    amount_min: 10
    amount_max: 25
    usr: user
    psw: pass
    card: 2222
    burst_count: 2
{% endhighlight %}

{:start="2"}
1. Open the debbit 2.0 folder. If it does not have a `state` directory, then create one. If `state` already exists, please delete the `debbit_2020_**.txt` file inside.

1. If debbit 1.0 or 2.0 are currently running, close them.

1. Open the `state` folder in debbit 1.0 and find the `debbit_2020_**.txt` file representing the current month.

1. Copy this file from debbit 1.0 `state` to debbit 2.0 `state`.

1. Double click the `debbit_2020_**.txt` file in debbit 2.0 `state` so we can edit it. The only change you need to make is to rename `amazon_gift_card_reload` to `your_card_description_amazon_gift_card_reload` and/or rename `xfinity_bill_pay` to `your_card_description_xfinity_bill_pay`. The `your_card_description` part must match what is inside your `config.txt`. Here is an example of the difference:

Before:
{% highlight yaml%}
amazon_gift_card_reload:
  purchase_count: 1
  transactions:
  - amount: 58 cents
    human_time: 2020-06-17 09:21PM
    unix_time: 1592454103
xfinity_bill_pay:
  purchase_count: 1
  transactions:
  - amount: 58 cents
    human_time: 2020-06-17 09:21PM
    unix_time: 1592454103
{% endhighlight %}

After:
{% highlight yaml%}
example_card_description_amazon_gift_card_reload:
  purchase_count: 1
  transactions:
  - amount: 58 cents
    human_time: 2020-06-17 09:21PM
    unix_time: 1592454103
example_card_description_xfinity_bill_pay:
  purchase_count: 1
  transactions:
  - amount: 58 cents
    human_time: 2020-06-17 09:21PM
    unix_time: 1592454103
{% endhighlight %}

{:start="7"}
1. Run debbit 2.0, it should print out the purchases migrated over from debbit 1.0.

```
1 example_card_description_amazon_gift_card_reload purchase complete for June 2020
1 example_card_description_xfinity_bill_pay purchase complete for June 2020
```
