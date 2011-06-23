import ez_setup
ez_setup.use_setuptools()

import sys, os, os.path, subprocess

try:
    from twisted import plugin
except ImportError, e:
    print >>sys.stderr, "setup.py requires Twisted to create a proper RestMQ installation."
    print >>sys.stderr, "Please install it before continuing."
    sys.exit(1)

from setuptools.command import easy_install
import pkg_resources as pkgrsrc

from distutils import log
log.set_threshold(log.INFO)

# disables creation of .DS_Store files inside tarballs on Mac OS X
os.environ['COPY_EXTENDED_ATTRIBUTES_DISABLE'] = 'true'
os.environ['COPYFILE_DISABLE'] = 'true'

postgenerate_cache_commands = ('build', 'build_py', 'build_ext',
    'build_clib', 'build_scripts', 'install', 'install_lib',
    'install_headers', 'install_scripts', 'install_data',
    'develop', 'easy_install')

pregenerate_cache_commands = ('sdist', 'bdist', 'bdist_dumb',
    'bdist_rpm', 'bdist_wininst', 'upload', 'bdist_egg', 'test')

def autosetup():
    from setuptools import setup, find_packages
    return setup(
        name            = "RestMQ",
        version         = "1.0",

        packages        = find_packages('src') + ['twisted.plugins'],
		package_dir		= {
			''			: 'src',
		},
        include_package_data = True,

        zip_safe = False,

        entry_points    = {
            'setuptools.file_finders'   : [
                'git = restmq.setup_extras:find_files_for_git',
            ],
        },
        
        install_requires = ['%s>=%s' % x for x in dict(
            twisted             = "10.1.0",
            simplejson          = "2.1.1",
            cyclone             = "0.4",
        ).items()],

        # metadata for upload to PyPI
        author          = "Gleicon Moraes",
        author_email    = "gleicon@gmail.com",
        description     = "REST/JSON/HTTP based message queue",
        keywords        = "rest json message queue",
        url             = "https://github.com/gleicon/restmq",
    )


if(__name__ == '__main__'):
    if(sys.argv[-1] in pregenerate_cache_commands):
        dist_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src')
        if(dist_dir not in sys.path):
            sys.path.insert(0, dist_dir)

        from restmq import setup_extras
        print 'Regenerating plugin cache...'
        setup_extras.regeneratePluginCache()

    dist = autosetup()
    if(sys.argv[-1] in postgenerate_cache_commands):
        subprocess.Popen(
            [sys.executable, '-c', 'from restmq import setup_extras; setup_extras.regeneratePluginCache(); print "Regenerating plugin cache..."'],
        ).wait()
