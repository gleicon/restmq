#!/usr/bin/python
# coding: utf-8
# author: Eduardo S. Scarpellini, <scarpellini@gmail.com>

import os
import ConfigParser

class read():
	__cfgfile = "%s/config/main.cfg" % os.path.dirname(os.path.realpath("%s/.." % __file__))

	def __init__(self, cfgfile=__cfgfile):
		self.__config = ConfigParser.ConfigParser()
		self.__config.read(cfgfile)
		self.__cfgvalues = {}

	def restmq(self):
		try:
			self.__cfgvalues = {
				"host": self.__config.get("RESTMQ", "host"),
				"port": self.__config.get("RESTMQ", "port"),
				"queuename": self.__config.get("RESTMQ", "queuename"),
			}
		except ConfigParser.Error, err:
			print err

		return self.__cfgvalues

	def dispatcher(self):
		try:
			self.__cfgvalues = {
				"cpu": self.__config.get("DISPATCHER", "cpu"),
				"mem": self.__config.get("DISPATCHER", "mem"),
				"load": self.__config.get("DISPATCHER", "load"),
				"swap": self.__config.get("DISPATCHER", "swap"),
			}
		except ConfigParser.Error, err:
			print err

		return self.__cfgvalues
