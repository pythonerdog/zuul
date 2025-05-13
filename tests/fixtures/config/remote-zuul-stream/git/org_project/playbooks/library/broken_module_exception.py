#!/usr/bin/env python3


def main():
    raise Exception('This module is broken')


try:
    from ansible.module_utils.basic import *  # noqa
except ImportError:
    pass


if __name__ == '__main__':
    main()
