import os, os.path, subprocess, warnings

has_git = None

def find_files_for_git(dirname):
	global has_git
	if(has_git is None):
		git = subprocess.Popen(['env', 'git', '--version'], stdout=subprocess.PIPE)
		git.wait()
		has_git = (git.returncode == 0)
	if(has_git):
		git = subprocess.Popen(['git', 'ls-files', dirname], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
		for line in git.stdout:
			path = os.path.join(dirname, line.strip())
			yield path
	else:
		warnings.warn("Can't find git binary.")

def pluginModules(moduleNames):
	from twisted.python.reflect import namedAny
	for moduleName in moduleNames:
		try:
			yield namedAny(moduleName)
		except ImportError:
			pass
		except ValueError, ve:
			if ve.args[0] != 'Empty module name':
				import traceback
				traceback.print_exc()
		except:
			import traceback
			traceback.print_exc()

def regeneratePluginCache():
	pluginPackages = ['twisted.plugins']
	
	from twisted import plugin
	
	for pluginModule in pluginModules(pluginPackages):
		plugin_gen = plugin.getPlugins(plugin.IPlugin, pluginModule)
		try:
			plugin_gen.next()
		except StopIteration, e:
			pass
		except TypeError, e:
			print 'TypeError: %s' % e

