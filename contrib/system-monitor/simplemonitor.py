#!/usr/bin/python
# coding: utf-8
# author: Eduardo S. Scarpellini, <scarpellini@gmail.com>

import statgrab
import simplejson

cpu  = statgrab.sg_get_cpu_percents()
mem  = statgrab.sg_get_mem_stats()
load = statgrab.sg_get_load_stats()
swap = statgrab.sg_get_swap_stats()

my_stats = {
	"cpu": {
		"kernel": cpu.kernel,
		"user": cpu.user,
		"iowait": cpu.iowait,
		"nice": cpu.nice,
		"swap": cpu.swap,
		"idle": cpu.idle,
	},
	"load": {
		"min1": load.min1,
		"min5": load.min5,
		"min15": load.min15,
	},
	"mem": {
		"used": mem.used,
		"cache": mem.cache,
		"free": mem.free,
		"total": mem.total,
	},
	"swap": {
		"used": swap.used,
		"free": swap.free,
		"total": swap.total,
	},
}

def get_all_values():
	return simplejson.dumps(my_stats)

if __name__ == "__main__":
	print get_all_values()
