from __future__ import unicode_literals
from enum import Enum
import sys


class Base():
    def __repr__(self):
        uni = self.__unicode__()
        return uni.encode('utf-8') if sys.version_info < (3, 0) else uni

    def __unicode__(self):
        return u'<%s %s (%s)>' % (self.type.upper(), self.name, self.url)


class User(Base):
    def __init__(self, data):
        if data['type'] != 'user':
            raise Exception("[!] %s <%s> is not a user" % (data['text'], data['path']))
        self.uid = data['uid']
        self.type = data['type']
        self.photo = data['photo']
        self.url = data['path']
        self.name = data['text']
        self.score = data['score']

        self.data = data

    @staticmethod
    def adaptFromChat(user_in_chat):
        """ Adapts user info from chat to User model acceptable initial dict

        :param user_in_chat: user info from chat

        'dir': None,
        'mThumbSrcSmall': None,
        'is_friend': False,
        'is_nonfriend_messenger_contact': True,
        'alternateName': '',
        'i18nGender': 16777216,
        'vanity': '',
        'type': 'friend',
        'searchTokens': ['Voznesenskij', 'Sergej'],
        'thumbSrc': 'https://fb-s-b-a.akamaihd.net/h-ak-xfa1/v/t1.0-1/c9.0.32.32/p32x32/10354686_10150004552801856_220367501106153455_n.jpg?oh=71a87d76d4e4d17615a20c43fb8dbb47&oe=59118CE4&__gda__=1493753268_ae75cef40e9785398e744259ccffd7ff',
        'mThumbSrcLarge': None,
        'firstName': 'Sergej',
        'name': 'Sergej Voznesenskij',
        'uri': 'https://www.facebook.com/profile.php?id=100014812758264',
        'id': '100014812758264',
        'gender': 2
        """

        return {
            'type': 'user',
            'uid': user_in_chat['id'],
            'photo': user_in_chat['thumbSrc'],
            'path': user_in_chat['uri'],
            'text': user_in_chat['name'],
            'score': '',
            'data': user_in_chat,
        }


class Thread():
    def __init__(self, **entries): 
        self.__dict__.update(entries)


class Message():
    def __init__(self, **entries):
        self.__dict__.update(entries)


class ThreadType(Enum):
    USER = 1
    GROUP = 2


class TypingStatus(Enum):
    DELETED = 0
    TYPING = 1


class EmojiSize(Enum):
    LARGE = '369239383222810'
    MEDIUM = '369239343222814'
    SMALL = '369239263222822'
