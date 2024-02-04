from termcolor import colored

def print_red(msg, **kwargs):
    print(colored(msg, 'red'), **kwargs)


def print_green(msg, **kwargs):
    print(colored(msg, 'green'), **kwargs)
