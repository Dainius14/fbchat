# -*- coding: UTF-8 -*-

"""
    fbchat
    ~~~~~~

    Facebook Chat (Messenger) for Python

    :copyright: (c) 2015      by Taehoon Kim.
    :copyright: (c) 2015-2016 by PidgeyL.
    :license: BSD, see LICENSE for more details.
"""

import requests
import logging
from uuid import uuid1
import warnings
from random import choice
from datetime import datetime
from bs4 import BeautifulSoup as bs
from mimetypes import guess_type
from .utils import *
from .models import *
import time
from .event_hook import EventHook


# Python 3 does not have raw_input, whereas Python 2 has and it's more secure
try:
    input = raw_input
except NameError:
    pass

# URLs
LoginURL     ="https://m.facebook.com/login.php?login_attempt=1"
SearchURL    ="https://www.facebook.com/ajax/typeahead/search.php"
SendURL      ="https://www.facebook.com/messaging/send/"
ThreadsURL   ="https://www.facebook.com/ajax/mercury/threadlist_info.php"
ThreadSyncURL="https://www.facebook.com/ajax/mercury/thread_sync.php"
MessagesURL  ="https://www.facebook.com/ajax/mercury/thread_info.php"
ReadStatusURL="https://www.facebook.com/ajax/mercury/change_read_status.php"
DeliveredURL ="https://www.facebook.com/ajax/mercury/delivery_receipts.php"
MarkSeenURL  ="https://www.facebook.com/ajax/mercury/mark_seen.php"
BaseURL      ="https://www.facebook.com"
MobileURL    ="https://m.facebook.com/"
StickyURL    ="https://0-edge-chat.facebook.com/pull"
PingURL      ="https://0-channel-proxy-06-ash2.facebook.com/active_ping"
UploadURL    ="https://upload.facebook.com/ajax/mercury/upload.php"
UserInfoURL  ="https://www.facebook.com/chat/user_info/"
ConnectURL   ="https://www.facebook.com/ajax/add_friend/action.php?dpr=1"
RemoveUserURL="https://www.facebook.com/chat/remove_participants/"
LogoutURL    ="https://www.facebook.com/logout.php"
AllUsersURL  ="https://www.facebook.com/chat/user_info_all"
SaveDeviceURL="https://m.facebook.com/login/save-device/cancel/"
CheckpointURL="https://m.facebook.com/login/checkpoint/"
facebookEncoding = 'UTF-8'

# Log settings
log = logging.getLogger("client")
log.setLevel(logging.DEBUG)


class Client(object):
    """A client for the Facebook Chat (Messenger).

    See http://github.com/carpedm20/fbchat for complete
    documentation for the API.
    """

    def __init__(self, email, password, debug=True, info_log=True, user_agent=None, max_retries=5, session_cookies=None):
        """A client for the Facebook Chat (Messenger).

        :param email: Facebook `email` or `id` or `phone number`
        :param password: Facebook account password
        :param debug: Configures the logger to `debug` logging_level
        :param info_log: Configures the logger to `info` logging_level
        :param user_agent: Custom user agent to use when sending requests. If `None`, user agent will be chosen from a premade list (see utils.py)
        :param max_retries: Maximum number of times to retry login
        :param session_cookies: Cookie dict from a previous session (Will default to login if these are invalid)
        """

        self.sticky, self.pool = (None, None)
        self._session = requests.session()
        self.req_counter = 1
        self.seq = "0"
        self.payloadDefault = {}
        self.client = 'mercury'
        self.listening = False
        self.is_def_thread_set = False
        self.def_thread_id = None
        self.def_thread_type = None
        self.threads = []

        # Setup event hooks
        self.onLoggingIn = EventHook(email=str)
        self.onLoggedIn = EventHook(email=str)
        self.onListening = EventHook()

        self.onMessage = EventHook(mid=str, author_id=str, message=str, thread_id=int, thread_type=ThreadType, ts=str, metadata=dict)
        self.onColorChange = EventHook(mid=str, author_id=str, new_color=str, thread_id=str, thread_type=ThreadType, ts=str, metadata=dict)
        self.onEmojiChange = EventHook(mid=str, author_id=str, new_emoji=str, thread_id=str, thread_type=ThreadType, ts=str, metadata=dict)
        self.onTitleChange = EventHook(mid=str, author_id=str, new_title=str, thread_id=str, thread_type=ThreadType, ts=str, metadata=dict)
        self.onNicknameChange = EventHook(mid=str, author_id=str, changed_for=str, new_title=str, thread_id=str, thread_type=ThreadType, ts=str, metadata=dict)
        # self.onTyping = EventHook(author_id=int, typing_status=TypingStatus)
        # self.onSeen = EventHook(seen_by=str, thread_id=str, timestamp=str)

        self.onInbox = EventHook(unseen=int, unread=int, recent_unread=int)
        self.onPeopleAdded = EventHook(added_ids=list, author_id=str, thread_id=str)
        self.onPersonRemoved = EventHook(removed_id=str, author_id=str, thread_id=str)
        self.onFriendRequest = EventHook(from_id=str)

        self.onUnknownMesssageType = EventHook(msg=dict)

        # Setup event handlers
        self.onLoggingIn += lambda email: log.info("Logging in %s..." % email)
        self.onLoggedIn += lambda email: log.info("Login of %s successful." % email)
        self.onListening += lambda: log.info("Listening...")

        self.onMessage += lambda mid, author_id, message, thread_id, thread_type, ts, metadata:\
            log.info("Message from %s in %s (%s): %s" % (author_id, thread_id, thread_type.name, message))

        self.onColorChange += lambda mid, author_id, new_color, thread_id, thread_type, ts, metadata:\
            log.info("Color change from %s in %s (%s): %s" % (author_id, thread_id, thread_type.name, new_color))
        self.onEmojiChange += lambda mid, author_id, new_emoji, thread_id, thread_type, ts, metadata:\
            log.info("Emoji change from %s in %s (%s): %s" % (author_id, thread_id, thread_type.name, new_emoji))
        self.onTitleChange += lambda mid, author_id, new_title, thread_id, thread_type, ts, metadata:\
            log.info("Title change from %s in %s (%s): %s" % (author_id, thread_id, thread_type.name, new_title))
        self.onNicknameChange += lambda mid, author_id, new_title, changed_for, thread_id, thread_type, ts, metadata:\
            log.info("Nickname change from %s in %s (%s) for %s: %s" % (author_id, thread_id, thread_type.name, changed_for, new_title))

        self.onPeopleAdded += lambda added_ids, author_id, thread_id:\
            log.info("%s added: %s" % (author_id, [x for x in added_ids]))
        self.onPersonRemoved += lambda removed_id, author_id, thread_id:\
            log.info("%s removed: %s" % (author_id, removed_id))

        self.onUnknownMesssageType += lambda msg:\
            log.info("Unknown message type received: %s" % msg)

        if not user_agent:
            user_agent = choice(USER_AGENTS)

        self._header = {
            'Content-Type' : 'application/x-www-form-urlencoded',
            'Referer' : BaseURL,
            'Origin' : BaseURL,
            'User-Agent' : user_agent,
            'Connection' : 'keep-alive',
        }

        # Configure the logger differently based on the 'debug' and 'info_log' parameters
        if debug:
            logging_level = logging.DEBUG
        elif info_log:
            logging_level = logging.INFO
        else:
            logging_level = logging.WARNING

        # Creates the console handler
        handler = logging.StreamHandler()
        handler.setLevel(logging_level)
        log.addHandler(handler)

        # If session cookies aren't set, not properly loaded or gives us an invalid session, then do the login
        if not session_cookies or not self.setSession(session_cookies) or not self.isLoggedIn():
            self.login(email, password, max_retries)

    def _generatePayload(self, query):
        """Adds the following defaults to the payload:
          __rev, __user, __a, ttstamp, fb_dtsg, __req
        """
        payload = self.payloadDefault.copy()
        if query:
            payload.update(query)
        payload['__req'] = str_base(self.req_counter, 36)
        payload['seq'] = self.seq
        self.req_counter += 1
        return payload

    def _get(self, url, query=None, timeout=30):
        payload = self._generatePayload(query)
        return self._session.get(url, headers=self._header, params=payload, timeout=timeout)

    def _post(self, url, query=None, timeout=30):
        payload = self._generatePayload(query)
        return self._session.post(url, headers=self._header, data=payload, timeout=timeout)

    def _cleanGet(self, url, query=None, timeout=30):
        return self._session.get(url, headers=self._header, params=query, timeout=timeout)

    def _cleanPost(self, url, query=None, timeout=30):
        self.req_counter += 1
        return self._session.post(url, headers=self._header, data=query, timeout=timeout)

    def _postFile(self, url, files=None, timeout=30):
        payload=self._generatePayload(None)
        return self._session.post(url, data=payload, timeout=timeout, files=files)

    def _postLogin(self):
        self.payloadDefault = {}
        self.client_id = hex(int(random()*2147483648))[2:]
        self.start_time = now()
        self.uid = int(self._session.cookies['c_user'])
        self.user_channel = "p_" + str(self.uid)
        self.ttstamp = ''

        r = self._get(BaseURL)
        soup = bs(r.text, "lxml")
        log.debug(r.text)
        log.debug(r.url)
        self.fb_dtsg = soup.find("input", {'name':'fb_dtsg'})['value']
        self.fb_h = soup.find("input", {'name':'h'})['value']

        for i in self.fb_dtsg:
            self.ttstamp += str(ord(i))
        self.ttstamp += '2'

        # Set default payload
        self.payloadDefault['__rev'] = int(r.text.split('"revision":',1)[1].split(",",1)[0])
        self.payloadDefault['__user'] = self.uid
        self.payloadDefault['__a'] = '1'
        self.payloadDefault['ttstamp'] = self.ttstamp
        self.payloadDefault['fb_dtsg'] = self.fb_dtsg

        self.form = {
            'channel' : self.user_channel,
            'partition' : '-2',
            'clientid' : self.client_id,
            'viewer_uid' : self.uid,
            'uid' : self.uid,
            'state' : 'active',
            'format' : 'json',
            'idle' : 0,
            'cap' : '8'
        }

        self.prev = now()
        self.tmp_prev = now()
        self.last_sync = now()

    def _login(self):
        if not (self.email and self.password):
            raise Exception("Email and password not found.")

        soup = bs(self._get(MobileURL).text, "lxml")
        data = dict((elem['name'], elem['value']) for elem in soup.findAll("input") if elem.has_attr('value') and elem.has_attr('name'))
        data['email'] = self.email
        data['pass'] = self.password
        data['login'] = 'Log In'

        r = self._cleanPost(LoginURL, data)

        # Usually, 'Checkpoint' will refer to 2FA
        if 'checkpoint' in r.url and 'Enter Security Code to Continue' in r.text:
            r = self._2FA(r)

        # Sometimes Facebook tries to show the user a "Save Device" dialog
        if 'save-device' in r.url:
            r = self._cleanGet(SaveDeviceURL)

        if 'home' in r.url:
            self._postLogin()
            return True
        else:
            return False

    def _2FA(self, r):
        soup = bs(r.text, "lxml")
        data = dict()

        s = input('Please enter your 2FA code --> ')
        data['approvals_code'] = s
        data['fb_dtsg'] = soup.find("input", {'name':'fb_dtsg'})['value']
        data['nh'] = soup.find("input", {'name':'nh'})['value']
        data['submit[Submit Code]'] = 'Submit Code'
        data['codes_submitted'] = 0
        log.info('Submitting 2FA code.')

        r = self._cleanPost(CheckpointURL, data)

        if 'home' in r.url:
            return r

        del(data['approvals_code'])
        del(data['submit[Submit Code]'])
        del(data['codes_submitted'])

        data['name_action_selected'] = 'save_device'
        data['submit[Continue]'] = 'Continue'
        log.info('Saving browser.')  # At this stage, we have dtsg, nh, name_action_selected, submit[Continue]
        r = self._cleanPost(CheckpointURL, data)

        if 'home' in r.url:
            return r

        del(data['name_action_selected'])
        log.info('Starting Facebook checkup flow.')  # At this stage, we have dtsg, nh, submit[Continue]
        r = self._cleanPost(CheckpointURL, data)

        if 'home' in r.url:
            return r

        del(data['submit[Continue]'])
        data['submit[This was me]'] = 'This Was Me'
        log.info('Verifying login attempt.')  # At this stage, we have dtsg, nh, submit[This was me]
        r = self._cleanPost(CheckpointURL, data)

        if 'home' in r.url:
            return r

        del(data['submit[This was me]'])
        data['submit[Continue]'] = 'Continue'
        data['name_action_selected'] = 'save_device'
        log.info('Saving device again.')  # At this stage, we have dtsg, nh, submit[Continue], name_action_selected
        r = self._cleanPost(CheckpointURL, data)
        return r

    def isLoggedIn(self):
        # Send a request to the login url, to see if we're directed to the home page.
        r = self._cleanGet(LoginURL)
        return 'home' in r.url

    def getSession(self):
        """Returns the session cookies"""
        return self._session.cookies.get_dict()

    def setSession(self, session_cookies):
        """Loads session cookies
        :param session_cookies: dictionary containing session cookies
        Return false if session_cookies does not contain proper cookies
        """

        # Quick check to see if session_cookies is formatted properly
        if not session_cookies or 'c_user' not in session_cookies:
            return False

        # Load cookies into current session
        self._session.cookies = requests.cookies.merge_cookies(self._session.cookies, session_cookies)
        self._postLogin()
        return True

    def login(self, email, password, max_retries=5):
        self.onLoggingIn(email=email)

        if not (email and password):
            raise Exception("Email and password not set.")

        self.email = email
        self.password = password

        for i in range(1, max_retries+1):
            if not self._login():
                log.warning("Attempt #{} failed{}".format(i, {True: ', retrying'}.get(i < 5, '')))
                time.sleep(1)
                continue
            else:
                self.onLoggedIn(email=email)
                break
        else:
            raise Exception("Login failed. Check email/password.")

    def logout(self, timeout=30):
        data = {
            'ref': "mb",
            'h': self.fb_h
        }

        payload=self._generatePayload(data)
        r = self._session.get(LogoutURL, headers=self._header, params=payload, timeout=timeout)
        # reset value
        self.payloadDefault={}
        self._session = requests.session()
        self.req_counter = 1
        self.seq = "0"
        return r

    def setDefaultThreadId(self, thread_id=str, thread_type=ThreadType):
        """Sets default recipient to send messages and images to.
        
        :param thread_id: user/group ID to default to
        :param thread_type: type of thread_id
        """
        self.def_thread_id = thread_id
        self.def_thread_type = thread_type
        self.is_def_thread_set = True

    def getAllUsers(self):
        """ Gets all users from chat with info included """

        data = {
            'viewer': self.uid,
        }
        r = self._post(AllUsersURL, query=data)
        if not r.ok or len(r.text) == 0:
            return None
        j = get_json(r.text)
        if not j['payload']:
            return None
        payload = j['payload']
        users = []

        for k in payload.keys():
            try:
                user = User.adaptFromChat(payload[k])
            except KeyError:
                continue

            users.append(User(user))

        return users

    def getUsers(self, name):
        """Find and get user by his/her name

        :param name: name of a person
        """

        payload = {
            'value' : name.lower(),
            'viewer' : self.uid,
            'rsp' : "search",
            'context' : "search",
            'path' : "/home.php",
            'request_id' : str(uuid1()),
        }

        r = self._get(SearchURL, payload)
        self.j = j = get_json(r.text)

        users = []
        for entry in j['payload']['entries']:
            if entry['type'] == 'user':
                users.append(User(entry))
        return users # have bug TypeError: __repr__ returned non-string (type bytes)

    """
    SEND METHODS
    """

    def _send(self, thread_id=None, message=None, thread_type=None, emoji_size=None, image_id=None, add_user_ids=None, new_title=None):
        """Send a message with given thread id

        :param thread_id: the user id or thread id that you want to send a message to
        :param message: a text that you want to send
        :param thread_type: determines if the recipient_id is for user or thread
        :param emoji_size: size of the like sticker you want to send
        :param image_id: id for the image to send, gotten from the UploadURL
        :param add_user_ids: a list of user ids to add to a chat
        :return: a list of message ids of the sent message(s)
        """

        if thread_id is None and self.is_def_thread_set:
            thread_id = self.def_thread_id
            thread_type = self.def_thread_type
        elif thread_id is None and not self.is_def_thread_set:
            raise ValueError('Default Thread ID is not set.')

        messageAndOTID = generateOfflineThreadingID()
        timestamp = now()
        date = datetime.now()
        data = {
            'client': self.client,
            'author' : 'fbid:' + str(self.uid),
            'timestamp' : timestamp,
            'timestamp_absolute' : 'Today',
            'timestamp_relative' : str(date.hour) + ":" + str(date.minute).zfill(2),
            'timestamp_time_passed' : '0',
            'is_unread' : False,
            'is_cleared' : False,
            'is_forward' : False,
            'is_filtered_content' : False,
            'is_filtered_content_bh': False,
            'is_filtered_content_account': False,
            'is_filtered_content_quasar': False,
            'is_filtered_content_invalid_app': False,
            'is_spoof_warning' : False,
            'source' : 'source:chat:web',
            'source_tags[0]' : 'source:chat',
            'html_body' : False,
            'ui_push_phase' : 'V3',
            'status' : '0',
            'offline_threading_id':messageAndOTID,
            'message_id' : messageAndOTID,
            'threading_id': generateMessageID(self.client_id),
            'ephemeral_ttl_mode:': '0',
            'manual_retry_cnt' : '0',
            'signatureID' : getSignatureID()
        }

        # Set recipient
        if thread_type == ThreadType.USER:
            data["other_user_fbid"] = thread_id
        elif thread_type == ThreadType.GROUP:
            data["thread_fbid"] = thread_id

        # Set title
        if new_title:
            data['action_type'] = 'ma-type:log-message'
            data['log_message_data[name]'] = new_title
            data['log_message_type'] = 'log:thread-name'

        # Set users to add
        if add_user_ids:
            data['action_type'] = 'ma-type:log-message'
            # It's possible to add multiple users
            for i, add_user_id in enumerate(add_user_ids):
                data['log_message_data[added_participants][' + str(i) + ']'] = "fbid:" + str(add_user_id)
            data['log_message_type'] = 'log:subscribe'

        # Sending a simple message
        if not add_user_ids and not new_title:
            data['action_type'] = 'ma-type:user-generated-message'
            data['body'] = message or ''
            data['has_attachment'] = image_id is not None
            data['specific_to_list[0]'] = 'fbid:' + str(thread_id)
            data['specific_to_list[1]'] = 'fbid:' + str(self.uid)

        # Set image to send
        if image_id:
            data['image_ids[0]'] = image_id

        # Set emoji to send
        if emoji_size:
            data["sticker_id"] = emoji_size.value

        r = self._post(SendURL, data)
        
        if not r.ok:
            log.warning('Error when sending message: Got {} response'.format(r.status_code))
            return False

        response_content = {}
        if isinstance(r.content, str) is False:
            response_content = r.content.decode(facebookEncoding)
        j = get_json(response_content)
        if 'error' in j:
            # 'errorDescription' is in the users own language!
            log.warning('Error #{} when sending message: {}'.format(j['error'], j['errorDescription']))
            return False
        
        message_ids = []
        try:
            message_ids += [action['message_id'] for action in j['payload']['actions'] if 'message_id' in action]
            message_ids[0] # Try accessing element
        except (KeyError, IndexError) as e:
            log.warning('Error when sending message: No message ids could be found')
            return False

        log.info('Message sent.')
        log.debug("Sending {}".format(r))
        log.debug("With data {}".format(data))
        return message_ids

    def sendMessage(self, message: str, thread_id: str = None, thread_type: ThreadType = None):
        """
        Sends a message to given (or default, if not) thread with an additional image.
        :param message: message to send
        :param thread_id: user/group chat ID
        :param thread_type: specify whether thread_id is user or group chat
        :return: a list of message ids of the sent message(s)
        """
        return self._send(thread_id, message, thread_type, None, None, None, None)

    def sendEmoji(self, emoji_size: EmojiSize, thread_id: str = None, thread_type: ThreadType = None):
        """
        Sends an emoji to given (or default, if not) thread.
        :param emoji_size: size of emoji to send
        :param thread_id: user/group chat ID
        :param thread_type: specify whether thread_id is user or group chat 
        :return: a list of message ids of the sent message(s)
        """
        return self._send(thread_id, None, thread_type, emoji_size, None, None, None)

    def sendRemoteImage(self, image_url: str, message: str = None, thread_id: str = None, thread_type: ThreadType = None):
        """
        Sends an image from given URL to given (or default, if not) thread.        
        :param image_url: URL of an image to upload and send
        :param message: additional message
        :param thread_id: user/group chat ID
        :param thread_type: specify whether thread_id is user or group chat 
        :return: a list of message ids of the sent message(s)
        """
        mimetype = guess_type(image_url)[0]
        remote_image = requests.get(image_url).content
        image_id = self._uploadImage({'file': (image_url, remote_image, mimetype)})
        return self._send(thread_id, message, thread_type, None, image_id, None, None)

    # Doesn't upload properly
    # def sendLocalImage(self, image_path: str, message: str = None, thread_id: str = None, thread_type: ThreadType = None):
    #     """
    #     Sends an image from given URL to given (or default, if not) thread.
    #     :param image_path: path of an image to upload and send
    #     :param message: additional message
    #     :param thread_id: user/group chat ID
    #     :param thread_type: specify whether thread_id is user or group chat
    #     :return: a list of message ids of the sent message(s)
    #     """
    #     mimetype = guess_type(image_path)[0]
    #     image_id = self._uploadImage({'file': (image_path, open(image_path, 'rb'), mimetype)})
    #     return self._send(thread_id, message, thread_type, None, image_id, None, None)

    def addUsersToChat(self, user_list: list, thread_id: str = None):
        """
        Adds users to given (or default, if not) thread.
        :param user_list: list of users to add
        :param thread_id: group chat ID
        :return: a list of message ids of the sent message(s)
        """
        return self._send(thread_id, None, ThreadType.GROUP, None, None, user_list, None)

    def removeUserFromChat(self, user_id: str, thread_id: str = None):
        """
        Adds users to given (or default, if not) thread.
        :param user_id: user ID to remove
        :param thread_id: group chat ID
        :return: true if user was removed
        """

        if thread_id is None and self.def_thread_type == ThreadType.GROUP:
            thread_id = self.def_thread_id
        elif thread_id is None:
            raise ValueError('Default Thread ID is not set.')

        data = {
            "uid": user_id,
            "tid": thread_id
        }

        r = self._post(RemoveUserURL, data)

        return r.ok

    def changeThreadTitle(self, new_title: str, thread_id: str = None):
        """
        Change title of a group conversation.
        :param new_title: new group chat title
        :param thread_id: group chat ID
        :return: a list of message ids of the sent message(s)
        """
        if thread_id is None and self.def_thread_type == ThreadType.GROUP:
            thread_id = self.def_thread_id
        elif thread_id is None:
            raise ValueError('Default Thread ID is not set.')
        return self._send(thread_id, None, ThreadType.GROUP, None, None, None, new_title)

    """
    END SEND METHODS    
    """

    def _uploadImage(self, image):
        """Upload an image and get the image_id for sending in a message

        :param image: a tuple of (file name, data, mime type) to upload to facebook
        """

        r = self._postFile(UploadURL, image)
        response_content = {}
        if isinstance(r.content, str) is False:
            response_content = r.content.decode(facebookEncoding)
        # Strip the start and parse out the returned image_id
        return json.loads(response_content[9:])['payload']['metadata'][0]['image_id']

    def getThreadInfo(self, userID, last_n=20, start=None, is_user=True):
        """Get the info of one Thread

        :param userID: ID of the user you want the messages from
        :param last_n: (optional) number of retrieved messages from start
        :param start: (optional) the start index of a thread (Deprecated)
        :param is_user: (optional) determines if the userID is for user or thread
        """

        assert last_n > 0, 'length must be positive integer, got %d' % last_n
        assert start is None, '`start` is deprecated, always 0 offset querry is returned'
        if is_user:
            key = 'user_ids'
        else:
            key = 'thread_fbids'

        # deprecated
        # `start` doesn't matter, always returns from the last
        # data['messages[{}][{}][offset]'.format(key, userID)] = start
        data = {'messages[{}][{}][offset]'.format(key, userID): 0,
                'messages[{}][{}][limit]'.format(key, userID): last_n - 1,
                'messages[{}][{}][timestamp]'.format(key, userID): now()}

        r = self._post(MessagesURL, query=data)
        if not r.ok or len(r.text) == 0:
            return None

        j = get_json(r.text)
        if not j['payload']:
            return None

        messages = []
        for message in j['payload']['actions']:
            messages.append(Message(**message))
        return list(reversed(messages))

    def getThreadList(self, start, length=20):
        """Get thread list of your facebook account.

        :param start: the start index of a thread
        :param length: (optional) the length of a thread
        """

        assert length < 21, '`length` is deprecated, max. last 20 threads are returned'

        data = {
            'client' : self.client,
            'inbox[offset]' : start,
            'inbox[limit]' : length,
        }

        r = self._post(ThreadsURL, data)
        if not r.ok or len(r.text) == 0:
            return None

        j = get_json(r.text)

        # Get names for people
        participants = {}
        try:
            for participant in j['payload']['participants']:
                participants[participant["fbid"]] = participant["name"]
        except Exception as e:
            log.warning(str(j))

        # Prevent duplicates in self.threads
        threadIDs = [getattr(x, "thread_id") for x in self.threads]
        for thread in j['payload']['threads']:
            if thread["thread_id"] not in threadIDs:
                try:
                    thread["other_user_name"] = participants[int(thread["other_user_fbid"])]
                except:
                    thread["other_user_name"] = ""
                t = Thread(**thread)
                self.threads.append(t)

        return self.threads

    def getUnread(self):
        form = {
            'client': 'mercury_sync',
            'folders[0]': 'inbox',
            'last_action_timestamp': now() - 60*1000
            # 'last_action_timestamp': 0
        }

        r = self._post(ThreadSyncURL, form)
        if not r.ok or len(r.text) == 0:
            return None

        j = get_json(r.text)
        result = {
            "message_counts": j['payload']['message_counts'],
            "unseen_threads": j['payload']['unseen_thread_ids']
        }
        return result

    def markAsDelivered(self, userID, threadID):
        data = {
            "message_ids[0]": threadID,
            "thread_ids[%s][0]" % userID: threadID
        }

        r = self._post(DeliveredURL, data)
        return r.ok

    def markAsRead(self, userID):
        data = {
            "watermarkTimestamp": now(),
            "shouldSendReadReceipt": True,
            "ids[%s]" % userID: True
        }

        r = self._post(ReadStatusURL, data)
        return r.ok

    def markAsSeen(self):
        r = self._post(MarkSeenURL, {"seen_timestamp": 0})
        return r.ok

    def friendConnect(self, friend_id):
        data = {
            "to_friend": friend_id,
            "action": "confirm"
        }

        r = self._post(ConnectURL, data)

        return r.ok

    def ping(self, sticky):
        data = {
            'channel': self.user_channel,
            'clientid': self.client_id,
            'partition': -2,
            'cap': 0,
            'uid': self.uid,
            'sticky': sticky,
            'viewer_uid': self.uid
        }
        r = self._get(PingURL, data)
        return r.ok

    def _getSticky(self):
        """Call pull api to get sticky and pool parameter, newer api needs these parameter to work."""

        data = {
            "msgs_recv": 0,
            "channel": self.user_channel,
            "clientid": self.client_id
        }

        r = self._get(StickyURL, data)
        j = get_json(r.text)

        if 'lb_info' not in j:
            raise Exception('Get sticky pool error')

        sticky = j['lb_info']['sticky']
        pool = j['lb_info']['pool']
        return sticky, pool

    def _pullMessage(self, sticky, pool):
        """Call pull api with seq value to get message data."""

        data = {
            "msgs_recv": 0,
            "sticky_token": sticky,
            "sticky_pool": pool,
            "clientid": self.client_id,
        }

        r = self._get(StickyURL, data)
        r.encoding = facebookEncoding
        j = get_json(r.text)

        self.seq = j.get('seq', '0')
        return j

    def _parseMessage(self, content):
        """Get message and author name from content.
        May contains multiple messages in the content.
        """

        if 'ms' not in content: return

        log.debug("Received {}".format(content["ms"]))
        for m in content["ms"]:
            mtype = m.get("type")
            try:
                # Things that directly change chat
                if mtype == "delta":

                    def getThreadIdAndThreadType(msg_metadata):
                        """Returns a tuple consisting of thread id and thread type"""
                        id_thread = None
                        type_thread = None
                        if 'threadFbId' in msg_metadata['threadKey']:
                            id_thread = str(msg_metadata['threadKey']['threadFbId'])
                            type_thread = ThreadType.GROUP
                        elif 'otherUserFbId' in msg_metadata['threadKey']:
                            id_thread = str(msg_metadata['threadKey']['otherUserFbId'])
                            type_thread = ThreadType.USER
                        return id_thread, type_thread

                    delta = m["delta"]
                    delta_type = delta.get("type")
                    metadata = delta.get("messageMetadata")

                    if metadata is not None:
                        mid = metadata["messageId"]
                        author_id = str(metadata['actorFbId'])
                        ts = int(metadata["timestamp"])

                    # Added participants
                    if 'addedParticipants' in delta:
                        added_ids = [str(x['userFbId']) for x in delta['addedParticipants']]
                        thread_id = str(metadata['threadKey']['threadFbId'])
                        self.onPeopleAdded(mid=mid, added_ids=added_ids, author_id=author_id, thread_id=thread_id, ts=ts)
                        continue

                    # Left/removed participants
                    elif 'leftParticipantFbId' in delta:
                        removed_id = str(delta['leftParticipantFbId'])
                        thread_id = str(metadata['threadKey']['threadFbId'])
                        self.onPersonRemoved(mid=mid, removed_id=removed_id, author_id=author_id, thread_id=thread_id, ts=ts)
                        continue

                    # Color change
                    elif delta_type == "change_thread_theme":
                        new_color = delta["untypedData"]["theme_color"]
                        thread_id, thread_type = getThreadIdAndThreadType(metadata)
                        self.onColorChange(mid=mid, author_id=author_id, new_color=new_color, thread_id=thread_id,
                                           thread_type=thread_type, ts=ts, metadata=metadata)
                        continue

                    # Emoji change
                    elif delta_type == "change_thread_icon":
                        new_emoji = delta["untypedData"]["thread_icon"]
                        thread_id, thread_type = getThreadIdAndThreadType(metadata)
                        self.onEmojiChange(mid=mid, author_id=author_id, new_emoji=new_emoji, thread_id=thread_id,
                                           thread_type=thread_type, ts=ts, metadata=metadata)
                        continue

                    # Thread title change
                    elif delta.get("class") == "ThreadName":
                        new_title = delta["name"]
                        thread_id, thread_type = getThreadIdAndThreadType(metadata)
                        self.onTitleChange(mid=mid, author_id=author_id, new_title=new_title, thread_id=thread_id,
                                           thread_type=thread_type, ts=ts, metadata=metadata)
                        continue

                    # Nickname change
                    elif delta_type == "change_thread_nickname":
                        changed_for = str(delta["untypedData"]["participant_id"])
                        new_title = delta["untypedData"]["nickname"]
                        thread_id, thread_type = getThreadIdAndThreadType(metadata)
                        self.onNicknameChange(mid=mid, author_id=author_id, changed_for=changed_for, new_title=new_title,
                                              thread_id=thread_id, thread_type=thread_type, ts=ts, metadata=metadata)
                        continue


                    # TODO properly implement these as they differ on different scenarios
                    # Seen
                    # elif delta.get("class") == "ReadReceipt":
                    #     seen_by = delta["actorFbId"] or delta["threadKey"]["otherUserFbId"]
                    #     thread_id = delta["threadKey"].get("threadFbId")
                    #     self.onSeen(seen_by=seen_by, thread_id=thread_id, ts=ts)
                    #
                    # # Message delivered
                    # elif delta.get("class") == 'DeliveryReceipt':
                    #     time_delivered = delta['deliveredWatermarkTimestampMs']
                    #     self.onDelivered()

                    # New message
                    elif delta.get("class") == "NewMessage":
                        message = delta.get('body', '')
                        thread_id, thread_type = getThreadIdAndThreadType(metadata)
                        self.onMessage(mid=mid, author_id=author_id, message=message,
                                       thread_id=thread_id, thread_type=thread_type, ts=ts, metadata=m)
                        continue

                # Inbox
                if mtype == "inbox":
                    self.onInbox(unseen=m["unseen"], unread=m["unread"], recent_unread=m["recent_unread"])

                # Typing
                # elif mtype == "typ":
                #     author_id = str(m.get("from"))
                #     typing_status = TypingStatus(m.get("st"))
                #     self.onTyping(author_id=author_id, typing_status=typing_status)

                # Seen
                # elif mtype == "m_read_receipt":
                #
                #     self.onSeen(m.get('realtime_viewer_fbid'), m.get('reader'), m.get('time'))

                # elif mtype in ['jewel_requests_add']:
                #         from_id = m['from']
                #         self.on_friend_request(from_id)

                # Happens on every login
                elif mtype == "qprimer":
                    pass

                # Is sent before any other message
                elif mtype == "deltaflow":
                    pass

                # Unknown message type
                else:
                    self.onUnknownMesssageType(msg=m)

            except Exception as e:
                log.debug(str(e))

    def startListening(self):
        """Start listening from an external event loop."""
        self.listening = True
        self.sticky, self.pool = self._getSticky()

    def doOneListen(self, markAlive=True):
        """Does one cycle of the listening loop.
        This method is only useful if you want to control fbchat from an
        external event loop."""
        try:
            if markAlive: self.ping(self.sticky)
            try:
                content = self._pullMessage(self.sticky, self.pool)
                if content: self._parseMessage(content)
            except requests.exceptions.RequestException as e:
                pass
        except KeyboardInterrupt:
            self.listening = False
        except requests.exceptions.Timeout:
            pass

    def stopListening(self):
        """Cleans up the variables from start_listening."""
        self.listening = False
        self.sticky, self.pool = (None, None)

    def listen(self, markAlive=True):
        self.startListening()
        self.onListening()

        while self.listening:
            self.doOneListen(markAlive)

        self.stopListening()

    def getUserInfo(self, *user_ids):
        """Get user info from id. Unordered.

        :param user_ids: one or more user id(s) to query
        """

        def fbidStrip(_fbid):
            # Stripping of `fbid:` from author_id
            if type(_fbid) == int:
                return _fbid

            if type(_fbid) in [str, unicode] and 'fbid:' in _fbid:
                return int(_fbid[5:])

        user_ids = [fbidStrip(uid) for uid in user_ids]

        data = {"ids[{}]".format(i):uid for i,uid in enumerate(user_ids)}
        r = self._post(UserInfoURL, data)
        info = get_json(r.text)
        full_data= [details for profile,details in info['payload']['profiles'].items()]
        if len(full_data)==1:
            full_data=full_data[0]
        return full_data
