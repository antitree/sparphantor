# Using phantomjs and selenium bindings to complete the Sparsa February
# 2016 challenge.
# Copyright (C) 2016 antitree
#
# This program is free software: you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation, either version 3 of the License, or (at your option) any later
# version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of  MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along with
# this program.  If not, see <http://www.gnu.org/licenses/>.


from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.common.exceptions import WebDriverException
from socket import error as socket_error
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities

# Config file. You should check this
import config

import random
import logging
import time
import sys
import threading
import Queue

# sparsa
from string import ascii_letters

# number of threads to run. PhantomJS uses a lot of resources
THREADNUM = config.MAX_THREAD_NUM
queue = Queue.Queue(maxsize=config.MAX_BATCH_SIZE)


def main():
    # Get all available URLs to collect and add them to queue
    # The queue is only a given size to for debugging purposes
    # If it is stable enough, the queue size could match the list
    # of urls but chunking it was cleaner especially in the case
    # PhantomJS crashed due to memory issues.
    urls = []

    # If you're using tor, make sure it's running. TODO make gooder
    check_tor()

    baseurl = 'https://ghostbin.com/paste/'
    for url in range(config.MAX_BATCH_SIZE):
        pathid = generate_path()
        urls.append(baseurl + pathid)

    for url in urls:
        if not queue.full():
            queue.put(url)
        else:
            logging.info("Queue successfully filled")
    totalcount = queue.qsize()

    # Create threads for the queue based on the THREADNUM global
    t = [None] * THREADNUM  # Create an empty thread list
    for i in range(THREADNUM):  # arbitrary #
        time.sleep(i % 5)  ## Stagger the start because smart
        t[i] = grabber(queue=queue, DEBUG=config.DEBUG)
        t[i].setDaemon(True)
        t[i].start()
    print("waiting for queue...")

    # Wait until the queue has finished to continue
    # Or fuckit. Just join()
    queue.join()
    print("RESULTS:")
    print("=" * 30)
    donecount, failcount = 0, 0
    for thread in t:
        donecount += thread.donecount
        failcount += thread.failcount
    myformat = '{0:10} -- {1:10d}/{2}'
    print myformat.format("Completed", donecount, totalcount)
    print myformat.format("Failed", failcount, totalcount)
    print("=" * 30)
    logging.info("Successfully completed")
    return donecount, failcount


def check_tor():
    import socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    result = sock.connect_ex(('127.0.0.1',config.SOCKS_PORT))
    if not result == 0:
        print("Tor port on %s does not look open" % config.SOCKS_PORT)
        sys.exit()


def generate_path(start=None):
    return ''.join(random.choice(ascii_letters) for _ in range(5))


class grabber(threading.Thread):
    def __init__(self, queue, DEBUG=config.DEBUG, reset=False, socksport=None):
        if not socksport:
            socksport = config.SOCKS_PORT
        ## TODO add checks that a socks proxy is even open
        ## TODO add Tor checks to make sure circuits are operating
        threading.Thread.__init__(self)
        self.reset = reset  # Whether to check if a url has been collected
        self.queue = queue  # Multithreading queue of urls
        self.proxysettings = [
            '--proxy=127.0.0.1:%s' % socksport,
            '--proxy-type=socks5',
        ]
        #self.proxysettings = [] # DEBUG
        #self.ignore_ssl = ['--ignore-ssl-errors=true', '--ssl-protocols=any']
        self.ignore_ssl = []
        self.service_args = self.proxysettings + self.ignore_ssl
        
        self.failcount = 0    # Counts failures
        self.donecount = 0    # Counts successes
        #self.tor = tor.tor()  # Manages Tor via control port

        if DEBUG:  # PhantomJS sends a lot of data if debug set to DEBUG
            logging.basicConfig(level=logging.INFO)

    def run(self):
        ''' Main threading loop'''
        while True:
            url = self.queue.get()          # Get single item from queue
            print(queue.qsize())            # TODO Debug
            try:                            # in case nonascii
                print("Getting: %s" % url)
            except:
                print("Getting next url [omitted]")

            if self.get_url(url):           # Track succeses
                self.donecount += 1
            else:                           # Track failures
                self.failcount += 1
            self.queue.task_done()          # Needed to pop queue


    def _init_browser(self):
        ''' Setup selenium browser. Uses default path location
        if none is specified. Returns browser object or
        None if it fails.'''
        # User Agent
        uas = [
            "Mozilla/5.0 (Windows NT 6.1; rv:31.0) Gecko/20100101 Firefox/31.0",
            "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/42.0.2311.135 Safari/537.36",
            "Mozilla/5.0 (Windows NT 6.1; WOW64; rv:37.0) Gecko/20100101 Firefox/37.0",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_3) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/42.0.2311.135 Safari/537.36",
            "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/42.0.2311.90 Safari/537.36",
            ]
        ua = random.choice(uas)

        ## PhantomJS Binary files
        phantoms = config.PHANTOM_PATH
        phantompath = random.choice(phantoms)

        # Custom user agent
        dc = dict(DesiredCapabilities.PHANTOMJS)
        dc["phantomjs.page.settings.userAgent"] = ua
        #dc["pages.settings.XSSAuditEnabled"] = "true"

        try:
            browser = webdriver.PhantomJS(
                phantompath,
                service_args=self.service_args,
                desired_capabilities=dc
            )
        except WebDriverException as err:
            logging.error("Could not create browser. Check path")
            logging.error(err)
            return None
        except:
            logging.error("Major problem with webdriver. "
                          "Could be related to performance."
                          "Decrease the number of threads.")
            return None
        browser.set_page_load_timeout(45)

        ## DELETED GOOD STUFF ##
        return browser


    def get_url(self, url, retry=10):
        '''Returns the source of a URL request made
        by the Selenium web driver'''
        ## TODO: Something something inplicit trust something

        id = url[-5:]
        browser = self._init_browser()
        if not browser:
            logging.error("Could not create browser object in get_url")
            time.sleep(5)
            return False
        nurl = url
        #self.tor.newnym()  # Create a new circuit
        source = ""
        try:
                browser.get(nurl)
        except TimeoutException:
                logging.info("Timeout exception")
                browser.quit()
                return False
        except socket_error as err:
                logging.info("An error occurred in selenium")
                print(err)
                browser.quit()
                self.PrintError()
                return False
        except AttributeError as err:
                logging.error("Attibute error. Problem calling webdriver")
                logging.error(err)
                self.PrintError()
                browser.quit()
                return False
        except:
                print("OMG Baddness")
                print(sys.exc_info())
                browser.quit()
                self.PrintError()
                return False
        source = browser.page_source
        if source == '<html><head></head><body></body></html>':
            print("No source found. Problem making a connection")
            return False

        if not "404" in browser.title:
            imagepath = 'images/' + id + ".png"
            if browser.save_screenshot(imagepath):
                print("Screenshot saved")
            else:
                print("Screenshot not saved")
        else:
            print("404 found for %s" % nurl)
        browser.quit()
        return True


    def PrintError(self):
        print("Meh. Error bro.")
        '''
        exc_type, exc_obj, tb = sys.exc_info()
        f = tb.tb_frame
        lineno = tb.tb_lineno
        filename = f.f_code.co_filename
        linecache.checkcache(filename)
        line = linecache.getline(filename, lineno, f.f_globals)
        print 'EXCEPTION IN ({}, LINE {} "{}"): {}'.format(filename, lineno, line.strip(), exc_obj)
        '''


if __name__ == "__main__":
    main()
