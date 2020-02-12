def cents_to_str(cents):
    if cents < 10:
        return '0.0' + str(cents)
    elif cents < 100:
        return '0.' + str(cents)
    else:
        return str(cents)[:-2] + '.' + str(cents)[-2:]
