# encoding: utf-8
# (C) Datadog, Inc. 2010-2016
# All rights reserved
# Licensed under Simplified BSD License (see LICENSE)

# stdlib
from hashlib import md5
import logging
import re
import zlib
import sys
import locale
# 3p
import requests
import simplejson as json

# project
from config import get_version
from utils.platform import get_os
from utils.proxy import set_no_proxy_settings

set_no_proxy_settings()

# urllib3 logs a bunch of stuff at the info level
requests_log = logging.getLogger("requests.packages.urllib3")
requests_log.setLevel(logging.WARN)
requests_log.propagate = True

# From http://stackoverflow.com/questions/92438/stripping-non-printable-characters-from-a-string-in-python
control_chars = ''.join(map(unichr, range(0, 32) + range(127, 160)))
control_char_re = re.compile('[%s]' % re.escape(control_chars))


def remove_control_chars(s):
    return control_char_re.sub('', s)


def http_emitter(message, log, agentConfig, endpoint):
    "Send payload"
    url = agentConfig['dd_url']
    print message
    supported_encoding = ('utf-8', 'gb2312', 'gbk', 'iso-8859-1', 'latin-1', 'gb18030', 'cp936', 'cp1252')
    sys_encoding = sys.getfilesystemencoding().lower()
    if get_os() == 'windows':
        sys_encoding = locale.getpreferredencoding().lower()
    try:
        if sys_encoding in supported_encoding:
            pass
        try:
            payload = json.dumps(message, encoding=sys_encoding)
        except UnicodeDecodeError:
            payload = json.dumps(message, encoding='utf-8')
    except UnicodeDecodeError:
        try:
            message = remove_control_chars(message)
        except:
            pass
        payload = json.dumps(message)

    zipped = zlib.compress(payload)

    log.debug("payload_size=%d, compressed_size=%d, compression_ratio=%.3f"
              % (len(payload), len(zipped), float(len(payload)) / float(len(zipped))))

    apiKey = message.get('apiKey', None)
    if not apiKey:
        raise Exception("The http emitter requires an api key")

    url = "{0}/intake/{1}?api_key={2}".format(url, endpoint, apiKey)

    try:
        headers = post_headers(agentConfig, zipped)
        r = requests.post(url, data=zipped, timeout=5, headers=headers)

        r.raise_for_status()

        if r.status_code >= 200 and r.status_code < 205:
            log.debug("Payload accepted")

    except Exception:
        log.exception("Unable to post payload.")
        try:
            log.error("Received status code: {0}".format(r.status_code))
        except Exception:
            pass


def post_headers(agentConfig, payload):
    return {
        'User-Agent': 'Datadog Agent/%s' % agentConfig['version'],
        'Content-Type': 'application/json',
        'Content-Encoding': 'deflate',
        'Accept': 'text/html, */*',
        'Content-MD5': md5(payload).hexdigest(),
        'DD-Collector-Version': get_version()
    }
