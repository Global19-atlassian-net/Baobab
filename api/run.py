#!/usr/bin/env python

from flask_failsafe import failsafe
import sys


@failsafe
def create_app():
    from app import manager
    return manager


# Remove encoding if upgrading to python 3.
if __name__ == '__main__':
    create_app().run()
