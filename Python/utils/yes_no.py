def yes_or_no(question):
    while True:
        reply = str(raw_input(question+' (y/n): ')).lower().strip()
        if reply[0] == 'y':
            return True
        else:
            print 'You replied No. Bye'
            return False

yse_or_no("Do you want to continue?")
