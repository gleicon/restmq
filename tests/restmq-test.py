# coding: utf-8
# author: Eduardo S. Scarpellini, <scarpellini@gmail.com>
from net.grinder.script.Grinder import grinder
from net.grinder.script import Test
from net.grinder.plugin.http import HTTPRequest, HTTPPluginControl
from HTTPClient import NVPair
from java.util import Random

# Import "random" module from the Jython lib path
import sys
#sys.path.append("/opt/jython2.5.1/Lib")
#import random
randomizer = Random()


# Parameters
RESTMQ_URL = "http://localhost:8888/"
QUEUENAME  = "PERFTEST"
VALUES     = [
	"fagtejmanP09as78d897891eidEnAidNa",
	"OdnutonbapHyGracasd8789asd0123Atvo",
	"igmesyaHenUrnoranGio",
	"lybDitdonCibW897989ewJedth",
	"CiUdlynJeHeySasd987asd8hkasd89ebjalky",
	"nafAtcepdetM_asdiu8aipgapGej",
	"itidpyctEijusas9d8821111hcoiWun",
	"yatnuWibAndOrHaubNqw0e897891ud",
	"CydIpavAycsEibsEiasd081xye",
	"dicedInBebEwatAigasd087Dab",
	1.1273,
	0.1771,
	9012830,
	1098,
	193,
	2.127398,
	67651,
	1218937829,
	981,
	8711
]

def rndIndex():
    return VALUES[randomizer.nextInt() % len(VALUES)]

# Logging
log = grinder.logger.output
out = grinder.logger.TERMINAL

test1 = Test(1, "enqueue")
test2 = Test(2, "dequeue")
request1 = test1.wrap(HTTPRequest())
request2 = test2.wrap(HTTPRequest())

# Test Interface
class TestRunner:
	def __call__(self):
                post_data={}
                for pt in ['1', '2', '3', '4', '5', 'X', 'K', 'Y', 'W', 'Z']:
                    post_data['FAKENAME'+pt]=rndIndex()

		log("Sending data (enqueuing): %s" % post_data )

		post_parameters = (
			NVPair("queue", QUEUENAME),
			NVPair("value", str(post_data)),
		)
		result1 = request1.POST(RESTMQ_URL, post_parameters)

		result2 = request2.GET("%s/q/%s" % (RESTMQ_URL.rstrip("/"), QUEUENAME))
		log("Getting data (dequeuing): %s" % result2.getText())
