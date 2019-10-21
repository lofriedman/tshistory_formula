from setuptools import setup


setup(name='tshistory_formula',
      version='0.3.0',
      author='Pythonian',
      author_email='aurelien.campeas@pythonian.fr',
      url='https://bitbucket.org/pythonian/tshistory_formula',
      description='Computed timeseries plugin for `tshistory`',

      packages=['tshistory_formula'],
      install_requires=[
          'decorator',
          'tshistory',
          'psyl'
      ],
      entry_points={'tshistory.subcommands': [
          'ingest-formulas=tshistory_formula.cli:ingest_formulas',
          'update-formula-metadata=tshistory_formula.cli:update_metadata',
          'typecheck-formula=tshistory_formula.cli:typecheck_formula',
          'test-formula=tshistory_formula.cli:test_formula',
          'drop-alias-tables=tshistory_formula.cli:drop_alias_tables',
          'shell=tshistory_formula.cli:shell'
      ]},
      classifiers=[
          'Development Status :: 4 - Beta',
          'Intended Audience :: Developers',
          'License :: OSI Approved :: GNU Lesser General Public License v3 (LGPLv3)',
          'Operating System :: OS Independent',
          'Programming Language :: Python :: 3',
          'Topic :: Database',
          'Topic :: Scientific/Engineering',
          'Topic :: Software Development :: Version Control'
      ]
)
