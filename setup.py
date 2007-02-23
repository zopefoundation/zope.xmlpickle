from setuptools import setup, find_packages

setup(name='zope.xmlpickle',
      version='0.1dev',
      url='http://svn.zope.org/zope.xmlpickle',
      license='ZPL 2.1',
      description='Zope xmlpickle',
      author='Zope Corporation and Contributors',
      author_email='zope3-dev@zope.org',
      packages=find_packages('src'),
      package_dir = {'': 'src'},

      namespace_packages=['zope',],
      include_package_data = True,

      zip_safe = False,
      )
