

# converts cents int to formatted dollar string
# 4 -> '0.04'
# 50 -> '0.50'
# 160 -> '1.60'
# 12345 -> '123.45'
def cents_to_str(cents):
    if cents < 10:
        return '0.0' + str(cents)
    elif cents < 100:
        return '0.' + str(cents)
    else:
        return str(cents)[:-2] + '.' + str(cents)[-2:]


# Removes all non-number characters and returns an int
# '$77.84' -> 7784
# 'balance: 1.50' -> 150
# '0.05' -> 5
def str_to_cents(str):
    return int(''.join([c for c in str if c.isdigit()]))
