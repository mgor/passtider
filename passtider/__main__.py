import sys

from passtider import main, parse_available_times

if __name__ == '__main__':
    with open('result.html') as fd:
        parse_available_times(fd.read())
    #sys.exit(main())
