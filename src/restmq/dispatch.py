# coding: utf-8

from twisted.internet import defer

class CommandDispatch:
    def __init__(self, ro):
        self.ro = ro

    @defer.inlineCallbacks
    def _add(self, jsonbody):
        """
            add an object to the queue
        """ 
        r={}
        try:
            e = yield self.ro.queue_add(jsonbody['queue'].encode("utf-8"), jsonbody['value'].encode("utf-8"))
            r['queue'] = jsonbody['queue']
            r['value'] = jsonbody['value']
            r['key'] = str(e)
            defer.returnValue(r)
        except Exception, e:
            defer.returnValue({"error":str(e)})
    
    @defer.inlineCallbacks
    def _get(self, jsonbody):
        """
            get an object from the queue. get is not destructive (wont pop the object out of the queue).
            check the 'count' attribute to see how many times a give object was requested
        """
        r={}
        try:
            p, e = yield self.ro.queue_get(jsonbody['queue'].encode("utf-8"), softget=True)
            if e is None:
                defer.returnValue({'error': 'empty queue'})
            else:
                r['queue'] = jsonbody['queue']
                r['value'] = e['value']
                r['key'] = e['key']
                r['count'] = e['count'] 
                defer.returnValue(r)
        except Exception, e:
            defer.returnValue({"error":str(e)})


    @defer.inlineCallbacks
    def _take(self, jsonbody):
        """
            get and delete an object from the queue. it is not really necessary as GET takes it out of the queue list, 
            so it will be basically hanging around redis with no reference. For now its a two pass operation, with no 
            guarantees and the same semantics as del
        """
        r={}
        try:
            p, e = yield self.ro.queue_getdel(jsonbody['queue'].encode("utf-8"))
            if e == False:
                defer.returnValue({"error":"empty queue"})
          
            if e == None:
                defer.returnValue({"error":"getdel error"})
            r['queue'] = jsonbody['queue']
            r['value'] = e['value']
            r['key'] = e['key']

            defer.returnValue(r)
        except Exception, e:
            defer.returnValue({"error":str(e)})

    @defer.inlineCallbacks
    def _del(self, jsonbody):
        """
            delete an object from the storage. returns key and a deleted attribute, false if the key doesn't exists'
        """
        r={}
        try:
            e = yield self.ro.queue_del(jsonbody['queue'].encode("utf-8"), jsonbody['key'])
            r['queue'] = jsonbody['queue']
            r['deleted'] = True if e['value'] > 0 else False
            r['key'] = e['key']
            defer.returnValue(r)
        except Exception, e:
            defer.returnValue({"error":str(e)})

        
    def execute(self, command, jsonbody):
        c = "_"+command
        if hasattr(self, c):
            m=getattr(self, c)
            return m(jsonbody)
        else:
            return None
