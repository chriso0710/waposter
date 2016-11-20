from yowsup.layers                                      import YowLayerEvent
from yowsup.layers.interface                            import YowInterfaceLayer, ProtocolEntityCallback
from yowsup.layers.network                              import YowNetworkLayer
from yowsup.layers.protocol_profiles.protocolentities   import *

import datetime, sys, json, time, os, tempfile, re

import boto
from boto.s3.key import Key

import requests
from requests.packages.urllib3.util import Retry
from requests.adapters import HTTPAdapter
from requests import Session, exceptions

class ReceiveLayer(YowInterfaceLayer):

    print("ReceiveLayer:")
    s = requests.Session()
    retries = Retry(total=5,
                    backoff_factor=0.2,
                    method_whitelist=["GET", "POST"],
                    status_forcelist=[ 500, 502, 503, 504 ])
    s.mount('http://', HTTPAdapter(max_retries=retries))
    s.mount('https://', HTTPAdapter(max_retries=retries))
    print s

    c = boto.connect_s3()
    print c
    b = c.get_bucket(os.environ['BUCKET'])
    print b

    def onEvent(self, layerEvent):
        print("onEvent: Event received: %s" % layerEvent.getName())
        if layerEvent.getName() == YowNetworkLayer.EVENT_STATE_DISCONNECTED:
            print("onEvent: Disconnected, reason: %s" % layerEvent.getArg("reason"))
            if layerEvent.getArg("reason") == 'Connection Closed':
                time.sleep(60)
                print("onEvent: Issueing EVENT_STATE_CONNECT")
                self.getStack().broadcastEvent(YowLayerEvent(YowNetworkLayer.EVENT_STATE_CONNECT))
        elif layerEvent.getName() == YowNetworkLayer.EVENT_STATE_CONNECTED:
            print("onEvent: Connected!")

    @ProtocolEntityCallback("success")
    def onSuccess(self, entity):
        print("onSuccess: Logged in!")

    @ProtocolEntityCallback("failure")
    def onFailure(self, entity):
        print("onFailure: Login failed, reason: %s" % entity.getReason())

    @ProtocolEntityCallback("message")
    def onMessage(self, message):

        # TODO
        #def onError(errorIqEntity, originalIqEntity):
        #    print("Error getting profile picture")

        #entity = GetPictureIqProtocolEntity(message.getFrom(), preview=False)
        #self._sendIq(entity, self.onGetContactPictureResult, onError)

        if message.getType() == 'text':
            self.getTextMessageBody(message)
        elif message.getType() == 'media':
            self.getMediaMessageBody(message)
        else:
            print("Unknown message type %s " % message.getType())

    @ProtocolEntityCallback("receipt")
    def onReceipt(self, entity):
        self.toLower(entity.ack())

    def getTextMessageBody(self, message):
        # print(dir(message))
        # 'getBody', 'getFrom', 'getId', 'getNotify', 'getParticipant', 'getTag', 'getTimestamp', 'getTo', 'getType'
        print("onTextMessageBody: Received %s '%s' from %s" % (message.getId(), message.getBody(), message.getFrom(False)))
        if self.postit(message):
            self.toLower(message.ack(True))

    def getMediaMessageBody(self, message):
        # print(dir(message))
        # 'getCaption', 'getFrom', 'getId', 'getMediaSize', 'getMediaType', 'getMediaUrl', 'getMimeType', 'getNotify', 'getParticipant', 'getPreview', 'getTag', 'getTimestamp', 'getTo', 'getType',
        print("onMediaMessageBody: Received %s %s from %s" % (message.getId(), message.getMediaType(), message.getFrom(False)))
        # TODO: "document", "audio"
        if message.getMediaType() in ("image", "video"):
            url = self.getDownloadableMediaMessageBody(message)
            print("onMediaMessageBody: Saved as %s" % url)
            if self.postit(message, url):
                self.toLower(message.ack(True))
        else:
            self.toLower(message.ack(True))

    def getDownloadableMediaMessageBody(self, message):
        # save as temp file
        #filename = "%s/%s%s"%(tempfile.gettempdir(),message.getId(),message.getExtension())
        #with open(filename, 'wb') as f:
        #    f.write(message.getMediaContent())
        k = Key(self.b)
        k.key = "%s%s"%(message.getId(),message.getExtension())
        k.set_contents_from_string(str(message.getMediaContent()))
        k.set_metadata('Content-Type', message.getMimeType())
        k.set_acl('public-read')
        return k.generate_url(expires_in=0, query_auth=False)

    def onGetContactPictureResult(self, resultGetPictureIqProtocolEntity, getPictureIqProtocolEntity):
        # write to file example:
        #print dir(resultGetPictureIqProtocolEntity)
        #print dir(getPictureIqProtocolEntity)
        #resultGetPictureIqProtocolEntity.writeToFile("/tmp/yowpics/%s_%s.jpg" % (getPictureIqProtocolEntity.getTo(), "preview" if resultGetPictureIqProtocolEntiy.isPreview() else "full"))
        #filename = "%s/%s-fullprofile.jpg"%(tempfile.gettempdir(),resultGetPictureIqProtocolEntity.getPictureId())
        #print filename
        #with open(filename, 'wb') as f:
        #    f.write(resultGetPictureIqProtocolEntity.getPictureData())
        id = re.sub(r"@.*","",getPictureIqProtocolEntity.getTo())
        filename = "%s-profile.jpg"%(id)
        print("checking %s", filename)
        k = self.b.get_key(filename)
        if k:
            url = k.generate_url(expires_in=0, query_auth=False)
            print("%s exists: %s" % (filename, url))
        else:
            k = Key(self.b)
            k.key = filename
            k.set_contents_from_string(str(resultGetPictureIqProtocolEntity.getPictureData()))
            k.set_metadata('Content-Type', 'image/jpeg')
            k.set_acl('public-read')
            url = k.generate_url(expires_in=0, query_auth=False)
            print("%s doesn't exist, created: %s" % (k, url))

    def postit(self, message, url = None):
        paramdict = {}

        if message.getType() == 'text':
            paramdict['messagecontent'] = message.getBody()
        if message.getType() == 'media':
            paramdict['messagecontent'] = message.getCaption()
            #paramdict['url']            = message.getMediaUrl()
            paramdict['url']            = url
            paramdict['size']           = message.getMediaSize()
            paramdict['mediatype']      = message.getMediaType()
            paramdict['mimetype']       = message.getMimeType()

        paramdict['messageid']      = message.getId()
        paramdict['type']           = message.getType()
        paramdict['to']             = message.getTo()
        paramdict['from']           = message.getFrom(False)
        paramdict['notify']         = message.getNotify()
        paramdict['participant']    = message.getParticipant()
        paramdict['timestamp']      = message.getTimestamp()
        paramdict['tag']            = message.getTag()

        post_data = json.dumps(paramdict)
        print post_data
        url = os.environ['URL']
        # url = 'http://httpstat.us/500'
        # url = 'http://bliblabblubb.de'
        try:
            r = self.s.post(url, post_data)
            print r.status_code
            print r.headers
            return True
        except (requests.exceptions.RetryError, requests.exceptions.ConnectionError) as e:
            print e
            return False
